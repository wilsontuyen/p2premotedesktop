import os
import json
import codecs

lang_dir = r"d:\Data\AG\remote_desktop\lang"

translations = {
    "Thuộc tính": {
        "en.json": "Properties",
        "cn.json": "属性",
        "tw.json": "屬性",
        "jp.json": "プロパティ",
        "kr.json": "속성",
        "de.json": "Eigenschaften",
        "fr.json": "Propriétés",
        "ru.json": "Свойства"
    },
    "Tên:": {
        "en.json": "Name:",
        "cn.json": "名称:",
        "tw.json": "名稱:",
        "jp.json": "名前:",
        "kr.json": "이름:",
        "de.json": "Name:",
        "fr.json": "Nom:",
        "ru.json": "Имя:"
    },
    "Loại:": {
        "en.json": "Type:",
        "cn.json": "类型:",
        "tw.json": "類型:",
        "jp.json": "種類:",
        "kr.json": "유형:",
        "de.json": "Typ:",
        "fr.json": "Type:",
        "ru.json": "Тип:"
    },
    "Vị trí:": {
        "en.json": "Location:",
        "cn.json": "位置:",
        "tw.json": "位置:",
        "jp.json": "場所:",
        "kr.json": "위치:",
        "de.json": "Ort:",
        "fr.json": "Emplacement:",
        "ru.json": "Расположение:"
    },
    "Kích thước:": {
        "en.json": "Size:",
        "cn.json": "大小:",
        "tw.json": "大小:",
        "jp.json": "サイズ:",
        "kr.json": "크기:",
        "de.json": "Größe:",
        "fr.json": "Taille:",
        "ru.json": "Размер:"
    },
    "Đang tính...": {
        "en.json": "Calculating...",
        "cn.json": "计算中...",
        "tw.json": "計算中...",
        "jp.json": "計算中...",
        "kr.json": "계산 중...",
        "de.json": "Berechne...",
        "fr.json": "Calcul en cours...",
        "ru.json": "Вычисление..."
    },
    "Chứa:": {
        "en.json": "Contains:",
        "cn.json": "包含:",
        "tw.json": "包含:",
        "jp.json": "内容:",
        "kr.json": "내용:",
        "de.json": "Enthält:",
        "fr.json": "Contient:",
        "ru.json": "Содержит:"
    },
    "Tệp: {file_count}, Thư mục: {folder_count}": {
        "en.json": "Files: {file_count}, Folders: {folder_count}",
        "cn.json": "文件: {file_count}, 文件夹: {folder_count}",
        "tw.json": "檔案: {file_count}, 資料夾: {folder_count}",
        "jp.json": "ファイル: {file_count}, フォルダ: {folder_count}",
        "kr.json": "파일: {file_count}, 폴더: {folder_count}",
        "de.json": "Dateien: {file_count}, Ordner: {folder_count}",
        "fr.json": "Fichiers: {file_count}, Dossiers: {folder_count}",
        "ru.json": "Файлов: {file_count}, Папок: {folder_count}"
    },
    "Sửa đổi:": {
        "en.json": "Modified:",
        "cn.json": "修改时间:",
        "tw.json": "修改時間:",
        "jp.json": "更新日時:",
        "kr.json": "수정 날짜:",
        "de.json": "Geändert:",
        "fr.json": "Modifié:",
        "ru.json": "Изменен:"
    },
    "Đóng": {
        "en.json": "Close",
        "cn.json": "关闭",
        "tw.json": "關閉",
        "jp.json": "閉じる",
        "kr.json": "닫기",
        "de.json": "Schließen",
        "fr.json": "Fermer",
        "ru.json": "Закрыть"
    }
}

files = os.listdir(lang_dir)
for f in files:
    if not f.endswith('.json'): continue
    path = os.path.join(lang_dir, f)
    
    with codecs.open(path, 'r', 'utf-8') as file:
        data = json.load(file)
        
    for vn_key, trans_dict in translations.items():
        if f == "lang_template.json":
            data[vn_key] = vn_key
        else:
            if f in trans_dict:
                data[vn_key] = trans_dict[f]
                
    # Sort keys alphabetically
    sorted_data = dict(sorted(data.items(), key=lambda item: item[0].lower()))
    
    with codecs.open(path, 'w', 'utf-8') as file:
        json.dump(sorted_data, file, ensure_ascii=False, indent=2)

print("Language files updated successfully.")
