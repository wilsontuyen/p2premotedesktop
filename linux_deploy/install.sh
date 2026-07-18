#!/bin/bash

# Script cài đặt cơ bản cho Ubuntu
echo "Bắt đầu cài đặt Easy Remote Desktop cho Linux..."

# Cài đặt các thư viện hệ thống cần thiết (nếu thiếu)
sudo apt-get update
sudo apt-get install -y python3-pip python3-tk xclip xdotool python3-xlib scrot python3-pil.imagetk gir1.2-appindicator3-0.1 gir1.2-ayatanaappindicator3-0.1

# Tạo thư mục cài đặt
INSTALL_DIR="/opt/antigravity_rd"
sudo mkdir -p $INSTALL_DIR
sudo cp -r ../* $INSTALL_DIR/

# Lấy username thực sự của người dùng thay vì 'ubuntu'
ACTUAL_USER=${SUDO_USER:-$USER}

# Tạo service file động với XAUTHORITY chuẩn xác
cat <<EOF | sudo tee /etc/systemd/system/antigravity_rd.service
[Unit]
Description=Easy Remote Desktop Service
After=network.target display-manager.service

[Service]
Type=simple
WorkingDirectory=/opt/antigravity_rd
ExecStart=/opt/antigravity_rd/app --headless
Restart=always
RestartSec=3

Environment="DISPLAY=:0"
Environment="XAUTHORITY=/home/$ACTUAL_USER/.Xauthority"

[Install]
WantedBy=multi-user.target
EOF

# Cài đặt Systemd service
sudo systemctl daemon-reload
sudo systemctl enable antigravity_rd.service
sudo systemctl restart antigravity_rd.service

echo "Cài đặt thành công! Dịch vụ đang chạy ngầm."
