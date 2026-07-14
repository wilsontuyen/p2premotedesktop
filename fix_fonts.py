import sys

with open('app.py', encoding='utf-8') as f:
    content = f.read()

replacements = [
    ('text="➕", font=("Segoe UI", 12, "bold")', 'text="➕", font=("Segoe UI Emoji", 12, "bold")'),
    ('text=_("📡 Quét mạng LAN (LAN Only)"), font=("Segoe UI", 9)', 'text=_("📡 Quét mạng LAN (LAN Only)"), font=("Segoe UI Emoji", 9)'),
    ('text=_("📋 Sao chép cả ID & Mật khẩu"), font=("Segoe UI", 9, "bold")', 'text=_("📋 Sao chép cả ID & Mật khẩu"), font=("Segoe UI Emoji", 9, "bold")'),
    ('text="📋", font=("Segoe UI", 10)', 'text="📋", font=("Segoe UI Emoji", 10)'),
    ('text=_("📋  Thông tin kỹ thuật"), font=("Segoe UI", 8, "bold")', 'text=_("📋  Thông tin kỹ thuật"), font=("Segoe UI Emoji", 8, "bold")'),
    ('text=_("🔧  Cách khắc phục"), font=("Segoe UI", 9, "bold")', 'text=_("🔧  Cách khắc phục"), font=("Segoe UI Emoji", 9, "bold")')
]

for old, new in replacements:
    content = content.replace(old, new)

with open('app.py', 'w', encoding='utf-8') as f:
    f.write(content)
print('Done!')
