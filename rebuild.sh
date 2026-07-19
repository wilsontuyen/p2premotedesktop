#!/bin/bash

# Thiết lập xác thực tự động qua Personal Access Token (PAT)
git remote set-url origin https://wilsontuyen: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@github.com/wilsontuyen/p2premotedesktop.git

echo "Đang tải bản cập nhật mới nhất từ branch feature/linux-support..."
git fetch origin
git reset --hard origin/feature/linux-support
git pull origin feature/linux-support

echo "Dọn dẹp thư mục build và dist cũ..."
rm -rf linux_deploy/build/ linux_deploy/dist/

echo "Bắt đầu build..."
chmod +x create_linux_release.sh
./create_linux_release.sh

echo "Dừng service đang chạy ngầm..."
echo "2946635" | sudo -S systemctl stop p2p_remote.service
echo "2946635" | sudo -S systemctl disable p2p_remote.service

echo "Xóa toàn bộ thư mục ứng dụng..."
echo "2946635" | sudo -S rm -rf /opt/p2p_remote

echo "Giải nén bản build vào /home/Tuyen..."
tar -xzf EasyRemoteDesktop_Linux_v1.0.tar.gz -C /home/Tuyen/

echo "Đang cài đặt..."
cd "/home/Tuyen/Easy Remote Desktop"
echo "2946635" | sudo -S ./install.sh

echo "Khởi động ứng dụng (GUI)..."
export DISPLAY=:0
/opt/p2p_remote/EasyRemoteDesktop > /dev/null 2>&1 &

echo "Hoàn tất quá trình rebuild và khởi động!"