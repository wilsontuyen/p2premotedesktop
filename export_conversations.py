import os
import json
import re
import datetime
from pathlib import Path

brain_dir = r"C:\Users\Tuyen\.gemini\antigravity-ide\brain"
output_dir = r"D:\Data\AG\remote_desktop\conversations"

os.makedirs(output_dir, exist_ok=True)

def sanitize_filename(name):
    name = re.sub(r'[\\/*?:"<>|]', "", name).strip()
    return re.sub(r'\s+', "_", name)

def get_readable_text(overview_path, dest_path):
    try:
        with open(overview_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
            
        with open(dest_path, "w", encoding="utf-8") as out:
            for line in lines:
                try:
                    data = json.loads(line.strip())
                    source = data.get("source", "")
                    content = data.get("content", "")
                    tool_calls = data.get("tool_calls", [])
                    
                    if source == "USER_EXPLICIT" and content:
                        # try to extract only USER_REQUEST if possible
                        req_match = re.search(r"<USER_REQUEST>\n(.*?)\n</USER_REQUEST>", content, re.DOTALL | re.IGNORECASE)
                        if req_match:
                            user_text = req_match.group(1).strip()
                        else:
                            user_text = content.strip()
                        out.write(f"========== USER ==========\n{user_text}\n\n")
                    
                    elif source == "MODEL":
                        if content:
                            out.write(f"========== MODEL ==========\n{content.strip()}\n\n")
                        if tool_calls:
                            for tc in tool_calls:
                                out.write(f"[Action: {tc.get('name')}]\n")
                                args = tc.get("args", {})
                                for k, v in args.items():
                                    if len(str(v)) < 200:
                                        out.write(f"  {k}: {v}\n")
                                    else:
                                        out.write(f"  {k}: {str(v)[:200]}...\n")
                            out.write("\n")
                except json.JSONDecodeError:
                    continue
    except Exception as e:
        print(f"Error formatting {overview_path}: {e}")

def process_conversation(conv_dir):
    overview_path = os.path.join(brain_dir, conv_dir, ".system_generated", "logs", "overview.txt")
    if not os.path.exists(overview_path):
        return

    with open(overview_path, "r", encoding="utf-8") as f:
        first_line = f.readline()
        if not first_line:
            return

    try:
        data = json.loads(first_line)
    except:
        return
        
    created_at = data.get("created_at", "")
    content = data.get("content", "")

    # Parse date
    try:
        dt = datetime.datetime.strptime(created_at, "%Y-%m-%dT%H:%M:%SZ")
        dt = dt + datetime.timedelta(hours=7) # UTC+7
        date_str = dt.strftime("%Y-%m-%d_%H%M%S")
    except:
        date_str = "UNKNOWN_DATE"

    # Extract title
    match = re.search(r"<USER_REQUEST>\n(.*?)\n", content, re.IGNORECASE)
    if match:
        title = match.group(1).strip()
    else:
        title = content.strip()
        
    # truncate title
    title = title[:40]

    title = sanitize_filename(title)
    if not title:
        title = conv_dir
        
    filename = f"{date_str}_{title}.txt"
    dest_path = os.path.join(output_dir, filename)

    get_readable_text(overview_path, dest_path)
    print(f"Exported: {filename}")

count = 0
for item in os.listdir(brain_dir):
    path = os.path.join(brain_dir, item)
    if os.path.isdir(path):
        process_conversation(item)
        count += 1
print(f"Done processing {count} folders.")
