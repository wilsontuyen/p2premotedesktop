# -*- coding: utf-8 -*-
"""
xp_host/app_xp.py
Entry-point chính của bản EasyRemoteDesktop Host XP Lite (32-bit):
  - Hỗ trợ đầy đủ các tham số dòng lệnh:
      --service            : Chạy dưới quyền Windows XP Interactive Service (Session 0: Login + Desktop)
      --install-service    : Cài đặt & khởi động Windows Service + mở tường lửa XP + Autorun Tray
      --uninstall-service  : Gỡ cài đặt Windows Service & dọn cấu hình Autorun
      --headless           : Chạy ngầm không giao diện
      --tray               : Khởi động thu nhỏ sẵn xuống khay hệ thống cạnh đồng hồ XP
      (mặc định)           : Hiển thị giao diện Host tối giản dùng font Tahoma chuẩn Windows XP
  - Tự động phát hiện nếu XP Service đang chạy (qua 127.0.0.1:12405) để đóng vai trò bảng điều khiển
    nhẹ (không chiếm cổng 12345 của Service); nếu chưa cài Service thì tự khởi chạy toàn bộ Engine
    như một bản Portable độc lập!
"""

import ctypes
from ctypes import wintypes
import os
import sys
import threading
import time

# Khi đóng gói bằng cx_Freeze chạy trên máy Windows XP sạch, trỏ sẵn TCL_LIBRARY / TK_LIBRARY
# vào thư mục đi kèm ứng dụng để Tkinter luôn tìm thấy init.tcl & tk.tcl.
if getattr(sys, "frozen", False):
    _exe_dir = os.path.dirname(os.path.abspath(sys.executable))
    for _tcl_root in (_exe_dir, os.path.join(_exe_dir, "lib"), os.path.join(_exe_dir, "tcl")):
        _tcl_cand = os.path.join(_tcl_root, "tcl8.6")
        _tk_cand = os.path.join(_tcl_root, "tk8.6")
        if os.path.isdir(_tcl_cand) and "TCL_LIBRARY" not in os.environ:
            os.environ["TCL_LIBRARY"] = _tcl_cand
        if os.path.isdir(_tk_cand) and "TK_LIBRARY" not in os.environ:
            os.environ["TK_LIBRARY"] = _tk_cand

# Cho phép chạy trực tiếp `python xp_host/app_xp.py` hoặc `python -m xp_host.app_xp`
if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from xp_host.xp_clipboard import xp_set_clipboard_text
    from xp_host.xp_config import (
        generate_session_password,
        get_base_dir,
        get_logs_dir,
        load_fixed_password,
        load_or_create_session_password,
        load_signaling_config,
        load_ui_prefs,
        load_zalo_phone,
        save_fixed_password,
        save_session_password,
        save_signaling_config,
        save_ui_prefs,
        save_zalo_phone,
        xp_log,
    )
    from xp_host.xp_host_engine import XPHostEngine
    from xp_host.xp_hwid import get_hwid
    from xp_host.xp_service import (
        install_xp_service,
        is_xp_autorun_enabled,
        query_running_service_ipc,
        run_headless_daemon,
        run_win32_service_dispatcher,
        set_xp_autorun_tray,
        uninstall_xp_service,
    )
    from xp_host.xp_signaling import XPNetworkCoordinator
else:
    from .xp_clipboard import xp_set_clipboard_text
    from .xp_config import (
        generate_session_password,
        get_base_dir,
        get_logs_dir,
        load_fixed_password,
        load_or_create_session_password,
        load_signaling_config,
        load_ui_prefs,
        load_zalo_phone,
        save_fixed_password,
        save_session_password,
        save_signaling_config,
        save_ui_prefs,
        save_zalo_phone,
        xp_log,
    )
    from .xp_host_engine import XPHostEngine
    from .xp_hwid import get_hwid
    from .xp_service import (
        install_xp_service,
        is_xp_autorun_enabled,
        query_running_service_ipc,
        run_headless_daemon,
        run_win32_service_dispatcher,
        set_xp_autorun_tray,
        uninstall_xp_service,
    )
    from .xp_signaling import XPNetworkCoordinator


