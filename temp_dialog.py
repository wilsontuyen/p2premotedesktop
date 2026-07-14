def inline_ask_string(parent, title, prompt, initialvalue=""):
    import tkinter as tk
    from tkinter import ttk
    var = tk.StringVar(value="")
    result = [None]
    
    blocker = tk.Frame(parent)
    blocker.place(relx=0, rely=0, relwidth=1, relheight=1)
    
    overlay = tk.Frame(blocker, bg="#F0F0F0", bd=1, relief=tk.SOLID)
    overlay.place(relx=0.5, rely=0.5, anchor=tk.CENTER)
    
    lbl_title = tk.Label(overlay, text=title, font=("Segoe UI", 10, "bold"), bg="#F0F0F0")
    lbl_title.pack(pady=(10, 5), padx=20, anchor=tk.W)
    
    lbl_msg = tk.Label(overlay, text=prompt, font=("Segoe UI", 9), bg="#F0F0F0")
    lbl_msg.pack(pady=(0, 5), padx=20, anchor=tk.W)
    
    entry = ttk.Entry(overlay, font=("Segoe UI", 9), width=35)
    entry.pack(padx=20, pady=(0, 10))
    if initialvalue:
        entry.insert(0, initialvalue)
        entry.select_range(0, tk.END)
    entry.focus_force()
    
    btn_frame = tk.Frame(overlay, bg="#F0F0F0")
    btn_frame.pack(fill=tk.X, padx=20, pady=(0, 10), side=tk.BOTTOM)
    
    def _ok(e=None):
        result[0] = entry.get()
        var.set("done")
        
    def _cancel(e=None):
        result[0] = None
        var.set("done")
        
    entry.bind("<Return>", _ok)
    entry.bind("<Escape>", _cancel)
    
    from core.i18n import _
    btn_ok = ttk.Button(btn_frame, text=_("Đồng ý"), command=_ok, width=10)
    btn_ok.pack(side=tk.LEFT, padx=(0, 5))
    
    btn_cancel = ttk.Button(btn_frame, text=_("Hủy"), command=_cancel, width=10)
    btn_cancel.pack(side=tk.RIGHT, padx=(5, 0))
    
    parent.wait_variable(var)
    blocker.destroy()
    return result[0]
