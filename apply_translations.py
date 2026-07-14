import json
import os

langs = ['en.json', 'de.json', 'fr.json', 'jp.json', 'kr.json', 'ru.json', 'cn.json', 'tw.json']

translations = {
    " và {count} mục khác": {
        "en.json": " and {count} other items",
        "de.json": " und {count} weitere Elemente",
        "fr.json": " et {count} autres éléments",
        "jp.json": " と他 {count} 項目",
        "kr.json": " 외 {count}개 항목",
        "ru.json": " и {count} других элементов",
        "cn.json": " 及其他 {count} 个项目",
        "tw.json": " 及其他 {count} 個項目"
    },
    "Bạn có chắc muốn xóa '{item_name}' không?": {
        "en.json": "Are you sure you want to delete '{item_name}'?",
        "de.json": "Möchten Sie '{item_name}' wirklich löschen?",
        "fr.json": "Êtes-vous sûr de vouloir supprimer '{item_name}'?",
        "jp.json": "本当に '{item_name}' を削除しますか？",
        "kr.json": "'{item_name}'을(를) 삭제하시겠습니까?",
        "ru.json": "Вы уверены, что хотите удалить '{item_name}'?",
        "cn.json": "您确定要删除 '{item_name}' 吗？",
        "tw.json": "您確定要刪除 '{item_name}' 嗎？"
    },
    "Bạn có chắc muốn xóa '{item_name}' khỏi máy điều khiển không?": {
        "en.json": "Are you sure you want to delete '{item_name}' from the remote host?",
        "de.json": "Möchten Sie '{item_name}' wirklich vom Remote-Host löschen?",
        "fr.json": "Êtes-vous sûr de vouloir supprimer '{item_name}' de l'hôte distant?",
        "jp.json": "本当にリモートホストから '{item_name}' を削除しますか？",
        "kr.json": "원격 호스트에서 '{item_name}'을(를) 삭제하시겠습니까?",
        "ru.json": "Вы уверены, что хотите удалить '{item_name}' с удаленного хоста?",
        "cn.json": "您确定要从远程主机中删除 '{item_name}' 吗？",
        "tw.json": "您確定要從遠端主機中刪除 '{item_name}' 嗎？"
    },
    "Bạn có chắc muốn xóa {count} mục đã chọn không?": {
        "en.json": "Are you sure you want to delete the {count} selected items?",
        "de.json": "Möchten Sie die {count} ausgewählten Elemente wirklich löschen?",
        "fr.json": "Êtes-vous sûr de vouloir supprimer les {count} éléments sélectionnés?",
        "jp.json": "選択した {count} 項目を本当に削除しますか？",
        "kr.json": "선택한 {count}개 항목을 삭제하시겠습니까?",
        "ru.json": "Вы уверены, что хотите удалить {count} выбранных элементов?",
        "cn.json": "您确定要删除选中的 {count} 个项目吗？",
        "tw.json": "您確定要刪除選中的 {count} 個項目嗎？"
    },
    "Bạn có chắc muốn xóa {count} mục đã chọn khỏi máy điều khiển không?": {
        "en.json": "Are you sure you want to delete the {count} selected items from the remote host?",
        "de.json": "Möchten Sie die {count} ausgewählten Elemente wirklich vom Remote-Host löschen?",
        "fr.json": "Êtes-vous sûr de vouloir supprimer les {count} éléments sélectionnés de l'hôte distant?",
        "jp.json": "選択した {count} 項目をリモートホストから本当に削除しますか？",
        "kr.json": "원격 호스트에서 선택한 {count}개 항목을 삭제하시겠습니까?",
        "ru.json": "Вы уверены, что хотите удалить {count} выбранных элементов с удаленного хоста?",
        "cn.json": "您确定要从远程主机中删除选中的 {count} 个项目吗？",
        "tw.json": "您確定要從遠端主機中刪除選中的 {count} 個項目嗎？"
    },
    "Chuyển qua\\n>>": {
        "en.json": "Transfer\\n>>",
        "de.json": "Übertragen\\n>>",
        "fr.json": "Transférer\\n>>",
        "jp.json": "転送\\n>>",
        "kr.json": "전송\\n>>",
        "ru.json": "Передать\\n>>",
        "cn.json": "传输\\n>>",
        "tw.json": "傳輸\\n>>"
    },
    "Không thể gửi lệnh: {ex}": {
        "en.json": "Failed to send command: {ex}",
        "de.json": "Befehl konnte nicht gesendet werden: {ex}",
        "fr.json": "Échec de l'envoi de la commande: {ex}",
        "jp.json": "コマンドの送信に失敗しました: {ex}",
        "kr.json": "명령 전송 실패: {ex}",
        "ru.json": "Не удалось отправить команду: {ex}",
        "cn.json": "发送命令失败: {ex}",
        "tw.json": "發送命令失敗: {ex}"
    },
    "Không thể lưu: {e}": {
        "en.json": "Cannot save: {e}",
        "de.json": "Speichern nicht möglich: {e}",
        "fr.json": "Impossible d'enregistrer: {e}",
        "jp.json": "保存できません: {e}",
        "kr.json": "저장할 수 없음: {e}",
        "ru.json": "Не удается сохранить: {e}",
        "cn.json": "无法保存: {e}",
        "tw.json": "無法保存: {e}"
    },
    "Không thể xem thư mục '{name}' bằng Notepad!": {
        "en.json": "Cannot view folder '{name}' with Notepad!",
        "de.json": "Ordner '{name}' kann nicht mit Notepad angezeigt werden!",
        "fr.json": "Impossible d'afficher le dossier '{name}' avec le Bloc-notes!",
        "jp.json": "Notepadでフォルダ '{name}' を表示できません！",
        "kr.json": "메모장으로 '{name}' 폴더를 볼 수 없습니다!",
        "ru.json": "Невозможно просмотреть папку '{name}' с помощью Блокнота!",
        "cn.json": "无法使用记事本查看文件夹 '{name}'！",
        "tw.json": "無法使用記事本查看資料夾 '{name}'！"
    },
    "Lỗi tạo Notepad: {ex}": {
        "en.json": "Error creating Notepad: {ex}",
        "de.json": "Fehler beim Erstellen von Notepad: {ex}",
        "fr.json": "Erreur de création du Bloc-notes: {ex}",
        "jp.json": "Notepadの作成エラー: {ex}",
        "kr.json": "메모장 생성 오류: {ex}",
        "ru.json": "Ошибка создания Блокнота: {ex}",
        "cn.json": "创建记事本时出错: {ex}",
        "tw.json": "創建記事本時出錯: {ex}"
    },
    "Lỗi xóa {name}: {e}": {
        "en.json": "Error deleting {name}: {e}",
        "de.json": "Fehler beim Löschen von {name}: {e}",
        "fr.json": "Erreur lors de la suppression de {name}: {e}",
        "jp.json": "{name} の削除エラー: {e}",
        "kr.json": "{name} 삭제 오류: {e}",
        "ru.json": "Ошибка удаления {name}: {e}",
        "cn.json": "删除 {name} 时出错: {e}",
        "tw.json": "刪除 {name} 時出錯: {e}"
    },
    "Nhận về\\n<<": {
        "en.json": "Receive\\n<<",
        "de.json": "Empfangen\\n<<",
        "fr.json": "Recevoir\\n<<",
        "jp.json": "受信\\n<<",
        "kr.json": "수신\\n<<",
        "ru.json": "Получить\\n<<",
        "cn.json": "接收\\n<<",
        "tw.json": "接收\\n<<"
    },
    "Nhập tên mới cho '{name}':": {
        "en.json": "Enter new name for '{name}':",
        "de.json": "Geben Sie einen neuen Namen für '{name}' ein:",
        "fr.json": "Entrez un nouveau nom pour '{name}':",
        "jp.json": "'{name}' の新しい名前を入力してください:",
        "kr.json": "'{name}'의 새 이름 입력:",
        "ru.json": "Введите новое имя для '{name}':",
        "cn.json": "为 '{name}' 输入新名称:",
        "tw.json": "為 '{name}' 輸入新名稱:"
    },
    "Nhập tên thư mục mới:": {
        "en.json": "Enter new folder name:",
        "de.json": "Geben Sie den neuen Ordnernamen ein:",
        "fr.json": "Entrez le nouveau nom du dossier:",
        "jp.json": "新しいフォルダ名を入力してください:",
        "kr.json": "새 폴더 이름 입력:",
        "ru.json": "Введите новое имя папки:",
        "cn.json": "输入新文件夹名称:",
        "tw.json": "輸入新資料夾名稱:"
    },
    "P2P Remote Desktop - Trình Quản Lý Tệp (File Manager){host_title}": {
        "en.json": "P2P Remote Desktop - File Manager{host_title}",
        "de.json": "P2P Remote Desktop - Dateimanager{host_title}",
        "fr.json": "P2P Remote Desktop - Gestionnaire de fichiers{host_title}",
        "jp.json": "P2P Remote Desktop - ファイルマネージャー{host_title}",
        "kr.json": "P2P Remote Desktop - 파일 관리자{host_title}",
        "ru.json": "P2P Remote Desktop - Файловый менеджер{host_title}",
        "cn.json": "P2P Remote Desktop - 文件管理器{host_title}",
        "tw.json": "P2P Remote Desktop - 檔案管理員{host_title}"
    },
    "Soạn thảo (Local) - {name}": {
        "en.json": "Editor (Local) - {name}",
        "de.json": "Editor (Lokal) - {name}",
        "fr.json": "Éditeur (Local) - {name}",
        "jp.json": "エディター (ローカル) - {name}",
        "kr.json": "편집기 (로컬) - {name}",
        "ru.json": "Редактор (Локальный) - {name}",
        "cn.json": "编辑器 (本地) - {name}",
        "tw.json": "編輯器 (本機) - {name}"
    },
    "Soạn thảo (Remote) - {name}": {
        "en.json": "Editor (Remote) - {name}",
        "de.json": "Editor (Remote) - {name}",
        "fr.json": "Éditeur (Distant) - {name}",
        "jp.json": "エディター (リモート) - {name}",
        "kr.json": "편집기 (원격) - {name}",
        "ru.json": "Редактор (Удаленный) - {name}",
        "cn.json": "编辑器 (远程) - {name}",
        "tw.json": "編輯器 (遠端) - {name}"
    },
    "Thư mục \"{new_name}\" đã tồn tại trên \"{current_dir}\"": {
        "en.json": "Folder \"{new_name}\" already exists in \"{current_dir}\"",
        "de.json": "Ordner \"{new_name}\" existiert bereits in \"{current_dir}\"",
        "fr.json": "Le dossier \"{new_name}\" existe déjà dans \"{current_dir}\"",
        "jp.json": "フォルダ \"{new_name}\" は \"{current_dir}\" に既に存在します",
        "kr.json": "\"{new_name}\" 폴더가 \"{current_dir}\"에 이미 존재합니다",
        "ru.json": "Папка \"{new_name}\" уже существует в \"{current_dir}\"",
        "cn.json": "文件夹 \"{new_name}\" 已存在于 \"{current_dir}\"",
        "tw.json": "資料夾 \"{new_name}\" 已存在於 \"{current_dir}\""
    },
    "Thư mục mới": {
        "en.json": "New Folder",
        "de.json": "Neuer Ordner",
        "fr.json": "Nouveau dossier",
        "jp.json": "新しいフォルダ",
        "kr.json": "새 폴더",
        "ru.json": "Новая папка",
        "cn.json": "新建文件夹",
        "tw.json": "新增資料夾"
    },
    "Xem file": {
        "en.json": "View file",
        "de.json": "Datei anzeigen",
        "fr.json": "Voir le fichier",
        "jp.json": "ファイルを表示",
        "kr.json": "파일 보기",
        "ru.json": "Просмотр файла",
        "cn.json": "查看文件",
        "tw.json": "查看檔案"
    },
    "{dst_title}\\n- Thư mục: {dst_path}\\n- Dung lượng: {dst_sz}\\n- Ngày sửa đổi: {dst_mtime}": {
        "en.json": "{dst_title}\\n- Folder: {dst_path}\\n- Size: {dst_sz}\\n- Modified: {dst_mtime}",
        "de.json": "{dst_title}\\n- Ordner: {dst_path}\\n- Größe: {dst_sz}\\n- Geändert: {dst_mtime}",
        "fr.json": "{dst_title}\\n- Dossier: {dst_path}\\n- Taille: {dst_sz}\\n- Modifié: {dst_mtime}",
        "jp.json": "{dst_title}\\n- フォルダ: {dst_path}\\n- サイズ: {dst_sz}\\n- 変更日: {dst_mtime}",
        "kr.json": "{dst_title}\\n- 폴더: {dst_path}\\n- 크기: {dst_sz}\\n- 수정일: {dst_mtime}",
        "ru.json": "{dst_title}\\n- Папка: {dst_path}\\n- Размер: {dst_sz}\\n- Изменено: {dst_mtime}",
        "cn.json": "{dst_title}\\n- 文件夹: {dst_path}\\n- 大小: {dst_sz}\\n- 修改日期: {dst_mtime}",
        "tw.json": "{dst_title}\\n- 資料夾: {dst_path}\\n- 大小: {dst_sz}\\n- 修改日期: {dst_mtime}"
    },
    "{src_title}\\n- Thư mục: {src_path}\\n- Dung lượng: {src_sz}\\n- Ngày sửa đổi: {src_mtime}": {
        "en.json": "{src_title}\\n- Folder: {src_path}\\n- Size: {src_sz}\\n- Modified: {src_mtime}",
        "de.json": "{src_title}\\n- Ordner: {src_path}\\n- Größe: {src_sz}\\n- Geändert: {src_mtime}",
        "fr.json": "{src_title}\\n- Dossier: {src_path}\\n- Taille: {src_sz}\\n- Modifié: {src_mtime}",
        "jp.json": "{src_title}\\n- フォルダ: {src_path}\\n- サイズ: {src_sz}\\n- 変更日: {src_mtime}",
        "kr.json": "{src_title}\\n- 폴더: {src_path}\\n- 크기: {src_sz}\\n- 수정일: {src_mtime}",
        "ru.json": "{src_title}\\n- Папка: {src_path}\\n- Размер: {src_sz}\\n- Изменено: {src_mtime}",
        "cn.json": "{src_title}\\n- 文件夹: {src_path}\\n- 大小: {src_sz}\\n- 修改日期: {src_mtime}",
        "tw.json": "{src_title}\\n- 資料夾: {src_path}\\n- 大小: {src_sz}\\n- 修改日期: {src_mtime}"
    },
    "Đã gửi yêu cầu mở file {ext} bằng ứng dụng mặc định trên máy bị điều khiển.": {
        "en.json": "Sent request to open {ext} file with the default application on the remote host.",
        "de.json": "Anfrage zum Öffnen der {ext}-Datei mit der Standardanwendung auf dem Remote-Host gesendet.",
        "fr.json": "Demande envoyée pour ouvrir le fichier {ext} avec l'application par défaut sur l'hôte distant.",
        "jp.json": "リモートホストのデフォルトアプリケーションで {ext} ファイルを開くリクエストを送信しました。",
        "kr.json": "원격 호스트의 기본 애플리케이션으로 {ext} 파일을 열도록 요청을 보냈습니다.",
        "ru.json": "Отправлен запрос на открытие файла {ext} с помощью приложения по умолчанию на удаленном хосте.",
        "cn.json": "已发送使用远程主机上的默认应用程序打开 {ext} 文件的请求。",
        "tw.json": "已發送使用遠端主機上的預設應用程式打開 {ext} 檔案的請求。"
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
