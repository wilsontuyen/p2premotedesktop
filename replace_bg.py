with open('app.py', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace('fg=self.text_white, bg="#3A3A4A"', 'fg=self.btn_cancel_fg, bg=self.btn_cancel_bg')

with open('app.py', 'w', encoding='utf-8') as f:
    f.write(content)
print('Replaced buttons again!')
