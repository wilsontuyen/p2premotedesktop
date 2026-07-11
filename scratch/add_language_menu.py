import json
import re

with open('scratch/lang_vi.json', 'r', encoding='utf-8') as f:
    lang_dict = json.load(f)

with open('app.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Load language before setup_ui
load_lang_code = """
        # Load language setting
        self.current_lang = tk.StringVar(value="vi")
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, "r") as f:
                    cfg = json.load(f)
                    saved_lang = cfg.get("language", "vi")
                    self.current_lang.set(saved_lang)
                    load_language(saved_lang)
        except:
            pass
"""
content = content.replace('self.load_window_position()', 'self.load_window_position()' + load_lang_code)

# 2. Save language in save_window_position
content = content.replace('config["geometry"] = geom', 'config["geometry"] = geom\n                    config["language"] = self.current_lang.get()')

# 3. Add change_language method
change_lang_method = """
    def change_language(self, *args):
        lang = self.current_lang.get()
        load_language(lang)
        self.save_window_position()
        messagebox.showinfo(_("Thay đổi thông tin"), _("Vui lòng khởi động lại ứng dụng để áp dụng ngôn ngữ mới."))
"""
content = content.replace('def change_theme(self):\n        from gui.themes import change_app_theme\n        change_app_theme(self)', 'def change_theme(self):\n        from gui.themes import change_app_theme\n        change_app_theme(self)\n' + change_lang_method)

# 4. Add language menu
lang_menu_code = """
        # Submenu: Language
        lang_menu = tk.Menu(options_menu, tearoff=0)
        langs = get_available_languages()
        for l in langs:
            lang_menu.add_radiobutton(label=l.upper(), variable=self.current_lang, value=l, command=self.change_language)
        
        # Export template
        lang_menu.add_separator()
        lang_menu.add_command(label="Xuất file ngôn ngữ mẫu...", command=self.export_lang_template)
        options_menu.add_cascade(label=_("Giao diện"), menu=lang_menu) # Tạm thay thế
        options_menu.add_separator()
"""
lang_menu_code = lang_menu_code.replace('_("Giao diện")', '"Ngôn ngữ (Language)"')

content = content.replace('# Submenu: Theme', lang_menu_code + '\n        # Submenu: Theme')

# 5. Add export_lang_template method
export_method = f"""
    def export_lang_template(self):
        try:
            template = {json.dumps(lang_dict, ensure_ascii=False, indent=4)}
            template_path = export_template(template)
            if template_path:
                messagebox.showinfo(_("Lưu lại"), f"File ngôn ngữ mẫu đã được lưu tại:\\n{{template_path}}\\nBạn có thể sao chép và đổi tên thành 'en.json' để dịch.")
        except Exception as e:
            messagebox.showerror("Error", str(e))
"""
content = content.replace('def change_language(self, *args):', export_method + '\n    def change_language(self, *args):')

with open('app.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Added language menu to app.py.")
