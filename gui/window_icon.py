import os
import sys
import tkinter as tk

from core.config import app_dir

_patched = False
_orig_toplevel_init = None


def _icon_file():
    ico = os.path.join(app_dir, "app_icon.ico")
    ico_alt = os.path.join(app_dir, "app.ico")
    png = os.path.join(app_dir, "app_icon.png")
    if os.path.exists(ico):
        return ico, png
    if os.path.exists(ico_alt):
        return ico_alt, png
    return "", png


def set_dialog_app_icon(win):
    """Gắn icon app lên Toplevel (thay icon lông chim Tk). Bỏ qua cửa sổ không viền."""
    try:
        if not win.winfo_exists():
            return
        try:
            if bool(win.overrideredirect()):
                return
        except Exception:
            pass
        icon_path, png = _icon_file()
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
                win.update_idletasks()
                hwnd = int(win.winfo_id())
                parent = ctypes.windll.user32.GetParent(hwnd)
                if parent:
                    hwnd = parent
                hicon = ctypes.windll.user32.LoadImageW(0, icon_path, 1, 0, 0, 0x0010)
                if hicon:
                    ctypes.windll.user32.SendMessageW(hwnd, 0x0080, 0, hicon)
                    ctypes.windll.user32.SendMessageW(hwnd, 0x0080, 1, hicon)
            except Exception:
                pass
    except Exception:
        pass


def _apply_when_ready(win):
    def _go():
        set_dialog_app_icon(win)

    try:
        win.after_idle(_go)
        win.after(80, _go)
    except Exception:
        _go()


def install_toplevel_app_icon():
    """Mọi tk.Toplevel (dialog) dùng icon app thay vì lông chim Tk."""
    global _patched, _orig_toplevel_init
    if _patched:
        return
    _patched = True
    _orig_toplevel_init = tk.Toplevel.__init__

    def _init(self, *args, **kwargs):
        _orig_toplevel_init(self, *args, **kwargs)
        _apply_when_ready(self)

    tk.Toplevel.__init__ = _init
