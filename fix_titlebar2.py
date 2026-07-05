import codecs

with open('app.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
skip = False
for i, line in enumerate(lines):
    if i == 1564:
        new_lines.append("""        super().__init__(parent)
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
""")
        skip = True
    elif i == 1581:
        skip = False
        # Do not append line 1581 because we append it starting from 1581 as normal
        new_lines.append(line)
    elif not skip:
        new_lines.append(line)

with open('app.py', 'w', encoding='utf-8') as f:
    f.writelines(new_lines)
print("Done")
