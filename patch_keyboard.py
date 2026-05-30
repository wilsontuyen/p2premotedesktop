import re

with open('app.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Update vk_map
vk_map_additions = """    'insert': 0x2D,
    'left meta': 0x5B,
    'right meta': 0x5C,
    'left super': 0x5B,
    'right super': 0x5C,
    'left windows': 0x5B,
    'right windows': 0x5C,
"""
content = re.sub(r"('delete': 0x2E,     # VK_DELETE\n)", r"\1" + vk_map_additions, content)

# 2. Update keyboard event
old_key = """                        if event.type == pygame.KEYDOWN:
                            if hasattr(event, 'unicode') and event.unicode and len(event.unicode) == 1 and ord(event.unicode) >= 32:
                                char_to_send = event.unicode"""

new_key = """                        if event.type == pygame.KEYDOWN:
                            if hasattr(event, 'unicode') and event.unicode and len(event.unicode) == 1 and ord(event.unicode) >= 32 and ord(event.unicode) != 127:
                                if key_name not in ['insert', 'delete', 'home', 'end', 'page up', 'page down', 'left meta', 'right meta', 'left super', 'right super']:
                                    char_to_send = event.unicode"""
content = content.replace(old_key, new_key)

with open('app.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("Patched keyboard!")
