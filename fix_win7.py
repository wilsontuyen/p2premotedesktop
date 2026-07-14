import sys
import platform

with open('app.py', encoding='utf-8') as f:
    content = f.read()

e_func = '''
import platform
def E(text):
    if platform.release() == "7" or platform.release() == "8" or platform.release() == "8.1":
        mapping = {
            "📋": "❐", "📁": "▤", "📡": "⛧", "🔧": "⚙",
            "🔄": "↻", "🔍": "⌕", "➕": "+", "❌": "X"
        }
        for k, v in mapping.items():
            text = text.replace(k, v)
    return text
'''

content = content.replace('from core.i18n import _, load_language', e_func + '\nfrom core.i18n import _, load_language')

replacements = [
    ('label=_("📡 Quét mạng LAN (LAN Discovery)")', 'label=E(_("📡 Quét mạng LAN (LAN Discovery)"))'),
    ('text="📋"', 'text=E("📋")'),
    ('text=_("📋 Sao chép cả ID & Mật khẩu")', 'text=E(_("📋 Sao chép cả ID & Mật khẩu"))'),
    ('text=_("📁 Danh sách máy tính đã lưu")', 'text=E(_("📁 Danh sách máy tính đã lưu"))'),
    ('text="➕"', 'text=E("➕")'),
    ('text=_("📡 Quét mạng LAN (LAN Only)")', 'text=E(_("📡 Quét mạng LAN (LAN Only)"))'),
    ('text="🔍"', 'text=E("🔍")'),
    ('text=_("🔄 Làm mới")', 'text=E(_("🔄 Làm mới"))'),
    ('text=_("🔄 Làm mới (30s)")', 'text=E(_("🔄 Làm mới (30s)"))'),
    ('text=_("📋  Thông tin kỹ thuật")', 'text=E(_("📋  Thông tin kỹ thuật"))'),
    ('text=_("🔧  Cách khắc phục")', 'text=E(_("🔧  Cách khắc phục"))')
]

for old, new in replacements:
    content = content.replace(old, new)

with open('app.py', 'w', encoding='utf-8') as f:
    f.write(content)
print('Done!')
