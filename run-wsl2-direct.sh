#!/bin/bash
# Run Link-Chat directly in WSL2 (without Docker)
# This bypasses Docker's AF_PACKET receive limitations

echo "=========================================="
echo "  Link-Chat WSL2 Direct Mode"
echo "=========================================="
echo ""
echo "Running Link-Chat in WSL2 (outside Docker)"
echo "This avoids Docker's AF_PACKET limitations on WSL2"
echo ""

# Navigate to project directory
cd "/mnt/d/UH/Año 3/Redes/Link-Chat"

# Set up X11 display
export DISPLAY=:0
export QT_QPA_PLATFORM=xcb

echo "Starting Link-Chat with sudo..."
echo "(Password required for raw socket access)"
echo ""

# Run with sudo for AF_PACKET permissions
sudo -E python3 -m linkchat.app.qt_main
