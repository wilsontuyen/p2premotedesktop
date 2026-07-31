#!/bin/bash

#Chuyển vào thư mục p2premotedesktop
cd ~/p2premotedesktop

# Thiết lập xác thực tự động qua Personal Access Token (PAT)
git remote set-url origin https://wilsontuyen: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@github.com/wilsontuyen/p2premotedesktop.git

echo "Đang tải bản cập nhật mới nhất từ branch main..."
git fetch origin
git reset --hard main
git pull origin main

# Lấy nội dung commit mới nhất
LATEST_COMMIT=$(git log -1 --pretty=format:"%s")
echo ""
read -p "Bạn có muốn tiếp tục với cập nhật \"$LATEST_COMMIT\" này không ? (y/n) " -n 1 -r
echo ""
if [[ ! $REPLY =~ ^[Yy]$ ]]
then
    echo "Đã hủy quá trình rebuild."
    exit 1
fi

echo "Dọn dẹp thư mục build và dist cũ..."
rm -rf linux_deploy/build/ linux_deploy/dist/

echo "Bắt đầu build..."
chmod +x create_linux_release.sh
./create_linux_release.sh

echo "Dừng ứng dụng giao diện đang mở..."
pkill -f EasyRemoteDesktop || true

echo "Dừng service đang chạy ngầm..."
echo "2946635" | sudo -S systemctl stop p2p_remote.service
echo "2946635" | sudo -S systemctl disable p2p_remote.service

echo "Sao lưu cấu hình..."
mkdir -p /tmp/p2p_remote_backup
if [ -f "/opt/p2p_remote/config/saved_computers.xml" ]; then
    echo "2946635" | sudo -S cp "/opt/p2p_remote/config/saved_computers.xml" "/tmp/p2p_remote_backup/"
fi
if [ -f "/opt/p2p_remote/config/window_config.json" ]; then
    echo "2946635" | sudo -S cp "/opt/p2p_remote/config/window_config.json" "/tmp/p2p_remote_backup/"
fi

echo "Xóa toàn bộ thư mục ứng dụng..."
echo "2946635" | sudo -S rm -rf /opt/p2p_remote

echo "Giải nén bản build vào thư mục home..."
tar -xzf EasyRemoteDesktop_Linux_v1.0.tar.gz -C $HOME/

echo "Đang cài đặt..."
cd "$HOME/Easy Remote Desktop"
echo "2946635" | sudo -S ./install.sh

echo "Khôi phục cấu hình..."
echo "2946635" | sudo -S mkdir -p "/opt/p2p_remote/config"
if [ -f "/tmp/p2p_remote_backup/saved_computers.xml" ]; then
    echo "2946635" | sudo -S cp "/tmp/p2p_remote_backup/saved_computers.xml" "/opt/p2p_remote/config/"
fi
if [ -f "/tmp/p2p_remote_backup/window_config.json" ]; then
    echo "2946635" | sudo -S cp "/tmp/p2p_remote_backup/window_config.json" "/opt/p2p_remote/config/"
fi
echo "2946635" | sudo -S rm -rf /tmp/p2p_remote_backup

echo "Khởi động ứng dụng (GUI)..."
if [ -z "$DISPLAY" ]; then
    export DISPLAY=:0
fi
nohup /opt/p2p_remote/EasyRemoteDesktop > /dev/null 2>&1 &

echo "Hoàn tất quá trình rebuild và khởi động EasyRemoteDesktop!"
echo "Cửa sổ sẽ tự đóng sau 10 giây..."
sleep 10