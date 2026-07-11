with open('d:/Data/AG/remote_desktop/core/network_manager.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Fix literal newlines in strings
content = content.replace('Từ chối kết nối:\n{msg}").format', 'Từ chối kết nối:\\n{msg}").format')
content = content.replace('Lỗi xác thực handshake:\n{err}").format', 'Lỗi xác thực handshake:\\n{err}").format')
content = content.replace('({ip}:{port}).\nKiểm tra Tường lửa', '({ip}:{port}).\\nKiểm tra Tường lửa')

# Fix backslashed single quotes
content = content.replace(r"peer_info[\'computer_name\']", r"peer_info['computer_name']")

with open('d:/Data/AG/remote_desktop/core/network_manager.py', 'w', encoding='utf-8') as f:
    f.write(content)
