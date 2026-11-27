# -*- coding: utf-8 -*-
"""
xp_host/xp_host_engine.py
Lõi xử lý phiên điều khiển từ xa (Host Session Engine) cho Windows XP:
  - Xác thực Handshake (Mật khẩu phiên + Mật khẩu cố định XML) & Phản hồi LAN Probe.
  - Hỗ trợ nhiều máy Win 10/11 cùng kết nối quan sát / điều khiển một máy XP.
  - Truyền phát màn hình GDI BitBlt + Pillow JPEG + Dirty-Rect (partial_frame) siêu nhẹ.
  - Tự động bám theo cả màn hình đăng nhập Windows XP (Winlogon) lẫn Desktop (Default).
  - Xử lý đầy đủ Chuột, Phím, Ctrl+Alt+Del (SAS), Gõ mật khẩu, Clipboard 2 chiều và File Manager.
"""

import base64
import ctypes
import json
import os
import platform
import queue
import select
import socket
import subprocess
import sys
import threading
import time

from .xp_capture import (
    XPGdiCapturer,
    attach_thread_to_active_desktop,
    compute_dirty_rect,
    encode_pil_jpeg,
    get_capture_geometry,
    get_input_desktop_name,
    resize_pil_if_needed,
)
from .xp_clipboard import CLIPBOARD_PKT_TYPES, XPClipboardSyncManager
from .xp_config import (
    LAN_APP_SIGNATURE,
    load_fixed_password,
    load_or_create_session_password,
    load_zalo_phone,
    xp_log,
)
from .xp_hwid import get_hwid, get_local_ip
from .xp_input import (
    get_cursor_pos,
    release_all_modifiers,
    send_keyboard_event,
    send_mouse_click,
    send_mouse_move,
    send_mouse_scroll,
    trigger_xp_ctrl_alt_del,
    type_text_unicode,
)
from .xp_socket import (
    APP_KEY,
    force_close_socket,
    is_lan_socket,
    recv_msg,
    send_msg,
    set_xp_keepalive,
    socket_passwords,
    tune_socket_for_xp_lan,
)


def _is_xp_domain_joined():
    """Kiểm tra máy XP có gia nhập Domain hay không qua NetGetJoinInformation (netapi32.dll)."""
    if sys.platform != "win32":
        return False, "Non-Windows"
    try:
        netapi32 = ctypes.windll.netapi32
        name_buf = ctypes.c_void_p()
        join_status = ctypes.c_int(0)
        res = netapi32.NetGetJoinInformation(None, ctypes.byref(name_buf), ctypes.byref(join_status))
        if res == 0:
            if name_buf.value:
                netapi32.NetApiBufferFree(name_buf)
            # NetSetupDomainName = 3
            return (join_status.value == 3), f"JoinStatus={join_status.value}"
    except Exception as e:
        return False, str(e)
    return False, "Workgroup"


def _wake_xp_display():
    if sys.platform != "win32":
        return
    try:
        # ES_SYSTEM_REQUIRED | ES_DISPLAY_REQUIRED
        ctypes.windll.kernel32.SetThreadExecutionState(0x00000001 | 0x00000002)
        # Nhích chuột 0px để đánh thức màn hình CRT/LCD trên máy XP đang tắt màn tiết kiệm điện
        ctypes.windll.user32.mouse_event(0x0001, 0, 0, 0, 0)
    except Exception:
        pass


