#!/bin/bash
# Run Link-Chat with MACVLAN networking
# Container will have unique MAC address for Layer 2 communication

set -e

NETWORK_NAME="linkchat-macvlan"

echo "=========================================="
echo "  Link-Chat MACVLAN Runner"
echo "=========================================="
echo ""

# Check if network exists
if ! docker network ls | grep -q "$NETWORK_NAME"; then
    echo "❌ MACVLAN network '$NETWORK_NAME' not found"
    echo ""
    echo "Please create it first:"
    echo "  ./docker/setup-macvlan.sh"
    echo ""
    exit 1
fi

# Check if image exists
if ! docker image inspect linkchat-interactive &> /dev/null; then
    echo "⚠️  Image 'linkchat-interactive' not found"
    echo ""
    read -p "Build image now? (Y/n): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Nn]$ ]]; then
        echo "Building image..."
        docker build -f docker/testing/Dockerfile.interactive.new -t linkchat-interactive .
    else
        echo "Aborted - please build image first"
        exit 1
    fi
fi

# Get next available IP from the network
echo "🔍 Getting network information..."
SUBNET=$(docker network inspect "$NETWORK_NAME" | grep -A 4 "Config" | grep "Subnet" | awk -F'"' '{print $4}')
BASE_IP=$(echo $SUBNET | cut -d/ -f1 | cut -d. -f1-3)

echo "  Network subnet: $SUBNET"
echo "  Container interface: eth0"
echo "  Container will get unique MAC address"
echo ""

# Allow X11 connections
xhost +local:docker > /dev/null 2>&1 || true

echo "🚀 Starting Link-Chat container..."
echo ""
echo "📝 IMPORTANT:"
echo "  • Interface to use in GUI: eth0"
echo "  • Your MAC address will be displayed after connection"
echo "  • Link-Chat uses Layer 2 (MAC addresses, not IP)"
echo "  • IP address is for Docker management only"
echo ""

# Run container
docker run -it --rm \
    --network "$NETWORK_NAME" \
    --cap-add=NET_ADMIN \
    --cap-add=NET_RAW \
    -e DISPLAY=$DISPLAY \
    -e QT_QPA_PLATFORM=xcb \
    -v /tmp/.X11-unix:/tmp/.X11-unix:rw \
    --name linkchat-instance-$RANDOM \
    linkchat-interactive \
    bash -c '
        # Ensure eth0 is UP (MACVLAN interfaces may start DOWN)
        ip link set eth0 up
        
        echo "Container network information:"
        echo "  Interface: eth0"
        echo "  MAC Address: $(cat /sys/class/net/eth0/address)"
        echo "  IP (Docker mgmt): $(ip addr show eth0 | grep "inet " | awk "{print \$2}")"
        echo "  Status: $(ip link show eth0 | grep -o "state [A-Z]*" | awk "{print \$2}")"
        echo ""
        echo "Starting Link-Chat GUI..."
        echo "Use interface: eth0"
        echo ""
        python -m linkchat.app.qt_main
    '

# Cleanup
xhost -local:docker > /dev/null 2>&1 || true

echo ""
echo "Link-Chat stopped"
