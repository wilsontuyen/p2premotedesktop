import json
import os

langs = ['en.json', 'de.json', 'fr.json', 'jp.json', 'kr.json', 'ru.json', 'cn.json', 'tw.json']

translations = {
    "Chuyển qua\n>>": {
        "en.json": "Upload\n>>",
        "de.json": "Hochladen\n>>",
        "fr.json": "Upload\n>>",
        "jp.json": "アップロード\n>>",
        "kr.json": "업로드\n>>",
        "ru.json": "Загрузить\n>>",
        "cn.json": "上传\n>>",
        "tw.json": "上傳\n>>"
    },
    "Nhận về\n<<": {
        "en.json": "Download\n<<",
        "de.json": "Herunterladen\n<<",
        "fr.json": "Download\n<<",
        "jp.json": "ダウンロード\n<<",
        "kr.json": "다운로드\n<<",
        "ru.json": "Скачать\n<<",
        "cn.json": "下载\n<<",
        "tw.json": "下載\n<<"
    }
}

for lang in langs:
    path = os.path.join('lang', lang)
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            target = json.load(f)
        for key, val in translations.items():
            target[key] = val[lang]
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(target, f, ensure_ascii=False, indent=2, sort_keys=True)
