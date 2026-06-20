import re

def search_app():
    with open("app.py", "r", encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()
    
    keywords = [
        r"EmptyClipboard",
        r"OpenClipboard",
        r"CloseClipboard",
        r"SetClipboardData",
        r"GetClipboardData",
        r"WM_DESTROYCLIPBOARD",
        r"WM_RENDERFORMAT",
        r"WM_RENDERALLFORMATS",
        r"delayed_clear_agent",
        r"clear_clipboard",
        r"destroy_clipboard",
        r"clipboard",
        r"ignore_destroy",
        r"sequence_number",
        r"GetClipboardSequenceNumber"
    ]
    
    compiled = {kw: re.compile(kw, re.IGNORECASE) for kw in keywords}
    
    out_lines = []
    for i, line in enumerate(lines, 1):
        matched = []
        for kw, regex in compiled.items():
            if regex.search(line):
                matched.append(kw)
        if matched:
            out_lines.append(f"Line {i:4d}: ({', '.join(matched)}) -> {line.strip()}\n")
            
    with open("scratch/clipboard_search_results.txt", "w", encoding="utf-8") as f:
        f.writelines(out_lines)

if __name__ == "__main__":
    search_app()
