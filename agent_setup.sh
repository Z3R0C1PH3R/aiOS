#!/bin/bash

# AI Agent Setup Script for Arch Linux
# This script sets up the OS-level AI agent

echo "=== Setting up AI Agent on Arch Linux ==="

# Update system
echo "📦 Updating system packages..."
sudo pacman -Syu --noconfirm

# Install Python and required packages
echo "🐍 Installing Python and dependencies..."
sudo pacman -S --noconfirm python python-pip python-requests python-psutil

# Install additional useful packages
echo "🛠️ Installing system utilities..."
sudo pacman -S --noconfirm htop neofetch git vim nano curl wget

# Create agent directory
AGENT_DIR="$HOME/ai-agent"
mkdir -p "$AGENT_DIR"
cd "$AGENT_DIR"

echo "📁 Created agent directory: $AGENT_DIR"

# Download the agent script (you'll need to host this)
echo "⬇️ Downloading AI agent..."
# Replace with your hosted URL
curl -L https://raw.githubusercontent.com/Z3R0C1PH3R/aiOS/refs/heads/main/os_ai_agent.py > agent.py

# For now, create a placeholder - you'll paste the script here
# cat > agent.py << 'EOF'
# Paste the AI agent Python code here
# Or download from your hosted location
# EOF

chmod +x agent.py

# Create a startup script
cat > start_agent.sh << 'EOF'
#!/bin/bash
cd "$(dirname "$0")"
python3 agent.py
EOF

chmod +x start_agent.sh

# Create desktop entry for easy access
cat > ~/.config/autostart/ai-agent.desktop << 'EOF'
[Desktop Entry]
Type=Application
Name=AI Agent
Comment=OS-level AI Agent
Exec=/home/$USER/ai-agent/start_agent.sh
Terminal=true
Hidden=false
X-GNOME-Autostart-enabled=true
EOF

# Create systemd service (optional)
sudo tee /etc/systemd/system/ai-agent.service > /dev/null << EOF
[Unit]
Description=AI Agent Service
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$AGENT_DIR
ExecStart=/usr/bin/python3 $AGENT_DIR/agent.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

echo "🔧 Configuration Instructions:"
echo "1. Edit $AGENT_DIR/agent.py and change LM_STUDIO_URL to your laptop's IP"
echo "2. Make sure LM Studio is running with Qwen2.5 Coder 7B loaded"
echo "3. Ensure your laptop and VM can communicate (same network)"
echo ""
echo "💡 Your laptop's IP is likely something like:"
echo "   - 192.168.1.xxx (home network)"
echo "   - 10.0.2.2 (VirtualBox NAT default gateway)"
echo ""
echo "🚀 To start the agent:"
echo "   cd $AGENT_DIR && python3 agent.py"
echo ""
echo "🎯 To run as service:"
echo "   sudo systemctl enable ai-agent"
echo "   sudo systemctl start ai-agent"
echo ""
echo "📝 Logs will be in: /tmp/arch_agent.log"

# Find and display network information
echo ""
echo "🌐 Network Information:"
ip route | grep default
ip addr show | grep "inet " | grep -v "127.0.0.1"

echo ""
echo "✅ Setup complete! Configure the IP address and start the agent."
