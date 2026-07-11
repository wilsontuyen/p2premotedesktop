import codecs
import re

# Read original_app.py (truncated refactored version)
with codecs.open("original_app.py", "r", encoding="utf-16") as f:
    new_app = f.read().replace('\r\n', '\n')

# Read old_app.py (monolithic pre-refactor version)
with codecs.open("old_app.py", "r", encoding="utf-16") as f:
    old_app_lines = f.read().replace('\r\n', '\n').split('\n')

methods_to_keep = [
    "save_window_position", "copy_id_and_password", "copy_to_clipboard", "make_context_menu",
    "refresh_password", "show_saved_computers_dialog", "add_current_partner_to_saved",
    "open_add_computer_dialog_with_vals", "open_edit_computer_dialog",
    "load_lan_peers", "save_lan_peers", "load_saved_computers", "save_saved_computers",
    "save_group_states_only", "load_fixed_password_from_xml", "save_fixed_password_to_xml",
    "save_fixed_password", "load_zalo_phone_from_xml", "save_zalo_phone_to_xml",
    "open_set_zalo_phone_dialog", "show_server_settings_dialog", "update_fixed_password_indicator",
    "open_set_fixed_password_dialog", "is_startup_enabled", "toggle_startup",
    "open_zalo", "show_zalo_error_popup", "open_phone_dialog", "show_phone_number_popup",
    "show_about_dialog", "query_computer_status", "check_and_default_offline",
    "update_saved_computer_status", "show_custom_info", "show_custom_error",
    "_show_lan_error_dialog", "show_custom_question", "update_status",
    "_poll_signaling_status", "_blink_status",
    "add_firewall_rule_for_app", "configure_uac_registry", "wake_on_lan", 
    "on_close_window", "setup_tray_icon", "show_gui_from_tray", "_restore_window", 
    "exit_from_tray", "destroy"
]

# Extract methods from old_app.py
extracted_methods = []
current_method = []
keeping = False

for line in old_app_lines:
    if line.startswith("    def "):
        method_name = line.split("def ")[1].split("(")[0]
        if method_name in methods_to_keep:
            if keeping:
                extracted_methods.append('\n'.join(current_method))
            keeping = True
            current_method = [line]
        else:
            if keeping:
                extracted_methods.append('\n'.join(current_method))
            keeping = False
            current_method = []
    elif keeping:
        current_method.append(line)

if keeping:
    extracted_methods.append('\n'.join(current_method))

# Extract __main__ block
main_block = []
in_main = False
for line in old_app_lines:
    if line.startswith("if __name__ == '__main__':"):
        in_main = True
    if in_main:
        main_block.append(line)

# Combine
final_app = new_app + "\n\n" + "\n\n".join(extracted_methods) + "\n\n" + "\n".join(main_block)

# Remove old change_theme body if present, just in case
final_app = re.sub(r'def change_theme\(self\):.*?(?=\n    def save_window_position)', 'def change_theme(self):\n        from gui.themes import change_app_theme\n        change_app_theme(self)', final_app, flags=re.DOTALL)

# Ensure no pynput imports
final_app = re.sub(r'from pynput.*?Controller.*?\n?', '', final_app)
final_app = re.sub(r'mouse = MouseController\(\)\n?', '', final_app)
final_app = re.sub(r'keyboard = KeyboardController\(\)\n?', '', final_app)

# Replace `# Color Theme Setup`
theme_setup_pattern = r'# Color Theme Setup.*?(?=self\.my_id_clean, self\.my_id_formatted)'
replacement1 = 'from gui.themes import setup_app_theme\n        setup_app_theme(self)\n        \n        '
final_app = re.sub(theme_setup_pattern, replacement1, final_app, flags=re.DOTALL)

# Save
with open("app.py", "w", encoding="utf-8", newline='\n') as f:
    f.write(final_app)
print(f"app.py built with {len(final_app.splitlines())} lines.")
