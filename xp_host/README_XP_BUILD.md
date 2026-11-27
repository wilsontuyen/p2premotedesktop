# Hướng Dẫn Đóng Gói Bản Host XP Lite (32-bit x86)

Toàn bộ bộ công cụ biên dịch dành riêng cho nhân **Windows XP (`NT 5.1`, 32-bit x86)** đã được thiết lập cô lập hoàn toàn trong `.xp_toolchain/` và `.venv_xp32/` (không ảnh hưởng tới môi trường `.venv` hay Inno Setup 6 của bản Windows 10/11).

---

## 1. Lệnh Build Trọn Gói (1 Lệnh Duy Nhất)

Mỗi khi sửa mã nguồn trong `xp_host/`, chỉ cần chạy lệnh sau từ thư mục gốc dự án:

```powershell
.\.venv_xp32\Scripts\python.exe xp_host\build_xp_host.py
```

### Tiến trình tự động thực hiện 6 bước:
1. Kiểm tra cú pháp sạch 100% toàn bộ file `.py` trong `xp_host/`.
2. Đóng gói `RemoteDesktopXPHost.exe` (32-bit `Win32GUI`) bằng `cx_Freeze` bản chuyên biệt cho Windows XP.
3. Đóng gói kèm trọn bộ `Tcl/Tk 8.6`, `vcruntime140.dll` và `Universal CRT x86 (10.0.19041)` để máy Windows XP SP2/SP3 mới cài sạch (chưa có VC++ Redistributable) vẫn chạy ngay lập tức.
4. Hạ `MajorSubsystemVersion` trong PE Header của mọi file `.exe` / `.dll` / `.pyd` về `5.01` (`NT 5.1`).
5. Kiểm toán tự động bảng Import bằng `lief` để đảm bảo **0% lời gọi hàm Vista+** (`GetTickCount64`, `SRWLock`, `bcrypt.dll`...) và xóa sạch file dữ liệu cá nhân.
6. Gọi `.xp_toolchain\innosetup5\ISCC.exe` (Inno Setup 5.6.1 Unicode) để xuất ra bộ cài đặt:
   * **Bộ cài đặt hoàn chỉnh:** `EasyRemoteDesktopXPHost_Installer.exe` (ở thư mục gốc dự án).
   * **Bản chạy ngay không cần cài (Portable):** `dist_xp_host\RemoteDesktopXPHost\RemoteDesktopXPHost.exe`.
