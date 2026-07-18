#!/bin/bash

# Script cài đặt cơ bản cho Ubuntu
echo "Bắt đầu cài đặt Antigravity Remote Desktop cho Linux..."

# Cài đặt các thư viện hệ thống cần thiết (nếu thiếu)
sudo apt-get update
sudo apt-get install -y python3-pip python3-tk xclip xdotool python3-xlib scrot

# Tạo thư mục cài đặt
INSTALL_DIR="/opt/antigravity_rd"
sudo mkdir -p $INSTALL_DIR
sudo cp -r ../* $INSTALL_DIR/

# Phân quyền cho file thực thi (nếu bạn build bằng PyInstaller ra file `app`)
# sudo chmod +x $INSTALL_DIR/app

# Cài đặt Systemd service
sudo cp antigravity_rd.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable antigravity_rd.service
sudo systemctl start antigravity_rd.service

echo "Cài đặt thành công! Dịch vụ đang chạy ngầm."
