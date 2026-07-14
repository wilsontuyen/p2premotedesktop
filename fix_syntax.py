with open('utils/file_manager.py', 'r', encoding='utf-8') as f:
    text = f.read()

# Replace any occurrence of literal \', which was placed by apply_translations.py
# that broke Python syntax
text = text.replace(r"_\(\'", r"_('")
text = text.replace(r"\')", r"')")
text = text.replace(r"_(\'", r"_('")
text = text.replace(r"_\(\\\'", r"_('")
text = text.replace(r"\\\')", r"')")

with open('utils/file_manager.py', 'w', encoding='utf-8') as f:
    f.write(text)
