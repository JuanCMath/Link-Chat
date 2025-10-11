#!/bin/bash
# Quick start script for Link-Chat in Docker

set -e

echo "========================================="
echo "  Link-Chat Docker Quick Start"
echo "========================================="

# Check if running on Linux
if [[ "$(uname)" != "Linux" ]]; then
    echo "❌ ERROR: Link-Chat requires a Linux host for AF_PACKET support"
    echo "   Docker Desktop on Windows/macOS won't work."
    exit 1
fi

# Check for Docker
if ! command -v docker &> /dev/null; then
    echo "❌ ERROR: Docker not installed"
    exit 1
fi

# Allow X11 connections from Docker
echo "🔧 Configuring X11 access..."
xhost +local:docker 2>/dev/null || echo "⚠️  Warning: xhost not available, GUI may not work"

# List available interfaces
echo ""
echo "📡 Available network interfaces:"
ip link show | grep -E "^[0-9]+: " | awk '{print "   - " $2}' | sed 's/:$//'

# Prompt for interface
echo ""
read -p "Enter interface name (default: wlan0): " INTERFACE
INTERFACE=${INTERFACE:-wlan0}

# Check if interface exists
if ! ip link show "$INTERFACE" &> /dev/null; then
    echo "⚠️  Warning: Interface '$INTERFACE' not found, but continuing anyway..."
fi

echo ""
echo "🐳 Building Docker image..."
docker build -t linkchat:latest .

echo ""
echo "🚀 Starting Link-Chat..."
echo "   Interface: $INTERFACE"
echo "   Display: $DISPLAY"
echo ""
echo "Press Ctrl+C to stop"
echo ""

# Run container
docker run -it --rm \
  --name linkchat-app \
  --network host \
  --cap-add=NET_RAW \
  --cap-add=NET_ADMIN \
  -e DISPLAY="$DISPLAY" \
  -e INTERFACE="$INTERFACE" \
  -e QT_QPA_PLATFORM=xcb \
  -v /tmp/.X11-unix:/tmp/.X11-unix:rw \
  -v "$(pwd)/downloads:/app/downloads" \
  linkchat:latest

# Cleanup X11 access
echo ""
echo "🧹 Cleaning up X11 access..."
xhost -local:docker 2>/dev/null || true

echo "✅ Done!"
