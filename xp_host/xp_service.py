# -*- coding: utf-8 -*-
"""
xp_host/xp_service.py
Quản lý Windows Service thuần Win32 API (advapi32.dll ctypes) cho Windows XP SP2/SP3:
  - Không phụ thuộc pythonservice.exe của pywin32 (tránh lỗi thiếu MSVCR manifest trên XP).
  - Đăng ký với cờ SERVICE_WIN32_OWN_PROCESS | SERVICE_INTERACTIVE_PROCESS (0x110) để chạy
    ở Session 0 có toàn quyền truy cập cả màn hình đăng nhập XP (Winlogon) lẫn Desktop (Default).
  - Mở cổng cục bộ 127.0.0.1:12405 để giao diện Tray/GUI của người dùng đồng bộ trạng thái,
    đổi mật khẩu và cấu hình Signaling tức thời mà không tranh chấp cổng 12345.
  - Cấu hình Firewall XP qua Registry chuẩn (không gọi PowerShell hay cmd.exe trung gian).
"""

import ctypes
from ctypes import wintypes
import json
import os
import socket
import sys
import threading
import time

from .xp_config import get_base_dir, xp_log
from .xp_host_engine import XPHostEngine
from .xp_signaling import XPNetworkCoordinator

SERVICE_NAME = "EasyRemoteDesktopXPService"
SERVICE_DISPLAY = "Easy Remote Desktop XP Host Service"
SERVICE_DESC = "Provides unattended P2P remote control access (including Login screen) for Windows XP."
AUTORUN_VALUE_NAME = "EasyRemoteDesktopXPTray"
LOCAL_CONTROL_PORT = 12405

# Win32 Service Constants
SC_MANAGER_ALL_ACCESS = 0xF003F
SERVICE_ALL_ACCESS = 0xF01FF
SERVICE_WIN32_OWN_PROCESS = 0x00000010
SERVICE_INTERACTIVE_PROCESS = 0x00000100
SERVICE_AUTO_START = 0x00000002
SERVICE_ERROR_NORMAL = 0x00000001
SERVICE_CONFIG_DESCRIPTION = 1

SERVICE_STOPPED = 0x00000001
SERVICE_START_PENDING = 0x00000002
SERVICE_STOP_PENDING = 0x00000003
SERVICE_RUNNING = 0x00000004

SERVICE_CONTROL_STOP = 0x00000001
SERVICE_CONTROL_INTERROGATE = 0x00000004
SERVICE_CONTROL_SHUTDOWN = 0x00000005

SERVICE_ACCEPT_STOP = 0x00000001
SERVICE_ACCEPT_SHUTDOWN = 0x00000004


class SERVICE_STATUS(ctypes.Structure):
    _fields_ = [
        ("dwServiceType", wintypes.DWORD),
        ("dwCurrentState", wintypes.DWORD),
        ("dwControlsAccepted", wintypes.DWORD),
        ("dwWin32ExitCode", wintypes.DWORD),
        ("dwServiceSpecificExitCode", wintypes.DWORD),
        ("dwCheckPoint", wintypes.DWORD),
        ("dwWaitHint", wintypes.DWORD),
    ]


class SERVICE_DESCRIPTIONW(ctypes.Structure):
    _fields_ = [("lpDescription", wintypes.LPWSTR)]


# ==============================================================================
# Local IPC Control Channel (127.0.0.1:12405) between Service & User GUI/Tray
# ==============================================================================
def query_running_service_ipc(cmd_dict=None, timeout=0.6):
    """Kiểm tra Service có đang chạy không và lấy trạng thái trực tiếp qua 127.0.0.1:12405."""
    payload = cmd_dict or {"cmd": "status"}
    s = None
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        s.connect(("127.0.0.1", LOCAL_CONTROL_PORT))
        s.sendall((json.dumps(payload) + "\n").encode("utf-8"))
        buf = bytearray()
        while len(buf) < 16384:
            ch = s.recv(4096)
            if not ch:
                break
            buf.extend(ch)
            if b"\n" in buf:
                break
        line = bytes(buf).splitlines()[0].decode("utf-8", errors="ignore")
        return json.loads(line)
    except Exception:
        return None
    finally:
        if s:
            try:
                s.close()
            except Exception:
                pass


