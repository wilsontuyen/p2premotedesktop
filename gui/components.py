import tkinter as tk
from tkinter import ttk
import os
import time
import sys
_DIALOG_FONT = "Segoe UI" if sys.platform == "win32" else "Helvetica"
from utils.logger import log_debug, log_overwrite_conflict
from core.i18n import _

try:
    from PIL import Image, ImageTk
except ImportError:
    pass

from gui.window_icon import install_toplevel_app_icon, set_dialog_app_icon, hide_tk_from_taskbar
install_toplevel_app_icon()

from gui.windows_ui import ProgressDialog, ui_scale  # re-export; class lives in windows_ui


def _blend_hex(widget, color, target, ratio):
    """Trộn màu `color` về phía `target` theo `ratio` (0..1); trả về chuỗi #RRGGBB."""
    try:
        r1, g1, b1 = [v // 257 for v in widget.winfo_rgb(color)]
        r2, g2, b2 = [v // 257 for v in widget.winfo_rgb(target)]
    except Exception:
        return color
    r = int(r1 + (r2 - r1) * ratio)
    g = int(g1 + (g2 - g1) * ratio)
    b = int(b1 + (b2 - b1) * ratio)
    return f"#{r:02x}{g:02x}{b:02x}"


def _color_luminance(widget, color):
    """Tính độ sáng cảm nhận (0..255) của mã màu Tk."""
    if not color:
        return 128
    try:
        r, g, b = [v // 257 for v in widget.winfo_rgb(color)]
        return int(0.299 * r + 0.587 * g + 0.114 * b)
    except Exception:
        return 128


def _pick_focus_border_color(widget, bg_color=None, parent_bg=None, accent_color=None):
    """Chọn màu viền focus tương phản cao cho mọi giao diện (Sáng/Tối/Pha lê/Đỏ/Cam...)."""
    try:
        if bg_color is None:
            bg_color = widget.cget("bg")
    except Exception:
        bg_color = "#2A2A35"
    if parent_bg is None:
        try:
            parent = widget.nametowidget(widget.winfo_parent())
            parent_bg = parent.cget("bg")
        except Exception:
            parent_bg = bg_color

    p_lum = _color_luminance(widget, parent_bg)
    b_lum = _color_luminance(widget, bg_color)
    if p_lum > 165:
        if b_lum < 85:
            return accent_color or "#00ADB5"
        return "#0F172A"
    if b_lum > 200:
        return accent_color or "#0F172A"
    return "#FFFFFF"


def attach_focus_ring(widget, bg_widgets=None, normal_bg=None, focus_bg=None, border_color=None, thickness=2, on_click=None):
    """Gắn viền focus 2px bằng .place() (không làm thay đổi kích thước/bố cục widget)."""
    if widget is None or getattr(widget, "_focus_ring_attached", False):
        return
    widget._focus_ring_attached = True
    strips = []

    def _ensure_strips():
        if strips:
            return strips
        col = border_color or _pick_focus_border_color(widget, normal_bg)
        for _ in range(4):
            s = tk.Frame(widget, bg=col, bd=0, highlightthickness=0, takefocus=0)
            s._focus_strip = True
            if on_click is not None:
                s.bind("<ButtonRelease-1>", lambda e: on_click(e))
            elif isinstance(widget, tk.Button):
                s.bind("<ButtonRelease-1>", lambda e: widget.invoke() if str(widget.cget("state")) != "disabled" else None)
            strips.append(s)
        return strips

    def _on_focus_in(event):
        if event.widget is not widget:
            return
        try:
            if str(widget.cget("state")) == "disabled":
                return
        except Exception:
            pass
        try:
            cur_bg = normal_bg if normal_bg is not None else widget.cget("bg")
        except Exception:
            cur_bg = "#2A2A35"
        col = border_color or _pick_focus_border_color(widget, cur_bg)
        try:
            s_top, s_bot, s_left, s_right = _ensure_strips()
            for s in (s_top, s_bot, s_left, s_right):
                s.config(bg=col)
            s_top.place(relx=0.0, rely=0.0, relwidth=1.0, height=thickness)
            s_bot.place(relx=0.0, rely=1.0, anchor="sw", relwidth=1.0, height=thickness)
            s_left.place(relx=0.0, rely=0.0, relheight=1.0, width=thickness)
            s_right.place(relx=1.0, rely=0.0, anchor="ne", relheight=1.0, width=thickness)
            for s in (s_top, s_bot, s_left, s_right):
                s.lift()
        except Exception:
            pass
        if bg_widgets and focus_bg:
            for bw in bg_widgets:
                try:
                    bw.config(bg=focus_bg)
                except Exception:
                    pass

    def _on_focus_out(event):
        if event.widget is not widget:
            return
        for s in strips:
            try:
                s.place_forget()
            except Exception:
                pass
        if bg_widgets and normal_bg:
            for bw in bg_widgets:
                try:
                    bw.config(bg=normal_bg)
                except Exception:
                    pass

    widget.bind("<FocusIn>", _on_focus_in, add="+")
    widget.bind("<FocusOut>", _on_focus_out, add="+")


def bind_flat_button_keyboard(root_widget, bg_widgets, bg, active_bg, cmd, parent_bg=None):
    """Cho phép flat button (Frame/Label) nhận Tab focus, hiển thị viền focus và bấm bằng Enter/Space."""
    try:
        root_widget.configure(takefocus=1)
    except Exception:
        pass
    root_widget._is_kb_focusable = True

    def _invoke(_event=None):
        try:
            if str(root_widget.cget("state")) == "disabled":
                return "break"
        except Exception:
            pass
        if callable(cmd):
            cmd()
        return "break"

    root_widget._kb_invoke = _invoke
    root_widget.bind("<Return>", _invoke)
    root_widget.bind("<KP_Enter>", _invoke)
    root_widget.bind("<space>", _invoke)

    lum = _color_luminance(root_widget, bg)
    focus_bg = active_bg if (active_bg and active_bg != bg) else _blend_hex(
        root_widget, bg, "#FFFFFF" if lum < 160 else "#000000", 0.18
    )
    b_col = _pick_focus_border_color(root_widget, bg_color=bg, parent_bg=parent_bg)
    attach_focus_ring(
        root_widget,
        bg_widgets=bg_widgets,
        normal_bg=bg,
        focus_bg=focus_bg,
        border_color=b_col,
        thickness=2,
        on_click=_invoke,
    )
    return root_widget


def ensure_canvas_widget_visible(canvas, scroll_frame, widget, pad=8):
    """Cuộn Canvas vừa đủ để widget đang chọn bằng phím mũi tên luôn nằm trong vùng nhìn thấy."""
    try:
        if not (canvas and scroll_frame and widget):
            return
        if not (canvas.winfo_exists() and scroll_frame.winfo_exists() and widget.winfo_exists()):
            return
        scroll_frame.update_idletasks()
        canvas.update_idletasks()
        total_h = max(1, scroll_frame.winfo_reqheight())
        canvas_h = max(1, canvas.winfo_height())
        if total_h <= canvas_h:
            canvas.yview_moveto(0.0)
            return
        wy = widget.winfo_y()
        wh = widget.winfo_height()
        top_frac, bot_frac = canvas.yview()
        vis_top = top_frac * total_h
        vis_bot = bot_frac * total_h
        if wy - pad < vis_top:
            canvas.yview_moveto(max(0.0, float(wy - pad) / total_h))
        elif wy + wh + pad > vis_bot:
            canvas.yview_moveto(min(1.0, float(wy + wh + pad - canvas_h) / total_h))
    except Exception:
        pass


def ensure_expanded_group_visible(canvas, scroll_frame, header_widget, group_rows=(), pad=10):
    """Khi bung một nhóm, đưa khung nhìn tham chiếu ngay tới tiêu đề nhóm và các máy bên trong nhóm đó."""
    try:
        if not (canvas and scroll_frame and header_widget):
            return
        if not (canvas.winfo_exists() and scroll_frame.winfo_exists() and header_widget.winfo_exists()):
            return
        scroll_frame.update_idletasks()
        canvas.update_idletasks()
        req_h = max(1, scroll_frame.winfo_reqheight())
        canv_w = max(1, canvas.winfo_width())
        canv_h = max(1, canvas.winfo_height())
        canvas.configure(scrollregion=(0, 0, canv_w, max(req_h, canv_h)))
        if req_h <= canv_h:
            canvas.yview_moveto(0.0)
            return

        hdr_top = header_widget.winfo_y()
        grp_bot = hdr_top + header_widget.winfo_height()
        for r in group_rows or ():
            if r is not None and r.winfo_exists() and r.winfo_ismapped():
                grp_bot = max(grp_bot, r.winfo_y() + r.winfo_height())

        top_frac = canvas.yview()[0]
        vis_top = top_frac * req_h
        vis_bot = vis_top + canv_h
        block_h = (grp_bot - hdr_top) + pad * 2

        if block_h >= canv_h:
            target_px = hdr_top - pad
        elif hdr_top - pad < vis_top:
            target_px = hdr_top - pad
        elif grp_bot + pad > vis_bot:
            target_px = grp_bot + pad - canv_h
        else:
            return

        max_px = max(0, req_h - canv_h)
        target_px = max(0, min(max_px, target_px))
        canvas.yview_moveto(float(target_px) / float(req_h))
    except Exception:
        pass


def _is_widget_focusable_now(w):
    try:
        if w is None or not w.winfo_exists() or not w.winfo_ismapped():
            return False
        st = str(w.cget("state"))
        if st == "disabled":
            return False
    except Exception:
        pass
    try:
        tf = str(w.cget("takefocus"))
        if tf == "0":
            return False
    except Exception:
        pass
    return True


def enhance_dialog_controls(container, accent_color=None):
    """Tự động gắn hiệu ứng focus rõ nét và phím Enter cho Button/Entry/Checkbutton bên trong container."""
    found = []

    def _walk(w):
        for ch in w.winfo_children():
            if getattr(ch, "_focus_strip", False):
                continue
            if isinstance(ch, (tk.Button, ttk.Button)):
                if isinstance(ch, tk.Button):
                    attach_focus_ring(ch, thickness=2)
                def _btn_ret(e, b=ch):
                    try:
                        if str(b.cget("state")) != "disabled":
                            b.invoke()
                    except Exception:
                        pass
                    return "break"
                ch.bind("<Return>", _btn_ret)
                ch.bind("<KP_Enter>", _btn_ret)
                found.append(ch)
            elif isinstance(ch, (tk.Checkbutton, ttk.Checkbutton, tk.Radiobutton, ttk.Radiobutton)):
                if isinstance(ch, (tk.Checkbutton, tk.Radiobutton)):
                    attach_focus_ring(ch, thickness=1)
                found.append(ch)
            elif isinstance(ch, (tk.Entry, ttk.Entry)):
                if isinstance(ch, tk.Entry):
                    try:
                        bd_val = int(float(ch.cget("bd")))
                        ht_val = int(float(ch.cget("highlightthickness")))
                        ebg = ch.cget("bg")
                        fcol = accent_color or _pick_focus_border_color(ch, ebg)
                        if str(ch.cget("relief")) == "flat" and ht_val == 0 and bd_val >= 2:
                            ch.configure(
                                bd=max(1, bd_val - 1),
                                highlightthickness=1,
                                highlightbackground=ebg,
                                highlightcolor=fcol,
                            )
                    except Exception:
                        pass
                found.append(ch)
            elif getattr(ch, "_is_kb_focusable", False):
                found.append(ch)
                continue
            _walk(ch)

    try:
        _walk(container)
    except Exception:
        pass
    return found


def setup_dialog_keyboard(
    dialog,
    on_enter=None,
    on_escape=None,
    default_focus=None,
    parent=None,
    restore_focus_to=None,
    nav_widgets=None,
    accent_color=None,
    enable_up_down=True,
    enable_left_right=True,
):
    """Thiết lập đầy đủ điều hướng bàn phím (Enter, Esc, Tab, Up/Down, Left/Right) và hoàn trả focus khi đóng dialog."""
    if dialog is None:
        return

    if parent is None:
        try:
            p_name = dialog.winfo_parent()
            if p_name:
                parent = dialog.nametowidget(p_name)
        except Exception:
            parent = None

    prev_focus = restore_focus_to
    if prev_focus is None and parent is not None:
        try:
            pf = parent.focus_get()
            if pf is not None and str(pf).startswith(str(parent)):
                prev_focus = pf
        except Exception:
            prev_focus = None

    discovered = enhance_dialog_controls(dialog, accent_color=accent_color)

    def _get_controls():
        src = nav_widgets if nav_widgets is not None else discovered
        return [w for w in src if _is_widget_focusable_now(w)]

    def _focus_widget(target):
        try:
            if target is None or not target.winfo_exists():
                return
            target.focus_set()
        except Exception:
            pass

    def _move_focus(delta):
        ctrls = _get_controls()
        if not ctrls:
            return "break"
        cur = None
        try:
            cur = dialog.focus_get()
        except Exception:
            pass
        if cur in ctrls:
            idx = (ctrls.index(cur) + delta) % len(ctrls)
        else:
            idx = 0 if delta > 0 else len(ctrls) - 1
        _focus_widget(ctrls[idx])
        return "break"

    def _handle_return(event):
        w = None
        try:
            w = dialog.focus_get()
        except Exception:
            pass
        if w is not None:
            if isinstance(w, (tk.Button, ttk.Button)):
                try:
                    if str(w.cget("state")) != "disabled":
                        w.invoke()
                except Exception:
                    pass
                return "break"
            kb_inv = getattr(w, "_kb_invoke", None)
            if callable(kb_inv):
                kb_inv(event)
                return "break"
            if isinstance(w, tk.Text):
                try:
                    if str(w.cget("takefocus")) != "0":
                        return None
                except Exception:
                    return None
        if callable(on_enter):
            on_enter()
            return "break"
        return None

    def _handle_escape(_event):
        if callable(on_escape):
            on_escape()
            return "break"
        return None

    def _handle_up(event):
        if not enable_up_down:
            return None
        w = event.widget
        if isinstance(w, tk.Text):
            try:
                if str(w.cget("takefocus")) != "0":
                    return None
            except Exception:
                return None
        return _move_focus(-1)

    def _handle_down(event):
        if not enable_up_down:
            return None
        w = event.widget
        if isinstance(w, tk.Text):
            try:
                if str(w.cget("takefocus")) != "0":
                    return None
            except Exception:
                return None
        return _move_focus(1)

    def _handle_left(event):
        if not enable_left_right:
            return None
        w = event.widget
        if isinstance(w, (tk.Entry, ttk.Entry, tk.Text)):
            return None
        return _move_focus(-1)

    def _handle_right(event):
        if not enable_left_right:
            return None
        w = event.widget
        if isinstance(w, (tk.Entry, ttk.Entry, tk.Text)):
            return None
        return _move_focus(1)

    if on_enter is not None or discovered:
        dialog.bind("<Return>", _handle_return)
        dialog.bind("<KP_Enter>", _handle_return)
    if on_escape is not None:
        dialog.bind("<Escape>", _handle_escape)
    if enable_up_down:
        dialog.bind("<Up>", _handle_up)
        dialog.bind("<Down>", _handle_down)
    if enable_left_right:
        dialog.bind("<Left>", _handle_left)
        dialog.bind("<Right>", _handle_right)

    def _restore_parent_focus(_event=None):
        if parent is None:
            return
        def _do_restore():
            try:
                if not parent.winfo_exists() or parent.state() == "withdrawn":
                    return
                parent.lift()
                cand = prev_focus or getattr(parent, "_default_kb_focus", None)
                if cand is not None and cand.winfo_exists():
                    cand.focus_set()
                else:
                    parent.focus_force()
            except Exception:
                pass
        try:
            parent.after(15, _do_restore)
        except Exception:
            pass

    dialog.bind("<Destroy>", lambda e: _restore_parent_focus(e) if e.widget is dialog else None, add="+")

    target_init = default_focus
    if target_init is None and discovered:
        target_init = discovered[0]
    dialog._default_kb_focus = target_init

    def _apply_initial_focus():
        try:
            if not dialog.winfo_exists():
                return
            dialog.lift()
            if target_init is not None and target_init.winfo_exists():
                target_init.focus_set()
            else:
                dialog.focus_force()
        except Exception:
            pass

    _apply_initial_focus()
    try:
        dialog.after(35, _apply_initial_focus)
    except Exception:
        pass


def setup_panel_keyboard_nav(root_win, ordered_widgets, default_focus=None):
    """Điều hướng phím mũi tên Lên/Xuống/Trái/Phải và Tab mượt mà cho các ô và nút trên cửa sổ chính."""
    for w in ordered_widgets:
        if isinstance(w, (tk.Entry, tk.Button, tk.Checkbutton)):
            if isinstance(w, tk.Button):
                attach_focus_ring(w, thickness=2)
            elif isinstance(w, tk.Checkbutton):
                attach_focus_ring(w, thickness=1)

    def _avail():
        return [w for w in ordered_widgets if _is_widget_focusable_now(w)]

    def _step(cur_w, delta):
        lst = _avail()
        if not lst:
            return "break"
        idx = (lst.index(cur_w) + delta) % len(lst) if cur_w in lst else (0 if delta > 0 else len(lst) - 1)
        try:
            lst[idx].focus_set()
        except Exception:
            pass
        return "break"

    for w in ordered_widgets:
        try:
            w.bind("<Down>", lambda e, cw=w: _step(cw, 1))
            w.bind("<Up>", lambda e, cw=w: _step(cw, -1))
            w.bind("<Tab>", lambda e, cw=w: _step(cw, 1))
            w.bind("<Shift-Tab>", lambda e, cw=w: _step(cw, -1))
            if sys.platform != "win32":
                w.bind("<ISO_Left_Tab>", lambda e, cw=w: _step(cw, -1))
            if not isinstance(w, (tk.Entry, ttk.Entry)):
                w.bind("<Right>", lambda e, cw=w: _step(cw, 1))
                w.bind("<Left>", lambda e, cw=w: _step(cw, -1))
        except Exception:
            pass

    init_w = default_focus or (ordered_widgets[0] if ordered_widgets else None)
    if init_w is not None:
        root_win._default_kb_focus = init_w
        try:
            root_win.after(60, lambda: init_w.focus_set() if init_w.winfo_exists() else None)
        except Exception:
            pass


def apply_row_online_state(row_root, is_online, base_bg, fg_names=()):
    """Làm tối dòng máy tính OFFLINE để phân biệt trực quan (theo mọi giao diện),
    đồng thời bảo toàn màu highlight nếu dòng đang được chọn bằng bàn phím.
    """
    try:
        if row_root is None or not row_root.winfo_exists():
            return
        row_root._row_is_online = is_online
        row_root._row_base_bg = base_bg
        if fg_names:
            row_root._row_fg_names = fg_names
        else:
            fg_names = getattr(row_root, "_row_fg_names", ())

        off_bg = _blend_hex(row_root, base_bg, "#000000", 0.22)
        sel_bg = getattr(row_root, "_row_sel_bg", None)
        is_sel = bool(getattr(row_root, "_kb_selected", False)) and bool(sel_bg)

        want_off = (is_online is False) and not is_sel
        target_bg = sel_bg if is_sel else (off_bg if want_off else base_bg)

        recognized_rgbs = {row_root.winfo_rgb(base_bg), row_root.winfo_rgb(off_bg)}
        if sel_bg:
            try:
                recognized_rgbs.add(row_root.winfo_rgb(sel_bg))
            except Exception:
                pass

        fg_rgbs = set()
        for n in fg_names:
            try:
                fg_rgbs.add(row_root.winfo_rgb(n))
            except Exception:
                pass

        def walk(w):
            if getattr(w, "_focus_strip", False):
                return
            try:
                cur_bg = w.cget("bg")
                cur_rgb = w.winfo_rgb(cur_bg)
            except Exception:
                cur_bg, cur_rgb = None, None
            if cur_rgb is not None and cur_rgb in recognized_rgbs:
                try:
                    w.config(bg=target_bg)
                except Exception:
                    pass
                if isinstance(w, tk.Label):
                    try:
                        orig = getattr(w, "_orig_fg", None)
                        cur_fg = w.cget("fg")
                        if orig is None and w.winfo_rgb(cur_fg) in fg_rgbs:
                            w._orig_fg = orig = cur_fg
                        if orig is not None:
                            w.config(fg=_blend_hex(w, orig, off_bg, 0.35) if want_off else orig)
                    except Exception:
                        pass
            for ch in w.winfo_children():
                walk(ch)

        walk(row_root)
    except Exception:
        pass


def resolve_open_group_colors(app_or_owner=None, base_bg="#2A2A35", accent_color="#00ADB5"):
    """Lấy cặp màu (open_bg, open_fg) cho tiêu đề nhóm đang mở trên mọi giao diện."""
    open_bg = getattr(app_or_owner, "group_open_bg", None) if app_or_owner is not None else None
    open_fg = getattr(app_or_owner, "group_open_fg", None) if app_or_owner is not None else None
    if open_bg and open_fg:
        return open_bg, open_fg
    from gui.themes import compute_open_group_colors
    return compute_open_group_colors(base_bg, accent_color)


def apply_group_header_style(
    header_widget,
    is_expanded,
    collapsed_bg="#2A2A35",
    collapsed_fg="#A0A0B0",
    open_bg="#346B78",
    open_fg="#FFFFFF",
    accent_color="#00ADB5",
):
    """Áp dụng màu nền highlight luôn hiện diện cho nhóm đang mở (và màu thường cho nhóm thu gọn)."""
    try:
        if header_widget is None or not header_widget.winfo_exists():
            return
        expanded = bool(is_expanded)
        header_widget._group_expanded = expanded
        base_bg = open_bg if expanded else collapsed_bg
        base_fg = open_fg if expanded else collapsed_fg
        header_widget._base_hdr_bg = base_bg
        header_widget._base_hdr_fg = base_fg
        header_widget._orig_hdr_bg = base_bg
        header_widget._orig_hdr_fg = base_fg

        if getattr(header_widget, "_kb_selected", False):
            set_row_selected(header_widget, True, base_bg=collapsed_bg, accent_color=accent_color)
        else:
            header_widget.config(bg=base_bg, fg=base_fg)
    except Exception:
        pass


def set_row_selected(row_root, is_selected, is_online=None, base_bg="#2A2A35", accent_color="#00ADB5", fg_names=()):
    """Bật/tắt highlight trực quan cho một dòng máy tính hoặc tiêu đề nhóm khi điều hướng bằng phím mũi tên."""
    try:
        if row_root is None or not row_root.winfo_exists():
            return
        row_root._kb_selected = bool(is_selected)

        if getattr(row_root, "is_group_header", False):
            base_hdr_bg = getattr(row_root, "_base_hdr_bg", None)
            if base_hdr_bg is None:
                base_hdr_bg = getattr(row_root, "_orig_hdr_bg", None) or row_root.cget("bg")
                row_root._base_hdr_bg = base_hdr_bg
            base_hdr_fg = getattr(row_root, "_base_hdr_fg", None)
            if base_hdr_fg is None:
                base_hdr_fg = getattr(row_root, "_orig_hdr_fg", None) or row_root.cget("fg")
                row_root._base_hdr_fg = base_hdr_fg

            if is_selected and not getattr(row_root, "_group_expanded", False):
                sel_hdr_bg = _blend_hex(row_root, base_hdr_bg, accent_color, 0.20)
                row_root.config(bg=sel_hdr_bg, fg=accent_color)
            else:
                row_root.config(bg=base_hdr_bg, fg=base_hdr_fg)
        else:
            lum = _color_luminance(row_root, base_bg)
            if lum > 150:
                tinted = _blend_hex(row_root, base_bg, accent_color, 0.30)
                sel_bg = _blend_hex(row_root, tinted, "#000000", 0.10)
            else:
                sel_bg = _blend_hex(row_root, base_bg, accent_color, 0.32)
            row_root._row_sel_bg = sel_bg

            eff_online = is_online if is_online is not None else getattr(row_root, "_row_is_online", True)
            apply_row_online_state(row_root, eff_online, base_bg, fg_names)

        strips = getattr(row_root, "_sel_strips", None)
        if is_selected:
            strip_col = accent_color
            if getattr(row_root, "is_group_header", False) and getattr(row_root, "_group_expanded", False):
                hdr_bg_now = getattr(row_root, "_base_hdr_bg", base_bg)
                if abs(_color_luminance(row_root, hdr_bg_now) - _color_luminance(row_root, accent_color)) < 45:
                    strip_col = getattr(row_root, "_base_hdr_fg", accent_color)
            if not strips:
                strips = []
                for _ in range(4):
                    s = tk.Frame(row_root, bg=strip_col, bd=0, highlightthickness=0, takefocus=0)
                    s._focus_strip = True
                    strips.append(s)
                row_root._sel_strips = strips
            s_top, s_bot, s_left, s_right = strips
            for s in strips:
                s.config(bg=strip_col)
            s_top.place(relx=0.0, rely=0.0, relwidth=1.0, height=2)
            s_bot.place(relx=0.0, rely=1.0, anchor="sw", relwidth=1.0, height=2)
            s_left.place(relx=0.0, rely=0.0, relheight=1.0, width=4)
            s_right.place(relx=1.0, rely=0.0, anchor="ne", relheight=1.0, width=2)
            for s in strips:
                s.lift()
        elif strips:
            for s in strips:
                try:
                    s.place_forget()
                except Exception:
                    pass
    except Exception:
        pass

if getattr(sys, 'frozen', False):
    app_dir = os.path.dirname(sys.executable)
else:
    app_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

class PremiumProgressBar(tk.Canvas):
    def __init__(self, parent, width=320, height=12, bg="#15151B", fg="#00ADB5", **kwargs):
        super().__init__(parent, width=width, height=height, bg=parent["bg"], highlightthickness=0, bd=0, **kwargs)
        self.width = width
        self.height = height
        self.fg = fg
        self.bg_color = bg
        
        self.draw_rounded_rect(0, 0, width, height, radius=5, fill=bg)
        self.fill_id = None

    def draw_rounded_rect(self, x1, y1, x2, y2, radius=5, **kwargs):
        points = [x1+radius, y1,
                  x2-radius, y1,
                  x2, y1,
                  x2, y1+radius,
                  x2, y2-radius,
                  x2, y2,
                  x2-radius, y2,
                  x1+radius, y2,
                  x1, y2,
                  x1, y2-radius,
                  x1, y1+radius,
                  x1, y1]
        return self.create_polygon(points, **kwargs, smooth=True)

    def set_progress(self, percent):
        percent = max(0, min(100, percent))
        if self.fill_id:
            self.delete(self.fill_id)
            self.fill_id = None
            
        if percent > 0:
            fill_width = int(self.width * (percent / 100))
            if fill_width > 10:
                self.fill_id = self.draw_rounded_rect(0, 0, fill_width, self.height, radius=5, fill=self.fg)
            elif fill_width > 0:
                self.fill_id = self.create_rectangle(0, 0, fill_width, self.height, fill=self.fg, width=0)

from os_utils.ui import get_file_icon_as_image

class ClassicCopyDialog(tk.Toplevel):
    def __init__(self, parent, filename, source_info, dest_info, has_multiple=False, on_done=None, owner_hwnd=None):
        super().__init__(parent)
        self.withdraw()
        # Viewer full-app: parent là Tk ẩn — dialog phải hiện trên cửa sổ pygame.
        self.owner_hwnd = None
        try:
            if owner_hwnd:
                self.owner_hwnd = int(owner_hwnd)
                if sys.platform == "win32":
                    import ctypes
                    user32 = ctypes.windll.user32
                    if not user32.IsWindow(self.owner_hwnd) or not user32.IsWindowVisible(self.owner_hwnd) or user32.IsIconic(self.owner_hwnd):
                        self.owner_hwnd = None
        except Exception:
            self.owner_hwnd = None
        self.resizable(False, False)
        self.configure(bg="#FFFFFF")
        # Không dùng Toplevel.geometry (bị DPI scale) — layout 520x420 bị vỡ, không bấm được.
        
        try:
            icon_path = os.path.join(app_dir, "app_icon.png")
            if os.path.exists(icon_path):
                icon_img = ImageTk.PhotoImage(Image.open(icon_path))
                self.iconphoto(False, icon_img)
                self._dialog_icon_img = icon_img
        except Exception:
            pass
            
        self.choice = None
        self.has_multiple = has_multiple
        self._on_done = on_done
        self._finished = False
        # Chặn click Paste/menu còn sót — nếu không dialog nháy rồi chọn Replace ngay.
        self._clicks_armed = False
        try:
            log_overwrite_conflict(
                f"ClassicCopyDialog.__init__ file={filename!r} "
                f"dest={(dest_info or {}).get('path')!r} has_multiple={has_multiple}"
            )
        except Exception:
            pass
        
        self.attributes("-topmost", True)
        self.title(_("Sao chép tệp"))
        _sc = ui_scale(self)
        S = lambda v: int(round(v * _sc))
        
        lbl_title = tk.Label(
            self, text=_("Đã có tệp cùng tên trong thư mục này."),
            font=(_DIALOG_FONT, 12), fg="#003399", bg="#FFFFFF", anchor="w", justify=tk.LEFT,
            wraplength=S(460)
        )
        lbl_title.pack(fill=tk.X, padx=S(24), pady=(S(20), S(2)))
        
        lbl_sub = tk.Label(
            self, text=_("Bấm vào tệp bạn muốn giữ lại"),
            font=(_DIALOG_FONT, 9), fg="#000000", bg="#FFFFFF", anchor="w", wraplength=S(460)
        )
        lbl_sub.pack(fill=tk.X, padx=S(24), pady=(0, S(15)))
        
        def format_size(bytes_size):
            if bytes_size < 1024:
                return f"{bytes_size} bytes"
            elif bytes_size < 1024 * 1024:
                return f"{bytes_size / 1024:.1f} KB"
            else:
                return f"{bytes_size / (1024 * 1024):.1f} MB"

        def format_time(timestamp):
            try:
                import datetime
                from core.i18n import _current_lang
                dt = datetime.datetime.fromtimestamp(timestamp)
                if _current_lang == "en":
                    return dt.strftime("%m/%d/%Y %I:%M %p")
                return dt.strftime("%d/%m/%Y %H:%M")
            except:
                return _("Không xác định")
                
        def format_location_info(file_path):
            if not file_path:
                return _("Vị trí không xác định")
            parent_dir = os.path.dirname(file_path)
            parent_folder_name = os.path.basename(parent_dir)
            if not parent_folder_name:
                parent_folder_name = parent_dir
            return f"{parent_folder_name} ({parent_dir})"
            
        src_icon_img = get_file_icon_as_image(filename)
        dest_icon_img = get_file_icon_as_image(dest_info.get("path", filename))
        
        self.src_icon = ImageTk.PhotoImage(src_icon_img) if src_icon_img else None
        self.dest_icon = ImageTk.PhotoImage(dest_icon_img) if dest_icon_img else None
        
        def get_all_children(w):
            children = [w]
            for child in w.winfo_children():
                children.extend(get_all_children(child))
            return children
            
        def setup_command_link(frame, action_val):
            normal_bg = "#FFFFFF"
            hover_bg = "#E5F1FB"
            normal_border = "#FFFFFF"
            hover_border = "#0066CC"
            
            frame.configure(background=normal_bg, highlightbackground=normal_border, highlightcolor=hover_border, highlightthickness=1, bd=0, takefocus=1)
            frame._is_kb_focusable = True

            def _set_highlight(active):
                bg_c = hover_bg if active else normal_bg
                bd_c = hover_border if active else normal_border
                frame.configure(background=bg_c, highlightbackground=bd_c)
                for child in get_all_children(frame):
                    if child is not frame:
                        try: child.configure(background=bg_c)
                        except: pass

            def on_enter(event):
                _set_highlight(True)
                    
            def on_leave(event):
                x, y = frame.winfo_pointerx() - frame.winfo_rootx(), frame.winfo_pointery() - frame.winfo_rooty()
                if x < 0 or x >= frame.winfo_width() or y < 0 or y >= frame.winfo_height():
                    has_focus = False
                    try:
                        has_focus = (self.focus_get() is frame)
                    except Exception:
                        pass
                    if not has_focus:
                        _set_highlight(False)
                        
            def on_click(event):
                if not getattr(self, "_clicks_armed", False):
                    return "break"
                self._finish(action_val)

            def on_kb_invoke(_event=None):
                self._clicks_armed = True
                self._finish(action_val)
                return "break"

            frame._kb_invoke = on_kb_invoke
            frame.bind("<FocusIn>", lambda e: _set_highlight(True) if e.widget is frame else None)
            frame.bind("<FocusOut>", lambda e: _set_highlight(False) if e.widget is frame else None)
            frame.bind("<Return>", on_kb_invoke)
            frame.bind("<KP_Enter>", on_kb_invoke)
            frame.bind("<space>", on_kb_invoke)
                
            for w in get_all_children(frame):
                w.bind("<Enter>", on_enter)
                w.bind("<Leave>", on_leave)
                # ButtonRelease: tránh nhận ButtonDown từ thao tác Paste trước đó.
                w.bind("<Button-1>", lambda e: "break" if not self._clicks_armed else None)
                w.bind("<ButtonRelease-1>", on_click)
                w.configure(cursor="hand2")
                
        def make_arrow(parent):
            # Vẽ mũi tên trên Canvas (glyph "→" font 16pt lệch baseline so với tiêu đề 10pt).
            return tk.Canvas(parent, width=S(22), height=S(20), bg="#FFFFFF", highlightthickness=0, bd=0)

        def draw_arrow(cv, ref_label):
            # Cao bằng dòng tiêu đề, mũi tên nằm giữa dòng.
            cv.update_idletasks()
            h = max(int(ref_label.winfo_reqheight() or 0), S(12))
            w = S(22)
            cv.configure(height=h, width=w)
            cv.delete("all")
            y = h / 2.0 + S(1)  # bù nhẹ: tâm chữ thị giác thấp hơn tâm line-height
            cv.create_line(
                S(2), y, w - S(2), y, fill="#0066CC", width=max(2, S(2)),
                arrow=tk.LAST, arrowshape=(S(8), S(9), S(4)), capstyle=tk.ROUND,
            )

        # Link 1: Copy and Replace
        link1 = tk.Frame(self, bg="#FFFFFF")
        link1.pack(fill=tk.X, padx=S(24), pady=S(5))
        
        lbl_arrow1 = make_arrow(link1)
        lbl_arrow1.pack(side=tk.LEFT, anchor="n", padx=(S(5), S(5)))
        
        right_content1 = tk.Frame(link1, bg="#FFFFFF")
        right_content1.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)
        
        lbl_title1 = tk.Label(right_content1, text=_("Sao chép và thay thế"), font=(_DIALOG_FONT, 10, "bold"), fg="#0066CC", bg="#FFFFFF", anchor="w")
        lbl_title1.pack(fill=tk.X)
        draw_arrow(lbl_arrow1, lbl_title1)
        
        lbl_desc1 = tk.Label(right_content1, text=_("Thay thế tệp trong thư mục đích bằng tệp bạn đang sao chép:"), font=(_DIALOG_FONT, 9), fg="#000000", bg="#FFFFFF", anchor="w", wraplength=S(430), justify=tk.LEFT)
        lbl_desc1.pack(fill=tk.X, pady=(0, S(5)))
        
        info_frame1 = tk.Frame(right_content1, bg="#FFFFFF")
        info_frame1.pack(fill=tk.X, padx=(S(10), 0))
        
        if self.src_icon:
            lbl_icon1 = tk.Label(info_frame1, image=self.src_icon, bg="#FFFFFF")
            lbl_icon1.pack(side=tk.LEFT, anchor="n", padx=(0, S(10)))
            
        info_text1 = tk.Frame(info_frame1, bg="#FFFFFF")
        info_text1.pack(side=tk.LEFT, fill=tk.X)
        
        target_loc_path = dest_info.get("path") or source_info.get("path")
        tk.Label(info_text1, text=filename, font=(_DIALOG_FONT, 9, "bold"), fg="#000000", bg="#FFFFFF", anchor="w").pack(fill=tk.X)
        tk.Label(info_text1, text=format_location_info(target_loc_path), font=(_DIALOG_FONT, 9), fg="#555555", bg="#FFFFFF", anchor="w").pack(fill=tk.X)
        tk.Label(info_text1, text=_("Kích thước: {size}").format(size=format_size(source_info.get("size", 0))), font=(_DIALOG_FONT, 9), fg="#555555", bg="#FFFFFF", anchor="w").pack(fill=tk.X)
        tk.Label(info_text1, text=_("Ngày sửa đổi: {date}").format(date=format_time(source_info.get("mtime", 0))), font=(_DIALOG_FONT, 9), fg="#555555", bg="#FFFFFF", anchor="w").pack(fill=tk.X)
        
        setup_command_link(link1, "replace")
        
        # Link 2: Don't Copy
        link2 = tk.Frame(self, bg="#FFFFFF")
        link2.pack(fill=tk.X, padx=S(24), pady=S(5))
        
        lbl_arrow2 = make_arrow(link2)
        lbl_arrow2.pack(side=tk.LEFT, anchor="n", padx=(S(5), S(5)))
        
        right_content2 = tk.Frame(link2, bg="#FFFFFF")
        right_content2.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)
        
        lbl_title2 = tk.Label(right_content2, text=_("Không sao chép"), font=(_DIALOG_FONT, 10, "bold"), fg="#0066CC", bg="#FFFFFF", anchor="w")
        lbl_title2.pack(fill=tk.X)
        draw_arrow(lbl_arrow2, lbl_title2)
        
        lbl_desc2 = tk.Label(right_content2, text=_("Không thay đổi tệp nào. Giữ nguyên tệp trong thư mục đích:"), font=(_DIALOG_FONT, 9), fg="#000000", bg="#FFFFFF", anchor="w", wraplength=S(430), justify=tk.LEFT)
        lbl_desc2.pack(fill=tk.X, pady=(0, S(5)))
        
        info_frame2 = tk.Frame(right_content2, bg="#FFFFFF")
        info_frame2.pack(fill=tk.X, padx=(S(10), 0))
        
        if self.dest_icon:
            lbl_icon2 = tk.Label(info_frame2, image=self.dest_icon, bg="#FFFFFF")
            lbl_icon2.pack(side=tk.LEFT, anchor="n", padx=(0, S(10)))
            
        info_text2 = tk.Frame(info_frame2, bg="#FFFFFF")
        info_text2.pack(side=tk.LEFT, fill=tk.X)
        
        tk.Label(info_text2, text=filename, font=(_DIALOG_FONT, 9, "bold"), fg="#000000", bg="#FFFFFF", anchor="w").pack(fill=tk.X)
        tk.Label(info_text2, text=format_location_info(dest_info.get("path")), font=(_DIALOG_FONT, 9), fg="#555555", bg="#FFFFFF", anchor="w").pack(fill=tk.X)
        tk.Label(info_text2, text=_("Kích thước: {size}").format(size=format_size(dest_info.get("size", 0))), font=(_DIALOG_FONT, 9), fg="#555555", bg="#FFFFFF", anchor="w").pack(fill=tk.X)
        tk.Label(info_text2, text=_("Ngày sửa đổi: {date}").format(date=format_time(dest_info.get("mtime", 0))), font=(_DIALOG_FONT, 9), fg="#555555", bg="#FFFFFF", anchor="w").pack(fill=tk.X)
        
        setup_command_link(link2, "skip")
        
        sep = tk.Frame(self, height=1, bg="#D0D0D0", bd=0)
        sep.pack(fill=tk.X, side=tk.BOTTOM, pady=(0, 0))
        
        bottom_bar = tk.Frame(self, bg="#F0F0F0", height=S(48))
        bottom_bar.pack(fill=tk.X, side=tk.BOTTOM)
        bottom_bar.pack_propagate(False)
        
        self.var_all = tk.BooleanVar()
        if has_multiple:
            chk = tk.Checkbutton(
                bottom_bar, text=_("Áp dụng cho mọi xung đột"), font=(_DIALOG_FONT, 9),
                variable=self.var_all, bg="#F0F0F0", activebackground="#F0F0F0", bd=0
            )
            chk.pack(side=tk.LEFT, padx=S(24), pady=S(10))
            
        btn_cancel = tk.Button(
            bottom_bar, text=_("Hủy"), font=(_DIALOG_FONT, 9), width=10,
            bg="#E1E1E1", fg="#000000", relief=tk.FLAT, bd=1, highlightthickness=0,
            command=self.on_cancel
        )
        btn_cancel.pack(side=tk.RIGHT, padx=S(24), pady=S(10))
        
        def btn_enter(event):
            btn_cancel.configure(bg="#E5F1FB", bd=1)
        def btn_leave(event):
            btn_cancel.configure(bg="#E1E1E1", bd=1)
        btn_cancel.bind("<Enter>", btn_enter)
        btn_cancel.bind("<Leave>", btn_leave)
        # Chặn Hủy nhận click Paste sót (đóng dialog ngay → không hỏi).
        def _cancel_click(event=None):
            if not getattr(self, "_clicks_armed", False):
                return "break"
            self.on_cancel()
        btn_cancel.configure(command=self.on_cancel)
        btn_cancel.bind("<Button-1>", lambda e: "break" if not getattr(self, "_clicks_armed", False) else None)
        btn_cancel.bind("<ButtonRelease-1>", _cancel_click)
        
        self.protocol("WM_DELETE_WINDOW", self.on_cancel)
        nav_items = [link1, link2]
        if has_multiple:
            nav_items.append(chk)
        nav_items.append(btn_cancel)
        setup_dialog_keyboard(
            self,
            on_enter=lambda: link1._kb_invoke(),
            on_escape=self.on_cancel,
            default_focus=link1,
            parent=parent,
            nav_widgets=nav_items,
            accent_color="#0066CC",
        )

        # Chiều cao theo nội dung (DPI 125%/150% làm 520x420 cắt mất nút Hủy).
        self.update_idletasks()
        w = max(int(self.winfo_reqwidth() or 0), S(520))
        h = max(int(self.winfo_reqheight() or 0) + S(8), S(360))
        ws = int(self.winfo_screenwidth() or w)
        hs = int(self.winfo_screenheight() or h)
        w = min(w, max(400, ws - 40))
        h = min(h, max(320, hs - 80))
        x = max(0, (ws - w) // 2)
        y = max(0, (hs - h) // 2)
        geo = "%dx%d+%d+%d" % (w, h, x, y)
        try:
            self.tk.call("wm", "geometry", self._w, geo)
        except Exception:
            self.geometry(geo)
        try:
            self.attributes("-alpha", 1.0)
        except Exception:
            pass
        self.deiconify()
        self.lift()
        self.focus_force()
        try:
            self.grab_set()
        except Exception:
            pass
        try:
            from gui.window_icon import set_dialog_app_icon
            set_dialog_app_icon(self)
        except Exception:
            pass
        self._apply_owner()
        self._force_show_over_owner()
        try:
            self.after(0, self._force_show_over_owner)
            self.after(80, self._force_show_over_owner)
        except Exception:
            pass
        # Chỉ nhận click sau khi chuột đã nhả + grace — tránh Paste menu tự chọn Replace.
        self.after(50, self._arm_clicks_when_idle)

    def _hwnd(self):
        try:
            return int(self.frame(), 16)
        except Exception:
            return 0

    def _apply_owner(self):
        """Gắn dialog thuộc cửa sổ viewer — không bị pygame che / parent Tk ẩn nuốt."""
        if not self.owner_hwnd or sys.platform != "win32":
            return
        hwnd = self._hwnd()
        if not hwnd:
            return
        try:
            import ctypes
            user32 = ctypes.windll.user32
            owner = int(self.owner_hwnd)
            if not user32.IsWindow(owner) or not user32.IsWindowVisible(owner) or user32.IsIconic(owner):
                return
            GWLP_HWNDPARENT = -8
            if ctypes.sizeof(ctypes.c_void_p) == 8:
                ctypes.windll.user32.SetWindowLongPtrW(
                    ctypes.c_void_p(hwnd), GWLP_HWNDPARENT, ctypes.c_void_p(owner)
                )
            else:
                ctypes.windll.user32.SetWindowLongW(hwnd, GWLP_HWNDPARENT, owner)
        except Exception:
            pass

    def _force_show_over_owner(self):
        try:
            if not self.winfo_exists():
                return
            self.attributes("-alpha", 1.0)
            self.attributes("-topmost", True)
            self.deiconify()
            self.lift()
            self.focus_force()
        except Exception:
            pass
        if sys.platform != "win32":
            return
        try:
            import ctypes
            hwnd = self._hwnd()
            if not hwnd:
                return
            user32 = ctypes.windll.user32
            HWND_TOPMOST = -1
            SWP_NOSIZE = 0x0001
            SWP_NOMOVE = 0x0002
            SWP_SHOWWINDOW = 0x0040
            user32.SetWindowPos(
                ctypes.c_void_p(hwnd), HWND_TOPMOST, 0, 0, 0, 0,
                SWP_NOSIZE | SWP_NOMOVE | SWP_SHOWWINDOW,
            )
            user32.BringWindowToTop(ctypes.c_void_p(hwnd))
            user32.ShowWindow(ctypes.c_void_p(hwnd), 5)
            try:
                user32.SetForegroundWindow(ctypes.c_void_p(hwnd))
            except Exception:
                pass
        except Exception:
            pass
        
    def _arm_clicks_when_idle(self):
        """Chờ LMB/RMB nhả rồi mới cho bấm Replace/Skip/Hủy."""
        if self._finished or not self.winfo_exists():
            return
        try:
            import ctypes
            user32 = ctypes.windll.user32
            lmb = bool(user32.GetAsyncKeyState(0x01) & 0x8000)
            rmb = bool(user32.GetAsyncKeyState(0x02) & 0x8000)
        except Exception:
            lmb = rmb = False
        if lmb or rmb:
            self.after(50, self._arm_clicks_when_idle)
            return
        # Grace thêm: nút vừa nhả vẫn có thể gửi ButtonRelease vào dialog.
        def _arm():
            if self._finished or not self.winfo_exists():
                return
            self._clicks_armed = True
            try:
                log_overwrite_conflict("ClassicCopyDialog clicks ARMED")
            except Exception:
                pass
        self.after(400, _arm)
        
    def _finish(self, action_val):
        if self._finished:
            return
        if action_val != "cancel" and not getattr(self, "_clicks_armed", False):
            try:
                log_overwrite_conflict(
                    f"ClassicCopyDialog IGNORE click (not armed) action={action_val!r}"
                )
            except Exception:
                pass
            return
        self._finished = True
        self.choice = action_val
        try:
            log_overwrite_conflict(
                f"ClassicCopyDialog._finish choice={action_val!r} armed={self._clicks_armed}"
            )
        except Exception:
            pass
        cb = self._on_done
        self._on_done = None
        if cb:
            try:
                cb(action_val)
            except Exception:
                pass
        try:
            self.grab_release()
        except Exception:
            pass
        try:
            self.destroy()
        except Exception:
            pass

    def on_cancel(self):
        # Cho phép đóng bằng X ngay; nút Hủy cần armed (tránh click sót).
        if self._finished:
            return
        self._clicks_armed = True
        self._finish("cancel")

class ConfirmDialog(tk.Toplevel):
    def __init__(self, parent, title, message, on_yes, on_no):
        super().__init__(parent)
        self.title(title)
        self.resizable(False, False)
        self.configure(bg="#1E1E24")
        
        try:
            icon_path = os.path.join(app_dir, "app_icon.png")
            if os.path.exists(icon_path):
                icon_img = ImageTk.PhotoImage(Image.open(icon_path))
                self.iconphoto(False, icon_img)
                self._dialog_icon_img = icon_img
        except Exception:
            pass
            
        # Thiết lập thuộc tính Modal & Topmost
        self.attributes("-topmost", True)
        # Chỉ liên kết transient nếu cửa sổ cha đang hiển thị, nếu không hộp thoại sẽ bị ẩn theo cha.
        if parent and parent.state() != "withdrawn":
            self.transient(parent)
        else:
            # Ép hiển thị vì nếu parent ẩn, Toplevel có thể bị ẩn theo mặc định
            self.deiconify()
            self.lift()
            self.focus_force()
        # Bỏ grab_set() để tránh xung đột Focus & Event routing trên một số hệ thống Windows
        
        lbl_title = tk.Label(self, text=title.upper(), font=(_DIALOG_FONT, 11, "bold"), fg="#00ADB5", bg="#1E1E24")
        lbl_title.pack(pady=(15, 10), padx=20, anchor=tk.W)
        
        lbl_msg = tk.Label(self, text=message, font=(_DIALOG_FONT, 9), fg="#FFFFFF", bg="#1E1E24", justify=tk.LEFT, wraplength=380)
        lbl_msg.pack(pady=(0, 15), padx=20, anchor=tk.W)
        
        btn_frame = tk.Frame(self, bg="#1E1E24")
        btn_frame.pack(fill=tk.X, padx=20, pady=(0, 15), side=tk.BOTTOM)
        
        self.decision_made = False
        self.on_yes_cb = on_yes
        self.on_no_cb = on_no
        
        def _yes():
            self.decision_made = True
            self.destroy()
            if self.on_yes_cb:
                self.on_yes_cb()
                
        def _no():
            self.decision_made = True
            self.destroy()
            if self.on_no_cb:
                self.on_no_cb()
                
        btn_yes = tk.Button(
            btn_frame, text=_("Đồng ý (Yes)"), font=(_DIALOG_FONT, 9, "bold"),
            fg="#FFFFFF", bg="#00ADB5", activeforeground="#FFFFFF", activebackground="#008B90",
            relief=tk.FLAT, bd=0, padx=15, pady=6, cursor="hand2", command=_yes
        )
        btn_yes.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        
        btn_no = tk.Button(
            btn_frame, text=_("Bỏ qua (No)"), font=(_DIALOG_FONT, 9, "bold"),
            fg="#FFFFFF", bg="#3A3A4A", activeforeground="#FFFFFF", activebackground="#2A2A35",
            relief=tk.FLAT, bd=0, padx=15, pady=6, cursor="hand2", command=_no
        )
        btn_no.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=(5, 0))
        
        self.protocol("WM_DELETE_WINDOW", _no)
        setup_dialog_keyboard(
            self,
            on_enter=_yes,
            on_escape=_no,
            default_focus=btn_yes,
            parent=parent,
            nav_widgets=[btn_yes, btn_no],
            accent_color="#00ADB5",
        )
        
        self.update_idletasks()
        dialog_w = 420
        dialog_h = 160
        
        parent_x = parent.winfo_x()
        parent_y = parent.winfo_y()
        parent_w = parent.winfo_width()
        parent_h = parent.winfo_height()
        
        x = parent_x + (parent_w - dialog_w) // 2
        y = parent_y + (parent_h - dialog_h) // 2
        self.geometry(f"{dialog_w}x{dialog_h}+{x}+{y}")

class InfoDialog(tk.Toplevel):
    def __init__(self, parent, title, message, button_text=None, show_cancel=False, cancel_text=None, on_ok=None, on_cancel=None, auto_close_sec=None):
        super().__init__(parent)
        self.withdraw()  # Ẩn tạm thời để tránh nháy
        self.title(title)
        self.resizable(False, False)
        self.configure(bg="#1E1E24")
        
        try:
            icon_path = os.path.join(app_dir, "app_icon.png")
            if os.path.exists(icon_path):
                icon_img = ImageTk.PhotoImage(Image.open(icon_path))
                self.iconphoto(False, icon_img)
                self._dialog_icon_img = icon_img
        except Exception:
            pass
            
        self.attributes("-topmost", True)
        if parent and parent.state() != "withdrawn":
            self.transient(parent)
        else:
            self.lift()
            self.focus_force()
        
        lbl_title = tk.Label(self, text=title.upper(), font=(_DIALOG_FONT, 11, "bold"), fg="#00ADB5", bg="#1E1E24")
        lbl_title.pack(pady=(15, 10), padx=20, anchor=tk.W)
        
        lbl_msg = tk.Label(self, text=message, font=(_DIALOG_FONT, 9), fg="#FFFFFF", bg="#1E1E24", justify=tk.LEFT, wraplength=440)
        lbl_msg.pack(pady=(0, 15), padx=20, anchor=tk.W)
        
        btn_frame = tk.Frame(self, bg="#1E1E24")
        btn_frame.pack(fill=tk.X, padx=20, pady=(0, 15), side=tk.BOTTOM)
        
        self._countdown_id = None
        def _ok():
            if self._countdown_id is not None:
                try:
                    self.after_cancel(self._countdown_id)
                except Exception:
                    pass
                self._countdown_id = None
            try:
                self.destroy()
            except Exception:
                pass
            if on_ok:
                on_ok()
                
        def _cancel():
            if self._countdown_id is not None:
                try:
                    self.after_cancel(self._countdown_id)
                except Exception:
                    pass
                self._countdown_id = None
            try:
                self.destroy()
            except Exception:
                pass
            if on_cancel:
                on_cancel()
                
        if button_text is None:
            button_text = _("Đồng ý (OK)")
            
        btn_ok = tk.Button(
            btn_frame, text=button_text, font=(_DIALOG_FONT, 9, "bold"),
            fg="#FFFFFF", bg="#00ADB5", activeforeground="#FFFFFF", activebackground="#008B90",
            relief=tk.FLAT, bd=0, padx=15, pady=6, cursor="hand2", command=_ok
        )
        btn_ok.pack(side=tk.RIGHT if not show_cancel else tk.LEFT, fill=tk.X if show_cancel else tk.NONE, expand=show_cancel, padx=(0, 5) if show_cancel else 0)
        
        nav_btns = [btn_ok]
        if show_cancel:
            if cancel_text is None:
                cancel_text = _("Hủy (Cancel)")
            btn_cancel = tk.Button(
                btn_frame, text=cancel_text, font=(_DIALOG_FONT, 9, "bold"),
                fg="#FFFFFF", bg="#3A3A4A", activeforeground="#FFFFFF", activebackground="#2A2A35",
                relief=tk.FLAT, bd=0, padx=15, pady=6, cursor="hand2", command=_cancel
            )
            btn_cancel.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=(5, 0))
            nav_btns.append(btn_cancel)
            self.protocol("WM_DELETE_WINDOW", _cancel)
        else:
            self.protocol("WM_DELETE_WINDOW", _ok)

        setup_dialog_keyboard(
            self,
            on_enter=_ok,
            on_escape=_cancel if show_cancel else _ok,
            default_focus=btn_ok,
            parent=parent,
            nav_widgets=nav_btns,
            accent_color="#00ADB5",
        )

        if auto_close_sec is not None and auto_close_sec > 0:
            def update_countdown(remaining):
                if not self.winfo_exists():
                    return
                if remaining > 0:
                    try:
                        btn_ok.config(text=f"{button_text} ({remaining}s)")
                    except Exception:
                        pass
                    self._countdown_id = self.after(1000, update_countdown, remaining - 1)
                else:
                    _ok()
            update_countdown(auto_close_sec)
        
        self.update_idletasks()
        # Tính toán chiều cao tự động dựa trên nội dung
        req_height = self.winfo_reqheight()
        dialog_w = 480
        dialog_h = max(160, req_height + 20)
        
        if parent:
            parent_x = parent.winfo_x()
            parent_y = parent.winfo_y()
            parent_w = parent.winfo_width()
            parent_h = parent.winfo_height()
            
            x = parent_x + (parent_w - dialog_w) // 2
            y = parent_y + (parent_h - dialog_h) // 2
            self.geometry(f"{dialog_w}x{dialog_h}+{x}+{y}")
        else:
            self.geometry(f"{dialog_w}x{dialog_h}")
            
        self.deiconify() # Hiển thị sau khi set geometry


class ToolTip(object):
    def __init__(self, widget, text='widget info'):
        self.widget = widget
        self.text = text
        self.widget.bind("<Enter>", self.enter)
        self.widget.bind("<Leave>", self.close)
        self.tw = None

    def enter(self, event=None):
        x = y = 0
        x, y, cx, cy = self.widget.bbox("insert")
        x += self.widget.winfo_rootx() + 25
        y += self.widget.winfo_rooty() + 20
        # creates a toplevel window
        self.tw = tk.Toplevel(self.widget)
        self.tw.wm_overrideredirect(True)
        self.tw.wm_geometry("+%d+%d" % (x, y))
        label = tk.Label(self.tw, text=self.text, justify='left',
                         background='#ffffe0', relief='solid', borderwidth=1,
                         font=(_DIALOG_FONT, "8", "normal"), padx=2, pady=1)
        label.pack(ipadx=1)

    def close(self, event=None):
        if self.tw:
            self.tw.destroy()
            self.tw = None
