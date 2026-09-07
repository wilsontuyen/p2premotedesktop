import os
import sys

from core.config import app_dir
from core.i18n import _current_lang


def _candidate_paths(filename):
    paths = [os.path.join(app_dir, filename)]
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    paths.append(os.path.join(here, filename))
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        paths.append(os.path.join(sys._MEIPASS, filename))
    return paths


def load_disclaimer_text(lang=None):
    lang = (lang or _current_lang or "vi").lower()
    filename = "disclaimer_en.txt" if lang != "vi" else "disclaimer_vi.txt"
    for path in _candidate_paths(filename):
        try:
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8-sig") as f:
                    text = f.read().strip()
                if text:
                    return text
        except Exception:
            continue
    if filename == "disclaimer_en.txt":
        for path in _candidate_paths("disclaimer_vi.txt"):
            try:
                if os.path.exists(path):
                    with open(path, "r", encoding="utf-8-sig") as f:
                        text = f.read().strip()
                    if text:
                        return text
            except Exception:
                continue
    return ""
