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
RELEASE_DIR="Antigravity_Linux_Release"
rm -rf $RELEASE_DIR
mkdir -p $RELEASE_DIR

# Copy compiled binary and dependencies
cp -r linux_deploy/dist/app/* $RELEASE_DIR/

# Copy systemd service template
cp linux_deploy/antigravity_rd.service $RELEASE_DIR/

# Create a clean install script for end-users
cat << 'EOF' > $RELEASE_DIR/install.sh
#!/bin/bash
echo "Installing Antigravity Remote Desktop..."

INSTALL_DIR="/opt/antigravity_rd"
sudo mkdir -p $INSTALL_DIR
sudo cp -r * $INSTALL_DIR/
sudo chmod +x $INSTALL_DIR/app

ACTUAL_USER=${SUDO_USER:-$USER}

# Generate service with correct XAUTHORITY
cat <<SVC | sudo tee /etc/systemd/system/antigravity_rd.service
[Unit]
Description=Antigravity Remote Desktop Service
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

sudo systemctl daemon-reload
sudo systemctl enable antigravity_rd.service
sudo systemctl restart antigravity_rd.service

echo "Installation complete! The service is running in the background."
EOF

chmod +x $RELEASE_DIR/install.sh

# 4. Create tar.gz archive
echo "[3/3] Creating tar.gz archive..."
tar -czvf Antigravity_Linux_v1.0.tar.gz $RELEASE_DIR/

echo "=== Success! Release package created at: Antigravity_Linux_v1.0.tar.gz ==="
echo "End-users only need to extract this archive and run sudo ./install.sh"
