#!/bin/bash

# Script cài đặt cơ bản cho Ubuntu
echo "Bắt đầu cài đặt Easy Remote Desktop cho Linux..."

# Cài đặt các thư viện hệ thống cần thiết (nếu thiếu)
sudo apt-get update
sudo apt-get install -y python3-pip python3-tk xclip xdotool python3-xlib scrot python3-pil.imagetk gir1.2-appindicator3-0.1 gir1.2-ayatanaappindicator3-0.1

# Tạo thư mục cài đặt
INSTALL_DIR="/opt/p2p_remote"
sudo mkdir -p $INSTALL_DIR
sudo cp -r ../* $INSTALL_DIR/

# Lấy username thực sự của người dùng thay vì 'root'
ACTUAL_USER=${SUDO_USER:-$USER}

# Phân quyền sở hữu thư mục cho người dùng hiện tại để ứng dụng có quyền ghi log
sudo chown -R $ACTUAL_USER:$ACTUAL_USER $INSTALL_DIR
sudo chmod -R 777 $INSTALL_DIR
sudo chmod +x $INSTALL_DIR/app 2>/dev/null || true

# ============================================================
# Setup /dev/uinput for keyboard input at GDM lock screen
# Without this, keyboard input won't work when the screen is locked
# ============================================================
echo "Cấu hình /dev/uinput cho nhập liệu bàn phím tại màn hình khóa..."

# Load uinput kernel module
sudo modprobe uinput

# Make it auto-load on boot
echo "uinput" | sudo tee /etc/modules-load.d/uinput.conf > /dev/null

# Create udev rule: allow 'input' group to access /dev/uinput
cat <<UDEV | sudo tee /etc/udev/rules.d/99-uinput.rules > /dev/null
KERNEL=="uinput", MODE="0660", GROUP="input", OPTIONS+="static_node=uinput"
UDEV

# Reload udev rules and trigger
sudo udevadm control --reload-rules
sudo udevadm trigger /dev/uinput 2>/dev/null || true

# Add user to input group (for non-root GUI app access in the future)
sudo usermod -aG input $ACTUAL_USER
# ============================================================

# Tạo service file động với XAUTHORITY chuẩn xác
cat <<EOF | sudo tee /etc/systemd/system/p2p_remote.service
[Unit]
Description=Easy Remote Desktop Service
After=network.target display-manager.service

[Service]
Type=simple
WorkingDirectory=/opt/p2p_remote
ExecStart=/opt/p2p_remote/app --headless
Restart=always
RestartSec=3

Environment="DISPLAY=:0"
Environment="XAUTHORITY=/home/$ACTUAL_USER/.Xauthority"
SupplementaryGroups=input

[Install]
WantedBy=multi-user.target
EOF

# Cài đặt Systemd service
sudo systemctl daemon-reload
sudo systemctl enable p2p_remote.service
sudo systemctl restart p2p_remote.service

echo "Cài đặt thành công! Dịch vụ đang chạy ngầm."
echo "Cửa sổ sẽ tự đóng sau 10 giây..."
sleep 10
