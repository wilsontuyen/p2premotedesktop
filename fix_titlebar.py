import codecs

with open('app.py', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace('\\r\\n', '\\n')

start = content.find("        super().__init__(parent)\\n        self.title(title_text)")
end = content.find("        self.total_size = total_size")

if start != -1 and end != -1:
    new_block = """        super().__init__(parent)
        self.overrideredirect(True)
        self.configure(bg="#FFFFFF", highlightbackground="#CCCCCC", highlightthickness=1)

        title_bg = "#F3F3F3"
        self.title_bar = tk.Frame(self, bg=title_bg, height=28)
        self.title_bar.pack(fill=tk.X, side=tk.TOP)
        self.title_bar.pack_propagate(False)
        self.title_lbl = tk.Label(self.title_bar, text=title_text, bg=title_bg, fg="#333333", font=("Segoe UI", 9, "bold"))
        self.title_lbl.pack(side=tk.LEFT, padx=10, pady=4)

        self.attributes("-topmost", True)
        self.lift()

"""
    content = content[:start] + new_block + content[end:]
    print("Replaced successfully")
else:
    print("Not found indices")

with open('app.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("Done")
