import sys

with open('app.py', encoding='utf-8') as f:
    content = f.read()

font_defs = '''
_is_old_win = platform.release() in ["7", "8", "8.1"]
EMOJI_FONT = ("Segoe UI Symbol", 9) if _is_old_win else ("Segoe UI Emoji", 9)
EMOJI_FONT_BOLD = ("Segoe UI Symbol", 9, "bold") if _is_old_win else ("Segoe UI Emoji", 9, "bold")
EMOJI_FONT_LARGE = ("Segoe UI Symbol", 12, "bold") if _is_old_win else ("Segoe UI Emoji", 12, "bold")
EMOJI_FONT_10 = ("Segoe UI Symbol", 10) if _is_old_win else ("Segoe UI Emoji", 10)
EMOJI_FONT_8_BOLD = ("Segoe UI Symbol", 8, "bold") if _is_old_win else ("Segoe UI Emoji", 8, "bold")
'''

content = content.replace('def E(text):', font_defs + '\ndef E(text):')

replacements = [
    ('("Segoe UI Emoji", 9)', 'EMOJI_FONT'),
    ('("Segoe UI Emoji", 9, "bold")', 'EMOJI_FONT_BOLD'),
    ('("Segoe UI Emoji", 12, "bold")', 'EMOJI_FONT_LARGE'),
    ('("Segoe UI Emoji", 10)', 'EMOJI_FONT_10'),
    ('("Segoe UI Emoji", 8, "bold")', 'EMOJI_FONT_8_BOLD')
]

for old, new in replacements:
    content = content.replace(old, new)

with open('app.py', 'w', encoding='utf-8') as f:
    f.write(content)
print('Done!')
