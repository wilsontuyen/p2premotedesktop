import json
import os
import sys
sys.stdout.reconfigure(encoding='utf-8')
from deep_translator import GoogleTranslator

vietnamese_chars = set("áàảãạăắằẳẵặâấầẩẫậéèẻẽẹêếềểễệíìỉĩịóòỏõọôốồổỗộơớờởỡợúùủũụưứừửữựýỳỷỹỵđÁÀẢÃẠĂẮẰẲẴẶÂẤẦẨẪẬÉÈẺẼẸÊẾỀỂỄỆÍÌỈĨỊÓÒỎÕỌÔỐỒỔỖỘƠỚỜỞỠỢÚÙỦŨỤƯỨỪỬỮỰÝỲỶỸỴĐ")

def is_valid_vietnamese(text):
    if len(text) > 100 and len(set(text).intersection(vietnamese_chars)) > 50:
        # Ignore the alphabet string itself
        return False
    return any(c in vietnamese_chars for c in text)

lang_map = {
    'en': 'en',
    'cn': 'zh-CN',
    'tw': 'zh-TW',
    'de': 'de',
    'fr': 'fr',
    'jp': 'ja',
    'kr': 'ko',
    'ru': 'ru'
}

with open('lang/lang_template.json', 'r', encoding='utf-8') as f:
    template = json.load(f)

# Delete bad keys
bad_keys = [k for k in template if not is_valid_vietnamese(k)]
for bk in bad_keys:
    del template[bk]
    print(f"Deleted bad key: {repr(bk)}")

with open('lang/lang_template.json', 'w', encoding='utf-8') as f:
    json.dump(template, f, ensure_ascii=False, indent=2)

for lf in os.listdir('lang'):
    if lf.endswith('.json') and lf not in ('lang_template.json', 'vi.json'):
        lang_code = lf[:-5]
        if lang_code not in lang_map: continue
        target_lang = lang_map[lang_code]
        
        filepath = os.path.join('lang', lf)
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        translator = GoogleTranslator(source='vi', target=target_lang)
        changed = False
        
        # Remove keys not in template
        keys_to_remove = [k for k in data if k not in template]
        for k in keys_to_remove:
            del data[k]
            changed = True
            
        count = 0
        for k in template:
            if k not in data or data[k] == "":
                try:
                    res = translator.translate(k)
                    data[k] = res if res else k
                    changed = True
                    count += 1
                except Exception:
                    pass
                    
        if changed:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
        print(f"Cleaned and translated {count} keys for {lf}")
