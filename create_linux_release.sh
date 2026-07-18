#!/bin/bash
echo "=== Building and Packaging Linux Release ==="

# 1. Build the binary using PyInstaller
echo "[1/3] Compiling binary with PyInstaller..."
cd linux_deploy
chmod +x build.sh
./build.sh
cd ..

# 2. Check if build succeeded
if [ ! -f "linux_deploy/dist/app/app" ]; then
    echo "Error: Build failed! Cannot find linux_deploy/dist/app/app"
    exit 1
fi

# 3. Create release folder structure
echo "[2/3] Preparing release folder..."
RELEASE_DIR="EasyRemoteDesktop_Linux_Release"
rm -rf $RELEASE_DIR
mkdir -p $RELEASE_DIR

# Copy compiled binary and dependencies
cp -r linux_deploy/dist/app/* $RELEASE_DIR/

# Copy systemd service template
cp linux_deploy/antigravity_rd.service $RELEASE_DIR/

# Create a clean install script for end-users
cat << 'EOF' > $RELEASE_DIR/install.sh
#!/bin/bash
echo "Installing Easy Remote Desktop..."

INSTALL_DIR="/opt/antigravity_rd"
sudo mkdir -p $INSTALL_DIR
sudo cp -r * $INSTALL_DIR/
sudo chmod +x $INSTALL_DIR/app

ACTUAL_USER=${SUDO_USER:-$USER}

# Generate service with correct XAUTHORITY
cat <<SVC | sudo tee /etc/systemd/system/antigravity_rd.service
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
SVC

# Create Desktop Shortcut (.desktop file) for the GUI Viewer
DESKTOP_FILE="/usr/share/applications/antigravity_rd.desktop"
cat <<DSK | sudo tee $DESKTOP_FILE
[Desktop Entry]
Name=Easy Remote Desktop
Comment=Connect to remote computers
Exec=/opt/antigravity_rd/app
Icon=/opt/antigravity_rd/app_icon.png
Terminal=false
Type=Application
Categories=Network;RemoteAccess;
DSK

# Copy shortcut to user's Desktop if it exists
USER_DESKTOP="/home/$ACTUAL_USER/Desktop"
if [ -d "$USER_DESKTOP" ]; then
    sudo cp $DESKTOP_FILE "$USER_DESKTOP/"
    sudo chown $ACTUAL_USER:$ACTUAL_USER "$USER_DESKTOP/antigravity_rd.desktop"
    sudo chmod +x "$USER_DESKTOP/antigravity_rd.desktop"
fi

sudo systemctl daemon-reload
sudo systemctl enable antigravity_rd.service
sudo systemctl restart antigravity_rd.service

echo "Installation complete! The service is running in the background."
EOF

chmod +x $RELEASE_DIR/install.sh

# 4. Create tar.gz archive
echo "[3/3] Creating tar.gz archive..."
tar -czvf EasyRemoteDesktop_Linux_v1.0.tar.gz $RELEASE_DIR/

echo "=== Success! Release package created at: EasyRemoteDesktop_Linux_v1.0.tar.gz ==="
echo "End-users only need to extract this archive and run sudo ./install.sh"
