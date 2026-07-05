import codecs

with open('app.py', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace('\\r\\n', '\\n')

search = "super().__init__(parent)\\n        self.withdraw()"
replace = "super().__init__(parent)\\n        # self.withdraw()"

if search in content:
    content = content.replace(search, replace, 1)
    print("Replaced withdraw")
else:
    print("Not found withdraw")

with open('app.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("Done")
