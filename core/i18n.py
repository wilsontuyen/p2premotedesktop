import os
import json
import sys

_translations = {}
_current_lang = "vi"

LANGUAGE_NAMES = {
    "vi": "Tiếng Việt",
    "en": "English",
    "de": "German",
    "fr": "French",
    "jp": "Japanese",
    "kr": "Korean",
    "ru": "Russian",
    "cn": "Chinese",
    "tw": "Traditional Chinese"
}

def get_language_name(lang_code):
    return LANGUAGE_NAMES.get(lang_code, lang_code.upper())

def get_lang_dir():
    if getattr(sys, 'frozen', False):
        base_dir = os.path.dirname(sys.executable)
    else:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    lang_dir = os.path.join(base_dir, "lang")
    os.makedirs(lang_dir, exist_ok=True)
    return lang_dir

def load_language(lang_code):
    global _translations, _current_lang
    _current_lang = lang_code
    
    lang_file = os.path.join(get_lang_dir(), f"{lang_code}.json")
    if os.path.exists(lang_file):
        try:
            with open(lang_file, "r", encoding="utf-8") as f:
                _translations = json.load(f)
        except:
            _translations = {}
    else:
        _translations = {}

def get_text(text):
    return _translations.get(text, text)

def _(text):
    return get_text(text)

def export_template(template_dict):
    lang_dir = get_lang_dir()
    template_file = os.path.join(lang_dir, "lang_template.json")
    try:
        with open(template_file, "w", encoding="utf-8") as f:
            json.dump(template_dict, f, ensure_ascii=False, indent=2)
        return template_file
    except:
        return None

def get_available_languages():
    lang_dir = get_lang_dir()
    langs = ["vi"]
    if os.path.exists(lang_dir):
        for f in os.listdir(lang_dir):
            if f.endswith(".json") and f != "lang_template.json" and f != "vi.json":
                langs.append(f[:-5])
    return list(set(langs))
