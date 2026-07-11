import json
import os

langs = {
    'en': {
        "Kết nối bị từ chối:\n{msg}": "Connection refused:\n{msg}",
        "Lỗi xác thực handshake:\n{err}": "Handshake authentication error:\n{err}"
    },
    'de': {
        "Kết nối bị từ chối:\n{msg}": "Verbindung abgelehnt:\n{msg}",
        "Lỗi xác thực handshake:\n{err}": "Handshake-Authentifizierungsfehler:\n{err}"
    },
    'fr': {
        "Kết nối bị từ chối:\n{msg}": "Connexion refusée:\n{msg}",
        "Lỗi xác thực handshake:\n{err}": "Erreur d'authentification handshake:\n{err}"
    },
    'jp': {
        "Kết nối bị từ chối:\n{msg}": "接続が拒否されました:\n{msg}",
        "Lỗi xác thực handshake:\n{err}": "ハンドシェイク認証エラー:\n{err}"
    },
    'kr': {
        "Kết nối bị từ chối:\n{msg}": "연결이 거부되었습니다:\n{msg}",
        "Lỗi xác thực handshake:\n{err}": "핸드셰이크 인증 오류:\n{err}"
    },
    'ru': {
        "Kết nối bị từ chối:\n{msg}": "В соединении отказано:\n{msg}",
        "Lỗi xác thực handshake:\n{err}": "Ошибка аутентификации handshake:\n{err}"
    },
    'cn': {
        "Kết nối bị từ chối:\n{msg}": "连接被拒绝：\n{msg}",
        "Lỗi xác thực handshake:\n{err}": "握手身份验证错误：\n{err}"
    },
    'tw': {
        "Kết nối bị từ chối:\n{msg}": "連線被拒絕：\n{msg}",
        "Lỗi xác thực handshake:\n{err}": "交握驗證錯誤：\n{err}"
    }
}

for lang, translations in langs.items():
    path = f'd:/Data/AG/remote_desktop/lang/{lang}.json'
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        for k, v in translations.items():
            data[k] = v
            
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            
print("Done translating missing keys.")
