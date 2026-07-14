with open('utils/file_manager.py', 'r', encoding='utf-8') as f:
    text = f.read()

text = text.replace(r"[\'", "['")
text = text.replace(r"\']", "']")
text = text.replace(r"\'{", "'{")
text = text.replace(r"}\'", "}'")

# And check for \'{name}\'
text = text.replace(r"\'{name}\'", "'{name}'")

with open('utils/file_manager.py', 'w', encoding='utf-8') as f:
    f.write(text)
