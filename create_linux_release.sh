#!/bin/bash
echo "=== Building and Packaging Linux Release ==="

# 1. Build the binary using PyInstaller
echo "[1/3] Compiling binary with PyInstaller..."
cd linux_deploy
chmod +x build.sh
./build.sh
cd ..

# 2. Check if build succeeded
if [ ! -f "linux_deploy/dist/EasyRemoteDesktop/EasyRemoteDesktop" ]; then
    echo "Error: Build failed! Cannot find linux_deploy/dist/EasyRemoteDesktop/EasyRemoteDesktop"
    exit 1
fi

# 3. Create release folder structure
echo "[2/3] Preparing release folder..."
RELEASE_DIR="Easy Remote Desktop"
rm -rf "$RELEASE_DIR"
mkdir -p "$RELEASE_DIR"

# Copy compiled binary and dependencies
cp -r linux_deploy/dist/EasyRemoteDesktop/* "$RELEASE_DIR/"

# Copy necessary assets (icon and languages)
cp app_icon.png "$RELEASE_DIR/"
cp -r lang "$RELEASE_DIR/"


# Copy systemd service template
cp linux_deploy/p2p_remote.service "$RELEASE_DIR/"

# Create a clean install script for end-users
cat << 'EOF' > "$RELEASE_DIR/install.sh"
#!/bin/bash
echo "Installing Easy Remote Desktop..."

INSTALL_DIR="/opt/p2p_remote"
sudo mkdir -p $INSTALL_DIR
sudo cp -r * $INSTALL_DIR/
sudo chmod +x $INSTALL_DIR/EasyRemoteDesktop

ACTUAL_USER=${SUDO_USER:-$USER}

# Setup /dev/uinput for keyboard input at GDM lock screen
echo "Setting up /dev/uinput for lock screen keyboard input..."
sudo modprobe uinput
echo "uinput" | sudo tee /etc/modules-load.d/uinput.conf > /dev/null
cat <<UDEV | sudo tee /etc/udev/rules.d/99-uinput.rules > /dev/null
KERNEL=="uinput", MODE="0660", GROUP="input", OPTIONS+="static_node=uinput"
UDEV
sudo udevadm control --reload-rules
sudo udevadm trigger /dev/uinput 2>/dev/null || true
sudo usermod -aG input $ACTUAL_USER

# Generate service with correct XAUTHORITY
cat <<SVC | sudo tee /etc/systemd/system/p2p_remote.service
[Unit]
Description=Easy Remote Desktop Service
After=network.target display-manager.service

[Service]
Type=simple
WorkingDirectory=/opt/p2p_remote
ExecStart=/opt/p2p_remote/EasyRemoteDesktop --headless
Restart=always
RestartSec=3

Environment="DISPLAY=:0"
Environment="XAUTHORITY=/home/$ACTUAL_USER/.Xauthority"
SupplementaryGroups=input

[Install]
WantedBy=multi-user.target
SVC

# Create Desktop Shortcut (.desktop file) for the GUI Viewer
DESKTOP_FILE="/usr/share/applications/p2p_remote.desktop"
cat <<DSK | sudo tee $DESKTOP_FILE
[Desktop Entry]
Name=Easy Remote Desktop
Comment=Connect to remote computers
Exec=/opt/p2p_remote/EasyRemoteDesktop
Path=/opt/p2p_remote
Icon=/opt/p2p_remote/app_icon.png
StartupWMClass=EasyRemoteDesktop
Terminal=false
Type=Application
Categories=Network;RemoteAccess;
DSK

# Copy shortcut to user's Desktop if it exists
USER_DESKTOP="/home/$ACTUAL_USER/Desktop"
if [ -d "$USER_DESKTOP" ]; then
    sudo cp $DESKTOP_FILE "$USER_DESKTOP/"
    sudo chown $ACTUAL_USER:$ACTUAL_USER "$USER_DESKTOP/p2p_remote.desktop"
    sudo chmod +x "$USER_DESKTOP/p2p_remote.desktop"
fi

sudo systemctl daemon-reload
sudo systemctl enable p2p_remote.service
sudo systemctl restart p2p_remote.service

echo "Installation complete! The service is running in the background."
EOF

chmod +x "$RELEASE_DIR/install.sh"

# 4. Create tar.gz archive
echo "[3/3] Creating tar.gz archive..."
tar -czvf EasyRemoteDesktop_Linux_v1.0.tar.gz "$RELEASE_DIR"/

echo "=== Success! Release package created at: EasyRemoteDesktop_Linux_v1.0.tar.gz ==="
echo "End-users only need to extract this archive and run sudo ./install.sh"
