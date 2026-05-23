# Chương trình Điều khiển Máy tính từ xa P2P (TeamViewer P2P Clone)

Ứng dụng điều khiển máy tính từ xa kết nối trực tiếp **Client-Client (Peer-to-Peer)** qua mạng Internet hoặc mạng LAN, sử dụng **Python/Tkinter**, công nghệ **HWID (Hardware ID)** và giao thức **TCP**.

Phiên bản này được trang bị khả năng **tự động dò tìm cổng mở (Port auto-fallback)** trên danh sách cổng phổ biến là `443`, `80` và `9999`, kết hợp với giao diện **Tkinter GUI (Dark Mode)** sang trọng và các phím tắt sao chép/dán siêu tiện lợi.

---

## Các tính năng nổi bật:
1. **Dò tìm cổng thông minh (Dynamic Port Fallback):** Khi mở ứng dụng, Host sẽ tự động quét và lắng nghe trên cổng đầu tiên khả dụng trong danh sách: **`443` -> `80` -> `9999`**. Việc dùng cổng `443` hoặc `80` (cổng HTTP/HTTPS tiêu chuẩn) giúp kết nối dễ dàng đi xuyên qua Firewall của Router/Nhà mạng mà không lo bị chặn!
2. **Hệ thống danh bạ động Serverless (IP:Port Registry):** Host sẽ tự động đăng ký chuỗi `Public_IP:Cổng_đã_mở` lên máy chủ danh bạ động trực tuyến miễn phí (`keyvalue.immanuel.co`). Client khi nhập ID đối tác sẽ tự phân giải ra IP và Cổng chính xác để kết nối. **Hoàn toàn tự động, không cần cài đặt server riêng!**
3. **ID cố định bằng phần cứng (HWID):** Tự động băm thông tin `CPUID` và `HDD Serial` để tạo ra một mã ID 9 số (ví dụ: `190 645 377`) cố định, duy nhất cho máy tính của bạn.
4. **Copy & Paste Siêu Tiện Lợi:**
   * Tích hợp các nút **Sao chép nhanh (📋)** bên cạnh ID và Mật khẩu của bạn để gửi cho đối tác chỉ với 1 click.
   * Tích hợp **Menu chuột phải (Right-click Context Menu)** đầy đủ các tính năng: *Cắt (Cut), Sao chép (Copy), Dán (Paste), Chọn tất cả (Select All)* trên các ô nhập ID đối tác và mật khẩu đối tác.
   * Hỗ trợ đầy đủ phím tắt hệ thống: `Ctrl+C`, `Ctrl+V`, `Ctrl+X`, `Ctrl+A`.
5. **Mật khẩu bảo mật:** Tự động tạo ngẫu nhiên mật khẩu 4 chữ số mỗi lần mở ứng dụng (có nút bấm đổi mật khẩu `↻`).
6. **Co giãn màn hình (Resizable Window):** Cửa sổ Pygame hiển thị màn hình đối tác có khả năng co giãn thoải mái và tự động scale tọa độ chuột/bàn phím chính xác.

---

## 1. Cài đặt các thư viện cần thiết (Nếu chạy từ Source Code)

Mở Command Prompt (cmd) hoặc PowerShell trên Windows và chạy lệnh sau để cài đặt các thư viện:

```bash
python -m pip install -r requirements.txt
```

---

## 2. Hướng dẫn chạy chương trình

### Cách 1: Chạy trực tiếp từ file chạy độc lập `.exe` (Đã được đóng gói sẵn)
Bạn chỉ cần mở thư mục **`dist`** và kích đúp chuột vào file **`RemoteDesktopP2P.exe`**. Bạn có thể gửi file này sang bất kỳ máy tính Windows khác để chạy mà không cần cài đặt thêm bất cứ thứ gì!

### Cách 2: Chạy từ mã nguồn Python
Chạy lệnh dưới đây trên terminal:
```bash
python app.py
```

---

## 3. Hướng dẫn cấu hình cổng mạng kết nối qua Internet

Vì ứng dụng hoạt động theo cơ chế **P2P trực tiếp giữa 2 máy** (không đi qua server trung gian để bảo mật dữ liệu tuyệt đối và tốc độ truyền hình ảnh nhanh nhất), máy **Host** (máy bị điều khiển) cần đảm bảo cổng lắng nghe được mở:

### Bước 1: Xem cổng đang hoạt động của ứng dụng
* Khi mở ứng dụng ở máy Host, hãy nhìn vào **Thanh trạng thái** ở dưới cùng. Nó sẽ hiển thị cổng mà ứng dụng đã liên kết thành công, ví dụ: `Trạng thái: Đăng ký thành công (Cổng 443)! Sẵn sàng kết nối.` hoặc `Cổng 80`, `Cổng 9999`.

### Bước 2: Mở cổng (Port Forwarding) trên Router của máy HOST (Máy bị điều khiển)
1. Truy cập vào trang cấu hình Router nhà bạn (thường là `192.168.1.1` hoặc `192.168.0.1`).
2. Tìm tới mục **Port Forwarding**, **Virtual Server**, hoặc **NAT Server**.
3. Thêm một quy tắc (Rule) mới tương ứng với cổng hiển thị trên thanh trạng thái (ví dụ: cổng `443` hoặc `80` hoặc `9999`):
   * **Internal Port (Cổng trong):** [Cổng hiển thị trên thanh trạng thái, ví dụ: 443]
   * **External Port (Cổng ngoài):** [Cổng hiển thị trên thanh trạng thái, ví dụ: 443]
   * **Protocol (Giao thức):** `TCP`
   * **IP Address:** Địa chỉ IP nội bộ của máy Host (Xem bằng cách gõ `ipconfig` trong cmd, ví dụ: `192.168.1.15`).
4. Lưu cấu hình.

### Bước 3: Cho phép cổng trên Firewall (Tường lửa) của máy HOST
1. Mở **Windows Defender Firewall** trên máy Host.
2. Chọn **Advanced Settings** -> **Inbound Rules** -> **New Rule**.
3. Chọn **Port** -> Chọn **TCP** và điền cổng **Specific local ports** tương ứng (ví dụ: `443` hoặc `80` hoặc `9999`).
4. Chọn **Allow the connection** và lưu tên rule là `Remote Desktop Host`.