class XPLocalControlServer:
    """Lắng nghe trên 127.0.0.1:12405 bên trong tiến trình Service/Daemon."""

    def __init__(self, engine: XPHostEngine, coordinator: XPNetworkCoordinator):
        self.engine = engine
        self.coordinator = coordinator
        self.last_status_text = "Đang khởi động dịch vụ..."
        self._sock = None
        self.running = False

    def set_status_text(self, txt):
        self.last_status_text = str(txt or "")

    def start(self):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind(("127.0.0.1", LOCAL_CONTROL_PORT))
            s.listen(5)
            self._sock = s
            self.running = True
            threading.Thread(target=self._loop, daemon=True, name="XPLocalIPC").start()
            return True
        except Exception as e:
            xp_log(f"[LocalIPC] Bind 127.0.0.1:{LOCAL_CONTROL_PORT} skipped: {e}")
            return False

    def stop(self):
        self.running = False
        if self._sock:
            try:
                self._sock.close()
            except Exception:
                pass
            self._sock = None

    def _loop(self):
        while self.running and self._sock:
            try:
                conn, _ = self._sock.accept()
                threading.Thread(target=self._handle_conn, args=(conn,), daemon=True).start()
            except Exception:
                if not self.running:
                    break
                time.sleep(0.2)

    def _handle_conn(self, conn):
        try:
            conn.settimeout(2.0)
            raw = conn.recv(4096)
            if not raw:
                return
            req = json.loads(raw.decode("utf-8", errors="ignore").strip().splitlines()[0])
            cmd = req.get("cmd", "status")
            if cmd == "reload_passwords":
                self.engine.reload_passwords()
            elif cmd == "restart_signaling":
                self.coordinator.restart_signaling()

            with self.engine.clients_lock:
                n_clients = len(self.engine.active_clients)
            resp = {
                "ok": True,
                "hwid": self.coordinator.hwid,
                "hwid_display": self.coordinator.hwid_display,
                "bound_port": self.coordinator.bound_port,
                "local_ip": self.coordinator.local_ip,
                "signaling_online": self.coordinator.signaling_online,
                "signaling_server": self.coordinator.signaling_server_active,
                "active_clients": n_clients,
                "status_text": self.last_status_text,
            }
            conn.sendall((json.dumps(resp) + "\n").encode("utf-8"))
        except Exception:
            pass
        finally:
            try:
                conn.close()
            except Exception:
                pass


# ==============================================================================
# Native Registry Helpers: XP Firewall Exception & Tray Autorun
# ==============================================================================
def _build_service_command_line(flag="--service"):
    if getattr(sys, "frozen", False) or hasattr(sys, "__compiled__"):
        exe = os.path.abspath(sys.executable)
        return f'"{exe}" {flag}', exe
    py_exe = os.path.abspath(sys.executable)
    pyw = os.path.join(os.path.dirname(py_exe), "pythonw.exe")
    runner = pyw if os.path.isfile(pyw) else py_exe
    script = os.path.abspath(os.path.join(os.path.dirname(__file__), "app_xp.py"))
    return f'"{runner}" "{script}" {flag}', exe_for_firewall(runner)


def exe_for_firewall(fallback_path):
    if getattr(sys, "frozen", False) or hasattr(sys, "__compiled__"):
        return os.path.abspath(sys.executable)
    return fallback_path


def configure_xp_firewall_exception(exe_path, enable=True):
    """Mở ngoại lệ Windows Firewall trên Windows XP SP2/SP3 trực tiếp qua Registry SharedAccess."""
    if sys.platform != "win32" or not exe_path:
        return False
    try:
        import winreg
        exe_abs = os.path.abspath(exe_path)
        rule_val = f"{exe_abs}:*:Enabled:EasyRemoteDesktopXP"
        for profile in ("StandardProfile", "DomainProfile"):
            reg_path = (
                r"SYSTEM\CurrentControlSet\Services\SharedAccess\Parameters\FirewallPolicy"
                + "\\" + profile + r"\AuthorizedApplications\List"
            )
            try:
                with winreg.CreateKeyEx(winreg.HKEY_LOCAL_MACHINE, reg_path, 0, winreg.KEY_SET_VALUE) as k:
                    if enable:
                        winreg.SetValueEx(k, exe_abs, 0, winreg.REG_SZ, rule_val)
                    else:
                        try:
                            winreg.DeleteValue(k, exe_abs)
                        except FileNotFoundError:
                            pass
            except Exception:
                continue
        return True
    except Exception:
        return False


def set_xp_autorun_tray(enable=True):
    """Đăng ký chạy khay hệ thống khi người dùng đăng nhập vào Desktop XP."""
    if sys.platform != "win32":
        return False
    try:
        import winreg
        cmd_str, _ = _build_service_command_line("--tray")
        reg_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        for root_hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
            try:
                with winreg.OpenKey(root_hive, reg_path, 0, winreg.KEY_SET_VALUE) as k:
                    if enable:
                        winreg.SetValueEx(k, AUTORUN_VALUE_NAME, 0, winreg.REG_SZ, cmd_str)
                    else:
                        try:
                            winreg.DeleteValue(k, AUTORUN_VALUE_NAME)
                        except FileNotFoundError:
                            pass
                if enable:
                    return True
            except Exception:
                continue
        return not enable
    except Exception:
        return False


