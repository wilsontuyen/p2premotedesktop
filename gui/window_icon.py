import os
import sys
import tkinter as tk

from core.config import app_dir

_patched = False
_orig_toplevel_init = None
_orig_tk_init = None


def _icon_file():
    ico = os.path.join(app_dir, "app_icon.ico")
    ico_alt = os.path.join(app_dir, "app.ico")
    png = os.path.join(app_dir, "app_icon.png")
    if os.path.exists(ico):
        return ico, png
    if os.path.exists(ico_alt):
        return ico_alt, png
    return "", png


def _toplevel_hwnd(win):
    """HWND khung ngoài (taskbar), không phải client HWND của Tk."""
    import ctypes
    hwnd = int(win.winfo_id())
    parent = ctypes.windll.user32.GetParent(hwnd)
    return parent or hwnd


def _set_default_icon(win):
    """Đặt icon mặc định cho cả cây Toplevel — không cần cửa sổ đang hiện.

    iconbitmap(path) trên cửa sổ withdrawn sẽ map cửa sổ (nháy lông chim).
    Dạng default= chỉ đổi class icon, không hiện cửa sổ.
    """
    icon_path, png = _icon_file()
    if sys.platform == "win32" and icon_path:
        try:
            win.iconbitmap(default=icon_path)
            return
        except Exception:
            pass
    if os.path.exists(png):
        try:
            img = tk.PhotoImage(file=png)
        except Exception:
            try:
                from PIL import Image, ImageTk
                img = ImageTk.PhotoImage(Image.open(png))
            except Exception:
                return
        try:
            win.iconphoto(True, img)
            win._app_icon_img_default = img
        except Exception:
            pass


def set_dialog_app_icon(win):
    """Gắn icon app lên cửa sổ Tk (thay icon lông chim Tcl trên taskbar Win11)."""
    try:
        if not win.winfo_exists():
            return
        _set_default_icon(win)
        mapped = False
        try:
            mapped = bool(win.winfo_ismapped())
        except Exception:
            mapped = False
        # winfo_id / iconbitmap(path) trên withdrawn sẽ mapped → nháy Tk lúc khởi động.
        if not mapped:
            return
        icon_path, png = _icon_file()
        borderless = False
        try:
            borderless = bool(win.overrideredirect())
        except Exception:
            pass
        if not borderless:
            if sys.platform == "win32" and icon_path:
                try:
                    win.iconbitmap(icon_path)
                except Exception:
                    pass
            elif os.path.exists(png):
                try:
                    img = tk.PhotoImage(file=png)
                except Exception:
                    from PIL import Image, ImageTk
                    img = ImageTk.PhotoImage(Image.open(png))
                win.iconphoto(False, img)
                win._app_icon_img = img
        if sys.platform == "win32" and icon_path:
            try:
                import ctypes
                hwnd = _toplevel_hwnd(win)
                hicon = ctypes.windll.user32.LoadImageW(0, icon_path, 1, 0, 0, 0x0010)
                if hicon:
                    ctypes.windll.user32.SendMessageW(hwnd, 0x0080, 0, hicon)
                    ctypes.windll.user32.SendMessageW(hwnd, 0x0080, 1, hicon)
                    win._app_hicon = hicon
            except Exception:
                pass
    except Exception:
        pass


def hide_tk_from_taskbar(win):
    """Ẩn cửa sổ Tk helper khỏi taskbar Win11 (icon lông chim Tcl)."""
    if sys.platform != "win32":
        return
    try:
        if not win.winfo_exists():
            return
    except Exception:
        return
    try:
        win.wm_attributes("-toolwindow", True)
    except Exception:
        pass
    try:
        if not win.winfo_ismapped():
            return
    except Exception:
        return
    try:
        import ctypes
        user32 = ctypes.windll.user32
        hwnd = _toplevel_hwnd(win)
        GWL_EXSTYLE = -20
        WS_EX_TOOLWINDOW = 0x00000080
        WS_EX_APPWINDOW = 0x00040000
        ex = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        ex = (ex | WS_EX_TOOLWINDOW) & ~WS_EX_APPWINDOW
        user32.SetWindowLongW(hwnd, GWL_EXSTYLE, ex)
        flags = 0x0001 | 0x0002 | 0x0004 | 0x0010 | 0x0020
        user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0, flags)
    except Exception:
        pass


def _apply_when_ready(win):
    """Icon mặc định ngay; WM_SETICON khi cửa sổ thực sự hiện."""
    _set_default_icon(win)
    applied = {"done": False}

    def _go(event=None):
        if applied["done"]:
            return
        try:
            if not win.winfo_exists() or not win.winfo_ismapped():
                return
        except Exception:
            return
        applied["done"] = True
        set_dialog_app_icon(win)

    try:
        win.bind("<Map>", _go, add="+")
        win.after_idle(_go)
        win.after(50, _go)
        win.after(200, _go)
    except Exception:
        pass


def install_toplevel_app_icon():
    """Mọi tk.Tk / tk.Toplevel dùng icon app thay vì lông chim Tcl."""
    global _patched, _orig_toplevel_init, _orig_tk_init
    if _patched:
        return
    _patched = True
    _orig_toplevel_init = tk.Toplevel.__init__
    _orig_tk_init = tk.Tk.__init__

    def _tl_init(self, *args, **kwargs):
        _orig_toplevel_init(self, *args, **kwargs)
        _apply_when_ready(self)

    def _tk_init(self, *args, **kwargs):
        _orig_tk_init(self, *args, **kwargs)
        try:
            self.withdraw()
        except Exception:
            pass
        _set_default_icon(self)
        _apply_when_ready(self)

    tk.Toplevel.__init__ = _tl_init
    tk.Tk.__init__ = _tk_init