# ==============================================================================
# Native Win32 System Tray Icon (Shell_NotifyIconW V1 - Zero pystray dependency)
# ==============================================================================
WM_TRAY_CALLBACK = 0x0400 + 55
WM_COMMAND = 0x0111
WM_LBUTTONDBLCLK = 0x0203
WM_RBUTTONUP = 0x0205
NIM_ADD = 0x00000000
NIM_MODIFY = 0x00000001
NIM_DELETE = 0x00000002
NIF_MESSAGE = 0x00000001
NIF_ICON = 0x00000002
NIF_TIP = 0x00000004


class NOTIFYICONDATAW_V1(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("hWnd", wintypes.HWND),
        ("uID", wintypes.UINT),
        ("uFlags", wintypes.UINT),
        ("uCallbackMessage", wintypes.UINT),
        ("hIcon", wintypes.HICON),
        ("szTip", ctypes.c_wchar * 64),
    ]


class XPNativeTrayIcon:
    """Biểu tượng khay hệ thống nhẹ thuần shell32.dll cho Windows XP -> Windows 11."""

    def __init__(self, tooltip, on_show, on_exit, icon_path=""):
        self.tooltip = (tooltip or "Easy Remote Desktop XP")[:63]
        self.on_show = on_show
        self.on_exit = on_exit
        self.icon_path = icon_path
        self.hwnd = 0
        self.hicon = 0
        self.running = True
        self._wndproc_ref = None
        if sys.platform == "win32":
            threading.Thread(target=self._loop, daemon=True, name="XPTrayThread").start()

    def _load_icon(self):
        user32 = ctypes.windll.user32
        IMAGE_ICON = 1
        LR_LOADFROMFILE = 0x0010
        for p in (
            self.icon_path,
            os.path.join(get_base_dir(), "app_icon.ico"),
            os.path.join(os.path.dirname(get_base_dir()), "app_icon.ico"),
        ):
            if p and os.path.isfile(p):
                h = user32.LoadImageW(0, ctypes.c_wchar_p(p), IMAGE_ICON, 16, 16, LR_LOADFROMFILE)
                if h:
                    return h
        return user32.LoadIconW(0, ctypes.cast(32512, wintypes.LPCWSTR))  # IDI_APPLICATION

    def _show_popup_menu(self, hwnd):
        user32 = ctypes.windll.user32
        hmenu = user32.CreatePopupMenu()
        if not hmenu:
            return
        MF_STRING = 0x0000
        MF_SEPARATOR = 0x0800
        TPM_RETURNCMD = 0x0100
        TPM_RIGHTBUTTON = 0x0002
        user32.AppendMenuW(hmenu, MF_STRING, 1001, ctypes.c_wchar_p("Mở Easy Remote Desktop XP"))
        user32.AppendMenuW(hmenu, MF_SEPARATOR, 0, None)
        user32.AppendMenuW(hmenu, MF_STRING, 1002, ctypes.c_wchar_p("Thoát (Exit)"))

        pt = wintypes.POINT()
        user32.GetCursorPos(ctypes.byref(pt))
        user32.SetForegroundWindow(hwnd)
        cmd = user32.TrackPopupMenu(hmenu, TPM_RETURNCMD | TPM_RIGHTBUTTON, pt.x, pt.y, 0, hwnd, None)
        user32.DestroyMenu(hmenu)
        if cmd == 1001 and callable(self.on_show):
            self.on_show()
        elif cmd == 1002 and callable(self.on_exit):
            self.on_exit()

    def _loop(self):
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        shell32 = ctypes.windll.shell32

        WPARAM_T = ctypes.c_size_t
        LPARAM_T = ctypes.c_ssize_t
        LRESULT_T = ctypes.c_ssize_t
        WNDPROCTYPE = ctypes.WINFUNCTYPE(LRESULT_T, wintypes.HWND, wintypes.UINT, WPARAM_T, LPARAM_T)

        class WNDCLASSEXW(ctypes.Structure):
            _fields_ = [
                ("cbSize", wintypes.UINT),
                ("style", wintypes.UINT),
                ("lpfnWndProc", WNDPROCTYPE),
                ("cbClsExtra", ctypes.c_int),
                ("cbWndExtra", ctypes.c_int),
                ("hInstance", wintypes.HINSTANCE),
                ("hIcon", wintypes.HICON),
                ("hCursor", wintypes.HANDLE),
                ("hbrBackground", wintypes.HBRUSH),
                ("lpszMenuName", wintypes.LPCWSTR),
                ("lpszClassName", wintypes.LPCWSTR),
                ("hIconSm", wintypes.HICON),
            ]

        user32.DefWindowProcW.argtypes = [wintypes.HWND, wintypes.UINT, WPARAM_T, LPARAM_T]
        user32.DefWindowProcW.restype = LRESULT_T

        def _wndproc(hwnd, msg, wparam, lparam):
            if msg == WM_TRAY_CALLBACK:
                ev = lparam & 0xFFFF
                if ev == WM_LBUTTONDBLCLK and callable(self.on_show):
                    self.on_show()
                elif ev == WM_RBUTTONUP:
                    self._show_popup_menu(hwnd)
                return 0
            return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

        self._wndproc_ref = WNDPROCTYPE(_wndproc)
        hinst = kernel32.GetModuleHandleW(None)
        cls_name = f"ERD_XPTrayWnd_{os.getpid()}"
        wc = WNDCLASSEXW()
        wc.cbSize = ctypes.sizeof(WNDCLASSEXW)
        wc.lpfnWndProc = self._wndproc_ref
        wc.hInstance = hinst
        wc.lpszClassName = cls_name
        user32.RegisterClassExW(ctypes.byref(wc))

        self.hwnd = user32.CreateWindowExW(0, cls_name, "ERD_XPTray", 0, 0, 0, 0, 0, 0, 0, hinst, None)
        if not self.hwnd:
            return
        self.hicon = self._load_icon()

        nid = NOTIFYICONDATAW_V1()
        nid.cbSize = ctypes.sizeof(NOTIFYICONDATAW_V1)
        nid.hWnd = self.hwnd
        nid.uID = 1
        nid.uFlags = NIF_MESSAGE | NIF_ICON | NIF_TIP
        nid.uCallbackMessage = WM_TRAY_CALLBACK
        nid.hIcon = self.hicon
        nid.szTip = self.tooltip
        shell32.Shell_NotifyIconW(NIM_ADD, ctypes.byref(nid))

        msg = wintypes.MSG()
        try:
            while self.running and user32.GetMessageW(ctypes.byref(msg), 0, 0, 0) > 0:
                user32.TranslateMessage(ctypes.byref(msg))
                user32.DispatchMessageW(ctypes.byref(msg))
        finally:
            shell32.Shell_NotifyIconW(NIM_DELETE, ctypes.byref(nid))

    def destroy(self):
        self.running = False
        if self.hwnd and sys.platform == "win32":
            try:
                ctypes.windll.user32.PostMessageW(self.hwnd, 0x0012, 0, 0)  # WM_QUIT
            except Exception:
                pass


