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

def setup_linux_ui(self):
    APP_FONT_NAME = "Segoe UI" if sys.platform == "win32" else "Helvetica"
    EMOJI_FONT_10 = (APP_FONT_NAME, 10)
    EMOJI_FONT_BOLD = (APP_FONT_NAME, 9, "bold")
    EMOJI_FONT = (APP_FONT_NAME, 9)
    EMOJI_FONT_LARGE = (APP_FONT_NAME, 12, "bold")

    def setup_ui(self):
        def create_flat_button(parent, **kwargs):
            cmd = kwargs.pop('command', None)
            active_bg = kwargs.pop('activebackground', kwargs.get('bg'))
            kwargs.pop('relief', None)
            kwargs.pop('bd', None)
            kwargs.pop('highlightthickness', None)
            kwargs.pop('highlightbackground', None)
            if 'cursor' not in kwargs:
                kwargs['cursor'] = 'hand2'
            pady = kwargs.pop('pady', 5)
            padx = kwargs.pop('padx', 5)
            
            text = kwargs.get('text', '')
            if text and len(text) > 2 and text[0] in ['📋', '📁', '📡', '🔧', '🔄', '🔍', '➕', '❌', '❐', '≡', '⌂', '¤', '↻', '⌕']:
                icon_char = text[0]
                label_text = text[1:].strip()
                kwargs.pop('text')
                
                frame = tk.Frame(parent, bg=kwargs.get('bg'), cursor=kwargs.get('cursor'))
                inner = tk.Frame(frame, bg=kwargs.get('bg'), cursor=kwargs.get('cursor'))
                inner.pack(expand=True, pady=pady)
                
                font = kwargs.get('font')
                fg = kwargs.get('fg')
                bg = kwargs.get('bg')
                
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
                    
                frame.bind("<Enter>", on_enter)
                inner.bind("<Enter>", on_enter)
                lbl_icon.bind("<Enter>", on_enter)
                lbl_text.bind("<Enter>", on_enter)
                frame.bind("<Leave>", on_leave)
                inner.bind("<Leave>", on_leave)
                lbl_icon.bind("<Leave>", on_leave)
                lbl_text.bind("<Leave>", on_leave)
                
                if cmd:
                    frame.bind("<Button-1>", lambda e: cmd())
                    inner.bind("<Button-1>", lambda e: cmd())
                    lbl_icon.bind("<Button-1>", lambda e: cmd())
                    lbl_text.bind("<Button-1>", lambda e: cmd())
                    
                return frame

            lbl = tk.Label(parent, pady=pady, padx=padx, **kwargs)
            lbl.bind("<Enter>", lambda e, l=lbl, c=active_bg: l.config(bg=c))
            lbl.bind("<Leave>", lambda e, l=lbl, c=kwargs.get('bg'): l.config(bg=c))
            if cmd:
                lbl.bind("<Button-1>", lambda e, c=cmd: c())
            return lbl

        # Setup Window Menu Bar
        menubar = tk.Menu(self)
        
        # 1. File Menu
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label=_("Danh sách (Saved Computers)"), command=self.show_saved_computers_dialog)
        file_menu.add_command(label=E(_("Quét mạng LAN (LAN Discovery)")), command=self.show_lan_computers_dialog)
        file_menu.add_separator()
        file_menu.add_command(label=_("Nhập khẩu (Import Saved Computers)"), command=self.import_saved_computers)
        file_menu.add_command(label=_("Xuất khẩu (Export Saved Computers)"), command=self.export_saved_computers)
        file_menu.add_separator()
        file_menu.add_command(label=_("Thoát (Exit)"), command=self.destroy)
        menubar.add_cascade(label=_("File"), menu=file_menu)
        
        # 2. Options Menu
        options_menu = tk.Menu(menubar, tearoff=0)

        # Submenu: Password type
        password_menu = tk.Menu(options_menu, tearoff=0)
        password_menu.add_radiobutton(
            label=_("4 chữ số"),
            variable=self.pass_type_var, value=_("4 chữ số"),
            command=self.refresh_password
        )
        password_menu.add_radiobutton(
            label=_("5 chữ số"),
            variable=self.pass_type_var, value=_("5 chữ số"),
            command=self.refresh_password
        )
        password_menu.add_radiobutton(
            label=_("8 ký tự (chữ + số)"),
            variable=self.pass_type_var, value=_("8 ký tự (chữ + số)"),
            command=self.refresh_password
        )
        password_menu.add_separator()
        password_menu.add_command(
            label=_("Cài mật khẩu cố định..."),
            command=self.open_set_fixed_password_dialog
        )
        options_menu.add_cascade(label=_("Mật khẩu (Password)"), menu=password_menu)
        options_menu.add_separator()
        options_menu.add_checkbutton(
            label=_("Chạy khi mở máy (Run on Startup)"),
            variable=self.startup_var,
            command=self.toggle_startup
        )
        options_menu.add_command(
            label=_("Cài Zalo / Điện thoại"),
            command=self.open_set_zalo_phone_dialog
        )
        options_menu.add_separator()
        options_menu.add_command(
            label=_("Cài đặt máy chủ..."),
            command=self.show_server_settings_dialog
        )
        if sys.platform == "darwin":
            options_menu.add_separator()
            options_menu.add_command(
                label=_("Sửa lỗi quyền macOS..."),
                command=self.fix_mac_permissions
            )
        options_menu.add_separator()
        
        
        # Submenu: Language
        lang_menu = tk.Menu(options_menu, tearoff=0)
        langs = get_available_languages()
        for l in langs:
            lang_menu.add_radiobutton(label=get_language_name(l), variable=self.current_lang, value=l, command=self.change_language)
        
        # Export template
        lang_menu.add_separator()
        lang_menu.add_command(label=_("Xuất tệp ngôn ngữ mẫu..."), command=self.export_lang_template)
        lang_menu.add_command(label=_("Ngôn ngữ riêng của bạn"), command=self.import_custom_language)
        options_menu.add_cascade(label=_("Ngôn ngữ (Language)"), menu=lang_menu) # Tạm thay thế
        options_menu.add_separator()

        # Submenu: Theme
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
        
        # 3. Help Menu
        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label=_("Zalo"), command=self.open_zalo)
        help_menu.add_command(label=_("Điện thoại"), command=self.open_phone_dialog)
        help_menu.add_command(label=_("About"), command=self.show_about_dialog)
        menubar.add_cascade(label=_("Help"), menu=help_menu)
        
        self.config(menu=menubar)
        

        # Header Label
        header = tk.Label(self, text=_("P2P REMOTE DESKTOP"), font=(APP_FONT_NAME, 16, "bold"), fg=self.btn_color, bg=self.bg_color)
        header.pack(pady=(15, 5))
        
        # Sub-header
        subheader = tk.Label(self, text=_("Điều khiển trực tuyến máy tính bằng HWID"), font=(APP_FONT_NAME, 9, "italic"), fg=self.text_gray, bg=self.bg_color)
        subheader.pack(pady=(0, 15))
        
        # Main Panels Container
        container = tk.Frame(self, bg=self.bg_color)
        self._main_container = container
        container.pack(fill=tk.BOTH, expand=True, padx=20)
        
        # LEFT PANEL: Allow Remote Control
        left_panel = tk.Frame(container, bg=self.card_color, bd=0, relief=tk.FLAT)
        self._left_panel = left_panel
        left_panel.place(relx=0.0, rely=0.0, relwidth=0.47, relheight=0.92)
        
        lbl_allow = tk.Label(left_panel, text=_("CHO PHÉP ĐIỀU KHIỂN"), font=(APP_FONT_NAME, 11, "bold"), fg=self.btn_color, bg=self.card_color)
        lbl_allow.pack(pady=(15, 10))
        
        lbl_id = tk.Label(left_panel, text=_("Mã ID của bạn:"), font=(APP_FONT_NAME, 9), fg=self.text_gray, bg=self.card_color)
        lbl_id.pack(anchor=tk.W, padx=20)
        
        id_frame = tk.Frame(left_panel, bg=self.card_color)
        self._id_frame = id_frame
        id_frame.pack(fill=tk.X, padx=20, pady=(5, 12))
        
        self.my_id_label = tk.Label(id_frame, text=self.my_id_formatted, font=(APP_FONT_NAME, 16, "bold"), fg=self.text_white, bg=self.entry_bg, bd=0, height=1)
        self.my_id_label.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        copy_id_btn = create_flat_button(id_frame, text=E("📋"), font=EMOJI_FONT_10, fg=self.text_white, bg=self.btn_color, activebackground=self.btn_hover, padx=2, pady=1, width=3, command=lambda: self.copy_to_clipboard(self.my_id_formatted))
        copy_id_btn.pack(side=tk.RIGHT, padx=(5, 0))
        ToolTip(copy_id_btn, _("Sao chép"))
        
        lbl_pass = tk.Label(left_panel, text=_("Mật khẩu kết nối:"), font=(APP_FONT_NAME, 9), fg=self.text_gray, bg=self.card_color)
        lbl_pass.pack(anchor=tk.W, padx=20)
        
        pass_frame = tk.Frame(left_panel, bg=self.card_color)
        self._pass_frame = pass_frame
        pass_frame.pack(fill=tk.X, padx=20, pady=(5, 5))
        
        self.my_pass_label = tk.Label(pass_frame, text=self.my_password, font=(APP_FONT_NAME, 16, "bold"), fg=self.text_white, bg=self.entry_bg, bd=0)
        self.my_pass_label.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        copy_pass_btn = create_flat_button(pass_frame, text=E("📋"), font=EMOJI_FONT_10, fg=self.text_white, bg=self.btn_color, activebackground=self.btn_hover, padx=2, pady=1, width=3, command=lambda: self.copy_to_clipboard(self.my_password))
        copy_pass_btn.pack(side=tk.RIGHT, padx=(5, 0))
        ToolTip(copy_pass_btn, _("Sao chép"))
        
        refresh_btn = create_flat_button(pass_frame, text="↻", font=(APP_FONT_NAME, 10, "bold"), fg=self.text_white, bg=self.btn_color, activebackground=self.btn_hover, padx=2, pady=1, width=3, command=self.refresh_password)
        refresh_btn.pack(side=tk.RIGHT, padx=(5, 0))
        ToolTip(refresh_btn, _("Đổi mật khẩu"))

        # Nhãn hiển thị trạng thái mật khẩu cố định
        self.fixed_pass_indicator = tk.Label(left_panel, text="", font=(APP_FONT_NAME, 8, "italic"), fg="#2ECC71", bg=self.card_color)
        self.fixed_pass_indicator.pack(anchor=tk.W, padx=20, pady=0)
        self.update_fixed_password_indicator()

        # Button to Copy both ID & Password at once
        copy_all_btn = create_flat_button(left_panel, text=E(_("📋 Sao chép cả ID & Mật khẩu")), font=EMOJI_FONT_BOLD, fg=self.text_white, bg=self.btn_color, activebackground=self.btn_hover, command=self.copy_id_and_password)
        copy_all_btn.pack(side=tk.TOP, padx=20, fill=tk.X, pady=(0, 5))

        # Nút gọi Danh sách máy tính đã lưu
        saved_list_btn = create_flat_button(left_panel, text=E(_("📁 Danh sách máy tính đã lưu")), font=EMOJI_FONT, fg="#FFFFFF", bg="#5B2C8E", activebackground="#7B3FA8", command=self.show_saved_computers_dialog)
        saved_list_btn.pack(side=tk.TOP, padx=20, fill=tk.X, pady=(0, 10))
        
        # RIGHT PANEL: Control Remote Computer
        right_panel = tk.Frame(container, bg=self.card_color, bd=0, relief=tk.FLAT)
        self._right_panel = right_panel
        right_panel.place(relx=0.53, rely=0.0, relwidth=0.47, relheight=0.92)
        
        lbl_control = tk.Label(right_panel, text=_("ĐIỀU KHIỂN ĐỐI TÁC"), font=(APP_FONT_NAME, 11, "bold"), fg=self.btn_color, bg=self.card_color)
        lbl_control.pack(pady=(15, 10))
        
        lbl_p_id = tk.Label(right_panel, text=_("Nhập ID đối tác:"), font=(APP_FONT_NAME, 9), fg=self.text_gray, bg=self.card_color)
        lbl_p_id.pack(anchor=tk.W, padx=20)
        
        self.entry_p_id = tk.Entry(right_panel, textvariable=self.partner_id_var, font=(APP_FONT_NAME, 13), fg=self.entry_fg, bg=self.entry_bg, insertbackground=self.text_white, relief=tk.FLAT, bd=0, highlightthickness=0, highlightbackground=self.card_color)
        self.entry_p_id.pack(pady=(5, 10), padx=20, fill=tk.X)
        
        lbl_p_pass = tk.Label(right_panel, text=_("Nhập Mật khẩu đối tác:"), font=(APP_FONT_NAME, 9), fg=self.text_gray, bg=self.card_color)
        lbl_p_pass.pack(anchor=tk.W, padx=20)
        
        self.entry_p_pass = tk.Entry(right_panel, textvariable=self.partner_pass_var, font=(APP_FONT_NAME, 13), fg=self.entry_fg, bg=self.entry_bg, insertbackground=self.text_white, show="*", relief=tk.FLAT, bd=0, highlightthickness=0, highlightbackground=self.card_color)
        self.entry_p_pass.pack(pady=(5, 35), padx=20, fill=tk.X)
        
        # Bind Enter keys to trigger Connection immediately
        self.entry_p_id.bind("<Return>", lambda event: self.click_connect())
        self.entry_p_id.bind("<KP_Enter>", lambda event: self.click_connect())
        self.entry_p_pass.bind("<Return>", lambda event: self.click_connect())
        self.entry_p_pass.bind("<KP_Enter>", lambda event: self.click_connect())
        
        # Container to hold CONNECT & ADD (+) buttons
        btn_container = tk.Frame(right_panel, bg=self.card_color)
        btn_container.pack(padx=20, fill=tk.X)
        
        self.connect_btn = create_flat_button(btn_container, text=_("KẾT NỐI (CONNECT)"), font=(APP_FONT_NAME, 11, "bold"), fg=self.text_white, bg=self.btn_color, activebackground=self.btn_hover, padx=10, pady=2, command=self.click_connect)
        self.connect_btn.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # Add button with a blue "+"
        self.add_partner_btn = create_flat_button(btn_container, text=E("➕"), font=EMOJI_FONT_LARGE, fg=self.text_white, bg="#007ACC", activebackground="#005A9E", pady=2, width=4, command=self.add_current_partner_to_saved)
        self.add_partner_btn.pack(side=tk.RIGHT, padx=(8, 0))
        ToolTip(self.add_partner_btn, _("Thêm máy tính"))

        # LAN Discovery button - Quét máy trong mạng nội bộ
        lan_btn = create_flat_button(right_panel, text=E(_("📡 Quét mạng LAN (LAN Only)")), font=EMOJI_FONT_BOLD, fg="#FFFFFF", bg="#5B2C8E", activebackground="#7B3FA8", pady=3, command=self.show_lan_computers_dialog)
        lan_btn.pack(side=tk.TOP, padx=20, fill=tk.X, pady=(5, 10))

        # Attach Context Menus for Copy & Paste
        self.make_context_menu(self.entry_p_id)
        self.make_context_menu(self.entry_p_pass)
        
        # BOTTOM STATUS BAR
        status_bar = tk.Frame(self, bg=self.entry_bg, height=25)
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        
        self.lbl_status = tk.Label(status_bar, textvariable=self.status_var, font=(APP_FONT_NAME, 8, "italic"), fg="#8A8A9A", bg=self.entry_bg, anchor=tk.W)
        self.lbl_status.pack(fill=tk.BOTH, padx=10, pady=2)
        
        # Khởi chạy icon khay hệ thống ngay khi bật ứng dụng
        if not self.is_headless:
            self.setup_tray_icon()
            
    setup_ui(self)
        
    # Auto formatting spaces inside ID: "123 456 789 012"
