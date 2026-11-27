# Hướng Dẫn Đóng Gói Bản Host XP Lite (32-bit x86)

Thư mục `xp_host/` chứa trọn bộ mã nguồn độc lập của **EasyRemoteDesktop Host XP Lite**, tương thích 100% giao thức với ứng dụng Client trên Windows 10/11 hiện tại nhưng loại bỏ hoàn toàn các thư viện nặng không chạy được trên nhân Windows XP (`NT 5.1`).

---

## 1. Chạy Thử Trực Tiếp Bằng Mã Nguồn (Trên Máy Dev Hoặc Máy XP Đã Có Python)

```powershell
# Khởi chạy giao diện Host XP Lite (tự mở khay đồng hồ + lắng nghe LAN & Signaling)
.\.venv\Scripts\python.exe xp_host\app_xp.py

# Cài đặt dịch vụ nền (hỗ trợ điều khiển từ màn hình đăng nhập Ctrl+Alt+Del của XP - cần quyền Admin)
.\.venv\Scripts\python.exe xp_host\app_xp.py --install-service

# Gỡ dịch vụ nền
.\.venv\Scripts\python.exe xp_host\app_xp.py --uninstall-service
```

---

## 2. Quy Trình Đóng Gói `.exe` Chạy Trên Mọi Máy Windows XP SP2/SP3 (32-bit)

Vì các máy Windows XP thực tế đa phần là **32-bit (x86)** và nhân `NT 5.1` thiếu các hàm API của Windows 7/10, khi đóng gói bản phân phối cho khách hàng dùng máy XP, hãy thực hiện 3 bước sau trên máy lập trình viên:

### Bước 1: Chuẩn bị môi trường Python 3.8 x86 (32-bit) XP-Backport
1. Tải bản **Python 3.8.x (32-bit x86) Windows XP Backport** (ví dụ bản *PythonWinXP / adoxa /adang1345 Python 3.8 x86 XP*) giải nén vào `C:\Python38-XP32`.
2. Tạo môi trường ảo 32-bit riêng cho XP và chỉ cài đúng các gói nhẹ trong `requirements_xp.txt`:
   ```powershell
   C:\Python38-XP32\python.exe -m venv .venv_xp32
   .\.venv_xp32\Scripts\pip.exe install -r xp_host\requirements_xp.txt pyinstaller==4.10
   ```
   *(Lưu ý: `pycryptodomex` cung cấp C-extension `ChaCha20_Poly1305` tốc độ cao trên x86; kể cả khi không cài `pycryptodomex`, `xp_crypto.py` vẫn có bộ mã hóa RFC 8439 thuần Python dự phòng sẵn).*

### Bước 2: Chạy Script Build & Tự Động Hạ PE Subsystem Về `5.01`
```powershell
.\.venv_xp32\Scripts\python.exe xp_host\build_xp_host.py
```
Script `build_xp_host.py` sẽ tự động:
* Kiểm tra cú pháp sạch 100% toàn bộ file trong `xp_host/`.
* Đóng gói ra thư mục `dist_xp_host\RemoteDesktopXPHost\` (không chứa `cv2`, `numpy`, `pygame`, `cryptography`, `dxcam`).
* **Tự động vá PE Header (`MajorSubsystemVersion = 5, MinorSubsystemVersion = 5.01`)** cho mọi file `.exe` / `.dll` / `.pyd` để Windows XP không bao giờ báo lỗi *"is not a valid Win32 application"*.
* Tự động xóa sạch các file cấu hình/mật khẩu cá nhân của máy build.

### Bước 3: Đóng Gói Bộ Cài Đặt Bằng Inno Setup 5.6.1
* Mở hoặc biên dịch `xp_host\installer_xp_host.iss` bằng **Inno Setup 5.6.1 Unicode** (Inno Setup 6 đã ngừng hỗ trợ Windows XP):
  ```powershell
  "C:\Program Files (x86)\Inno Setup 5\ISCC.exe" xp_host\installer_xp_host.iss
  ```
* Sản phẩm đầu ra: `EasyRemoteDesktopXPHost_Installer.exe` (~12–16 MB), tự động cài dịch vụ nền XP, mở ngoại lệ tường lửa XP qua Registry và tạo biểu tượng ngoài màn hình Desktop XP.
