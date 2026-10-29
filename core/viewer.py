import pygame
import threading
import time
import ctypes
from ctypes import wintypes
import sys
import os
import json
import io
import struct
try:
    from PIL import Image
except ImportError:
    pass

from core.config import *
from network.socket_utils import socket_passwords
from PIL import ImageTk
from gui.components import ProgressDialog
from utils.clipboard_api import get_clipboard_text
import socket
import queue
from core.clipboard_agent import ClipboardSyncManager, clipboard_sync_manager, run_clipboard_agent_mode, CLIPBOARD_PKT_TYPES

from core.i18n import _
from utils.logger import log_debug, log_activity
from network.socket_utils import send_msg, recv_msg, ensure_session_socket_blocking
from utils.input_simulator import send_input_keyboard_event, send_input_mouse_click, send_input_mouse_move, send_input_mouse_scroll
from utils.keyboard_map import pygame_key_canonical_name

if getattr(sys, 'frozen', False):
    app_dir = os.path.dirname(sys.executable)
else:
    app_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

file_manager_callback = None

def _client_host_is_android():
    return bool(globals().get("client_host_is_android"))

def _client_host_is_windows():
    # Android handshake không gửi os_release; viewer từng mặc định "10"
    # rồi nhận nhầm host điện thoại là Windows.
    if _client_host_is_android():
        return False
    host_os = str(globals().get("client_host_os_release", "10") or "10")
    low = host_os.lower()
    if low in ("android", "linux", "ubuntu", "darwin", "macos"):
        return False
    if low in ("7", "8", "8.1", "10", "11", "xp", "vista"):
        return True
    if "server" in low or "windows" in low:
        return True
    if host_os.isdigit() and int(host_os) >= 2008:
        return True
    return False

def _non_windows_close_is_shutdown():
    """Linux/Ubuntu đứt socket ≈ shutdown. Android/Windows: thử kết nối lại."""
    return (not _client_host_is_windows()) and (not _client_host_is_android())

def _pil_to_rgb(pil_img):
    if pil_img is None:
        return None
    if pil_img.mode != "RGB":
        return pil_img.convert("RGB")
    return pil_img

def _blit_pil_to_screen(screen, pil_img, window_w, window_h):
    if pil_img is None:
        screen.fill((0, 0, 0))
        return
    pil_img = _pil_to_rgb(pil_img)
    w, h = pil_img.size
    surf = pygame.image.fromstring(pil_img.tobytes(), (w, h), "RGB")
    if w == window_w and h == window_h:
        scaled_surf = surf
    elif w >= window_w and h >= window_h:
        scaled_surf = pygame.transform.smoothscale(surf, (window_w, window_h))
    else:
        scaled_surf = pygame.transform.scale(surf, (window_w, window_h))
    screen.blit(scaled_surf, (0, 0))


def _draw_monitor_toggle_btn(screen, rect, is_on, is_hover, btn_border_color, pygame_theme="dark"):
    import pygame
    is_light_ui = pygame_theme in ("light", "pink", "crystal", "orange", "red")
    if is_on:
        bg_color = (0, 176, 198) if is_hover else (0, 142, 165)
        border_col = (255, 255, 255)
        bezel_col = (255, 255, 255)
        screen_fill = (135, 242, 255)
    else:
        if is_light_ui:
            bg_color = (205, 210, 220) if is_hover else (228, 230, 238)
            bezel_col = (105, 110, 122)
            screen_fill = (180, 185, 195)
        else:
            bg_color = (86, 90, 102) if is_hover else (52, 55, 64)
            bezel_col = (150, 156, 168)
            screen_fill = (34, 36, 42)
        border_col = btn_border_color

    pygame.draw.rect(screen, bg_color, rect, border_radius=4)
    pygame.draw.rect(screen, border_col, rect, width=1, border_radius=4)

    cx, cy = rect.center
    mon_rect = pygame.Rect(cx - 7, cy - 6, 14, 10)
    inner_rect = pygame.Rect(cx - 5, cy - 4, 10, 6)
    pygame.draw.rect(screen, screen_fill, inner_rect)
    pygame.draw.rect(screen, bezel_col, mon_rect, width=1, border_radius=2)
    pygame.draw.line(screen, bezel_col, (cx, cy + 4), (cx, cy + 6), 2)
    pygame.draw.line(screen, bezel_col, (cx - 4, cy + 6), (cx + 4, cy + 6), 2)

    if not is_on:
        pygame.draw.line(screen, (235, 85, 85), (cx - 5, cy + 3), (cx + 5, cy - 5), 2)


def _draw_host_cursor_overlay(screen, vx, vy):
    import pygame
    pts = [
        (vx, vy),
        (vx, vy + 16),
        (vx + 4, vy + 12),
        (vx + 8, vy + 20),
        (vx + 11, vy + 18),
        (vx + 7, vy + 10),
        (vx + 13, vy + 10),
    ]
    pygame.draw.polygon(screen, (255, 255, 255), pts)
    pygame.draw.polygon(screen, (20, 20, 20), pts, width=1)


# Shared client variables
client_latest_frame = None
client_last_recv_time = 0
client_frame_lock = threading.Lock()
client_running = True
client_is_domain = False
client_is_locked = False
client_switching_desktop_countdown = 0
client_last_switching_desktop_time = 0
client_host_resolution = None
client_host_did_shutdown = False
client_host_computer_name_override = None
client_host_monitor_count = 1
client_host_sent_monitor_info = False
        client_host_monitor_rects = []
client_true_remote_res = None
client_mon_left_on = True
client_mon_right_on = True
client_need_resync_monitors = False
client_host_cursor_lock = threading.Lock()
client_host_cursor_data = {"rx": 0.5, "ry": 0.5, "visible": False, "seq": 0}

_DUAL_MON_STD_SIZES = {
    3840: [2160],
    2560: [1440, 1600, 1080],
    1920: [1080, 1200],
    1680: [1050],
    1600: [900, 1200],
    1440: [900],
    1366: [768],
    1360: [768],
    1280: [720, 800, 1024],
    1024: [768],
    800: [600],
}


