<div align="center">
================================================================================

# 💻 P2P REMOTE DESKTOP 💻

## 🖥️ Easy Remote Desktop 🖥️

(Cập nhật: 23/10/2026)

================================================================================
</div>

MÔ TẢ DỰ ÁN
----------
Ứng dụng điều khiển máy tính từ xa kết nối trực tiếp Peer-to-Peer (P2P)
qua mạng Internet hoặc mạng LAN, xây dựng bằng Python / Tkinter.
Khi kết nối P2P không thành công, hệ thống tự chuyển sang chế độ Relay
thông qua signaling server để đảm bảo luôn kết nối được.


TÍNH NĂNG CHÍNH
---------------
- Kết nối P2P trực tiếp: dữ liệu truyền thẳng giữa 2 máy, nhanh & bảo mật
- Signaling Server tích hợp: không phụ thuộc dịch vụ bên thứ ba, tự quản lý
- Relay tự động dự phòng: tự chuyển tiếp khi P2P đục lỗ không thành công
- Mã hóa ChaCha20-Poly1305: toàn bộ gói tin được mã hóa trước khi gửi
- ID cố định bằng HWID: mã 12 số dựa phần cứng, không đổi mỗi lần mở máy
- Tự động dò cổng, hỗ trợ nhiều cổng làm việc đồng thời
- Truyền tệp & đồng bộ bảng tạm: copy/paste 2 chiều giữa 2 máy
- Hỗ trợ Windows 7/10/11, Linux (Ubuntu), thử nghiệm trên Android
- Đóng gói file .exe độc lập: không cần cài Python để chạy



CẤU TRÚC DỰ ÁN
--------------
```text
p2premotedesktop/
├── core/
│   └── Xử lý chụp màn hình, nén, điều khiển chuột/bàn phím
├── network/
│   ├── Kết nối mạng, signaling, P2P hole punching
│   ├── signaling_server.py
│   │   └── Server đăng ký, tìm đường & relay
│   └── signaling_client.py
│       └── Phía khách kết nối signaling
├── gui/
│   └── Giao diện người dùng Tkinter (Dark Mode)
├── conversations/
│   └── Xử lý phiên, clipboard, truyền tệp
├── os_utils/
│   └── Tương tác hệ thống, quyền UAC, dịch vụ Windows
├── lang/
│   └── Đa ngôn ngữ (Tiếng Việt, Anh, ...)
├── linux_deploy/
│   └── Script triển khai trên Linux
├── pyinstaller/
│   └── Cấu hình đóng gói file thực thi
├── app.py
│   └── Điểm vào chính ứng dụng
├── requirements.txt
│   └── Thư viện phụ thuộc
├── signaling_server.ini
│   └── Cấu hình signaling server
└── server.ini
   └── (dự phòng) Cấu hình signaling server

```

CÀI ĐẶT MÔI TRƯỜNG
-----------------
python -m pip install -r requirements.txt


KHỞI CHẠY
----------
Cách 1: Chạy từ mã nguồn
 # Khởi động ứng dụng (Host hoặc Client)
python app.py

 # (Tùy chọn) Tự chạy Signaling Server riêng
python signaling_server.py

Cách 2: Dùng file .exe đã đóng gói
Mở thư mục dist/, chạy RemoteDesktopP2P.exe
Không cần cài đặt thêm gì.


CÁCH HOẠT ĐỘNG
--------------
1. Signaling Server
- Mặc định lắng nghe tại 0.0.0.0:8765
- Cấu hình trong: signaling_server.ini / server.ini
- Chức năng:
+ Nhận đăng ký ID -> Địa chỉ kết nối từ máy Host
+ Chuyển tiếp thông tin IP:Cổng giữa Client và Host
+ Tự tạo kênh Relay khi P2P không thành công

Ví dụ file signaling_server.ini:
[server]
host = 0.0.0.0
port = 8765

[Log]
checkonline = 1
all = 1

2. Quy trình kết nối
Máy Host       ---- đăng ký ID --------> Signaling Server

Máy Client     ---- tìm ID ------------> Signaling Server

Signaling Server -- trả IP:Cổng -------> Client & Host

Client <=======================================> Host
(Kết nối P2P trực tiếp)

Nếu P2P thất bại:
Client -----------> Relay trên Server -----------> Host

3. Bảo mật
- Toàn bộ gói tin mã hóa bằng ChaCha20-Poly1305
- Khóa suy ra từ mật khẩu phiên + hằng số ứng dụng
- Mật khẩu phiên tự tạo ngẫu nhiên mỗi lần khởi động


TRIỂN KHAI SERVER RIÊNG
-----------------------
1. Tải signaling_server.py lên VPS
2. Tạo file signaling_server.ini với cấu hình phù hợp
3. Chạy: python signaling_server.py
4. Cập nhật địa chỉ server trong cấu hình ứng dụng về IP/Domain của VPS


LƯU Ý QUAN TRỌNG
----------------
- KHÔNG dùng dịch vụ bên thứ ba nào
Toàn bộ logic tự xử lý trong code
- KHÔNG có server keyvalue.immanuel.co hay tương tự trong code
- Signaling Server chỉ đóng vai trò sổ địa chỉ và relay dự phòng
- Nội dung màn hình đi trực tiếp khi P2P thành công
- Khi triển khai chính thức, đổi APP_KEY trong code thành chuỗi bí mật riêng


THÔNG TIN DỰ ÁN
---------------
Ngôn ngữ: Python (~98%) + Kotlin (hỗ trợ Android)
Cập nhật: Tháng 10/2026
Nguồn: https://github.com/wilsontuyen/p2premotedesktop
Nguồn: https://github.com/wilsontuyen/p2premotedesktop  
Đang phát triển: http://www.vietmirc.com/index.html
================================================================================
📄 **Tuyên bố miễn trừ trách nhiệm:** Xem chi tiết tại [DISCLAIMER.md](DISCLAIMER.md)