class XPHostEngine:
    def __init__(self, base_dir=None, tk_root=None, on_session_status=None):
        self.base_dir = base_dir
        self.on_session_status = on_session_status
        self.hwid, self.hwid_display, self.macs = get_hwid(base_dir)
        self.session_password = load_or_create_session_password(base_dir=base_dir)
        self.fixed_password = load_fixed_password(base_dir=base_dir)
        self.bound_port = 12345

        self.active_clients = {}
        self.clients_lock = threading.Lock()
        self.clipboard_mgr = XPClipboardSyncManager(tk_root=tk_root)
        self._fm_abort = threading.Event()

    def bind_tk_root(self, tk_root):
        self.clipboard_mgr.bind_tk_root(tk_root)

    def reload_passwords(self):
        self.session_password = load_or_create_session_password(base_dir=self.base_dir)
        self.fixed_password = load_fixed_password(base_dir=self.base_dir)
        return self.session_password, self.fixed_password

    def notify_shutdown(self, kind="shutdown"):
        ptype = "host_restart" if kind == "restart" else "host_shutdown"
        pkt = json.dumps({"type": ptype, "kind": kind}).encode("utf-8")
        with self.clients_lock:
            conns = [(cs["conn"], cs["password"]) for cs in self.active_clients.values() if cs.get("conn")]
        for c, pw in conns:
            try:
                send_msg(c, pkt, pw)
            except Exception:
                pass

    def _emit_session_status(self, msg):
        xp_log(f"[HostEngine] {msg}", base_dir=self.base_dir)
        if callable(self.on_session_status):
            try:
                self.on_session_status(msg)
            except Exception:
                pass

    # ==========================================================================
    # 1. Handshake & LAN Probe Handler
    # ==========================================================================
    def handle_client_connection(self, conn, addr):
        client_pass = None
        try:
            self.reload_passwords()
            cand_keys = [k for k in (self.session_password, self.fixed_password, APP_KEY) if k]
            socket_passwords[conn] = cand_keys

            conn.settimeout(12.0)
            msg = recv_msg(conn, cand_keys)
            if not msg:
                err_pkt = json.dumps({
                    "status": "error",
                    "message": "Sai mật khẩu kết nối hoặc dữ liệu không hợp lệ!",
                }).encode("utf-8")
                send_msg(conn, err_pkt, APP_KEY)
                time.sleep(0.3)
                force_close_socket(conn)
                return

            data = json.loads(msg.decode("utf-8"))

            # Phản hồi dò tìm máy trong mạng LAN / VPN (Client scan)
            if data.get("action") == "probe":
                pong = json.dumps({
                    "status": "ok",
                    "type": "probe_pong",
                    "sig": LAN_APP_SIGNATURE,
                    "hwid": self.hwid,
                    "computer_name": platform.node() or "WIN-XP-HOST",
                    "os": "Windows",
                    "port": self.bound_port,
                    "local_ip": get_local_ip(),
                    "macs": self.macs,
                }).encode("utf-8")
                send_msg(conn, pong, APP_KEY)
                time.sleep(0.1)
                force_close_socket(conn)
                return

            client_pass = data.get("password") or ""
            valid = bool(
                (self.session_password and client_pass == self.session_password)
                or (self.fixed_password and client_pass == self.fixed_password)
            )
            if not valid:
                err_pkt = json.dumps({
                    "status": "error",
                    "message": "Sai mật khẩu kết nối!",
                }).encode("utf-8")
                send_msg(conn, err_pkt, client_pass or APP_KEY)
                time.sleep(0.3)
                force_close_socket(conn)
                return

            socket_passwords[conn] = client_pass
            try:
                conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            except Exception:
                pass
            if is_lan_socket(conn):
                tune_socket_for_xp_lan(conn)
            set_xp_keepalive(conn, 10000, 3000)

            attach_thread_to_active_desktop()
            left, top, host_w, host_h, mon_rects = get_capture_geometry("both")
            is_domain, chk_reason = _is_xp_domain_joined()
            client_comp = data.get("computer_name") or data.get("client_id") or str(addr[0])

            res_info = json.dumps({
                "status": "ok",
                "width": host_w,
                "height": host_h,
                "monitor_count": max(1, len(mon_rects)),
                "monitors": [{"left": r[0], "top": r[1], "width": r[2], "height": r[3]} for r in mon_rects],
                "computer_name": platform.node() or "WIN-XP-HOST",
                "zalo_phone": load_zalo_phone(self.base_dir),
                "is_domain": is_domain,
                "chk_reason": chk_reason,
                "os_release": "XP",
                "is_android": False,
                "macs": self.macs,
                "hwid": self.hwid,
            }).encode("utf-8")
            if not send_msg(conn, res_info, client_pass):
                force_close_socket(conn)
                return

            client_state = {
                "conn": conn,
                "password": client_pass,
                "running": True,
                "net_class": "high" if is_lan_socket(conn) else "medium",
                "quality_mode": "quality",
                "monitor_mode": "both",
                "cap_rect": (left, top, host_w, host_h),
                "viewer_w": host_w,
                "viewer_h": host_h,
                "has_viewer_size": False,
                "force_update": True,
                "wake_event": threading.Event(),
            }

            # Xử lý bước đo tốc độ mạng (WAN speed test) hoặc tín hiệu ping sẵn sàng (LAN)
            try:
                conn.settimeout(12.0)
                while client_state["running"]:
                    probe_raw = recv_msg(conn, client_pass)
                    if not probe_raw:
                        break
                    probe = json.loads(probe_raw.decode("utf-8"))
                    act = probe.get("action")
                    evt = probe.get("type")
                    if act == "speed_test_ping":
                        send_msg(conn, json.dumps({"action": "speed_test_pong"}).encode("utf-8"), client_pass)
                    elif act == "speed_test_bw_req":
                        sz = max(1024, min(int(probe.get("suggested_size", 131072)), 524288))
                        send_msg(conn, json.dumps({"action": "speed_test_bw_start", "size": sz}).encode("utf-8"), client_pass)
                        conn.sendall(b"\x00" * sz)
                    elif act == "speed_test_result":
                        client_state["net_class"] = probe.get("net_class", "medium")
                        break
                    elif evt == "ping":
                        break
                    else:
                        break
            except Exception:
                pass
            finally:
                try:
                    conn.settimeout(None)
                except Exception:
                    pass

            _wake_xp_display()
            with self.clients_lock:
                self.active_clients[addr] = client_state
                n_clients = len(self.active_clients)
            self._emit_session_status(f"Đang được điều khiển bởi {client_comp} ({n_clients} kết nối)")

            self.clipboard_mgr.add_socket(conn)
            t_send = threading.Thread(
                target=self._sender_loop, args=(conn, client_state, client_pass), daemon=True, name="XPSender"
            )
            t_cur = threading.Thread(
                target=self._cursor_watcher_loop, args=(conn, client_state, client_pass), daemon=True, name="XPCursor"
            )
            t_recv = threading.Thread(
                target=self._receiver_loop, args=(conn, client_state, client_pass), daemon=True, name="XPReceiver"
            )
            t_send.start()
            t_cur.start()
            t_recv.start()

            try:
                t_recv.join()
            finally:
                client_state["running"] = False
                client_state["wake_event"].set()
                t_send.join(timeout=2.0)
                self.clipboard_mgr.remove_socket(conn)
                with self.clients_lock:
                    self.active_clients.pop(addr, None)
                    rem = len(self.active_clients)
                if rem > 0:
                    self._emit_session_status(f"Đang có {rem} kết nối điều khiển")
                else:
                    self._emit_session_status(f"Đã ngắt kết nối với {client_comp} (Sẵn sàng)")
                force_close_socket(conn)

        except Exception as e:
            xp_log(f"[Handshake] Error from {addr}: {e}", base_dir=self.base_dir)
            force_close_socket(conn)

    # ==========================================================================
    # 2. Screen Sender & Cursor Sync Threads
    # ==========================================================================
    def _cursor_watcher_loop(self, conn, client_state, password):
        last_pos = None
        last_vis = True
        while client_state.get("running", False):
            try:
                pos = get_cursor_pos()
                if pos is not None and pos != last_pos:
                    cx, cy = pos
                    inj = client_state.get("last_injected_cursor")
                    inj_ts = client_state.get("last_client_mouse_ts", 0.0)
                    now = time.time()
                    if (inj and abs(cx - inj[0]) <= 4 and abs(cy - inj[1]) <= 4) or (now - inj_ts < 0.12):
                        last_pos = pos
                    else:
                        ox, oy, cw, ch = client_state.get("cap_rect", (0, 0, 1024, 768))
                        if cw > 1 and ch > 1:
                            inside = (ox <= cx < ox + cw) and (oy <= cy < oy + ch)
                            if not inside:
                                if last_vis:
                                    pkt = json.dumps({"type": "host_cursor", "visible": False}).encode("utf-8")
                                    if send_msg(conn, pkt, password, lock_timeout=0.015):
                                        last_vis = False
                                last_pos = pos
                            else:
                                rx = max(0.0, min(1.0, (cx - ox) / float(cw - 1)))
                                ry = max(0.0, min(1.0, (cy - oy) / float(ch - 1)))
                                pkt = json.dumps({
                                    "type": "host_cursor",
                                    "rx": round(rx, 5),
                                    "ry": round(ry, 5),
                                    "visible": True,
                                }).encode("utf-8")
                                if send_msg(conn, pkt, password, lock_timeout=0.015):
                                    last_pos = pos
                                    last_vis = True
            except Exception:
                pass
            time.sleep(0.04)

    def _sender_loop(self, conn, client_state, password):
        capturer = XPGdiCapturer()
        send_msg(conn, json.dumps({"type": "pong"}).encode("utf-8"), password)

        net_class = client_state.get("net_class", "medium")
        quality = 82 if net_class == "high" else (72 if net_class == "medium" else 62)
        sleep_time = 1.0 / 18.0 if net_class == "high" else 1.0 / 12.0
        dyn_scale = -1.0
        prev_img = None
        last_desk = None
        last_hb = time.time()

        while client_state.get("running", False):
            try:
                q_mode = client_state.get("quality_mode", "quality")
                mon_mode = client_state.get("monitor_mode", "both")
                force_upd = bool(client_state.pop("force_update", False))

                img, ox, oy, cw, ch, desk_name = capturer.grab_pil(mon_mode)
                client_state["cap_rect"] = (ox, oy, cw, ch)

                # Thông báo cho Viewer khi máy XP chuyển giữa màn hình khóa Winlogon <-> Desktop Default
                if desk_name != last_desk:
                    last_desk = desk_name
                    force_upd = True
                    prev_img = None
                    is_locked = desk_name not in ("default", "")
                    is_dom, rsn = _is_xp_domain_joined()
                    send_msg(
                        conn,
                        json.dumps({
                            "type": "domain_status",
                            "is_domain": is_dom,
                            "reason": rsn,
                            "is_locked": is_locked,
                        }).encode("utf-8"),
                        password,
                    )

                target_w = client_state.get("viewer_w", cw) if client_state.get("has_viewer_size") else cw
                target_h = client_state.get("viewer_h", ch) if client_state.get("has_viewer_size") else ch
                send_img = resize_pil_if_needed(img, target_w, target_h, dyn_scale=dyn_scale, max_edge=1920)

                if force_upd:
                    kind, bbox = "full", None
                else:
                    kind, bbox = compute_dirty_rect(send_img, prev_img)

                if kind == "static":
                    ceil_q = 75 if q_mode == "speed" else 90
                    if quality < ceil_q or dyn_scale > 0:
                        quality = min(ceil_q, quality + 12)
                        dyn_scale = -1.0
                        kind = "full"
                    else:
                        # Giữ kết nối sống mỗi 3s khi màn hình đứng yên hoàn toàn
                        if time.time() - last_hb >= 3.0:
                            if not send_msg(conn, json.dumps({"type": "pong"}).encode("utf-8"), password):
                                client_state["running"] = False
                                break
                            last_hb = time.time()
                        client_state["wake_event"].wait(0.10)
                        client_state["wake_event"].clear()
                        continue

                prev_img = send_img
                out_img = send_img
                if kind == "partial" and bbox is not None:
                    fw, fh = send_img.size
                    out_img = send_img.crop(bbox)
                    meta = {"type": "partial_frame", "bbox": bbox, "fw": int(fw), "fh": int(fh)}
                    if not send_msg(conn, json.dumps(meta).encode("utf-8"), password):
                        client_state["running"] = False
                        break

                jpeg_bytes = encode_pil_jpeg(out_img, quality=quality, quality_mode=q_mode)
                t0 = time.time()
                if not send_msg(conn, jpeg_bytes, password):
                    client_state["running"] = False
                    break
                send_dt = time.time() - t0
                last_hb = time.time()

                ema = client_state.get("send_ema", send_dt)
                ema = 0.8 * ema + 0.2 * send_dt
                client_state["send_ema"] = ema

                # Điều chỉnh chất lượng & FPS mượt trên CPU máy XP
                if q_mode == "speed":
                    quality = 65 if ema > 0.30 else 75
                    sleep_time = min(0.20, max(1.0 / 16.0, sleep_time + (0.02 if ema > 0.30 else -0.005)))
                else:
                    if ema > 0.35:
                        quality = max(62, quality - 5)
                        sleep_time = min(0.25, sleep_time + 0.03)
                    elif ema < 0.18:
                        quality = min(90, quality + 2)
                        sleep_time = max(1.0 / 18.0, sleep_time - 0.005)

                # Nhường CPU cho luồng nhận file nếu đang copy file nặng trên XP
                if self.clipboard_mgr.incoming_transfers:
                    time.sleep(max(sleep_time, 0.20))
                else:
                    time.sleep(sleep_time)

            except Exception as e:
                xp_log(f"[Sender] Capture/send retry: {e}", base_dir=self.base_dir)
                prev_img = None
                time.sleep(0.35)

    # ==========================================================================
    # 3. Input & Command Receiver Thread
    # ==========================================================================
    def _resolve_mouse_xy(self, event, client_state):
        ox, oy, cw, ch = client_state.get("cap_rect", (0, 0, 1024, 768))
        rx, ry = event.get("rx"), event.get("ry")
        if rx is not None and ry is not None:
            rx_c = max(0.0, min(1.0, float(rx)))
            ry_c = max(0.0, min(1.0, float(ry)))
            return int(round(ox + rx_c * max(1, cw - 1))), int(round(oy + ry_c * max(1, ch - 1)))
        x, y = event.get("x"), event.get("y")
        if x is not None and y is not None:
            return int(x) + int(ox), int(y) + int(oy)
        return None, None

    def _receiver_loop(self, conn, client_state, password):
        in_q = queue.Queue()

        def _worker():
            attach_thread_to_active_desktop()
            while client_state.get("running", False):
                try:
                    ev = in_q.get(timeout=0.5)
                    if ev == "STOP":
                        break
                    self._handle_event(ev, conn, password, client_state)
                except queue.Empty:
                    continue
                except Exception as e:
                    xp_log(f"[InputWorker] Error: {e}", base_dir=self.base_dir)

        threading.Thread(target=_worker, daemon=True, name="XPInputExec").start()

        last_recv = time.time()
        try:
            while client_state.get("running", False):
                r, _, _ = select.select([conn], [], [], 1.0)
                if not r:
                    release_all_modifiers()
                    if time.time() - last_recv > 60.0:
                        client_state["running"] = False
                        break
                    continue

                raw = recv_msg(conn, password)
                if not raw:
                    break
                last_recv = time.time()
                try:
                    event = json.loads(raw.decode("utf-8"))
                except Exception:
                    continue

                etype = event.get("type", "")
                if etype in CLIPBOARD_PKT_TYPES:
                    if etype == "cancel_transfer":
                        self._fm_abort.set()
                    event["_peer_sock"] = conn
                    self.clipboard_mgr.enqueue_packet(event)
                else:
                    in_q.put(event)
                    if etype in ("mouse_click", "mouse_scroll", "key_event", "set_monitors"):
                        client_state["force_update"] = True
                        client_state["wake_event"].set()
        except Exception as e:
            xp_log(f"[Receiver] Disconnected: {e}", base_dir=self.base_dir)
        finally:
            in_q.put("STOP")
            release_all_modifiers()

    def _handle_event(self, event, conn, password, client_state):
        ev_type = event.get("type")
        if ev_type == "mouse_move":
            tx, ty = self._resolve_mouse_xy(event, client_state)
            if tx is not None and ty is not None:
                client_state["last_injected_cursor"] = (tx, ty)
                client_state["last_client_mouse_ts"] = time.time()
                send_mouse_move(tx, ty)

        elif ev_type == "mouse_click":
            attach_thread_to_active_desktop()
            tx, ty = self._resolve_mouse_xy(event, client_state)
            if tx is not None and ty is not None:
                client_state["last_injected_cursor"] = (tx, ty)
                client_state["last_client_mouse_ts"] = time.time()
            send_mouse_click(event.get("button", "left"), event.get("pressed", False), tx, ty)

        elif ev_type == "mouse_scroll":
            attach_thread_to_active_desktop()
            send_mouse_scroll(event.get("dx", 0), event.get("dy", 0))

        elif ev_type == "key_event":
            attach_thread_to_active_desktop()
            send_keyboard_event(event.get("key", ""), event.get("pressed", False))

        elif ev_type == "set_monitors":
            l_on = bool(event.get("left", True))
            r_on = bool(event.get("right", True))
            if not l_on and not r_on:
                l_on = True
            client_state["monitor_mode"] = "both" if (l_on and r_on) else ("left" if l_on else "right")
            client_state["force_update"] = True
            client_state["wake_event"].set()

        elif ev_type == "resize_viewer":
            client_state["viewer_w"] = int(event.get("w", 1024) or 1024)
            client_state["viewer_h"] = int(event.get("h", 768) or 768)
            client_state["has_viewer_size"] = True
            client_state["force_update"] = True
            client_state["wake_event"].set()

        elif ev_type == "quality_mode":
            client_state["quality_mode"] = event.get("mode", "quality")
            client_state["force_update"] = True
            client_state["wake_event"].set()

        elif ev_type == "ping":
            send_msg(conn, json.dumps({"type": "pong"}).encode("utf-8"), password)

        elif ev_type == "trigger_sas":
            trigger_xp_ctrl_alt_del()
            client_state["force_update"] = True
            client_state["wake_event"].set()

        elif ev_type == "type_password":
            pwd_txt = event.get("password", "")
            if pwd_txt:
                type_text_unicode(pwd_txt)

        elif ev_type == "trigger_terminal":
            try:
                subprocess.Popen(["cmd.exe"], close_fds=True)
            except Exception:
                pass

        elif ev_type == "trigger_taskmgr":
            try:
                subprocess.Popen(["taskmgr.exe"], close_fds=True)
            except Exception:
                pass

        elif ev_type == "check_domain":
            is_dom, rsn = _is_xp_domain_joined()
            desk = get_input_desktop_name()
            is_locked = desk not in ("default", "")
            send_msg(
                conn,
                json.dumps({
                    "type": "domain_status",
                    "is_domain": is_dom,
                    "reason": rsn,
                    "is_locked": is_locked,
                }).encode("utf-8"),
                password,
            )

        elif ev_type == "request_list_dir":
            self._handle_list_dir(event, conn, password)

        elif ev_type == "request_file_download":
            self._handle_file_download(event, conn, password)

        elif ev_type == "request_download_batch":
            self._handle_batch_download(event, conn, password)

    # ==========================================================================
    # 4. Built-in Remote File Manager Handlers (100% compatible with Viewer)
    # ==========================================================================
    def _handle_list_dir(self, event, conn, password):
        path = event.get("path", "C:\\")
        items = []
        try:
            if not path or path in ("/", "drives"):
                bitmask = ctypes.windll.kernel32.GetLogicalDrives() if sys.platform == "win32" else 0
                for i in range(26):
                    if bitmask & (1 << i):
                        drv = f"{chr(65 + i)}:\\"
                        items.append({"name": drv, "is_dir": True, "size": 0})
            elif os.path.isdir(path):
                for name in os.listdir(path):
                    full = os.path.join(path, name)
                    try:
                        is_d = os.path.isdir(full)
                        sz = 0 if is_d else os.path.getsize(full)
                    except Exception:
                        is_d, sz = False, 0
                    items.append({"name": name, "is_dir": is_d, "size": sz})
        except Exception:
            pass
        send_msg(conn, json.dumps({"type": "list_dir_result", "path": path, "items": items}).encode("utf-8"), password)

    def _handle_file_download(self, event, conn, password):
        p = event.get("path")
        t_dir = event.get("target_dir_local")
        if not p or not os.path.isfile(p):
            return

        def _dl():
            self._fm_abort.clear()
            name = os.path.basename(p)
            sz = os.path.getsize(p)
            if not send_msg(
                conn,
                json.dumps({"type": "file_start", "name": name, "size": sz, "target_dir": t_dir}).encode("utf-8"),
                password,
            ):
                return
            with open(p, "rb") as fh:
                while not self._fm_abort.is_set():
                    chunk = fh.read(65536)
                    if not chunk:
                        break
                    pkt = {"type": "file_chunk", "name": name, "data": base64.b64encode(chunk).decode("ascii")}
                    if not send_msg(conn, json.dumps(pkt).encode("utf-8"), password):
                        return
            if not self._fm_abort.is_set():
                send_msg(conn, json.dumps({"type": "file_end", "name": name}).encode("utf-8"), password)

        threading.Thread(target=_dl, daemon=True, name="XPFmDownload").start()

    def _handle_batch_download(self, event, conn, password):
        paths = event.get("paths") or []
        t_dir = event.get("target_dir_local")

        def _batch():
            self._fm_abort.clear()
            all_files = []
            total_sz = 0
            for p in paths:
                if os.path.isfile(p):
                    sz = os.path.getsize(p)
                    all_files.append((p, os.path.basename(p), sz))
                    total_sz += sz
                elif os.path.isdir(p):
                    parent = os.path.dirname(os.path.abspath(p))
                    for root, _dirs, files in os.walk(p):
                        rel_dir = os.path.relpath(root, parent)
                        for fn in files:
                            full = os.path.join(root, fn)
                            if os.path.isfile(full):
                                sz = os.path.getsize(full)
                                rname = os.path.join(rel_dir, fn).replace("\\", "/")
                                all_files.append((full, rname, sz))
                                total_sz += sz
            if not all_files:
                send_msg(conn, json.dumps({"type": "batch_end"}).encode("utf-8"), password)
                return
            disp = all_files[0][1] if len(paths) == 1 else f"{len(paths)} mục"
            if not send_msg(
                conn,
                json.dumps({
                    "type": "batch_start",
                    "count": len(all_files),
                    "total_size": total_sz,
                    "display_name": disp,
                }).encode("utf-8"),
                password,
            ):
                return
            for full, rname, sz in all_files:
                if self._fm_abort.is_set():
                    return
                if not send_msg(
                    conn,
                    json.dumps({"type": "file_start", "name": rname, "size": sz, "target_dir": t_dir}).encode("utf-8"),
                    password,
                ):
                    return
                with open(full, "rb") as fh:
                    while not self._fm_abort.is_set():
                        chunk = fh.read(65536)
                        if not chunk:
                            break
                        pkt = {"type": "file_chunk", "name": rname, "data": base64.b64encode(chunk).decode("ascii")}
                        if not send_msg(conn, json.dumps(pkt).encode("utf-8"), password):
                            return
                if not send_msg(conn, json.dumps({"type": "file_end", "name": rname}).encode("utf-8"), password):
                    return
            if not self._fm_abort.is_set():
                send_msg(conn, json.dumps({"type": "batch_end"}).encode("utf-8"), password)

        threading.Thread(target=_batch, daemon=True, name="XPFmBatch").start()