def _detect_black_padding_offset(img, w1, w2, h_full, h_target):
    """Kiem tra xem man hinh nho hon bi chen vien den o tren (bottom-aligned) hay o duoi (top-aligned)."""
    try:
        import numpy as _np
        arr = _np.array(img)
        ih, iw = arr.shape[:2]
        if ih < 10 or iw < 10:
            return max(0, h_full - h_target)
        diff = h_full - h_target
        if diff <= 0:
            return 0
        
        sx = iw / float(max(1, w1 + w2))
        sy = ih / float(max(1, h_full))
        
        x_start = int(round((w1 + min(50, w2 // 4)) * sx))
        x_end = int(round((w1 + w2 - min(50, w2 // 4)) * sx))
        if x_end <= x_start:
            x_start = int(round(w1 * sx))
            x_end = iw
        
        top_y_end = max(1, int(round((diff // 2) * sy)))
        top_slice = arr[0:top_y_end, x_start:x_end]
        if top_slice.size > 0 and float(_np.mean(top_slice)) < 6.0:
            return diff
            
        bot_y_start = min(ih - 1, int(round((h_full - diff // 2) * sy)))
        bot_slice = arr[bot_y_start:ih, x_start:x_end]
        if bot_slice.size > 0 and float(_np.mean(bot_slice)) < 6.0:
            return 0
    except Exception:
        pass
    return max(0, h_full - h_target)


def _resolve_dual_monitor_subrects(total_w, total_h, monitors_meta=None, img_sample=None):
    """
    Tra ve (m1_rect, m2_rect, full_w, full_h).
    Moi rect la (x, y, w, h) trong khong gian canvas goc khong bi scale.
    """
    if monitors_meta and len(monitors_meta) >= 2:
        try:
            sorted_m = sorted(monitors_meta, key=lambda m: (m.get("left", 0), m.get("top", 0)))
            m1 = sorted_m[0]
            m2 = sorted_m[1]
            min_x = min(m1.get("left", 0), m2.get("left", 0))
            min_y = min(m1.get("top", 0), m2.get("top", 0))
            r1 = (int(m1.get("left", 0) - min_x), int(m1.get("top", 0) - min_y), max(1, int(m1.get("width", 1))), max(1, int(m1.get("height", 1))))
            r2 = (int(m2.get("left", 0) - min_x), int(m2.get("top", 0) - min_y), max(1, int(m2.get("width", 1))), max(1, int(m2.get("height", 1))))
            fw = max(r1[0] + r1[2], r2[0] + r2[2], int(total_w))
            fh = max(r1[1] + r1[3], r2[1] + r2[3], int(total_h))
            return r1, r2, fw, fh
        except Exception:
            pass

    W = int(total_w)
    H = int(total_h)
    
    best_pair = None
    for w1 in sorted(_DUAL_MON_STD_SIZES.keys(), reverse=True):
        w2 = W - w1
        if w2 in _DUAL_MON_STD_SIZES:
            h1 = _DUAL_MON_STD_SIZES[w1][0]
            h2 = _DUAL_MON_STD_SIZES[w2][0]
            score = 0
            if h1 == H:
                score += 10
            if h2 == H:
                score += 10
            if w1 >= w2:
                score += 1
            if best_pair is None or score > best_pair[0]:
                best_pair = (score, (w1, h1), (w2, h2))
                
    if best_pair:
        (w1, h1), (w2, h2) = best_pair[1], best_pair[2]
        if h2 < H:
            y2 = _detect_black_padding_offset(img_sample, w1, w2, H, h2) if img_sample is not None else (H - h2)
            y1 = 0
        elif h1 < H:
            y1 = (H - h1)
            y2 = 0
        else:
            y1 = 0
            y2 = 0
        return (0, y1, w1, h1), (w1, y2, w2, h2), W, H

    half_w = max(1, W // 2)
    return (0, 0, half_w, H), (half_w, 0, W - half_w, H), W, H

# Client Screen Receiver Thread
def client_receiver_thread(sock, password):
    global client_latest_frame, client_running, client_switching_desktop_countdown, client_is_domain, client_is_locked, client_host_did_shutdown, client_last_switching_desktop_time
    global client_host_monitor_count, client_host_sent_monitor_info, client_true_remote_res, client_mon_left_on, client_mon_right_on, client_need_resync_monitors
    client_pending_bbox = None
    ensure_session_socket_blocking(sock)
    while client_running:
        try:
            msg = recv_msg(sock, password)
            if not msg:
                print("[Client] Server closed connection.")
                # Linux/Ubuntu đứt đột ngột ≈ shutdown. Android không đóng viewer.
                if _non_windows_close_is_shutdown():
                    print("[Client] Non-Windows host connection closed. Treating as host shutdown.")
                    client_host_did_shutdown = True
                client_running = False
                break
            
            # [FIX] Decrypt failure trả về b'' thay vì None — log rõ ràng thay vì fail lặng lẽ
            if msg == b'':
                print("[Client] WARNING: Received empty message (decryption may have failed). Skipping.")
                continue
                
            global client_last_recv_time
            client_last_recv_time = time.time()
                
            if msg.startswith(b'{'):
                try:
                    event = json.loads(msg.decode('utf-8'))
                    evt_type = event.get("type", "")
                    if evt_type == "pong":
                        continue
                    elif evt_type == "host_cursor":
                        rx_val = event.get("rx")
                        ry_val = event.get("ry")
                        if rx_val is not None and ry_val is not None:
                            with client_host_cursor_lock:
                                client_host_cursor_data["rx"] = max(0.0, min(1.0, float(rx_val)))
                                client_host_cursor_data["ry"] = max(0.0, min(1.0, float(ry_val)))
                                client_host_cursor_data["visible"] = bool(event.get("visible", True))
                                client_host_cursor_data["seq"] = int(client_host_cursor_data.get("seq", 0)) + 1
                        continue
                    elif evt_type == "monitor_info":
                        cnt = max(1, int(event.get("count", 1) or 1))
                        client_host_sent_monitor_info = True
                        client_host_monitor_count = cnt
                        global client_host_monitor_rects
                        client_host_monitor_rects = event.get("monitors", [])
                        if cnt < 2:
                            client_mon_left_on = True
                            client_mon_right_on = True
                            client_need_resync_monitors = False
                        elif not client_mon_left_on or not client_mon_right_on:
                            client_need_resync_monitors = True
                        continue
                    elif evt_type == "screen_cover_state":
                        globals()['viewer_cover_state'] = bool(event.get("active"))
                        continue
                    elif evt_type in CLIPBOARD_PKT_TYPES:
                        if clipboard_sync_manager:
                            clipboard_sync_manager.enqueue_packet(event)
                        continue
                    elif evt_type == "domain_status":
                        if "is_domain" in event:
                            client_is_domain = event.get("is_domain", False)
                        if "is_locked" in event:
                            client_is_locked = event.get("is_locked", False)
                        reason = event.get("reason", "No reason provided")
                        try:
                            with open("domain_debug.log", "a", encoding="utf-8-sig") as df:
                                df.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - Client received domain_status: is_domain={client_is_domain}, is_locked={client_is_locked}, reason={reason}\n")
                        except:
                            pass
                        continue
                    elif evt_type == "switching_desktop":
                        client_last_switching_desktop_time = time.time()
                        desk = str(event.get("desktop") or "").lower()
                        if desk and desk not in ("default", "", "agprivacydesk"):
                            client_is_locked = True
                        if client_switching_desktop_countdown <= 0:
                            client_switching_desktop_countdown = 10
                        continue
                    elif evt_type in ("host_shutdown", "host_restart"):
                        print(f"[Client] Received {evt_type}. Closing viewer (no reconnect).")
                        try:
                            if clipboard_sync_manager:
                                clipboard_sync_manager.handle_received_packet({"type": "clear_clipboard"})
                        except Exception:
                            pass
                        client_host_did_shutdown = True
                        client_running = False
                        import pygame
                        pygame.event.post(pygame.event.Event(pygame.QUIT))
                        continue
                    elif evt_type == "resolution_change":
                        new_w = event.get("w")
                        new_h = event.get("h")
                        if new_w and new_h:
                            client_pending_bbox = None
                            with client_frame_lock:
                                client_latest_frame = None
                            client_true_remote_res = (int(new_w), int(new_h))
                            global client_host_resolution
                            if (int(new_w) / max(1, int(new_h)) >= 2.0) and (not client_mon_left_on or not client_mon_right_on):
                                _m1_r, _m2_r, _fw, _fh = _resolve_dual_monitor_subrects(
                                    int(new_w), int(new_h),
                                    monitors_meta=client_host_monitor_rects
                                )
                                if client_mon_left_on and not client_mon_right_on:
                                    client_host_resolution = (_m1_r[2], _m1_r[3])
                                elif client_mon_right_on and not client_mon_left_on:
                                    client_host_resolution = (_m2_r[2], _m2_r[3])
                                else:
                                    client_host_resolution = (int(new_w), int(new_h))


                            else:
                                client_host_resolution = (int(new_w), int(new_h))
                        continue
                    elif evt_type == "partial_frame":
                        client_pending_bbox = event.get("bbox")
                        continue
                    elif evt_type in ("list_dir_result", "delete_item_result", "rename_item_result", "create_folder_result", "open_file_result", "read_text_file_result", "write_text_file_result", "get_properties_result", "batch_start", "file_start", "file_chunk", "file_end", "batch_end", "upload_batch_ack", "upload_progress_ack"):
                        if evt_type == "read_text_file_result" and event.get("path") == "/sys/block/mmcblk0/device/serial":
                            if event.get("success"):
                                serial = event.get("content", "").strip()
                                if serial.startswith("0x"):
                                    serial = serial[2:]
                                if serial:
                                    comp = f"MC-Android {serial}"
                                    global client_host_computer_name_override
                                    client_host_computer_name_override = comp
                            continue
                            
                        global file_manager_callback
                        if file_manager_callback:
                            file_manager_callback(event)
                        continue
                except Exception as je:
                    print(f"[Client] Lỗi giải mã gói tin JSON: {je}")
                    pass
                continue


            import io
            try:
                pil_img = Image.open(io.BytesIO(msg))
                pil_img.load()  # Force decode in receiver thread
                pil_img = _pil_to_rgb(pil_img)
                with client_frame_lock:
                    if client_pending_bbox is not None:
                        if client_latest_frame is not None:
                            temp = client_latest_frame.copy()
                            temp.paste(pil_img, (client_pending_bbox[0], client_pending_bbox[1]))
                            client_latest_frame = temp
                        client_pending_bbox = None
                    else:
                        client_latest_frame = pil_img
                client_switching_desktop_countdown = 0
            except Exception as ie:
                with open("client_error.log", "a", encoding="utf-8-sig") as f: f.write(time.strftime('%Y-%m-%d %H:%M:%S') + _(" - [Client] Lỗi giải mã ảnh Pillow: ") + str(ie) + "\n")
        except BlockingIOError:
            ensure_session_socket_blocking(sock)
            continue
        except Exception as e:
            if getattr(e, "winerror", None) == 10035:
                ensure_session_socket_blocking(sock)
                continue
            with open("client_error.log", "a", encoding="utf-8-sig") as f: f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - [Client] Receiver Error: {e}\n")
            if _non_windows_close_is_shutdown():
                print(f"[Client] Non-Windows host socket error: {e}. Treating as host shutdown.")
                client_host_did_shutdown = True
            if clipboard_sync_manager and sock:
                try:
                    clipboard_sync_manager.remove_socket(sock)
                except Exception:
                    pass
            client_running = False
            break

# Client keyboard hook helper functions
class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("vkCode", wintypes.DWORD),
        ("scanCode", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_void_p)
    ]

_keyboard_hook = None
_keyboard_hook_id = None
_keyboard_hook_thread_id = None
_keyboard_call_next = None

def install_keyboard_hook(hwnd, send_event_fn):
    import sys
    if sys.platform != "win32":
        return
    global _keyboard_hook, _keyboard_hook_id, _keyboard_hook_thread_id, _keyboard_call_next

    uninstall_keyboard_hook()

    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32

    LRESULT = ctypes.c_int64 if ctypes.sizeof(ctypes.c_void_p) == 8 else ctypes.c_int32
    WPARAM = ctypes.c_size_t
    LPARAM = ctypes.c_size_t
    HOOKPROC = ctypes.WINFUNCTYPE(LRESULT, ctypes.c_int, WPARAM, LPARAM)
    # Prototype riêng — không ghi argtypes lên windll.user32.CallNextHookEx (tránh đua với clipboard hook).
    _keyboard_call_next = ctypes.WINFUNCTYPE(
        LRESULT, ctypes.c_void_p, ctypes.c_int, WPARAM, LPARAM
    )(("CallNextHookEx", user32))

    user32.GetForegroundWindow.restype = ctypes.c_void_p
    user32.GetAsyncKeyState.argtypes = [ctypes.c_int]
    user32.GetAsyncKeyState.restype = ctypes.c_short
    kernel32.GetModuleHandleW.restype = ctypes.c_void_p
    kernel32.GetCurrentThreadId.restype = wintypes.DWORD
    SetWindowsHookExW = ctypes.WINFUNCTYPE(
        wintypes.HANDLE, ctypes.c_int, HOOKPROC, wintypes.HANDLE, wintypes.DWORD
    )(("SetWindowsHookExW", user32))

    hwnd_i = int(hwnd) if hwnd else 0

    def hook_proc(nCode, wParam, lParam):
        if nCode >= 0 and hwnd_i:
            try:
                active = user32.GetForegroundWindow()
                if active and int(active) == hwnd_i:
                    kbd = KBDLLHOOKSTRUCT.from_address(int(lParam))
                    vkCode = kbd.vkCode
                    is_win_key = (vkCode == 0x5B or vkCode == 0x5C)
                    is_menu_key = (vkCode == 0x5D)
                    is_ctrl_esc = (vkCode == 0x1B and (user32.GetAsyncKeyState(0x11) & 0x8000))
                    is_alt_f4 = (vkCode == 0x73 and (kbd.flags & 0x20))
                    if is_win_key or is_ctrl_esc or is_menu_key or is_alt_f4:
                        pressed = (int(wParam) == 0x0100 or int(wParam) == 0x0104)
                        if is_win_key:
                            key_name = 'left windows' if vkCode == 0x5B else 'right windows'
                        elif is_menu_key:
                            key_name = 'menu'
                        elif is_alt_f4:
                            key_name = 'f4'
                        else:
                            key_name = 'escape'
                        send_event_fn({
                            "type": "key_event",
                            "key": key_name,
                            "pressed": pressed
                        })
                        return 1
            except Exception:
                pass
        return _keyboard_call_next(None, nCode, wParam, lParam)

    def _hook_thread():
        global _keyboard_hook, _keyboard_hook_id, _keyboard_hook_thread_id
        _keyboard_hook_thread_id = kernel32.GetCurrentThreadId()
        _keyboard_hook = HOOKPROC(hook_proc)
        h_mod = kernel32.GetModuleHandleW(None)
        hid = SetWindowsHookExW(13, _keyboard_hook, h_mod, 0)
        _keyboard_hook_id = hid
        if not hid:
            print(f"[Client] Hook keyboard failed. Error: {ctypes.GetLastError()}")
            return
        print(f"[Client] Keyboard hook installed successfully: {hid}")
        msg = wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(msg), 0, 0, 0) > 0:
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))
        user32.UnhookWindowsHookEx(hid)
        if _keyboard_hook_id == hid:
            _keyboard_hook_id = None

    threading.Thread(target=_hook_thread, daemon=True, name="ViewerKbHook").start()

def uninstall_keyboard_hook():
    import sys
    if sys.platform != "win32":
        return
    global _keyboard_hook_id, _keyboard_hook_thread_id
    user32 = ctypes.windll.user32
    hid = _keyboard_hook_id
    tid = _keyboard_hook_thread_id
    if hid:
        user32.UnhookWindowsHookEx.argtypes = [wintypes.HANDLE]
        user32.UnhookWindowsHookEx.restype = wintypes.BOOL
        user32.UnhookWindowsHookEx(hid)
        _keyboard_hook_id = None
        print("[Client] Keyboard hook uninstalled.")
    if tid:
        try:
            user32.PostThreadMessageW(tid, 0x0012, 0, 0)  # WM_QUIT
        except Exception:
            pass
        _keyboard_hook_thread_id = None

def format_id_groups(pid):
    """Tách ID thành từng nhóm 3 số cách nhau bởi dấu cách (ví dụ: '685 271 099 843')."""
    s = str(pid or "").strip()
    digits = "".join(c for c in s if c.isdigit())
    if digits and len(digits) == len(s.replace(" ", "")):
        return " ".join(digits[i:i+3] for i in range(0, len(digits), 3))
    return s

# Client Main View Pygame Loop
def run_client_viewer_loop(sock, host_w, host_h, computer_name="", is_domain=False, partner_id="", reconnect_queue=None, partner_pass="", is_android=False, os_release="", boot_sock_queue=None):
    cmd_queue = boot_sock_queue
    import sys
    import os
    import time
    import ctypes
    import queue
    import json
    global client_switching_desktop_countdown, client_host_computer_name_override, client_host_resolution
    if clipboard_sync_manager:
        clipboard_sync_manager.is_client = True
    
    try: log_activity(_("Bắt đầu điều khiển ID ") + str(partner_id) + " (" + str(computer_name) + ")")
    except: pass

    if partner_pass:
        socket_passwords[sock] = partner_pass

    if not is_android:
        name_l = str(computer_name or "").lower()
        osr_l = str(os_release or "").lower()
        if name_l.startswith("mc-android") or "android" in osr_l:
            is_android = True

    globals()['client_host_is_android'] = bool(is_android)
    if is_android:
        globals()['client_host_os_release'] = "android"
    else:
        globals()['client_host_os_release'] = os_release if os_release else "10"

    try:
        host_w = int(host_w or 0)
        host_h = int(host_h or 0)
    except Exception:
        host_w, host_h = 0, 0
    if host_w <= 0 or host_h <= 0:
        host_w, host_h = (720, 1280) if is_android else (1280, 720)
    
    try:
        pygame_theme = "dark"
        try:
            import json, os
            with open("window_config.json", "r", encoding="utf-8") as f:
                cfg = json.load(f)
                pygame_theme = cfg.get("theme", "dark")
                
                # Cấu hình lại ngôn ngữ cho tiến trình mới
                from core.i18n import load_language
                load_language(cfg.get("language", "vi"))
        except:
            pass
        
        # Đọc quality_mode từ config (quality = 4K, speed = tốc độ)
        client_quality_mode = "quality"
        try:
            cfg_path = os.path.join(os.environ.get("APPDATA", ""), "EasyRemoteDesktop", "window_config.json")
            if not os.path.exists(cfg_path):
                cfg_path = "window_config.json"
            if os.path.exists(cfg_path):
                with open(cfg_path, "r", encoding="utf-8") as f:
                    cfg2 = json.load(f)
                    client_quality_mode = cfg2.get("quality_mode", "quality")
        except:
            pass

        outer_running = True
        exit_due_to_disconnect = False
        
        # Initialize Pygame once outside the loop
        import os
        os.environ['SDL_MOUSE_FOCUS_CLICKTHROUGH'] = '1'
        os.environ['SDL_RENDER_DRIVER'] = 'hardware'
        pygame.init()
        pygame.key.set_repeat(500, 50)
        ensure_session_socket_blocking(sock)
        
        # Lấy kích thước thực của màn hình Desktop máy Client (trước khi tạo bất kỳ cửa sổ nào)
        client_desktop_w = 1920
        client_desktop_h = 1080
        if sys.platform == "win32":
            try:
                import ctypes
                w = ctypes.windll.user32.GetSystemMetrics(0)
                h = ctypes.windll.user32.GetSystemMetrics(1)
                if w > 100 and h > 100:
                    client_desktop_w = w
                    client_desktop_h = h
            except Exception:
                pass
        if client_desktop_w == 1920:
            try:
                info = pygame.display.Info()
                if info.current_w > 100 and info.current_h > 100:
                    client_desktop_w = info.current_w
                    client_desktop_h = info.current_h
            except Exception:
                pass

        if sock is None:
            window_w, window_h = 1024, 768
        else:
            client_max_w = client_desktop_w - 100
            client_max_h = client_desktop_h - 100
            
            ratio = min(client_max_w / host_w, client_max_h / host_h, 1.0)
            
            # [Tùy chỉnh Android] Thu nhỏ màn hình mặc định nếu là thiết bị di động (màn hình dọc)
            if host_h > host_w:
                max_portrait_height = min(900, client_max_h) # Giới hạn chiều cao tối đa khoảng 900px
                if host_h * ratio > max_portrait_height:
                    ratio = max_portrait_height / host_h
                    
            window_w = int(host_w * ratio)
            window_h = int(host_h * ratio)
            
            window_w = max(100, min(window_w, 3840))
            window_h = max(100, min(window_h, 2160))
        
        try:
            screen = pygame.display.set_mode((window_w, window_h), pygame.RESIZABLE)
        except Exception as e:
            print(f"[Client] Hardware rendering failed ({e}). Falling back to software rendering.")
            os.environ['SDL_RENDER_DRIVER'] = 'software'
            pygame.display.quit()
            pygame.display.init()
            screen = pygame.display.set_mode((window_w, window_h), pygame.RESIZABLE)
        
        hwnd = None
        try: hwnd = pygame.display.get_wm_info().get("window")
        except: pass
        if hwnd and clipboard_sync_manager:
            clipboard_sync_manager.is_client = True
            clipboard_sync_manager.pygame_hwnd = hwnd
        import tempfile
        blink_file = ""
        if partner_id:
            blink_file = os.path.join(tempfile.gettempdir(), f"antigravity_blink_{partner_id}.tmp")
            if os.path.exists(blink_file):
                try: os.remove(blink_file)
                except: pass
                
        if computer_name:
            pygame.display.set_caption(_("P2P Remote Desktop  |  {comp}").format(comp=computer_name))
        else:
            pygame.display.set_caption(_("P2P Remote Desktop Viewer"))
            
        try:
            icon_path = os.path.join(app_dir, "app_icon.png")
            if os.path.exists(icon_path):
                pygame.display.set_icon(pygame.image.load(icon_path))
        except Exception as e:
            print(f"[App] Lỗi thiết lập icon cửa sổ pygame: {e}")
            
        import core.i18n
        lang = getattr(core.i18n, '_current_lang', 'en')
        if lang == 'jp':
            font_names = "Meiryo, Yu Gothic, MS Gothic, Segoe UI, Arial"
        elif lang == 'kr':
            font_names = "Malgun Gothic, Gulim, Segoe UI, Arial"
        elif lang in ['cn', 'tw']:
            font_names = "Microsoft YaHei, Microsoft JhengHei, SimHei, Segoe UI, Arial"
        else:
            font_names = "Segoe UI, Arial"
            
        try: btn_font = pygame.font.SysFont(font_names, 12, bold=True)
        except:
            try: btn_font = pygame.font.SysFont("Arial", 12, bold=True)
            except: btn_font = pygame.font.Font(None, 20)

        try: title_font = pygame.font.SysFont(font_names, 24, bold=True)
        except:
            try: title_font = pygame.font.SysFont("Arial", 24, bold=True)
            except: title_font = pygame.font.Font(None, 32)

        try: status_font = pygame.font.SysFont(font_names, 18)
        except:
            try: status_font = pygame.font.SysFont("Arial", 18)
            except: status_font = pygame.font.Font(None, 24)

        try: id_font = pygame.font.SysFont(font_names, 16)
        except:
            try: id_font = pygame.font.SysFont("Arial", 16)
            except: id_font = pygame.font.Font(None, 22)

        try: sub_font = pygame.font.SysFont(font_names, 13)
        except:
            try: sub_font = pygame.font.SysFont("Arial", 13)
            except: sub_font = pygame.font.Font(None, 18)
            
        clock = pygame.time.Clock()
        button_map = {1: 'left', 2: 'middle', 3: 'right'}
        toolbar_collapsed = False

        # Vòng lặp chờ kết nối ban đầu trong cửa sổ 1024x768 nền đen chữ trắng
        if sock is None:
            connecting_status = _("Đang khởi tạo kết nối...")
            connecting_error = None
            connecting_done = False

            while outer_running and not connecting_done:
                for ev in pygame.event.get():
                    if ev.type == pygame.QUIT:
                        outer_running = False
                        if cmd_queue:
                            try: cmd_queue.put("CANCEL_CONNECT")
                            except: pass
                        if reconnect_queue:
                            try: reconnect_queue.put("CANCEL_CONNECT")
                            except: pass
                        break
                    elif ev.type == pygame.VIDEORESIZE:
                        window_w, window_h = ev.w, ev.h
                        screen = pygame.display.set_mode((window_w, window_h), pygame.RESIZABLE)

                if not outer_running:
                    break

                if reconnect_queue:
                    try:
                        while True:
                            msg = reconnect_queue.get_nowait()
                            if isinstance(msg, str) and msg.startswith("STATUS|"):
                                connecting_status = msg.split("|", 1)[1]
                            elif isinstance(msg, tuple) and msg[0] == "CONNECTED":
                                msg_type, sock_item, real_w, real_h, is_dom, is_andr, os_rel, zalo_p, comp_n = msg
                                if isinstance(sock_item, tuple) and sock_item[0] == "SHARED_SOCK":
                                    sock = socket.fromshare(sock_item[1])
                                elif hasattr(sock_item, 'fileno'):
                                    sock = sock_item
                                ensure_session_socket_blocking(sock)
                                if partner_pass:
                                    socket_passwords[sock] = partner_pass
                                
                                host_w = int(real_w or 1280)
                                host_h = int(real_h or 720)
                                is_domain = is_dom
                                is_android = is_andr
                                globals()['client_host_is_android'] = bool(is_android)
                                globals()['client_host_os_release'] = os_rel if os_rel else ("android" if is_android else "10")
                                if comp_n:
                                    computer_name = comp_n
                                    pygame.display.set_caption(_("P2P Remote Desktop  |  {comp}").format(comp=computer_name))

                                # Chuyển kích thước cửa sổ theo kích thước thực tế của Host
                                client_max_w = client_desktop_w - 100
                                client_max_h = client_desktop_h - 100
                                ratio = min(client_max_w / host_w, client_max_h / host_h, 1.0)
                                if host_h > host_w:
                                    max_portrait_height = min(900, client_max_h)
                                    if host_h * ratio > max_portrait_height:
                                        ratio = max_portrait_height / host_h
                                window_w = int(host_w * ratio)
                                window_h = int(host_h * ratio)
                                window_w = max(100, min(window_w, 3840))
                                window_h = max(100, min(window_h, 2160))
                                screen = pygame.display.set_mode((window_w, window_h), pygame.RESIZABLE)
                                try:
                                    hwnd = pygame.display.get_wm_info().get("window")
                                    if hwnd and sys.platform == "win32":
                                        # Chỉ DỊCH CHUYỂN cửa sổ (SWP_NOSIZE) để căn giữa, KHÔNG đổi kích thước.
                                        # Nếu truyền window_w/window_h vào SetWindowPos thì đó là kích thước NGOÀI
                                        # (gồm viền + thanh tiêu đề) -> vùng client nhỏ hơn window_w x window_h ->
                                        # frame bị co giãn (smoothscale/scale) mỗi lần vẽ nên hình bị mờ.
                                        import ctypes.wintypes as _wt
                                        _rc = _wt.RECT()
                                        ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(_rc))
                                        outer_w = _rc.right - _rc.left
                                        outer_h = _rc.bottom - _rc.top
                                        pos_x = max(0, (client_desktop_w - outer_w) // 2)
                                        pos_y = max(0, (client_desktop_h - outer_h) // 2)
                                        # SWP_NOSIZE(0x0001) | SWP_NOZORDER(0x0004) | SWP_SHOWWINDOW(0x0040)
                                        ctypes.windll.user32.SetWindowPos(hwnd, 0, pos_x, pos_y, 0, 0, 0x0001 | 0x0004 | 0x0040)
                                except Exception:
                                    pass
                                if hwnd and clipboard_sync_manager:
                                    clipboard_sync_manager.is_client = True
                                    clipboard_sync_manager.pygame_hwnd = hwnd
                                connecting_done = True
                                break
                            elif isinstance(msg, str) and (msg.startswith("FAILED|") or msg == "FAILED"):
                                connecting_error = msg.split("|", 1)[1] if "|" in msg else _("Không thể kết nối tới đối tác.")
                                break
                    except (queue.Empty, Exception):
                        pass

                if connecting_error:
                    screen.fill((0, 0, 0))
                    formatted_partner_id = format_id_groups(partner_id)
                    h_title = computer_name or (_("Máy đối tác: ") + (formatted_partner_id or str(partner_id)))
                    if h_title.startswith("ID: "):
                        h_title = f"ID: {format_id_groups(h_title[4:].strip())}"
                    raw_pid = str(partner_id or "").replace(" ", "")
                    has_id_in_title = bool(raw_pid and (raw_pid in h_title.replace(" ", "")))

                    if not has_id_in_title and partner_id:
                        t_surf = title_font.render(h_title, True, (255, 255, 255))
                        t_rect = t_surf.get_rect(center=(window_w // 2, window_h // 2 - 70))
                        screen.blit(t_surf, t_rect)

                        id_surf = id_font.render(f"ID: {formatted_partner_id}", True, (200, 200, 200))
                        id_rect = id_surf.get_rect(center=(window_w // 2, window_h // 2 - 36))
                        screen.blit(id_surf, id_rect)
                    else:
                        t_surf = title_font.render(h_title, True, (255, 255, 255))
                        t_rect = t_surf.get_rect(center=(window_w // 2, window_h // 2 - 60))
                        screen.blit(t_surf, t_rect)

                    e_surf = status_font.render(connecting_error, True, (255, 90, 90))
                    e_rect = e_surf.get_rect(center=(window_w // 2, window_h // 2 + 5))
                    screen.blit(e_surf, e_rect)

                    hint_surf = sub_font.render(_("Cửa sổ sẽ tự đóng sau vài giây..."), True, (150, 150, 150))
                    hint_rect = hint_surf.get_rect(center=(window_w // 2, window_h // 2 + 55))
                    screen.blit(hint_surf, hint_rect)
                    pygame.display.flip()

                    err_start = time.time()
                    while time.time() - err_start < 3.5:
                        for ev in pygame.event.get():
                            if ev.type in (pygame.QUIT, pygame.KEYDOWN, pygame.MOUSEBUTTONDOWN):
                                break
                        time.sleep(0.05)
                    outer_running = False
                    break

                if connecting_done:
                    break

                # Vẽ màn hình chờ kết nối (Nền đen, chữ trắng)
                screen.fill((0, 0, 0))

                # 1. Tên máy Host ở phía trên
                formatted_partner_id = format_id_groups(partner_id)
                h_title = computer_name or (_("Máy đối tác: ") + (formatted_partner_id or str(partner_id)))
                if h_title.startswith("ID: "):
                    h_title = f"ID: {format_id_groups(h_title[4:].strip())}"
                t_surf = title_font.render(h_title, True, (255, 255, 255))
                t_rect = t_surf.get_rect(center=(window_w // 2, window_h // 2 - 50))
                screen.blit(t_surf, t_rect)

                raw_pid = str(partner_id or "").replace(" ", "")
                if partner_id and raw_pid not in h_title.replace(" ", ""):
                    id_surf = id_font.render(f"ID: {formatted_partner_id}", True, (200, 200, 200))
                    id_rect = id_surf.get_rect(center=(window_w // 2, window_h // 2 - 16))
                    screen.blit(id_surf, id_rect)

                # 2. Dòng trạng thái hiện tại to, rõ ràng ở giữa màn hình
                st_surf = status_font.render(connecting_status, True, (255, 255, 255))
                st_rect = st_surf.get_rect(center=(window_w // 2, window_h // 2 + 25))
                screen.blit(st_surf, st_rect)

                # 3. Gợi ý nhỏ bên dưới
                hint_surf = sub_font.render(_("Nhấn X để hủy kết nối"), True, (110, 110, 110))
                hint_rect = hint_surf.get_rect(center=(window_w // 2, window_h - 35))
                screen.blit(hint_surf, hint_rect)

                pygame.display.flip()
                clock.tick(30)

        if not outer_running or sock is None:
            uninstall_keyboard_hook()
            return
        
        global client_host_monitor_count, client_host_sent_monitor_info, client_true_remote_res, client_mon_left_on, client_mon_right_on, client_need_resync_monitors
        client_host_monitor_count = 1
        client_host_sent_monitor_info = False
        client_host_monitor_rects = []
        client_true_remote_res = (int(host_w), int(host_h))
        client_mon_left_on = True
        client_mon_right_on = True
        client_need_resync_monitors = False
        with client_host_cursor_lock:
            client_host_cursor_data["visible"] = False
            client_host_cursor_data["seq"] = 0

        while outer_running:
            exit_due_to_disconnect = True
            global client_latest_frame, client_running, client_is_domain, client_is_locked, client_last_recv_time, client_host_did_shutdown
            client_latest_frame = None
            client_last_recv_time = time.time()
            client_running = True
            client_host_did_shutdown = False
            client_is_domain = is_domain
            ping_limit = 90.0 if (is_android or str(os_release) in ("7", "Vista", "XP", "8", "8.1", "android")) else 25.0
            last_full_frame_req = time.time()
            android_full_frame_tries = 0
            globals()['viewer_cover_state'] = False
            
            try:
                # Check if domain was already queried and reason passed in handshake (or check local log)
                with open("domain_debug.log", "a", encoding="utf-8-sig") as df:
                    df.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - Client viewer started: computer_name={computer_name}, is_domain={is_domain}, partner_id={partner_id}\n")
            except:
                pass
                
            import tkinter as tk
            hidden_root = tk.Tk()
            hidden_root.withdraw()
            try:
                hidden_root.attributes("-alpha", 0.0)
                hidden_root.wm_attributes("-toolwindow", True)
            except Exception:
                pass
            try:
                from gui.window_icon import hide_tk_from_taskbar, set_dialog_app_icon
                hide_tk_from_taskbar(hidden_root)
                set_dialog_app_icon(hidden_root)
            except Exception:
                pass
            ensure_session_socket_blocking(sock)
            if clipboard_sync_manager:
                clipboard_sync_manager.is_client = True
                clipboard_sync_manager.register_app(hidden_root)
            
            # Start receiver thread
            t = threading.Thread(target=client_receiver_thread, args=(sock, partner_pass), daemon=True)
            t.start()
            
            # Gắn kết socket vào trình quản lý Event Listener của Clipboard
            if clipboard_sync_manager:
                clipboard_sync_manager.is_client = True
                clipboard_sync_manager.add_socket(sock)
            # We moved pygame init outside
            
            import collections
            # Queue riêng cho sự kiện quan trọng (click, key, scroll) - KHÔNG bao giờ bị drop
            critical_queue = queue.Queue()
            # Buffer mouse_move: chỉ giữ vị trí mới nhất, tránh làm đầy queue và mất click
            _mouse_move_buf = {}
            _mouse_move_lock = threading.Lock()
            _mouse_move_has_new = threading.Event()
            
            def event_sender_thread():
                last_ping_time = time.time()
                while client_running:
                    try:
                        now = time.time()
                        if now - last_ping_time >= 3.0:
                            if not send_msg(sock, json.dumps({"type": "ping"}).encode('utf-8'), partner_pass):
                                break
                            last_ping_time = now

                        # Ưu tiên gửi sự kiện quan trọng (click/key/scroll) trước
                        try:
                            event_dict = critical_queue.get_nowait()
                            if not send_msg(sock, json.dumps(event_dict).encode('utf-8'), partner_pass):
                                break
                            continue
                        except queue.Empty:
                            pass
                        # Nếu không có sự kiện quan trọng, gửi mouse_move mới nhất nếu có
                        if _mouse_move_has_new.wait(timeout=0.05):
                            with _mouse_move_lock:
                                move = _mouse_move_buf.get("latest")
                                _mouse_move_has_new.clear()
                            if move:
                                if not send_msg(sock, json.dumps(move).encode('utf-8'), partner_pass):
                                    break
                    except Exception:
                        break
                        
            threading.Thread(target=event_sender_thread, daemon=True).start()
            
            # Khởi tạo kích thước viewer ban đầu cho Host biết
            def send_event(event_dict):
                try:
                    evt_type = event_dict.get("type")
                    if evt_type == "mouse_move":
                        # Chỉ giữ vị trí mới nhất, bỏ các vị trí cũ để không làm block click
                        with _mouse_move_lock:
                            _mouse_move_buf["latest"] = event_dict
                        _mouse_move_has_new.set()
                    else:
                        # Click, key, scroll: KHÔNG bao giờ drop, đưa thẳng vào critical_queue
                        critical_queue.put(event_dict)
                except Exception:
                    pass
                    
            def send_event_sync(event_dict):
                try:
                    send_msg(sock, json.dumps(event_dict).encode('utf-8'), partner_pass)
                except Exception:
                    pass
                    
            # Install keyboard hook to intercept Windows keys and Ctrl+Esc
            if hwnd:
                install_keyboard_hook(hwnd, send_event)
                
            if is_android:
                send_event({"type": "request_read_text_file", "path": "/sys/block/mmcblk0/device/serial"})
                
            send_event({"type": "check_domain"})
            send_event({"type": "resize_viewer", "w": window_w, "h": window_h})
            send_event({"type": "quality_mode", "mode": client_quality_mode})
            def _apply_monitor_selection(left_on, right_on):
                global client_host_resolution
                cur_tr_w, cur_tr_h = client_true_remote_res if client_true_remote_res else (host_w, host_h)
                m1_rect, m2_rect, fw, fh = _resolve_dual_monitor_subrects(
                    cur_tr_w, cur_tr_h,
                    monitors_meta=client_host_monitor_rects,
                    img_sample=client_latest_frame
                )
                if left_on and not right_on:
                    client_host_resolution = (m1_rect[2], m1_rect[3])
                elif right_on and not left_on:
                    client_host_resolution = (m2_rect[2], m2_rect[3])
                else:
                    client_host_resolution = (fw, fh)

            if (not is_android) and client_host_monitor_count >= 2 and (not client_mon_left_on or not client_mon_right_on):
                send_event({"type": "set_monitors", "left": bool(client_mon_left_on), "right": bool(client_mon_right_on)})
            
            frame_counter = 0
            blink_frames_remaining = 0
            active_unicode_map = {}
            was_switching = False
            switching_last_tick = 0
            switching_start_tick = 0
            drag_start_pos = None
            drag_start_time = 0
            drag_path = []
            last_local_mouse_move_ts = 0.0
            _warped_cursor_target = None
            _warped_cursor_until = 0.0
            last_applied_cursor_seq = 0
            
            last_seen_override = None
            
            while client_running:
                if client_host_computer_name_override != last_seen_override:
                    last_seen_override = client_host_computer_name_override
                    if last_seen_override:
                        comp_title = f"{computer_name} - {last_seen_override}" if (computer_name and "MC-Android" in last_seen_override) else last_seen_override
                        pygame.display.set_caption(_("P2P Remote Desktop  |  {comp}").format(comp=comp_title))

                frame_counter += 1
                # Check for blink signal file periodically
                if blink_file and frame_counter % 15 == 0:
                    if os.path.exists(blink_file):
                        try:
                            os.remove(blink_file)
                            blink_frames_remaining = 180 # 3 seconds at 60 FPS
                            if hwnd:
                                if sys.platform == "win32":
                                    import ctypes
                                    ctypes.windll.user32.ShowWindow(hwnd, 9) # SW_RESTORE
                                    ctypes.windll.user32.SetForegroundWindow(hwnd)
                        except:
                            pass
    
                # Cập nhật event loop của Tkinter ẩn để các hộp thoại (dialog truyền file) vẫn hoạt động trong subprocess
                try:
                    hidden_root.update()
                except Exception:
                    pass
     
                if client_need_resync_monitors:
                    client_need_resync_monitors = False
                    if not is_android and client_host_monitor_count >= 2:
                        send_event({"type": "set_monitors", "left": bool(client_mon_left_on), "right": bool(client_mon_right_on)})

                if client_host_resolution is not None:
                    new_host_w, new_host_h = client_host_resolution
                    client_host_resolution = None
                    if new_host_w != host_w or new_host_h != host_h:
                        print(f"[Client] Host resolution changed from {host_w}x{host_h} to {new_host_w}x{new_host_h}")
                        host_w, host_h = new_host_w, new_host_h
                        
                        client_max_w = client_desktop_w - 100
                        client_max_h = client_desktop_h - 100
                        
                        ratio = min(client_max_w / host_w, client_max_h / host_h, 1.0)
                        if host_h > host_w:
                            max_portrait_height = min(900, client_max_h)
                            if host_h * ratio > max_portrait_height:
                                ratio = max_portrait_height / host_h
                        new_win_w = max(100, min(int(host_w * ratio), 3840))
                        new_win_h = max(100, min(int(host_h * ratio), 2160))
                        
                        if new_win_w != window_w or new_win_h != window_h:
                            window_w, window_h = new_win_w, new_win_h
                            screen = pygame.display.set_mode((window_w, window_h), pygame.RESIZABLE)
                            try:
                                hwnd = pygame.display.get_wm_info().get("window")
                                if hwnd and sys.platform == "win32":
                                    import ctypes.wintypes as _wt
                                    _rc = _wt.RECT()
                                    ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(_rc))
                                    outer_w = _rc.right - _rc.left
                                    outer_h = _rc.bottom - _rc.top
                                    pos_x = max(0, (client_desktop_w - outer_w) // 2)
                                    pos_y = max(0, (client_desktop_h - outer_h) // 2)
                                    # SWP_NOSIZE(0x0001) | SWP_NOZORDER(0x0004) | SWP_NOACTIVATE(0x0010)
                                    ctypes.windll.user32.SetWindowPos(hwnd, 0, pos_x, pos_y, 0, 0, 0x0001 | 0x0004 | 0x0010)
                            except Exception:
                                pass
                            if hwnd and clipboard_sync_manager:
                                clipboard_sync_manager.is_client = True
                                clipboard_sync_manager.pygame_hwnd = hwnd
                            send_event({"type": "resize_viewer", "w": window_w, "h": window_h})

                # Calculate floating button rectangle dynamically
                min_btn_w, min_btn_h = 40, 22
                mon_btn_w, mon_btn_h = 30, 22
                cad_btn_w, cad_btn_h = 145, 22
                eye_btn_w, eye_btn_h = 30, 22
                file_btn_w, file_btn_h = 110, 22
                power_btn_w, power_btn_h = 40, 22
                rec_btn_w, rec_btn_h = 30, 22
                close_btn_w, close_btn_h = 40, 22
                fold_btn_w, fold_btn_h = 28, 16
                
                is_switching = (globals().get('client_switching_desktop_countdown', 0) > 0)
                show_buttons = not is_switching
                show_toolbar = show_buttons and (not toolbar_collapsed)
                
                show_cad_button = show_buttons and not is_android
                show_file_button = show_buttons and is_android
                show_power_button = show_buttons and is_android
                tr_w, tr_h = client_true_remote_res if client_true_remote_res else (host_w, host_h)
                is_legacy_dual_fallback = (
                    (not is_android)
                    and (not client_host_sent_monitor_info)
                    and (tr_h > 0)
                    and ((tr_w / float(tr_h)) >= 2.0)
                )
                show_mon_buttons = show_buttons and (not is_android) and (client_host_monitor_count >= 2 or is_legacy_dual_fallback)
                
                host_os = globals().get('client_host_os_release', '10')
                is_host_windows = host_os in ["7", "8", "8.1", "10", "11", "XP", "Vista"] or "Server" in host_os
                if not is_host_windows:
                    cad_btn_w = 80
                
                # Hide privacy eye button if host is Windows 7 or 8.
                show_eye_button = show_cad_button and is_host_windows and (host_os not in ["7", "8", "8.1", "post2008Server", "post2012Server"])
                
                total_w = 0
                if show_toolbar:
                    total_w = (
                        min_btn_w + 10
                        + (mon_btn_w + 10 if show_mon_buttons else 0)
                        + (file_btn_w + 10 if show_file_button else 0)
                        + (power_btn_w + 10 if show_power_button else 0)
                        + (eye_btn_w + 10 if show_eye_button else 0)
                        + (cad_btn_w + 10 if show_cad_button else 0)
                        + rec_btn_w + 10
                        + (mon_btn_w + 10 if show_mon_buttons else 0)
                        + close_btn_w
                    )
                    
                start_x = (window_w - total_w) // 2
                
                if show_toolbar:
                    min_btn_rect = pygame.Rect(start_x, 0, min_btn_w, min_btn_h)
                    current_x = start_x + min_btn_w + 10

                    if show_mon_buttons:
                        mon_left_btn_rect = pygame.Rect(current_x, 0, mon_btn_w, mon_btn_h)
                        current_x += mon_btn_w + 10
                    else:
                        mon_left_btn_rect = pygame.Rect(-1000, -1000, 0, 0)
                    
                    if show_power_button:
                        power_btn_rect = pygame.Rect(current_x, 0, power_btn_w, power_btn_h)
                        current_x += power_btn_w + 10
                    else:
                        power_btn_rect = pygame.Rect(-1000, -1000, 0, 0)

                    if show_file_button:
                        file_btn_rect = pygame.Rect(current_x, 0, file_btn_w, file_btn_h)
                        current_x += file_btn_w + 10
                    else:
                        file_btn_rect = pygame.Rect(-1000, -1000, 0, 0)
                        
                    if show_eye_button:
                        eye_btn_rect = pygame.Rect(current_x, 0, eye_btn_w, eye_btn_h)
                        current_x += eye_btn_w + 10
                    else:
                        eye_btn_rect = pygame.Rect(-1000, -1000, 0, 0)
                        
                    if show_cad_button:
                        cad_btn_rect = pygame.Rect(current_x, 0, cad_btn_w, cad_btn_h)
                        current_x += cad_btn_w + 10
                    else:
                        cad_btn_rect = pygame.Rect(-1000, -1000, 0, 0)
                        
                    rec_btn_rect = pygame.Rect(current_x, 0, rec_btn_w, rec_btn_h)
                    current_x += rec_btn_w + 10

                    if show_mon_buttons:
                        mon_right_btn_rect = pygame.Rect(current_x, 0, mon_btn_w, mon_btn_h)
                        current_x += mon_btn_w + 10
                    else:
                        mon_right_btn_rect = pygame.Rect(-1000, -1000, 0, 0)

                    close_btn_rect = pygame.Rect(current_x, 0, close_btn_w, close_btn_h)
                    if show_cad_button:
                        fold_btn_rect = pygame.Rect(cad_btn_rect.centerx - fold_btn_w // 2, cad_btn_rect.bottom + 2, fold_btn_w, fold_btn_h)
                    else:
                        fold_btn_rect = pygame.Rect(start_x + max(total_w, fold_btn_w) // 2 - fold_btn_w // 2, min_btn_h + 2, fold_btn_w, fold_btn_h)
                else:
                    min_btn_rect = pygame.Rect(-1000, -1000, 0, 0) # Hidden
                    mon_left_btn_rect = pygame.Rect(-1000, -1000, 0, 0) # Hidden
                    file_btn_rect = pygame.Rect(-1000, -1000, 0, 0) # Hidden
                    power_btn_rect = pygame.Rect(-1000, -1000, 0, 0) # Hidden
                    eye_btn_rect = pygame.Rect(-1000, -1000, 0, 0) # Hidden
                    cad_btn_rect = pygame.Rect(-1000, -1000, 0, 0) # Hidden
                    rec_btn_rect = pygame.Rect(-1000, -1000, 0, 0) # Hidden
                    mon_right_btn_rect = pygame.Rect(-1000, -1000, 0, 0) # Hidden
                    close_btn_rect = pygame.Rect(-1000, -1000, 0, 0) # Hidden
                    if show_buttons:
                        fold_btn_rect = pygame.Rect((window_w - fold_btn_w) // 2, 0, fold_btn_w, fold_btn_h)
                    else:
                        fold_btn_rect = pygame.Rect(-1000, -1000, 0, 0)

                mx, my = pygame.mouse.get_pos()
                min_is_hover = min_btn_rect.collidepoint(mx, my) if show_toolbar else False
                mon_left_is_hover = mon_left_btn_rect.collidepoint(mx, my) if show_toolbar else False
                file_is_hover = file_btn_rect.collidepoint(mx, my) if show_toolbar else False
                power_is_hover = power_btn_rect.collidepoint(mx, my) if show_toolbar else False
                eye_is_hover = eye_btn_rect.collidepoint(mx, my) if show_toolbar else False
                cad_is_hover = cad_btn_rect.collidepoint(mx, my) if show_toolbar else False
                rec_is_hover = rec_btn_rect.collidepoint(mx, my) if show_toolbar else False
                mon_right_is_hover = mon_right_btn_rect.collidepoint(mx, my) if show_toolbar else False
                close_is_hover = close_btn_rect.collidepoint(mx, my) if show_toolbar else False
                fold_is_hover = fold_btn_rect.collidepoint(mx, my) if show_buttons else False
                def _calc_target_mouse_pos(mx_val, my_val):
                    rx_n = max(0.0, min(1.0, mx_val / max(1, window_w - 1))) if window_w > 1 else 0.0
                    ry_n = max(0.0, min(1.0, my_val / max(1, window_h - 1))) if window_h > 1 else 0.0
                    is_dual = (not is_android) and (client_host_monitor_count >= 2 or is_legacy_dual_fallback)
                    if is_dual:
                        m1_r, m2_r, fw, fh = _resolve_dual_monitor_subrects(
                            tr_w, tr_h,
                            monitors_meta=client_host_monitor_rects,
                            img_sample=client_latest_frame
                        )
                        if client_mon_left_on and not client_mon_right_on:
                            ox, oy, mw, mh = m1_r
                            hx = int(round(ox + rx_n * max(1, mw - 1)))
                            hy = int(round(oy + ry_n * max(1, mh - 1)))
                            rxs = hx / float(max(1, fw - 1))
                            rys = hy / float(max(1, fh - 1))
                        elif client_mon_right_on and not client_mon_left_on:
                            ox, oy, mw, mh = m2_r
                            hx = int(round(ox + rx_n * max(1, mw - 1)))
                            hy = int(round(oy + ry_n * max(1, mh - 1)))
                            rxs = hx / float(max(1, fw - 1))
                            rys = hy / float(max(1, fh - 1))
                        else:
                            hx = int(round(rx_n * max(1, fw - 1)))
                            hy = int(round(ry_n * max(1, fh - 1)))
                            rxs = rx_n
                            rys = ry_n
                    else:
                        rxs = rx_n
                        rys = ry_n
                        hx = int(mx_val * (host_w / window_w))
                        hy = int(my_val * (host_h / window_h))
                    return hx, hy, rxs, rys
                any_toolbar_hover = (
                    min_is_hover or mon_left_is_hover or file_is_hover or power_is_hover
                    or eye_is_hover or cad_is_hover or rec_is_hover or mon_right_is_hover
                    or close_is_hover or fold_is_hover
                )
     
                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        exit_due_to_disconnect = False
                        client_running = False
                        outer_running = False
                        break
                        
                    elif event.type == pygame.VIDEORESIZE:
                        window_w, window_h = event.w, event.h
                        screen = pygame.display.set_mode((window_w, window_h), pygame.RESIZABLE)
                        send_event({"type": "resize_viewer", "w": window_w, "h": window_h})
                        
                    elif event.type == pygame.MOUSEMOTION:
                        if show_buttons and (fold_btn_rect.collidepoint(event.pos) or (show_toolbar and (min_btn_rect.collidepoint(event.pos) or mon_left_btn_rect.collidepoint(event.pos) or file_btn_rect.collidepoint(event.pos) or power_btn_rect.collidepoint(event.pos) or eye_btn_rect.collidepoint(event.pos) or cad_btn_rect.collidepoint(event.pos) or rec_btn_rect.collidepoint(event.pos) or mon_right_btn_rect.collidepoint(event.pos) or close_btn_rect.collidepoint(event.pos)))):
                            continue
                        mx_pos, my_pos = event.pos
                        now_mono = time.monotonic()
                        if _warped_cursor_target is not None and now_mono < _warped_cursor_until:
                            if abs(mx_pos - _warped_cursor_target[0]) <= 3 and abs(my_pos - _warped_cursor_target[1]) <= 3:
                                _warped_cursor_target = None
                                continue
                        last_local_mouse_move_ts = now_mono
                        host_x, host_y, rx_send, ry_send = _calc_target_mouse_pos(mx_pos, my_pos)
                        if False:
                        ry_norm = max(0.0, min(1.0, my_pos / max(1, window_h - 1))) if window_h > 1 else 0.0
                        if is_legacy_dual_fallback:
                            if client_mon_left_on and not client_mon_right_on:
                                rx_send = rx_norm * 0.5
                            elif client_mon_right_on and not client_mon_left_on:
                                rx_send = 0.5 + rx_norm * 0.5
                            else:
                                rx_send = rx_norm
                            host_x = int(round(rx_send * max(1, tr_w - 1)))
                            host_y = int(round(ry_norm * max(1, tr_h - 1)))
                        else:
                            rx_send = rx_norm
                            host_x = int(mx_pos * (host_w / window_w))
                            host_y = int(my_pos * (host_h / window_h))
                        
                        if is_android and drag_start_pos is not None:
                            # Record drag path points for Android swipes/patterns
                            if not drag_path:
                                drag_path.append(drag_start_pos)
                            
                            last_pt = drag_path[-1]
                            # Record point if it moved at least 5 pixels (squared distance > 25) to avoid excessive points
                            if (host_x - last_pt[0])**2 + (host_y - last_pt[1])**2 > 25:
                                drag_path.append((host_x, host_y))
                        else:
                            send_event({"type": "mouse_move", "x": host_x, "y": host_y, "rx": round(rx_send, 6), "ry": round(ry_norm, 6)})
                        
                    elif event.type in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP):
                        if show_buttons and fold_btn_rect.collidepoint(event.pos):
                            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                                toolbar_collapsed = not toolbar_collapsed
                            continue
                        if show_toolbar and min_btn_rect.collidepoint(event.pos):
                            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                                print("[Client] Minimize Button Clicked. Minimizing viewer.")
                                pygame.display.iconify()
                            continue
                        if show_toolbar and show_mon_buttons and mon_left_btn_rect.collidepoint(event.pos):
                            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                                if client_mon_left_on:
                                    # Không cho phép tắt nếu màn hình bên phải cũng đang tắt
                                    if client_mon_right_on:
                                        client_mon_left_on = False
                                        send_event({"type": "set_monitors", "left": False, "right": True})
                                        _apply_monitor_selection(False, True)
                                else:
                                    client_mon_left_on = True
                                    send_event({"type": "set_monitors", "left": True, "right": bool(client_mon_right_on)})
                                    _apply_monitor_selection(True, bool(client_mon_right_on))
                            continue
                        if show_toolbar and file_btn_rect.collidepoint(event.pos):
                            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                                import utils.file_manager as fm
                                if hasattr(fm, 'fm_top') and fm.fm_top:
                                    try:
                                        if fm.fm_top.winfo_exists():
                                            def restore_fm():
                                                try:
                                                    fm.fm_top.deiconify()
                                                    fm.fm_top.attributes("-alpha", 1.0)
                                                except Exception:
                                                    pass
                                                try:
                                                    fm.fm_top.lift()
                                                    fm.fm_top.focus_force()
                                                except Exception:
                                                    pass
                                            fm.fm_top.after(0, restore_fm)
                                            continue
                                    except: pass

                                print("[Client] Transfer File Button Clicked.")
                                hwnd = pygame.display.get_wm_info().get("window")
                                comp_to_use = client_host_computer_name_override if client_host_computer_name_override else computer_name
                                threading.Thread(target=fm.open_transfer_window, args=(comp_to_use, is_android, send_event, hwnd, window_w, window_h), kwargs={"send_event_sync": send_event_sync}, daemon=True).start()
                            continue
                        if show_toolbar and power_btn_rect.collidepoint(event.pos):
                            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                                print("[Client] Power Button Clicked. Sending power key event to Android.")
                                send_event({"type": "key_event", "key": "power", "pressed": True})
                            continue
                        if show_toolbar and eye_btn_rect.collidepoint(event.pos):
                            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                                print("[Client] Eye Button Clicked. Sending toggle_screen_cover to host.")
                                state = globals().get('viewer_cover_state', False)
                                globals()['viewer_cover_state'] = not state
                                send_event({"type": "toggle_screen_cover"})
                            continue
                        if show_toolbar and cad_btn_rect.collidepoint(event.pos):
                            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                                is_host_win = globals().get('client_host_os_release', '10') in ["7", "8", "8.1", "10", "11", "XP", "Vista"] or "Server" in globals().get('client_host_os_release', '10')
                                if is_host_win:
                                    print("[Client] CAD Button Clicked. Sending trigger_sas to host.")
                                    send_event({"type": "trigger_sas"})
                                else:
                                    print("[Client] Terminal Button Clicked. Sending trigger_terminal to host.")
                                    send_event({"type": "trigger_terminal"})
                            continue
                        if show_toolbar and rec_btn_rect.collidepoint(event.pos):
                            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                                import cv2 as _cv2
                                import os as _os
                                import datetime as _datetime
                                state = globals().get('viewer_record_state', {'is_recording': False, 'writer': None})
                                
                                state['is_recording'] = not state['is_recording']
                                if state['is_recording']:
                                    print("[Client] Started recording viewer...")
                                    c_name = client_host_computer_name_override if client_host_computer_name_override else computer_name
                                    c_name = c_name if c_name else "host"
                                    # Replace invalid chars from computer name
                                    c_name = "".join([c if c.isalnum() else "_" for c in c_name])
                                    filename = f"{c_name}_{_datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.mp4"
                                    videos_dir = _os.path.join(_os.path.expanduser('~'), 'Videos')
                                    _os.makedirs(videos_dir, exist_ok=True)
                                    filepath = _os.path.join(videos_dir, filename)
                                    
                                    fourcc = _cv2.VideoWriter_fourcc(*'mp4v')
                                    state['writer'] = _cv2.VideoWriter(filepath, fourcc, 20.0, (host_w, host_h))
                                    state['size'] = (host_w, host_h)
                                else:
                                    print("[Client] Stopped recording viewer.")
                                    if state['writer']:
                                        state['writer'].release()
                                        state['writer'] = None
                                        
                                globals()['viewer_record_state'] = state
                            continue

                        if show_toolbar and show_mon_buttons and mon_right_btn_rect.collidepoint(event.pos):
                            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                                if client_mon_right_on:
                                    # Không cho phép tắt nếu màn hình bên trái cũng đang tắt
                                    if client_mon_left_on:
                                        client_mon_right_on = False
                                        send_event({"type": "set_monitors", "left": True, "right": False})
                                        _apply_monitor_selection(True, False)
                                else:
                                    client_mon_right_on = True
                                    send_event({"type": "set_monitors", "left": bool(client_mon_left_on), "right": True})
                                    _apply_monitor_selection(bool(client_mon_left_on), True)
                            continue
                        if show_toolbar and close_btn_rect.collidepoint(event.pos):
                            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                                print("[Client] Close Button Clicked. Exiting viewer.")
                                pygame.event.post(pygame.event.Event(pygame.QUIT))
                            continue
                        if event.button in button_map:
                            mx_pos, my_pos = event.pos
                            last_local_mouse_move_ts = time.monotonic()
                            host_x, host_y, rx_send, ry_send = _calc_target_mouse_pos(mx_pos, my_pos)
                        if False:
                            ry_norm = max(0.0, min(1.0, my_pos / max(1, window_h - 1))) if window_h > 1 else 0.0
                            if is_legacy_dual_fallback:
                                if client_mon_left_on and not client_mon_right_on:
                                    rx_send = rx_norm * 0.5
                                elif client_mon_right_on and not client_mon_left_on:
                                    rx_send = 0.5 + rx_norm * 0.5
                                else:
                                    rx_send = rx_norm
                                host_x = int(round(rx_send * max(1, tr_w - 1)))
                                host_y = int(round(ry_norm * max(1, tr_h - 1)))
                            else:
                                rx_send = rx_norm
                                host_x = int(mx_pos * (host_w / window_w))
                                host_y = int(my_pos * (host_h / window_h))
                            
                            if event.type == pygame.MOUSEBUTTONDOWN:
                                drag_start_pos = (host_x, host_y)
                                drag_start_time = time.time()
                                send_event({
                                    "type": "mouse_click",
                                    "button": button_map[event.button],
                                    "pressed": True,
                                    "x": host_x,
                                    "y": host_y,
                                    "rx": round(rx_send, 6),
                                    "ry": round(ry_norm, 6),
                                })
                            else: # MOUSEBUTTONUP
                                if drag_start_pos and is_android:
                                    dx = host_x - drag_start_pos[0]
                                    dy = host_y - drag_start_pos[1]
                                    if (dx*dx + dy*dy) > 400 or len(drag_path) > 3: # distance > 20 pixels or multi-point path
                                        duration = int((time.time() - drag_start_time) * 1000)
                                        duration = max(200, min(duration, 3000))
                                        
                                        if drag_path and drag_path[-1] != (host_x, host_y):
                                            drag_path.append((host_x, host_y))
                                            
                                        if len(drag_path) > 3:
                                            # Subsample if too many points to avoid massive payloads
                                            if len(drag_path) > 50:
                                                step = len(drag_path) / 50.0
                                                subsampled_path = [drag_path[int(i*step)] for i in range(50)]
                                                if subsampled_path[-1] != drag_path[-1]:
                                                    subsampled_path.append(drag_path[-1])
                                                drag_path = subsampled_path
                                                
                                            send_event({
                                                "type": "mouse_swipe_path",
                                                "path": drag_path,
                                                "duration": duration
                                            })
                                        else:
                                            send_event({
                                                "type": "mouse_swipe",
                                                "x1": drag_start_pos[0],
                                                "y1": drag_start_pos[1],
                                                "x2": host_x,
                                                "y2": host_y,
                                                "duration": duration
                                            })
                                        drag_start_pos = None
                                        drag_path = []
                                        continue
                                        
                                send_event({
                                    "type": "mouse_click",
                                    "button": button_map[event.button],
                                    "pressed": False,
                                    "x": host_x,
                                    "y": host_y,
                                    "rx": round(rx_send, 6),
                                    "ry": round(ry_norm, 6),
                                })
                                drag_start_pos = None
                                drag_path = []
                            
                    elif event.type == pygame.MOUSEWHEEL:
                        send_event({"type": "mouse_scroll", "dx": event.x, "dy": event.y})
                        
                    elif event.type in (pygame.KEYDOWN, pygame.KEYUP):
                        key_name = pygame_key_canonical_name(event)
                        
                        char_to_send = key_name
                        if event.type == pygame.KEYDOWN:
                            if is_android:
                                # Handle Ctrl+V (Paste) directly by fetching PC clipboard and sending paste_text
                                if event.key == pygame.K_v and (pygame.key.get_mods() & pygame.KMOD_CTRL):
                                    try:
                                        clip_text = get_clipboard_text()
                                        if clip_text:
                                            send_event({
                                                "type": "paste_text",
                                                "text": clip_text
                                            })
                                    except Exception as e:
                                        print(f"[Client] Lỗi paste Ctrl+V: {e}")
                                    continue
                                    
                                # For Android, we inject characters directly into text fields using Accessibility.
                                # Therefore, we MUST use event.unicode to capture Shift modifications (e.g. 'A' instead of 'a').
                                # We also map special keys to their string equivalents.
                                if hasattr(event, 'unicode'):
                                    print(f"[DEBUG KEY] name='{key_name}', unicode='{event.unicode}', mod={event.mod}")
                                    
                                if key_name == "space":
                                    char_to_send = " "
                                elif key_name == "tab":
                                    char_to_send = "tab"
                                elif key_name == "return" or key_name == "enter":
                                    char_to_send = "enter" # handled by Android handleKey
                                elif key_name == "backspace":
                                    char_to_send = "backspace"
                                elif hasattr(event, 'unicode') and event.unicode and len(event.unicode) > 0 and ord(event.unicode[0]) >= 32:
                                    char_to_send = event.unicode
                                else:
                                    if key_name in ["escape", "home", "menu", "volume up", "volume down", "delete", "up", "down", "left", "right"]:
                                        char_to_send = key_name
                                    else:
                                        active_unicode_map[event.key] = ""
                                        continue
                            else:
                                # Host Windows/Linux: luôn gửi phím vật lý (104-key).
                                # Không dùng event.unicode — keypad * unicode '*' bị VkKeyScan thành 8.
                                char_to_send = key_name
                            
                            active_unicode_map[event.key] = char_to_send
                        else:
                            char_to_send = active_unicode_map.get(event.key, key_name)
                            if event.key in active_unicode_map:
                                del active_unicode_map[event.key]
                                
                        send_event({
                            "type": "key_event",
                            "key": char_to_send,
                            "pressed": event.type == pygame.KEYDOWN
                        })
                        
                # Draw frame
                with client_frame_lock:
                    frame_to_draw = client_latest_frame

                # Chỉ xin frame mới khi đã chờ lâu — request_full_frame trên Android
                # xóa JPEG cache, màn đứng im phải đợi VirtualDisplay tạo frame mới.
                if is_android and frame_to_draw is None and android_full_frame_tries < 2:
                    now_req = time.time()
                    if now_req - last_full_frame_req >= 4.0:
                        send_event({"type": "request_full_frame"})
                        last_full_frame_req = now_req
                        android_full_frame_tries += 1
                    
                if frame_to_draw is not None:
                    try:
                        frame_to_draw = _pil_to_rgb(frame_to_draw)
                        raw_w, raw_h = frame_to_draw.size
                        if raw_w <= 0 or raw_h <= 0:
                            raise ValueError("empty frame size")
                        if (not is_android) and (not client_host_sent_monitor_info) and ((raw_w / float(raw_h)) >= 2.25):
                            cur_tr = client_true_remote_res
                            if cur_tr is None or cur_tr[1] <= 0 or (cur_tr[0] / float(cur_tr[1])) < 2.25:
                                client_true_remote_res = (raw_w, raw_h)
                            if client_mon_left_on and not client_mon_right_on:
                                frame_to_draw = frame_to_draw.crop((0, 0, max(1, raw_w // 2), raw_h))
                            elif client_mon_right_on and not client_mon_left_on:
                                frame_to_draw = frame_to_draw.crop((raw_w // 2, 0, raw_w, raw_h))
                        w, h = frame_to_draw.size
                        if (w != host_w or h != host_h) and w > 100 and h > 100:
                            client_host_resolution = (w, h)
                        surf = pygame.image.fromstring(frame_to_draw.tobytes(), (w, h), 'RGB')
                        if w == window_w and h == window_h:
                            scaled_surf = surf
                        elif w >= window_w and h >= window_h:
                            scaled_surf = pygame.transform.smoothscale(surf, (window_w, window_h))
                        else:
                            scaled_surf = pygame.transform.scale(surf, (window_w, window_h))
                        screen.blit(scaled_surf, (0, 0))
                    except Exception as blit_err:
                        print(f"[Client] Blit error: {blit_err}")
                        frame_to_draw = None

                if frame_to_draw is not None:
                    
                    state = globals().get('viewer_record_state', {'is_recording': False, 'writer': None})
                    if state['is_recording'] and state['writer']:
                        try:
                            import cv2 as _cv2
                            import numpy as _np
                            frame_arr = _np.array(frame_to_draw)
                            bgr_frame = _cv2.cvtColor(frame_arr, _cv2.COLOR_RGB2BGR)
                            
                            record_size = state.get('size', (host_w, host_h))
                            if bgr_frame.shape[1] != record_size[0] or bgr_frame.shape[0] != record_size[1]:
                                bgr_frame = _cv2.resize(bgr_frame, record_size)
                            
                            # Draw beautiful anti-aliased mouse cursor overlay for recording
                            mx, my = pygame.mouse.get_pos()
                            if pygame.mouse.get_focused() and 0 <= mx <= window_w and 0 <= my <= window_h:
                                hx = int(mx * (w / window_w)) if window_w else 0
                                hy = int(my * (h / window_h)) if window_h else 0
                                pts = _np.array([
                                    [hx, hy], [hx, hy + 17], [hx + 4, hy + 13],
                                    [hx + 9, hy + 23], [hx + 12, hy + 21],
                                    [hx + 7, hy + 11], [hx + 14, hy + 11]
                                ], _np.int32)
                                _cv2.fillPoly(bgr_frame, [pts], (255, 255, 255), lineType=_cv2.LINE_AA)
                                _cv2.polylines(bgr_frame, [pts], True, (0, 0, 0), 1, lineType=_cv2.LINE_AA)
                                
                            state['writer'].write(bgr_frame)
                        except Exception as e:
                            print(f"[Client] Recording error: {e}")
                else:
                    if is_android:
                        screen.fill((30, 30, 30))
                        try:
                            wait_font = pygame.font.SysFont(font_names, 22, bold=True)
                        except Exception:
                            wait_font = pygame.font.Font(None, 28)
                        wait_surf = wait_font.render(_("Đang nhận màn hình máy Android..."), True, (220, 220, 220))
                        wait_rect = wait_surf.get_rect(center=(window_w // 2, window_h // 2))
                        screen.blit(wait_surf, wait_rect)
                    else:
                        if pygame_theme == "light":
                            screen.fill((240, 240, 245))
                            text_col = (110, 115, 125)
                        elif pygame_theme == "gray":
                            screen.fill((82, 89, 98))
                            text_col = (220, 220, 225)
                        elif pygame_theme == "pink":
                            screen.fill((255, 240, 245))
                            text_col = (150, 100, 120)
                        elif pygame_theme == "crystal":
                            screen.fill((224, 247, 250))
                            text_col = (80, 120, 130)
                        elif pygame_theme == "orange":
                            screen.fill((255, 243, 224))
                            text_col = (150, 110, 70)
                        elif pygame_theme == "red":
                            screen.fill((255, 235, 238))
                            text_col = (150, 90, 100)
                        else:
                            screen.fill((30, 30, 30))
                            text_col = (200, 200, 200)
                        try:
                            wait_font = pygame.font.SysFont(font_names, 20, bold=True)
                        except Exception:
                            wait_font = pygame.font.Font(None, 24)
                        wait_surf = wait_font.render(_("Đang kết nối / Đang chờ màn hình từ máy chủ..."), True, text_col)
                        wait_rect = wait_surf.get_rect(center=(window_w // 2, window_h // 2))
                        screen.blit(wait_surf, wait_rect)
                    
                # Draw red border if blinking (focus requested)
                if blink_frames_remaining > 0:
                    if (blink_frames_remaining // 15) % 2 == 0:
                        border_rect = pygame.Rect(0, 0, window_w, window_h)
                        pygame.draw.rect(screen, (255, 0, 0), border_rect, width=10)
                    blink_frames_remaining -= 1
                    
                # Đồng bộ vị trí chuột của Host lên cửa sổ Viewer
                if not is_android and frame_to_draw is not None:
                    with client_host_cursor_lock:
                        cur_seq = client_host_cursor_data.get("seq", 0)
                        cur_vis = bool(client_host_cursor_data.get("visible", False))
                        cur_rx = float(client_host_cursor_data.get("rx", 0.5))
                        cur_ry = float(client_host_cursor_data.get("ry", 0.5))
                    if cur_vis and window_w > 1 and window_h > 1:
                        vx = max(0, min(window_w - 1, int(round(cur_rx * (window_w - 1)))))
                        vy = max(0, min(window_h - 1, int(round(cur_ry * (window_h - 1)))))
                        if pygame.mouse.get_focused():
                            if cur_seq != last_applied_cursor_seq:
                                last_applied_cursor_seq = cur_seq
                                now_m = time.monotonic()
                                if (
                                    (not any_toolbar_hover)
                                    and (not any(pygame.mouse.get_pressed()))
                                    and (now_m - last_local_mouse_move_ts >= 0.15)
                                ):
                                    cur_mx, cur_my = pygame.mouse.get_pos()
                                    if abs(cur_mx - vx) > 1 or abs(cur_my - vy) > 1:
                                        _warped_cursor_target = (vx, vy)
                                        _warped_cursor_until = now_m + 0.12
                                        try:
                                            pygame.mouse.set_pos((vx, vy))
                                        except Exception:
                                            pass
                        else:
                            last_applied_cursor_seq = cur_seq
                            _draw_host_cursor_overlay(screen, vx, vy)

                # Draw floating buttons on top
                if show_toolbar:
                    # Minimize button
                    min_bg_color = (51, 153, 255) if min_is_hover else (0, 102, 204)
                    min_border_color = (255, 255, 255)
                    pygame.draw.rect(screen, min_bg_color, min_btn_rect, border_radius=4)
                    pygame.draw.rect(screen, min_border_color, min_btn_rect, width=1, border_radius=4)
                    
                    min_text_surf = btn_font.render("_", True, (255, 255, 255))
                    min_text_rect = min_text_surf.get_rect(center=min_btn_rect.center)
                    min_text_rect.y -= 2 # Adjust slightly up to center visually
                    screen.blit(min_text_surf, min_text_rect)

                    # Extract common border color for buttons
                    if pygame_theme == "light":
                        btn_border_color = (0, 173, 181)
                    elif pygame_theme == "gray":
                        btn_border_color = (0, 173, 181)
                    elif pygame_theme == "pink":
                        btn_border_color = (255, 105, 180)
                    elif pygame_theme == "crystal":
                        btn_border_color = (128, 222, 234)
                    elif pygame_theme == "orange":
                        btn_border_color = (255, 167, 38)
                    elif pygame_theme == "red":
                        btn_border_color = (229, 57, 53)
                    else:
                        btn_border_color = (0, 173, 181)

                    # Left Monitor toggle button (🖥️ kế bên phải nút Minimize)
                    if show_mon_buttons:
                        _draw_monitor_toggle_btn(screen, mon_left_btn_rect, client_mon_left_on, mon_left_is_hover, btn_border_color, pygame_theme)

                    # CAD / File buttons
                    if show_cad_button or show_file_button:
                        if pygame_theme == "light":
                            cad_bg_color = (220, 220, 235) if cad_is_hover else (245, 245, 255)
                            file_bg_color = (220, 220, 235) if file_is_hover else (245, 245, 255)
                            cad_text_color = (40, 40, 50)
                            file_text_color = (40, 40, 50)
                        elif pygame_theme == "gray":
                            cad_bg_color = (99, 106, 115) if cad_is_hover else (82, 89, 98)
                            file_bg_color = (99, 106, 115) if file_is_hover else (82, 89, 98)
                            cad_text_color = (240, 240, 240)
                            file_text_color = (240, 240, 240)
                        elif pygame_theme == "pink":
                            cad_bg_color = (255, 105, 180) if cad_is_hover else (255, 182, 193)
                            file_bg_color = (255, 105, 180) if file_is_hover else (255, 182, 193)
                            cad_text_color = (255, 255, 255)
                            file_text_color = (255, 255, 255)
                        elif pygame_theme == "crystal":
                            cad_bg_color = (38, 198, 218) if cad_is_hover else (0, 188, 212)
                            file_bg_color = (38, 198, 218) if file_is_hover else (0, 188, 212)
                            cad_text_color = (255, 255, 255)
                            file_text_color = (255, 255, 255)
                        elif pygame_theme == "orange":
                            cad_bg_color = (255, 183, 77) if cad_is_hover else (255, 152, 0)
                            file_bg_color = (255, 183, 77) if file_is_hover else (255, 152, 0)
                            cad_text_color = (255, 255, 255)
                            file_text_color = (255, 255, 255)
                        elif pygame_theme == "red":
                            cad_bg_color = (239, 154, 154) if cad_is_hover else (244, 67, 54)
                            file_bg_color = (239, 154, 154) if file_is_hover else (244, 67, 54)
                            cad_text_color = (255, 255, 255)
                            file_text_color = (255, 255, 255)
                        else:
                            cad_bg_color = (58, 58, 77) if cad_is_hover else (42, 42, 53)
                            file_bg_color = (58, 58, 77) if file_is_hover else (42, 42, 53)
                            cad_text_color = (255, 255, 255)
                            file_text_color = (255, 255, 255)
                        
                        if show_file_button:
                            pygame.draw.rect(screen, file_bg_color, file_btn_rect, border_radius=4)
                            pygame.draw.rect(screen, btn_border_color, file_btn_rect, width=1, border_radius=4)
                            
                            file_text_surf = btn_font.render(_("Chuyển tệp"), True, file_text_color)
                            file_text_rect = file_text_surf.get_rect(center=file_btn_rect.center)
                            screen.blit(file_text_surf, file_text_rect)

                        if show_power_button:
                            import math
                            cx, cy = power_btn_rect.center
                            
                            # Nền nút hình chữ nhật xám giống nút quay video
                            power_bg_color = (80, 80, 80) if power_is_hover else (50, 50, 50)
                            if pygame_theme in ["light", "crystal", "orange", "red"]:
                                power_bg_color = (220, 220, 235) if power_is_hover else (245, 245, 255)
                            pygame.draw.rect(screen, power_bg_color, power_btn_rect, border_radius=4)
                            pygame.draw.rect(screen, btn_border_color, power_btn_rect, width=1, border_radius=4)

                            # Nền hình tròn xanh lá như hình đính kèm
                            bg_color = (40, 190, 80) if power_is_hover else (30, 170, 70)
                            pygame.draw.circle(screen, bg_color, (cx, cy), 10)
                            pygame.draw.circle(screen, btn_border_color, (cx, cy), 10, 1)

                            # Icon Power màu trắng, nét đơn (1px)
                            r = 5
                            # Vòng cung khuyết ở trên
                            pygame.draw.arc(screen, (255, 255, 255), (cx - r, cy - r, r * 2, r * 2), math.pi/2 + 0.65, 2.5 * math.pi - 0.65, 1)
                            # Dấu | ở giữa (nét đơn)
                            pygame.draw.line(screen, (255, 255, 255), (cx, cy - r - 1), (cx, cy + 1), 1)

                        if show_cad_button:
                            # Draw Eye Button
                            eye_bg = (100, 100, 100) if globals().get('viewer_cover_state', False) else cad_bg_color
                            if eye_is_hover and not globals().get('viewer_cover_state', False):
                                pass # cad_bg_color already has hover color assigned
                            elif eye_is_hover:
                                eye_bg = (130, 130, 130)
                            
                            pygame.draw.rect(screen, eye_bg, eye_btn_rect, border_radius=4)
                            pygame.draw.rect(screen, btn_border_color, eye_btn_rect, width=1, border_radius=4)
                            
                            eye_icon_rect = pygame.Rect(0, 0, 16, 10)
                            eye_icon_rect.center = eye_btn_rect.center
                            pygame.draw.ellipse(screen, cad_text_color, eye_icon_rect, width=1)
                            pygame.draw.circle(screen, cad_text_color, eye_icon_rect.center, 3)

                            # Draw CAD Button
                            pygame.draw.rect(screen, cad_bg_color, cad_btn_rect, border_radius=4)
                            pygame.draw.rect(screen, btn_border_color, cad_btn_rect, width=1, border_radius=4)
                            
                            is_host_win = globals().get('client_host_os_release', '10') in ["7", "8", "8.1", "10", "11", "XP", "Vista"] or "Server" in globals().get('client_host_os_release', '10')
                            cad_text_str = "Ctrl + Alt + Delete" if is_host_win else "Terminal"
                            cad_text_surf = btn_font.render(cad_text_str, True, cad_text_color)
                            cad_text_rect = cad_text_surf.get_rect(center=cad_btn_rect.center)
                            screen.blit(cad_text_surf, cad_text_rect)
                    
                    # Record button (Red circle)
                    state = globals().get('viewer_record_state', {'is_recording': False, 'writer': None})
                    rec_bg_color = (80, 80, 80) if rec_is_hover else (50, 50, 50)
                    if pygame_theme in ["light", "crystal", "orange", "red"]:
                        rec_bg_color = (220, 220, 235) if rec_is_hover else (245, 245, 255)
                    
                    pygame.draw.rect(screen, rec_bg_color, rec_btn_rect, border_radius=4)
                    pygame.draw.rect(screen, btn_border_color, rec_btn_rect, width=1, border_radius=4)
                    
                    if state['is_recording']:
                        pygame.draw.rect(screen, (255, 0, 0), pygame.Rect(rec_btn_rect.centerx - 4, rec_btn_rect.centery - 4, 8, 8))
                    else:
                        pygame.draw.circle(screen, (255, 0, 0), rec_btn_rect.center, 5)
                        
                    if state['is_recording']:
                        import time as _time
                        if int(_time.time() * 2) % 2 == 0:
                            # Make the icon dim to simulate blinking
                            dim_surf = pygame.Surface(rec_btn_rect.size, pygame.SRCALPHA)
                            dim_surf.fill((0, 0, 0, 128))
                            screen.blit(dim_surf, rec_btn_rect.topleft)

                    # Right Monitor toggle button (🖥️ kế bên trái nút Close X)
                    if show_mon_buttons:
                        _draw_monitor_toggle_btn(screen, mon_right_btn_rect, client_mon_right_on, mon_right_is_hover, btn_border_color, pygame_theme)

                    # Close button (Red X)
                    close_bg_color = (255, 77, 77) if close_is_hover else (204, 0, 0)
                    close_border_color = (255, 255, 255)
                    pygame.draw.rect(screen, close_bg_color, close_btn_rect, border_radius=4)
                    pygame.draw.rect(screen, close_border_color, close_btn_rect, width=1, border_radius=4)
                    
                    close_text_surf = btn_font.render("X", True, (255, 255, 255))
                    close_text_rect = close_text_surf.get_rect(center=close_btn_rect.center)
                    screen.blit(close_text_surf, close_text_rect)

                if show_buttons:
                    if pygame_theme == "light":
                        fold_border = (0, 173, 181)
                        fold_bg = (220, 220, 235) if fold_is_hover else (245, 245, 255)
                        fold_fg = (40, 40, 50)
                    elif pygame_theme == "gray":
                        fold_border = (0, 173, 181)
                        fold_bg = (99, 106, 115) if fold_is_hover else (82, 89, 98)
                        fold_fg = (240, 240, 240)
                    elif pygame_theme == "pink":
                        fold_border = (255, 105, 180)
                        fold_bg = (255, 105, 180) if fold_is_hover else (255, 182, 193)
                        fold_fg = (255, 255, 255)
                    elif pygame_theme == "crystal":
                        fold_border = (128, 222, 234)
                        fold_bg = (38, 198, 218) if fold_is_hover else (0, 188, 212)
                        fold_fg = (255, 255, 255)
                    elif pygame_theme == "orange":
                        fold_border = (255, 167, 38)
                        fold_bg = (255, 183, 77) if fold_is_hover else (255, 152, 0)
                        fold_fg = (255, 255, 255)
                    elif pygame_theme == "red":
                        fold_border = (229, 57, 53)
                        fold_bg = (239, 154, 154) if fold_is_hover else (244, 67, 54)
                        fold_fg = (255, 255, 255)
                    else:
                        fold_border = (0, 173, 181)
                        fold_bg = (58, 58, 77) if fold_is_hover else (42, 42, 53)
                        fold_fg = (255, 255, 255)
                    pygame.draw.rect(screen, fold_bg, fold_btn_rect, border_radius=4)
                    pygame.draw.rect(screen, fold_border, fold_btn_rect, width=1, border_radius=4)
                    cx, cy = fold_btn_rect.center
                    tw, th = 8, 5
                    if toolbar_collapsed:
                        fold_pts = [(cx - tw // 2, cy - th // 2), (cx + tw // 2, cy - th // 2), (cx, cy + th // 2)]
                    else:
                        fold_pts = [(cx, cy - th // 2), (cx - tw // 2, cy + th // 2), (cx + tw // 2, cy + th // 2)]
                    pygame.draw.polygon(screen, fold_fg, fold_pts)
                    
                current_countdown = globals().get('client_switching_desktop_countdown', 0)
                if current_countdown > 0:
                    if not was_switching:
                        was_switching = True
                        switching_last_tick = pygame.time.get_ticks()
                        switching_start_tick = pygame.time.get_ticks()
                    
                    # Có khung hình thật (logon/sign-out) thì không che overlay chữ.
                    has_live_frame = False
                    try:
                        with client_frame_lock:
                            has_live_frame = client_latest_frame is not None
                    except Exception:
                        pass
                    if not has_live_frame:
                        if "msg_font" not in locals():
                            try: msg_font = pygame.font.SysFont(font_names, 24, bold=True)
                            except: msg_font = pygame.font.Font(None, 32)
                        
                        overlay = pygame.Surface((window_w, window_h))
                        overlay.set_alpha(150)
                        overlay.fill((0, 0, 0))
                        screen.blit(overlay, (0, 0))
                        
                        elapsed_switching = pygame.time.get_ticks() - switching_start_tick
                        if globals().get('client_is_locked', False):
                            text_msg = _("Đang đăng nhập...")
                        elif elapsed_switching > 3000:
                            text_msg = _("Màn hình bảo mật (UAC / Lock Screen) đang hiển thị ở máy Host...")
                        else:
                            text_msg = _("Đang chuyển giao diện... Vui lòng đợi ") + str(current_countdown) + _(" giây...")
                        
                        text_surf = msg_font.render(text_msg, True, (255, 255, 255))
                        text_rect = text_surf.get_rect(center=(window_w//2, window_h//2))
                        screen.blit(text_surf, text_rect)
                    
                    current_tick = pygame.time.get_ticks()
                    if current_tick - switching_last_tick >= 1000:
                        client_switching_desktop_countdown = max(0, current_countdown - 1)
                        switching_last_tick = current_tick
                        if client_switching_desktop_countdown == 0:
                            was_switching = False
                            send_event({"type": "check_domain"})
                elif was_switching:
                    was_switching = False
                    send_event({"type": "check_domain"})
                
                effective_ping = ping_limit
                if current_countdown > 0 or globals().get('client_is_locked', False):
                    effective_ping = max(ping_limit, 45.0)
                if client_last_recv_time > 0 and time.time() - client_last_recv_time > effective_ping:
                    print("[Client] Connection ping timeout. Disconnecting.")
                    if _non_windows_close_is_shutdown():
                        print("[Client] Non-Windows host ping timeout. Treating as host shutdown.")
                        client_host_did_shutdown = True
                    exit_due_to_disconnect = True
                    client_running = False
                    break

                pygame.display.flip()
                clock.tick(60)
                
            if client_host_did_shutdown:
                exit_due_to_disconnect = False
                outer_running = False

            uninstall_keyboard_hook()
            
            state = globals().get('viewer_record_state', {'is_recording': False, 'writer': None})
            if state['writer']:
                state['writer'].release()
                state['writer'] = None
                state['is_recording'] = False
                globals()['viewer_record_state'] = state
            
            if exit_due_to_disconnect and not client_host_did_shutdown and reconnect_queue:
                countdown = 60
                last_tick = pygame.time.get_ticks()
                try: msg_font = pygame.font.SysFont(font_names, 24, bold=True)
                except: msg_font = pygame.font.Font(None, 32)
                try: title_font = pygame.font.SysFont(font_names, 32, bold=True)
                except: title_font = msg_font
                
                last_switch_age = time.time() - float(globals().get('client_last_switching_desktop_time', 0) or 0)
                # Chi coi la handoff khi dang lock/doi desktop — KHONG coi moi host Windows
                # la handoff (neu khong se an "Mất kết nối..." khi dut mang that).
                session_handoff = bool(
                    globals().get('client_is_locked', False)
                    or was_switching
                    or globals().get('client_switching_desktop_countdown', 0) > 0
                    or (0 < last_switch_age < 12)
                )
                frozen_img = None
                try:
                    with client_frame_lock:
                        if client_latest_frame is not None:
                            frozen_img = client_latest_frame.copy()
                except Exception:
                    frozen_img = None
                
                # Flush toàn bộ các message cũ còn tồn đọng trong reconnect_queue
                try:
                    while not reconnect_queue.empty():
                        reconnect_queue.get_nowait()
                except Exception:
                    pass

                req_msg = "RECONNECT_REQUEST|LOGIN" if session_handoff else "RECONNECT_REQUEST|DROP"
                print(f"[Client] Disconnected. Requesting reconnect in background ({req_msg})...")
                # Gửi yêu cầu reconnect vào cmd_queue (kênh chuyên dụng lên App chính)
                if cmd_queue:
                    try: cmd_queue.put(req_msg)
                    except Exception as e: print(f"[Client] Failed to put to cmd_queue: {e}")
                if reconnect_queue:
                    try: reconnect_queue.put(req_msg)
                    except: pass
                
                status_msg_text = _("Đang thử kết nối lại (lần {x}/10)...").format(x=1)
                
                while countdown > 0 and outer_running:
                    for event in pygame.event.get():
                        if event.type == pygame.QUIT:
                            countdown = 0
                            exit_due_to_disconnect = False
                            outer_running = False
                    
                    if not outer_running:
                        break
                        
                    sock_acquired = False
                    try:
                        while True:
                            new_sock = reconnect_queue.get_nowait()
                            if isinstance(new_sock, str) and new_sock.startswith("RECONNECT_REQUEST"):
                                # Viewer lỡ lấy được RECONNECT_REQUEST, trả lại ngay để App chính đọc!
                                if cmd_queue:
                                    try: cmd_queue.put(new_sock)
                                    except: pass
                                else:
                                    try: reconnect_queue.put(new_sock)
                                    except: pass
                                time.sleep(0.05)
                                continue
                            elif isinstance(new_sock, str) and new_sock.startswith("STATUS|"):
                                new_status = new_sock.split("|", 1)[1]
                                if "Đang thử kết nối lại" in new_status or _("Đang thử kết nối lại") in new_status or "lần " in new_status:
                                    status_msg_text = new_status
                                elif not status_msg_text:
                                    status_msg_text = new_status
                                continue
                            elif isinstance(new_sock, str) and (new_sock == "FAILED" or new_sock.startswith("FAILED|")):
                                fail_reason = new_sock.split("|", 1)[1] if "|" in new_sock else ""
                                if fail_reason:
                                    status_msg_text = fail_reason
                                continue
                            elif isinstance(new_sock, tuple) and new_sock[0] in ("SHARED_SOCK", "CONNECTED"):
                                print("[Client] Received shared socket. Resuming session!")
                                if new_sock[0] == "SHARED_SOCK":
                                    sock = socket.fromshare(new_sock[1])
                                else:
                                    sock_item = new_sock[1]
                                    if isinstance(sock_item, tuple) and sock_item[0] == "SHARED_SOCK":
                                        sock = socket.fromshare(sock_item[1])
                                    elif hasattr(sock_item, 'fileno'):
                                        sock = sock_item
                                    if len(new_sock) > 3 and new_sock[2] and new_sock[3]:
                                        host_w, host_h = int(new_sock[2]), int(new_sock[3])
                                ensure_session_socket_blocking(sock)
                                if partner_pass:
                                    socket_passwords[sock] = partner_pass
                                sock_acquired = True
                                break # Break inner wait loop
                            elif hasattr(new_sock, 'fileno'):
                                print("[Client] Received new socket. Resuming session!")
                                sock = new_sock
                                if partner_pass:
                                    socket_passwords[sock] = partner_pass
                                sock_acquired = True
                                break # Break inner wait loop
                    except Exception as re_err:
                        pass # Ignore queue.Empty
                        
                    if not outer_running or sock_acquired:
                        break
                    
                    if session_handoff and frozen_img is not None:
                        _blit_pil_to_screen(screen, frozen_img, window_w, window_h)
                        overlay = pygame.Surface((window_w, window_h))
                        overlay.set_alpha(170)
                        overlay.fill((20, 20, 20))
                        screen.blit(overlay, (0, 0))
                    else:
                        screen.fill((30, 30, 30))

                    title = _("Mất kết nối.")
                    title_surf = title_font.render(title, True, (255, 80, 80))
                    title_rect = title_surf.get_rect(center=(window_w//2, window_h//2 - 36))
                    screen.blit(title_surf, title_rect)

                    if status_msg_text:
                        detail = str(status_msg_text)
                    else:
                        detail = ""
                    if detail:
                        detail_surf = msg_font.render(detail, True, (255, 255, 255))
                        detail_rect = detail_surf.get_rect(center=(window_w//2, window_h//2 + 8))
                        screen.blit(detail_surf, detail_rect)

                    cd_surf = msg_font.render(_("Thời gian chờ: ") + str(countdown) + _(" giây"), True, (180, 180, 180))
                    cd_rect = cd_surf.get_rect(center=(window_w//2, window_h//2 + 44))
                    screen.blit(cd_surf, cd_rect)
                        
                    pygame.display.flip()
                    
                    current_tick = pygame.time.get_ticks()
                    if current_tick - last_tick >= 1000:
                        countdown -= 1
                        last_tick = current_tick
                        
                    clock.tick(30)
                    
                if outer_running and countdown == 0:
                    print("[Client] Reconnect timeout. Closing window.")
                    outer_running = False
                    
                if outer_running:
                    continue # Jump back to the start of the outer_running loop!
                    
            # If we reach here, we are truly exiting
            outer_running = False
            
        uninstall_keyboard_hook()
        # pygame.quit() # Bỏ qua để tránh deadlock SetParent với Tkinter thread
        if clipboard_sync_manager and sock:
            try:
                clipboard_sync_manager.remove_socket(sock)
            except Exception:
                pass
        try: log_activity(_("Ngừng điều khiển ID ") + str(partner_id) + " (" + str(computer_name) + ")")
        except: pass
        import os
        if client_host_did_shutdown:
            print("[Client] Viewer closed because host shutdown/restart.")
            os._exit(0)
        if exit_due_to_disconnect:
            print("[Client] Viewer exited due to disconnect. Exit code 99.")
            os._exit(99)
        os._exit(0)
    except Exception as critical_e:
        uninstall_keyboard_hook()
        import traceback
        with open("client_crash.log", "w", encoding="utf-8-sig") as f:
            f.write(f"CRITICAL ERROR IN VIEWER LOOP:\n{traceback.format_exc()}\n")
        # try: pygame.quit()
        # except: pass
        import os
        if client_host_did_shutdown:
            os._exit(0)
        if exit_due_to_disconnect:
            os._exit(99)
        os._exit(1)

