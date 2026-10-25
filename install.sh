#!/usr/bin/env bash
set -e

echo "=========================================================="
echo "      ⚡ Installing VSDCraft Linux (Stream Dock N3)        "
echo "=========================================================="

# 1. Check Python 3
if ! command -v python3 &> /dev/null; then
    echo "❌ Error: python3 is not installed. Please install Python 3.10+."
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# 2. Install Python Dependencies
echo "📦 Installing Python dependencies..."
python3 -m pip install --upgrade pip
python3 -m pip install -r "${SCRIPT_DIR}/requirements.txt"

# 3. Setup Udev Permissions (Allows non-root access to Stream Dock HID)
echo "🔒 Installing udev rules for Stream Dock USB access..."
if [ -f "${SCRIPT_DIR}/99-streamdock.rules" ]; then
    sudo cp "${SCRIPT_DIR}/99-streamdock.rules" /etc/udev/rules.d/99-streamdock.rules
    sudo udevadm control --reload-rules
    sudo udevadm trigger
    echo "✅ Udev rules active! (If your device is already plugged in, unplug & re-plug it)"
fi

# 4. Install Desktop Application Shortcut
echo "🖥️ Installing Desktop shortcut..."
DESKTOP_DIR="${HOME}/.local/share/applications"
mkdir -p "${DESKTOP_DIR}"
cat <<EOF > "${DESKTOP_DIR}/vsdcraft.desktop"
[Desktop Entry]
Name=VSDCraft Linux
Comment=Stream Dock N3 Controller
Exec=python3 -m vsdcraft
Path=${SCRIPT_DIR}
Icon=input-gaming
Terminal=false
Type=Application
Categories=Utility;AudioVideo;
EOF
chmod +x "${DESKTOP_DIR}/vsdcraft.desktop"

# 5. Optional Systemd User Service Setup
echo ""
echo "🚀 Installation completed successfully!"
echo ""
echo "To start the VSDCraft GUI:"
echo "    cd ${SCRIPT_DIR} && python3 -m vsdcraft"
echo ""
echo "To run in simulation mode without hardware:"
echo "    python3 -m vsdcraft --mock"
echo ""
echo "To enable background auto-start on boot (systemd service):"
echo "    mkdir -p ~/.config/systemd/user/"
echo "    cp ${SCRIPT_DIR}/vsdcraft.service ~/.config/systemd/user/"
echo "    systemctl --user daemon-reload"
echo "    systemctl --user enable --now vsdcraft.service"
echo "=========================================================="
