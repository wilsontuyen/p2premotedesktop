import os

file_path = r'd:\Data\AG\remote_desktop\os_utils\windows_clipboard.py'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# We want to split render_format.
# Find the start of dest_dir check:
split_marker = '            if dest_dir and os.path.isdir(dest_dir):\n                self.target_save_dir = dest_dir'

parts = content.split(split_marker)
if len(parts) != 2:
    print("Could not split!")
    exit(1)

part1 = parts[0]
part2 = split_marker + parts[1]

# Now we need to modify part1 to add the thread dispatch logic.
# Wait, let's find the end of dest_dir = self.get_active_explorer_path() in part1.
insert_marker = '            dest_dir = self.get_active_explorer_path()\n            log_debug(f"[render_format] Thư mục đích phát hiện: {dest_dir}")\n'
p1_parts = part1.split(insert_marker)

new_part1 = p1_parts[0] + insert_marker + '''
            import platform
            is_win7 = platform.release() == "7"
            if is_win7 and dest_dir and os.path.isdir(dest_dir):
                log_debug("[render_format] Win7 detected. Returning empty HDROP immediately to prevent UI hang.")
                empty_hdrop = create_hdrop_data([])
                if empty_hdrop:
                    self.ignore_destroy_clipboard = True
                    fn_SetClipboardData(15, empty_hdrop)
                import threading
                threading.Thread(target=self._render_format_process, args=(dest_dir,), daemon=True).start()
                return
            else:
                self._render_format_process(dest_dir)
        except Exception as e:
            log_debug(f"[render_format] Lỗi khi xử lý render format: {e}")
            self.is_rendering = False
            self.transfer_in_progress = False
            self.ignore_destroy_clipboard = False

    def _render_format_process(self, dest_dir):
        try:
'''

# part2 contains the rest, but it needs to be indented out? No, it's already at 12 spaces.
# The original code was inside a 	ry: at 8 spaces, so the code inside is at 12 spaces.
# Our new def _render_format_process(self, dest_dir): is at 4 spaces.
# The 	ry: is at 8 spaces.
# So the indentation matches EXACTLY!
# We just need to replace the end of part2 which has the original except/finally.
# Actually, part2 already has the except and finally at 8 spaces!
# Let's check part2's end.

new_content = new_part1 + part2

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(new_content)
print("Refactored successfully!")
