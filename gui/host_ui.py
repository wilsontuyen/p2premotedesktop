import tkinter as tk
import sys
from core.i18n import _, get_available_languages, get_language_name
from gui.components import ToolTip


def E(text):
    if sys.platform == "darwin":
        return text
    import platform
    if sys.platform != "win32" or platform.release() in ["7", "8", "8.1"]:
        mapping = {
            "📋": "❐", "📁": "≡", "📡": "⌂", "🔧": "¤",
            "🔄": "↻", "🔍": "⌕", "➕": "+", "❌": "X"
        }
        for k, v in mapping.items():
            text = text.replace(k, v)
    return text


def setup_host_ui(self):
    """Minimal TeamViewer-Host-style UI: ID, password, incoming session only."""
    APP_FONT_NAME = "Segoe UI" if sys.platform == "win32" else "Helvetica"
    EMOJI_FONT_10 = (APP_FONT_NAME, 10)
    EMOJI_FONT_BOLD = (APP_FONT_NAME, 9, "bold")

    def create_flat_button(parent, **kwargs):
        cmd = kwargs.pop("command", None)
        active_bg = kwargs.pop("activebackground", kwargs.get("bg"))
        kwargs.pop("relief", None)
        kwargs.pop("bd", None)
        kwargs.pop("highlightthickness", None)
        kwargs.pop("highlightbackground", None)
        if "cursor" not in kwargs:
            kwargs["cursor"] = "hand2"
        pady = kwargs.pop("pady", 5)
        padx = kwargs.pop("padx", 5)

        text = kwargs.get("text", "")
        if text and len(text) > 2 and text[0] in [
            "📋", "📁", "📡", "🔧", "🔄", "🔍", "➕", "❌", "❐", "≡", "⌂", "¤", "↻", "⌕"
        ]:
            icon_char = text[0]
            label_text = text[1:].strip()
            kwargs.pop("text")

            frame = tk.Frame(parent, bg=kwargs.get("bg"), cursor=kwargs.get("cursor"))
            inner = tk.Frame(frame, bg=kwargs.get("bg"), cursor=kwargs.get("cursor"))
            inner.pack(expand=True, pady=pady)

            font = kwargs.get("font")
            fg = kwargs.get("fg")
            bg = kwargs.get("bg")

            lbl_icon = tk.Label(inner, text=icon_char, font=font, fg=fg, bg=bg)
            lbl_text = tk.Label(inner, text=label_text, font=font, fg=fg, bg=bg)
            lbl_icon.pack(side=tk.LEFT, padx=(padx, 2), pady=(0, 4), anchor=tk.CENTER)
            lbl_text.pack(side=tk.LEFT, padx=(0, padx), anchor=tk.CENTER)

            def on_enter(e):
                frame.config(bg=active_bg)
                inner.config(bg=active_bg)
                lbl_icon.config(bg=active_bg)
                lbl_text.config(bg=active_bg)

            def on_leave(e):
                frame.config(bg=bg)
                inner.config(bg=bg)
                lbl_icon.config(bg=bg)
                lbl_text.config(bg=bg)

            for w in (frame, inner, lbl_icon, lbl_text):
                w.bind("<Enter>", on_enter)
                w.bind("<Leave>", on_leave)
                if cmd:
                    w.bind("<Button-1>", lambda e: cmd())
            return frame

        lbl = tk.Label(parent, pady=pady, padx=padx, **kwargs)
        lbl.bind("<Enter>", lambda e, l=lbl, c=active_bg: l.config(bg=c))
        lbl.bind("<Leave>", lambda e, l=lbl, c=kwargs.get("bg"): l.config(bg=c))
        if cmd:
            lbl.bind("<Button-1>", lambda e, c=cmd: c())
        return lbl

    menubar = tk.Menu(self)

    file_menu = tk.Menu(menubar, tearoff=0)
    file_menu.add_command(label=_("Thoát (Exit)"), command=self.destroy)
    menubar.add_cascade(label=_("File"), menu=file_menu)

    options_menu = tk.Menu(menubar, tearoff=0)
    password_menu = tk.Menu(options_menu, tearoff=0)
    password_menu.add_radiobutton(
        label=_("4 chữ số"),
        variable=self.pass_type_var, value=_("4 chữ số"),
        command=self.refresh_password,
    )
    password_menu.add_radiobutton(
        label=_("5 chữ số"),
        variable=self.pass_type_var, value=_("5 chữ số"),
        command=self.refresh_password,
    )
    password_menu.add_radiobutton(
        label=_("8 ký tự (chữ + số)"),
        variable=self.pass_type_var, value=_("8 ký tự (chữ + số)"),
        command=self.refresh_password,
    )
    password_menu.add_separator()
    password_menu.add_command(
        label=_("Cài mật khẩu cố định..."),
        command=self.open_set_fixed_password_dialog,
    )
    options_menu.add_cascade(label=_("Mật khẩu (Password)"), menu=password_menu)
    options_menu.add_separator()
    options_menu.add_checkbutton(
        label=_("Chạy khi mở máy (Run on Startup)"),
        variable=self.startup_var,
        command=self.toggle_startup,
    )
    options_menu.add_command(
        label=_("Cài Zalo / Điện thoại"),
        command=self.open_set_zalo_phone_dialog,
    )
    options_menu.add_separator()
    options_menu.add_command(
        label=_("Cài đặt máy chủ..."),
        command=self.show_server_settings_dialog,
    )
    if sys.platform == "darwin":
        options_menu.add_separator()
        options_menu.add_command(
            label=_("Sửa lỗi quyền macOS..."),
            command=self.fix_mac_permissions,
        )
    options_menu.add_separator()

    lang_menu = tk.Menu(options_menu, tearoff=0)
    langs = get_available_languages()
    for l in langs:
        lang_menu.add_radiobutton(
            label=get_language_name(l),
            variable=self.current_lang,
            value=l,
            command=self.change_language,
        )
    lang_menu.add_separator()
    lang_menu.add_command(label=_("Xuất tệp ngôn ngữ mẫu..."), command=self.export_lang_template)
    lang_menu.add_command(label=_("Ngôn ngữ riêng của bạn"), command=self.import_custom_language)
    options_menu.add_cascade(label=_("Ngôn ngữ (Language)"), menu=lang_menu)
    options_menu.add_separator()

    theme_menu = tk.Menu(options_menu, tearoff=0)
    theme_menu.add_radiobutton(label=_("Sáng"), variable=self.current_theme, value="light", command=self.change_theme)
    theme_menu.add_radiobutton(label=_("Tối"), variable=self.current_theme, value="dark", command=self.change_theme)
    theme_menu.add_radiobutton(label=_("Xám"), variable=self.current_theme, value="gray", command=self.change_theme)
    theme_menu.add_radiobutton(label=_("Hồng"), variable=self.current_theme, value="pink", command=self.change_theme)
    theme_menu.add_radiobutton(label=_("Pha lê"), variable=self.current_theme, value="crystal", command=self.change_theme)
    theme_menu.add_radiobutton(label=_("Cam"), variable=self.current_theme, value="orange", command=self.change_theme)
    theme_menu.add_radiobutton(label=_("Đỏ"), variable=self.current_theme, value="red", command=self.change_theme)
    theme_menu.add_separator()
    theme_menu.add_radiobutton(label=_("Tùy chỉnh"), variable=self.current_theme, value="custom", command=self.change_theme)
    options_menu.add_cascade(label=_("Giao diện"), menu=theme_menu)
    menubar.add_cascade(label=_("Options"), menu=options_menu)

    help_menu = tk.Menu(menubar, tearoff=0)
    help_menu.add_command(label=_("Zalo"), command=self.open_zalo)
    help_menu.add_command(label=_("Điện thoại"), command=self.open_phone_dialog)
    help_menu.add_command(label=_("About"), command=self.show_about_dialog)
    menubar.add_cascade(label=_("Help"), menu=help_menu)
    self.config(menu=menubar)

    header = tk.Label(
        self, text=_("P2P REMOTE HOST"),
        font=(APP_FONT_NAME, 16, "bold"), fg=self.btn_color, bg=self.bg_color,
    )
    header.pack(pady=(15, 12))

    panel = tk.Frame(self, bg=self.card_color, bd=0, relief=tk.FLAT)
    self._left_panel = panel
    panel.pack(fill=tk.BOTH, expand=True, padx=18, pady=(0, 8))

    lbl_allow = tk.Label(
        panel, text=_("CHO PHÉP ĐIỀU KHIỂN"),
        font=(APP_FONT_NAME, 11, "bold"), fg=self.btn_color, bg=self.card_color,
    )
    lbl_allow.pack(pady=(14, 10))

    tk.Label(
        panel, text=_("Mã ID của bạn:"),
        font=(APP_FONT_NAME, 9), fg=self.text_gray, bg=self.card_color,
    ).pack(anchor=tk.W, padx=18)

    id_frame = tk.Frame(panel, bg=self.card_color)
    self._id_frame = id_frame
    id_frame.pack(fill=tk.X, padx=18, pady=(5, 12))

    self.my_id_label = tk.Label(
        id_frame, text=self.my_id_formatted,
        font=(APP_FONT_NAME, 16, "bold"), fg=self.text_white, bg=self.entry_bg, bd=0, height=1,
    )
    self.my_id_label.pack(side=tk.LEFT, fill=tk.X, expand=True)

    copy_id_btn = create_flat_button(
        id_frame, text=E("📋"), font=EMOJI_FONT_10, fg=self.text_white,
        bg=self.btn_color, activebackground=self.btn_hover, padx=2, pady=1, width=3,
        command=lambda: self.copy_to_clipboard(self.my_id_formatted),
    )
    copy_id_btn.pack(side=tk.RIGHT, padx=(5, 0))
    ToolTip(copy_id_btn, _("Sao chép"))

    tk.Label(
        panel, text=_("Mật khẩu kết nối:"),
        font=(APP_FONT_NAME, 9), fg=self.text_gray, bg=self.card_color,
    ).pack(anchor=tk.W, padx=18)

    pass_frame = tk.Frame(panel, bg=self.card_color)
    self._pass_frame = pass_frame
    pass_frame.pack(fill=tk.X, padx=18, pady=(5, 5))

    self.my_pass_label = tk.Label(
        pass_frame, text=self.my_password,
        font=(APP_FONT_NAME, 16, "bold"), fg=self.text_white, bg=self.entry_bg, bd=0,
    )
    self.my_pass_label.pack(side=tk.LEFT, fill=tk.X, expand=True)

    copy_pass_btn = create_flat_button(
        pass_frame, text=E("📋"), font=EMOJI_FONT_10, fg=self.text_white,
        bg=self.btn_color, activebackground=self.btn_hover, padx=2, pady=1, width=3,
        command=lambda: self.copy_to_clipboard(self.my_password),
    )
    copy_pass_btn.pack(side=tk.RIGHT, padx=(5, 0))
    ToolTip(copy_pass_btn, _("Sao chép"))

    refresh_btn = create_flat_button(
        pass_frame, text="↻", font=(APP_FONT_NAME, 10, "bold"), fg=self.text_white,
        bg=self.btn_color, activebackground=self.btn_hover, padx=2, pady=1, width=3,
        command=self.refresh_password,
    )
    refresh_btn.pack(side=tk.RIGHT, padx=(5, 0))
    ToolTip(refresh_btn, _("Đổi mật khẩu"))

    self.fixed_pass_indicator = tk.Label(
        panel, text="", font=(APP_FONT_NAME, 8, "italic"), fg="#2ECC71", bg=self.card_color,
    )
    self.fixed_pass_indicator.pack(anchor=tk.W, padx=18, pady=0)
    self.update_fixed_password_indicator()

    copy_all_btn = create_flat_button(
        panel, text=E(_("📋 Sao chép cả ID & Mật khẩu")), font=EMOJI_FONT_BOLD,
        fg=self.text_white, bg=self.btn_color, activebackground=self.btn_hover,
        command=self.copy_id_and_password,
    )
    copy_all_btn.pack(side=tk.TOP, padx=18, fill=tk.X, pady=(4, 6))

    fixed_btn = create_flat_button(
        panel, text=_("Cài mật khẩu cố định..."), font=EMOJI_FONT_BOLD,
        fg=self.text_white, bg="#5B2C8E", activebackground="#7B3FA8",
        command=self.open_set_fixed_password_dialog,
    )
    fixed_btn.pack(side=tk.TOP, padx=18, fill=tk.X, pady=(0, 8))

    startup_chk = tk.Checkbutton(
        panel,
        text=_("Chạy khi mở máy (Run on Startup)"),
        variable=self.startup_var,
        command=self.toggle_startup,
        font=(APP_FONT_NAME, 9),
        fg=self.text_white,
        bg=self.card_color,
        selectcolor=self.entry_bg,
        activebackground=self.card_color,
        activeforeground=self.text_white,
        highlightthickness=0,
        bd=0,
        anchor=tk.W,
    )
    startup_chk.pack(anchor=tk.W, padx=16, pady=(0, 12))

    # Stubs only — real Tk Entry/Button steal OLE clipboard and break remote paste.
    class _HostUiStub:
        def config(self, **kwargs):
            return None
        def index(self, *args, **kwargs):
            return 0
        def icursor(self, *args, **kwargs):
            return None
        def bind(self, *args, **kwargs):
            return None
        def pack(self, *args, **kwargs):
            return None

    _stub = _HostUiStub()
    self.entry_p_id = _stub
    self.entry_p_pass = _stub
    self.connect_btn = _stub
    self.add_partner_btn = _stub
    self._right_panel = None

    status_bar = tk.Frame(self, bg=self.entry_bg, height=25)
    status_bar.pack(side=tk.BOTTOM, fill=tk.X)
    self.lbl_status = tk.Label(
        status_bar, textvariable=self.status_var,
        font=(APP_FONT_NAME, 8, "italic"), fg="#8A8A9A", bg=self.entry_bg, anchor=tk.W,
    )
    self.lbl_status.pack(fill=tk.BOTH, padx=10, pady=2)

    if not self.is_headless:
        self.setup_tray_icon()