# ==============================================================================
# Lightweight Windows XP Host GUI (Tahoma Font - Classic & Clean)
# ==============================================================================
THEMES_XP = {
    "classic_xp": {"bg": "#ECE9D8", "card": "#FFFFFF", "fg": "#000000", "sub": "#4A4A4A", "accent": "#0054E3", "entry": "#F7F6F0"},
    "light":      {"bg": "#F4F6F9", "card": "#FFFFFF", "fg": "#1E293B", "sub": "#64748B", "accent": "#2563EB", "entry": "#EEF2F6"},
    "dark":       {"bg": "#1E1E2E", "card": "#2A2A3C", "fg": "#F8FAFC", "sub": "#94A3B8", "accent": "#3B82F6", "entry": "#181825"},
}


def run_xp_gui(start_minimized=False):
    import tkinter as tk
    from tkinter import messagebox, simpledialog

    bdir = get_base_dir()
    prefs = load_ui_prefs(bdir)
    hwid, hwid_disp, _ = get_hwid(bdir)
    sess_pw = load_or_create_session_password(prefs.get("pass_mode", "4digits"), bdir)

    root = tk.Tk()
    root.title("Easy Remote Desktop Host AI version")
    root.geometry("410x330")
    root.resizable(False, False)

    for ico_cand in (
        os.path.join(bdir, "app_icon.ico"),
        os.path.join(os.path.dirname(bdir), "app_icon.ico"),
    ):
        if os.path.isfile(ico_cand):
            try:
                root.iconbitmap(ico_cand)
                break
            except Exception:
                pass

    # Kiểm tra xem Windows Service có đang chạy sẵn ở cổng nội bộ 12405 không
    svc_status = query_running_service_ipc()
    service_delegated = svc_status is not None
    local_engine = None
    local_coord = None

    id_var = tk.StringVar(value=hwid_disp)
    pw_var = tk.StringVar(value=sess_pw)
    fixed_info_var = tk.StringVar(value="")
    status_var = tk.StringVar(value="Đang khởi tạo kết nối...")
    pass_mode_var = tk.StringVar(value=prefs.get("pass_mode", "4digits"))
    theme_var = tk.StringVar(value=prefs.get("theme", "classic_xp"))
    startup_var = tk.BooleanVar(value=is_xp_autorun_enabled())

    def _refresh_fixed_badge():
        fp = load_fixed_password(bdir)
        fixed_info_var.set("Đã bật mật khẩu cố định" if fp else "Chưa đặt mật khẩu cố định")

    _refresh_fixed_badge()

    # Nếu chưa cài Service -> tự chạy Engine & Network ngay trong tiến trình GUI (Portable mode)
    if not service_delegated:
        def _status_cb(txt):
            try:
                root.after(0, lambda t=txt: status_var.set(t))
            except Exception:
                pass

        local_engine = XPHostEngine(base_dir=bdir, tk_root=root, on_session_status=_status_cb)
        local_coord = XPNetworkCoordinator(
            on_client_socket=local_engine.handle_client_connection,
            on_status_change=_status_cb,
            base_dir=bdir,
        )
        local_coord.start()
        local_engine.bound_port = local_coord.bound_port
    else:
        status_var.set(svc_status.get("status_text") or f"Dịch vụ XP đang chạy (Cổng {svc_status.get('bound_port')})")

    # ---------- Actions ----------
    def copy_info():
        txt = f"ID: {hwid_disp}\r\nPass: {pw_var.get()}"
        xp_set_clipboard_text(txt)
        status_var.set("Đã chép ID & Mật khẩu vào bộ nhớ tạm!")

    def regen_password():
        mode = pass_mode_var.get()
        prefs["pass_mode"] = mode
        save_ui_prefs(prefs, bdir)
        new_pw = generate_session_password(mode)
        save_session_password(new_pw, bdir)
        pw_var.set(new_pw)
        if query_running_service_ipc({"cmd": "reload_passwords"}) is None and local_engine:
            local_engine.reload_passwords()
        status_var.set("Đã tạo mật khẩu phiên mới.")

    def set_fixed_pw_dialog():
        cur = load_fixed_password(bdir)
        ans = simpledialog.askstring(
            "Mật khẩu cố định",
            "Nhập mật khẩu cố định (để trống nếu muốn xóa):",
            initialvalue=cur,
            parent=root,
        )
        if ans is None:
            return
        save_fixed_password(ans.strip(), bdir)
        _refresh_fixed_badge()
        if query_running_service_ipc({"cmd": "reload_passwords"}) is None and local_engine:
            local_engine.reload_passwords()
        messagebox.showinfo("Thành công", "Đã lưu cấu hình mật khẩu cố định!", parent=root)

    def set_server_dialog():
        hosts, port = load_signaling_config(bdir)
        cur_str = f"{hosts[0]}:{port}" if hosts else "homed.auavn.com:8765"
        ans = simpledialog.askstring(
            "Cài đặt máy chủ Signaling",
            "Nhập địa chỉ máy chủ Signaling (vd: homed.auavn.com:8765):",
            initialvalue=cur_str,
            parent=root,
        )
        if not ans:
            return
        raw = ans.strip()
        if ":" in raw:
            h, p_str = raw.rsplit(":", 1)
            p = int(p_str) if p_str.isdigit() else port
        else:
            h, p = raw, port
        save_signaling_config([h.strip()], p, bdir)
        if query_running_service_ipc({"cmd": "restart_signaling"}) is None and local_coord:
            local_coord.restart_signaling()
        messagebox.showinfo("Máy chủ Signaling", f"Đã cập nhật máy chủ: {h.strip()}:{p}", parent=root)

    def set_zalo_dialog():
        cur = load_zalo_phone(bdir)
        ans = simpledialog.askstring("Zalo / Điện thoại", "Số điện thoại / Zalo hiển thị cho kỹ thuật viên:", initialvalue=cur, parent=root)
        if ans is not None:
            save_zalo_phone(ans.strip(), bdir)

    def toggle_autorun():
        ok = set_xp_autorun_tray(startup_var.get())
        if not ok:
            startup_var.set(is_xp_autorun_enabled())

    def install_svc_from_menu():
        nonlocal service_delegated
        if local_coord:
            local_coord.stop()
        ok, err = install_xp_service()
        if ok:
            service_delegated = True
            messagebox.showinfo(
                "Dịch vụ Windows XP",
                "Đã cài đặt và khởi chạy Dịch vụ nền thành công!\nMáy có thể được điều khiển ngay cả ở màn hình đăng nhập Windows XP.",
                parent=root,
            )
        else:
            if local_coord:
                local_coord.start()
            messagebox.showerror("Lỗi cài dịch vụ", str(err), parent=root)

    def uninstall_svc_from_menu():
        ok, err = uninstall_xp_service()
        if ok:
            messagebox.showinfo("Dịch vụ Windows XP", "Đã gỡ bỏ Dịch vụ nền.", parent=root)
        else:
            messagebox.showerror("Lỗi gỡ dịch vụ", str(err), parent=root)

    def open_logs_dir():
        ld = get_logs_dir(bdir)
        try:
            os.startfile(ld)
        except Exception:
            pass

    # ---------- Build UI (Font Tahoma chuẩn Windows XP) ----------
    container_Holder = {"frame": None}

    def rebuild_ui():
        th = THEMES_XP.get(theme_var.get(), THEMES_XP["classic_xp"])
        prefs["theme"] = theme_var.get()
        save_ui_prefs(prefs, bdir)
        root.configure(bg=th["bg"])

        if container_Holder["frame"] is not None:
            container_Holder["frame"].destroy()

        main_f = tk.Frame(root, bg=th["bg"])
        main_f.pack(fill="both", expand=True)
        container_Holder["frame"] = main_f

        tk.Label(
            main_f, text="EASY REMOTE DESKTOP - XP HOST",
            font=("Tahoma", 12, "bold"), fg=th["accent"], bg=th["bg"],
        ).pack(pady=(14, 2))
        tk.Label(
            main_f, text="Cho phép kỹ thuật viên điều khiển máy Windows XP này từ xa",
            font=("Tahoma", 8), fg=th["sub"], bg=th["bg"],
        ).pack(pady=(0, 10))

        card = tk.Frame(main_f, bg=th["card"], bd=1, relief="solid", padx=16, pady=12)
        card.pack(fill="x", padx=20, pady=4)

        # Row 1: ID
        tk.Label(card, text="ID Của Bạn (Your ID):", font=("Tahoma", 8, "bold"), fg=th["sub"], bg=th["card"], anchor="w").pack(fill="x")
        id_row = tk.Frame(card, bg=th["card"])
        id_row.pack(fill="x", pady=(2, 10))
        ent_id = tk.Entry(
            id_row, textvariable=id_var, font=("Tahoma", 15, "bold"),
            fg=th["accent"], readonlybackground=th["entry"], relief="flat", state="readonly", justify="center",
        )
        ent_id.pack(side="left", fill="x", expand=True, ipady=3)
        tk.Button(
            id_row, text="Sao chép", font=("Tahoma", 8, "bold"),
            bg=th["accent"], fg="#FFFFFF", activebackground="#003EB3", activeforeground="#FFFFFF",
            relief="raised", bd=1, padx=10, command=copy_info,
        ).pack(side="left", padx=(8, 0), ipady=2)

        # Row 2: Password
        tk.Label(card, text="Mật Khẩu Phiên (Password):", font=("Tahoma", 8, "bold"), fg=th["sub"], bg=th["card"], anchor="w").pack(fill="x")
        pw_row = tk.Frame(card, bg=th["card"])
        pw_row.pack(fill="x", pady=(2, 6))
        ent_pw = tk.Entry(
            pw_row, textvariable=pw_var, font=("Tahoma", 13, "bold"),
            fg=th["fg"], readonlybackground=th["entry"], relief="flat", state="readonly", justify="center",
        )
        ent_pw.pack(side="left", fill="x", expand=True, ipady=3)
        tk.Button(
            pw_row, text="Đổi mới", font=("Tahoma", 8),
            bg=th["bg"], fg=th["fg"], relief="raised", bd=1, padx=10, command=regen_password,
        ).pack(side="left", padx=(8, 0), ipady=2)

        # Row 3: Fixed password quick link
        fp_row = tk.Frame(card, bg=th["card"])
        fp_row.pack(fill="x", pady=(4, 0))
        tk.Label(fp_row, textvariable=fixed_info_var, font=("Tahoma", 8, "italic"), fg=th["sub"], bg=th["card"]).pack(side="left")
        tk.Button(
            fp_row, text="Mật khẩu cố định...", font=("Tahoma", 8),
            bg=th["bg"], fg=th["fg"], relief="groove", bd=1, command=set_fixed_pw_dialog,
        ).pack(side="right")

        # Bottom Status Bar
        st_bar = tk.Frame(main_f, bg=th["entry"], height=26, bd=1, relief="sunken")
        st_bar.pack(side="bottom", fill="x")
        st_bar.pack_propagate(False)
        tk.Label(
            st_bar, textvariable=status_var, font=("Tahoma", 8),
            fg=th["fg"], bg=th["entry"], anchor="w",
        ).pack(fill="both", padx=8, pady=2)

    # ---------- Menu Bar ----------
    menubar = tk.Menu(root)
    m_file = tk.Menu(menubar, tearoff=0)
    m_file.add_command(label="Ẩn xuống khay đồng hồ (Minimize to Tray)", command=lambda: hide_to_tray())
    m_file.add_separator()
    m_file.add_command(label="Thoát hoàn toàn (Exit)", command=lambda: quit_all())
    menubar.add_cascade(label="Tệp (File)", menu=m_file)

    m_opt = tk.Menu(menubar, tearoff=0)
    m_pw = tk.Menu(m_opt, tearoff=0)
    m_pw.add_radiobutton(label="4 chữ số", variable=pass_mode_var, value="4digits", command=regen_password)
    m_pw.add_radiobutton(label="5 chữ số", variable=pass_mode_var, value="5digits", command=regen_password)
    m_pw.add_radiobutton(label="8 ký tự (chữ + số)", variable=pass_mode_var, value="8alnum", command=regen_password)
    m_pw.add_separator()
    m_pw.add_command(label="Cài mật khẩu cố định...", command=set_fixed_pw_dialog)
    m_opt.add_cascade(label="Mật khẩu", menu=m_pw)

    m_svc = tk.Menu(m_opt, tearoff=0)
    m_svc.add_command(label="Cài đặt Dịch vụ nền XP (Hỗ trợ màn hình Login)", command=install_svc_from_menu)
    m_svc.add_command(label="Gỡ Dịch vụ nền XP", command=uninstall_svc_from_menu)
    m_opt.add_cascade(label="Dịch vụ Windows XP (Service)", menu=m_svc)

    m_opt.add_checkbutton(label="Tự mở khay hệ thống khi bật máy", variable=startup_var, command=toggle_autorun)
    m_opt.add_separator()
    m_opt.add_command(label="Cài đặt máy chủ Signaling...", command=set_server_dialog)
    m_opt.add_command(label="Số Zalo / Điện thoại...", command=set_zalo_dialog)
    m_opt.add_command(label="Mở thư mục Nhật ký (Logs)", command=open_logs_dir)
    m_opt.add_separator()

    m_theme = tk.Menu(m_opt, tearoff=0)
    m_theme.add_radiobutton(label="Cổ điển Windows XP (Luna)", variable=theme_var, value="classic_xp", command=rebuild_ui)
    m_theme.add_radiobutton(label="Sáng hiện đại", variable=theme_var, value="light", command=rebuild_ui)
    m_theme.add_radiobutton(label="Tối (Dark)", variable=theme_var, value="dark", command=rebuild_ui)
    m_opt.add_cascade(label="Giao diện", menu=m_theme)
    menubar.add_cascade(label="Tùy chọn (Options)", menu=m_opt)

    m_help = tk.Menu(menubar, tearoff=0)
    m_help.add_command(
        label="Giới thiệu (About)",
        command=lambda: messagebox.showinfo(
            "Easy Remote Desktop XP Lite",
            f"Phiên bản Host siêu nhẹ dành riêng cho Windows XP (32-bit)\nID máy: {hwid_disp}\nTương thích 100% với EasyRemoteDesktop Windows 10/11.",
            parent=root,
        ),
    )
    menubar.add_cascade(label="Trợ giúp", menu=m_help)
    root.config(menu=menubar)

    rebuild_ui()

    # ---------- System Tray Integration & Periodic Polling ----------
    def show_from_tray():
        root.after(0, lambda: (root.deiconify(), root.lift(), root.focus_force()))

    def hide_to_tray():
        root.withdraw()

    def quit_all():
        tray.destroy()
        if local_engine:
            local_engine.notify_shutdown("shutdown")
        if local_coord:
            local_coord.stop()
        root.after(0, root.destroy)

    tray = XPNativeTrayIcon(
        tooltip=f"EasyRemoteDesktop XP - ID: {hwid_disp}",
        on_show=show_from_tray,
        on_exit=quit_all,
    )
    # Đóng nút [X] trên cửa sổ -> thu nhỏ xuống khay đồng hồ XP để không rớt kết nối từ xa
    root.protocol("WM_DELETE_WINDOW", hide_to_tray)

    def _periodic_tick():
        if local_engine:
            local_engine.clipboard_mgr.process_gui_queue()
        else:
            st = query_running_service_ipc()
            if st and st.get("status_text"):
                status_var.set(st["status_text"])
        root.after(250, _periodic_tick)

    root.after(250, _periodic_tick)
    if start_minimized:
        root.withdraw()
    root.mainloop()


def main():
    args = [a.lower() for a in sys.argv[1:]]
    if "--install-service" in args:
        ok, err = install_xp_service()
        if not ok:
            xp_log(f"[InstallService] Failed: {err}")
            sys.exit(1)
        sys.exit(0)
    if "--uninstall-service" in args:
        ok, err = uninstall_xp_service()
        if not ok:
            xp_log(f"[UninstallService] Failed: {err}")
            sys.exit(1)
        sys.exit(0)
    if "--service" in args:
        run_win32_service_dispatcher()
        return
    if "--headless" in args:
        run_headless_daemon()
        return
    run_xp_gui(start_minimized=("--tray" in args or "--minimized" in args))


if __name__ == "__main__":
    main()
