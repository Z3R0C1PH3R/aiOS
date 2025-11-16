#!/bin/bash

echo "🚀 Setting up AI OS Agent Web Interface..."

# Install Python dependencies
echo "📦 Installing Python dependencies..."
pip install flask flask-socketio

# Make web server executable
chmod +x web_server.py

# Create templates directory if it doesn't exist
mkdir -p templates

# Copy systemd service (requires sudo)
echo "🔧 Installing systemd service..."
sudo cp aios-web.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable aios-web.service

echo ""
echo "✅ Setup complete!"
echo ""
echo "To start the web interface:"
echo "  sudo systemctl start aios-web"
echo ""
echo "To run manually:"
echo "  python3 web_server.py"
echo ""
echo "Access at: http://YOUR_VM_IP:5000"
