import os
import json
import re
import datetime
from pathlib import Path

brain_dirs = [
    r"C:\Users\Tuyen\.gemini\antigravity-ide\brain",
    r"C:\Users\Tuyen\.gemini\antigravity\brain",
]
output_dir = r"D:\Data\AI Code\remote_desktop\conversations"

os.makedirs(output_dir, exist_ok=True)

def sanitize_filename(name):
    name = re.sub(r'[\\/*?:"<>|]', "", name).strip()
    return re.sub(r'\s+', "_", name)

def get_readable_text(log_path, dest_path):
    try:
        with open(log_path, "r", encoding="utf-8") as f:
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
                        req_match = re.search(r"<USER_REQUEST>\s*(.*?)\s*</USER_REQUEST>", content, re.DOTALL | re.IGNORECASE)
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
                                tc_name = tc.get("name") or tc.get("tool_name") or "tool"
                                out.write(f"[Action: {tc_name}]\n")
                                args = tc.get("args") or tc.get("arguments") or {}
                                if isinstance(args, str):
                                    try:
                                        args = json.loads(args)
                                    except Exception:
                                        args = {"raw": args}
                                if isinstance(args, dict):
                                    for k, v in args.items():
                                        if len(str(v)) < 200:
                                            out.write(f"  {k}: {v}\n")
                                        else:
                                            out.write(f"  {k}: {str(v)[:200]}...\n")
                            out.write("\n")
                except json.JSONDecodeError:
                    continue
    except Exception as e:
        print(f"Error formatting {log_path}: {e}")

def find_log_file(brain_dir, conv_dir):
    logs_dir = os.path.join(brain_dir, conv_dir, ".system_generated", "logs")
    for fname in ("transcript_full.jsonl", "transcript.jsonl", "overview.txt"):
        candidate = os.path.join(logs_dir, fname)
        if os.path.exists(candidate) and os.path.getsize(candidate) > 0:
            return candidate
    return None

def parse_iso_datetime(created_at):
    if not created_at:
        return None
    try:
        clean = created_at.strip()
        if clean.endswith("Z"):
            clean = clean[:-1] + "+00:00"
        dt = datetime.datetime.fromisoformat(clean)
        if dt.tzinfo is not None:
            tz_vn = datetime.timezone(datetime.timedelta(hours=7))
            dt = dt.astimezone(tz_vn)
        else:
            dt = dt + datetime.timedelta(hours=7)
        return dt.strftime("%Y-%m-%d_%H%M%S")
    except Exception:
        try:
            dt = datetime.datetime.strptime(created_at[:19], "%Y-%m-%dT%H:%M:%S")
            dt = dt + datetime.timedelta(hours=7)
            return dt.strftime("%Y-%m-%d_%H%M%S")
        except Exception:
            return None

def process_conversation(brain_dir, conv_dir):
    log_path = find_log_file(brain_dir, conv_dir)
    if not log_path:
        return False

    first_user_data = None
    first_data = None
    with open(log_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
            except Exception:
                continue
            if first_data is None:
                first_data = d
            if d.get("source") == "USER_EXPLICIT" and d.get("content"):
                first_user_data = d
                break

    data = first_user_data or first_data
    if not data:
        return False
        
    created_at = data.get("created_at", "") or (first_data.get("created_at", "") if first_data else "")
    content = data.get("content", "")

    date_str = parse_iso_datetime(created_at) or "UNKNOWN_DATE"

    # Extract title
    match = re.search(r"<USER_REQUEST>\s*(.*?)\s*</USER_REQUEST>", content, re.IGNORECASE | re.DOTALL)
    raw_title = match.group(1).strip() if match else content.strip()
    lines = [ln.strip() for ln in raw_title.splitlines() if ln.strip()]
    title = lines[0] if lines else ""
        
    # truncate title
    title = title[:40]

    title = sanitize_filename(title)
    if not title:
        title = conv_dir
        
    filename = f"{date_str}_{title}.txt"
    dest_path = os.path.join(output_dir, filename)

    get_readable_text(log_path, dest_path)
    return True

if __name__ == "__main__":
    count = 0
    for b_dir in brain_dirs:
        if not os.path.exists(b_dir):
            continue
        for item in os.listdir(b_dir):
            path = os.path.join(b_dir, item)
            if os.path.isdir(path):
                if process_conversation(b_dir, item):
                    count += 1
    print(f"Done processing {count} conversations.")
