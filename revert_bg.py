with open('app.py', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace('fg=self.btn_cancel_fg, bg=self.btn_cancel_bg', 'fg=self.text_white, bg="#3A3A4A"')

with open('app.py', 'w', encoding='utf-8') as f:
    f.write(content)
print('Reverted buttons!')
