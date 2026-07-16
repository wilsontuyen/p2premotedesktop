import unicodedata
import sys

with open("app.py", "r", encoding="utf-8") as f:
    content = f.read()

target = "KẾT NỐI"
out = []
out.append(f"Target in script: length={len(target)}")
for i, char in enumerate(target):
    out.append(f"Char {i}: U+{ord(char):04X} Name: {unicodedata.name(char)}")

idx = content.find("KẾT NỐI")
if idx != -1:
    snippet = content[idx:idx+7]
    out.append(f"Found snippet in app.py: length={len(snippet)}")
    for i, char in enumerate(snippet):
        out.append(f"Snippet Char {i}: U+{ord(char):04X} Name: {unicodedata.name(char)}")
else:
    # Try finding "KẾT"
    idx2 = content.find("KẾT")
    if idx2 != -1:
        snippet = content[idx2:idx2+3]
        out.append(f"Found 'KẾT' snippet: length={len(snippet)}")
        for i, char in enumerate(snippet):
            out.append(f"Snippet Char {i}: U+{ord(char):04X} Name: {unicodedata.name(char)}")

with open("scratch/norm_results.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(out))
print("Done!")
