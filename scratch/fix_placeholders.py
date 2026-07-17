import json
import os
import re

base_dir = 'd:/Data/AG/remote_desktop/lang'
template_path = os.path.join(base_dir, 'lang_template.json')

with open(template_path, 'r', encoding='utf-8') as f:
    template = json.load(f)

for filename in os.listdir(base_dir):
    if not filename.endswith('.json') or filename == 'lang_template.json':
        continue
        
    filepath = os.path.join(base_dir, filename)
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        updated = False
        for k, v in data.items():
            if k in template:
                # find all placeholders in original
                orig_placeholders = re.findall(r'\{[a-zA-Z0-9_]+\}', k)
                if orig_placeholders:
                    # check if the translated string has the exact same placeholders
                    trans_placeholders = re.findall(r'\{.*?\}', v)
                    
                    if len(orig_placeholders) == len(trans_placeholders):
                        # replace translated placeholders with original ones
                        new_v = v
                        for i, orig_p in enumerate(orig_placeholders):
                            if trans_placeholders[i] != orig_p:
                                new_v = new_v.replace(trans_placeholders[i], orig_p)
                                updated = True
                        data[k] = new_v
                    else:
                        # mismatch in count, revert to original
                        if v != k:
                            data[k] = k
                            updated = True
                            
        if updated:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"Fixed placeholders in {filename}")
            
    except Exception as e:
        print(f"Error processing {filename}: {e}")