def is_xp_autorun_enabled():
    if sys.platform != "win32":
        return False
    try:
        import winreg
        reg_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
            try:
                with winreg.OpenKey(hive, reg_path, 0, winreg.KEY_READ) as k:
                    val, _ = winreg.QueryValueEx(k, AUTORUN_VALUE_NAME)
                    if val:
                        return True
            except Exception:
                continue
    except Exception:
        pass
    return False


# ==============================================================================
# Native Win32 Service Install / Uninstall / Dispatcher (advapi32.dll)
# ==============================================================================
def install_xp_service():
    """Đăng ký & Khởi chạy Interactive Windows Service cho XP (cần quyền Administrator)."""
    if sys.platform != "win32":
        return False, "Windows only"
    advapi32 = ctypes.windll.advapi32
    bin_cmd, fw_exe = _build_service_command_line("--service")
    configure_xp_firewall_exception(fw_exe, enable=True)
    set_xp_autorun_tray(enable=True)

    scm = advapi32.OpenSCManagerW(None, None, SC_MANAGER_ALL_ACCESS)
    if not scm:
        return False, f"OpenSCManagerW failed (err={ctypes.GetLastError()}). Cần chạy quyền Administrator."

    svc = 0
    try:
        svc = advapi32.OpenServiceW(scm, ctypes.c_wchar_p(SERVICE_NAME), SERVICE_ALL_ACCESS)
        if svc:
            # Dừng nếu đang chạy và cập nhật lại đường dẫn binary + cờ Interactive
            st = SERVICE_STATUS()
            advapi32.ControlService(svc, SERVICE_CONTROL_STOP, ctypes.byref(st))
            time.sleep(0.8)
            advapi32.ChangeServiceConfigW(
                svc,
                SERVICE_WIN32_OWN_PROCESS | SERVICE_INTERACTIVE_PROCESS,
                SERVICE_AUTO_START,
                SERVICE_ERROR_NORMAL,
                ctypes.c_wchar_p(bin_cmd),
                None, None, None, None, None,
                ctypes.c_wchar_p(SERVICE_DISPLAY),
            )
        else:
            svc = advapi32.CreateServiceW(
                scm,
                ctypes.c_wchar_p(SERVICE_NAME),
                ctypes.c_wchar_p(SERVICE_DISPLAY),
                SERVICE_ALL_ACCESS,
                SERVICE_WIN32_OWN_PROCESS | SERVICE_INTERACTIVE_PROCESS,
                SERVICE_AUTO_START,
                SERVICE_ERROR_NORMAL,
                ctypes.c_wchar_p(bin_cmd),
                None, None, None, None, None,
            )
            if not svc:
                return False, f"CreateServiceW failed (err={ctypes.GetLastError()})"

        desc = SERVICE_DESCRIPTIONW(lpDescription=SERVICE_DESC)
        advapi32.ChangeServiceConfig2W(svc, SERVICE_CONFIG_DESCRIPTION, ctypes.byref(desc))

        # Bật cho phép tương tác màn hình trên khoá Registry dịch vụ (đảm bảo trên mọi bản XP SP2/SP3)
        try:
            import winreg
            with winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                rf"SYSTEM\CurrentControlSet\Services\{SERVICE_NAME}",
                0,
                winreg.KEY_SET_VALUE,
            ) as k:
                winreg.SetValueEx(k, "Type", 0, winreg.REG_DWORD, SERVICE_WIN32_OWN_PROCESS | SERVICE_INTERACTIVE_PROCESS)
        except Exception:
            pass

        advapi32.StartServiceW(svc, 0, None)
        xp_log(f"[XPService] Installed & started {SERVICE_NAME} -> {bin_cmd}")
        return True, None
    finally:
        if svc:
            advapi32.CloseServiceHandle(svc)
        advapi32.CloseServiceHandle(scm)


def uninstall_xp_service():
    if sys.platform != "win32":
        return False, "Windows only"
    _, fw_exe = _build_service_command_line("--service")
    configure_xp_firewall_exception(fw_exe, enable=False)
    set_xp_autorun_tray(enable=False)

    advapi32 = ctypes.windll.advapi32
    scm = advapi32.OpenSCManagerW(None, None, SC_MANAGER_ALL_ACCESS)
    if not scm:
        return False, f"OpenSCManagerW failed (err={ctypes.GetLastError()})"
    svc = 0
    try:
        svc = advapi32.OpenServiceW(scm, ctypes.c_wchar_p(SERVICE_NAME), SERVICE_ALL_ACCESS)
        if not svc:
            return True, None
        st = SERVICE_STATUS()
        advapi32.ControlService(svc, SERVICE_CONTROL_STOP, ctypes.byref(st))
        time.sleep(0.8)
        advapi32.DeleteService(svc)
        xp_log(f"[XPService] Uninstalled {SERVICE_NAME}")
        return True, None
    finally:
        if svc:
            advapi32.CloseServiceHandle(svc)
        advapi32.CloseServiceHandle(scm)


