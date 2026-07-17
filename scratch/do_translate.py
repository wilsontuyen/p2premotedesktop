import json
import os
import time
import sys
import urllib.request
import urllib.parse

sys.stdout.reconfigure(encoding='utf-8')

LANG_MAP = {
    "en": "en",
    "de": "de",
    "fr": "fr",
    "jp": "ja",
    "kr": "ko",
    "ru": "ru",
    "cn": "zh-cn",
    "tw": "zh-tw"
}

def translate_text(text, src, dest):
    url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl={src}&tl={dest}&dt=t&q={urllib.parse.quote(text)}"
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    try:
        response = urllib.request.urlopen(req)
        data = json.loads(response.read().decode('utf-8'))
        # The result is typically data[0][0][0], but for multi-sentence it could be multiple
        res = ""
        if data and data[0]:
            for chunk in data[0]:
                if chunk[0]:
                    res += chunk[0]
        return res
    except Exception as e:
        print(f"Failed to translate '{text}': {e}")
        return text

base_dir = 'd:/Data/AG/remote_desktop/lang'
template_path = os.path.join(base_dir, 'lang_template.json')

with open(template_path, 'r', encoding='utf-8') as f:
    template = json.load(f)

for lang_code, google_code in LANG_MAP.items():
    lang_file = os.path.join(base_dir, f"{lang_code}.json")
    
    existing = {}
    if os.path.exists(lang_file):
        try:
            with open(lang_file, 'r', encoding='utf-8') as f:
                existing = json.load(f)
        except:
            pass
            
    print(f"Translating {lang_code}...")
    
    # We translate item by item with delay to avoid ban
    count = 0
    for k in template.keys():
        if k not in existing or existing[k] == k or not existing[k]:
            if len(k) <= 2 and not any(c.isalpha() for c in k):
                existing[k] = k
            else:
                existing[k] = translate_text(k, 'vi', google_code)
                count += 1
                if count % 10 == 0:
                    print(f"  [{lang_code}] Translated {count} items")
                time.sleep(0.5)  # Rate limiting
                
    with open(lang_file, 'w', encoding='utf-8') as f:
        json.dump(existing, f, ensure_ascii=False, indent=2)

print("Translation completed.")