def run_headless_daemon(stop_event=None):
    """Chạy nền trực tiếp (dùng cho cả ServiceMain lẫn chế độ --headless)."""
    bdir = get_base_dir()
    stop_ev = stop_event or threading.Event()
    ipc_holder = {}

    def _on_status(txt):
        srv = ipc_holder.get("ipc")
        if srv:
            srv.set_status_text(txt)

    engine = XPHostEngine(base_dir=bdir, tk_root=None, on_session_status=_on_status)
    coord = XPNetworkCoordinator(
        on_client_socket=engine.handle_client_connection,
        on_status_change=_on_status,
        base_dir=bdir,
    )
    ipc = XPLocalControlServer(engine, coord)
    ipc_holder["ipc"] = ipc
    ipc.start()
    coord.start()
    engine.bound_port = coord.bound_port

    xp_log(f"[XPDaemon] Running (HWID={coord.hwid}, Port={coord.bound_port})", base_dir=bdir)
    try:
        while not stop_ev.is_set():
            stop_ev.wait(1.0)
    except KeyboardInterrupt:
        pass
    finally:
        engine.notify_shutdown("shutdown")
        ipc.stop()
        coord.stop()
        xp_log("[XPDaemon] Stopped cleanly.", base_dir=bdir)


# Giữ tham chiếu toàn cục cho callback ctypes để GC không thu hồi khi Service chạy nhiều ngày
_SVC_REFS = {}


def run_win32_service_dispatcher():
    """Điểm vào chính khi Service Control Manager (services.exe) của Windows XP gọi --service."""
    if sys.platform != "win32":
        run_headless_daemon()
        return

    advapi32 = ctypes.windll.advapi32
    stop_ev = threading.Event()
    status_handle_box = [0]

    HANDLER_EX = ctypes.WINFUNCTYPE(wintypes.DWORD, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p, ctypes.c_void_p)
    SERVICE_MAIN = ctypes.WINFUNCTYPE(None, wintypes.DWORD, ctypes.POINTER(wintypes.LPWSTR))

    class SERVICE_TABLE_ENTRYW(ctypes.Structure):
        _fields_ = [
            ("lpServiceName", wintypes.LPWSTR),
            ("lpServiceProc", SERVICE_MAIN),
        ]

    def _report_status(state, wait_hint=0):
        h = status_handle_box[0]
        if not h:
            return
        st = SERVICE_STATUS()
        st.dwServiceType = SERVICE_WIN32_OWN_PROCESS | SERVICE_INTERACTIVE_PROCESS
        st.dwCurrentState = state
        st.dwControlsAccepted = (SERVICE_ACCEPT_STOP | SERVICE_ACCEPT_SHUTDOWN) if state == SERVICE_RUNNING else 0
        st.dwWin32ExitCode = 0
        st.dwWaitHint = wait_hint
        advapi32.SetServiceStatus(h, ctypes.byref(st))

    def _ctrl_handler(control, _ev_type, _ev_data, _ctx):
        if control in (SERVICE_CONTROL_STOP, SERVICE_CONTROL_SHUTDOWN):
            _report_status(SERVICE_STOP_PENDING, 3000)
            stop_ev.set()
            return 0
        if control == SERVICE_CONTROL_INTERROGATE:
            return 0
        return 120  # ERROR_CALL_NOT_IMPLEMENTED

    def _service_main(_argc, _argv):
        c_handler = HANDLER_EX(_ctrl_handler)
        _SVC_REFS["handler"] = c_handler
        h_status = advapi32.RegisterServiceCtrlHandlerExW(ctypes.c_wchar_p(SERVICE_NAME), c_handler, None)
        status_handle_box[0] = h_status
        _report_status(SERVICE_START_PENDING, 3000)
        _report_status(SERVICE_RUNNING, 0)
        try:
            run_headless_daemon(stop_event=stop_ev)
        finally:
            _report_status(SERVICE_STOPPED, 0)

    c_main = SERVICE_MAIN(_service_main)
    _SVC_REFS["main"] = c_main
    table = (SERVICE_TABLE_ENTRYW * 2)()
    table[0].lpServiceName = SERVICE_NAME
    table[0].lpServiceProc = c_main
    table[1].lpServiceName = None
    table[1].lpServiceProc = SERVICE_MAIN(0)

    ok = advapi32.StartServiceCtrlDispatcherW(ctypes.byref(table))
    if not ok:
        # Nếu người dùng gõ nhầm --service từ cửa sổ dòng lệnh thay vì SCM, chạy như headless daemon
        xp_log(f"[XPService] StartServiceCtrlDispatcherW returned 0 (err={ctypes.GetLastError()}), running standalone.")
        run_headless_daemon(stop_event=stop_ev)
