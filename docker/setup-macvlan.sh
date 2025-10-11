#!/bin/bash
# Setup MACVLAN network for Link-Chat
# Note: Link-Chat operates at Layer 2 (Ethernet frames with MAC addresses)
# IP addresses are only used by Docker for network management, NOT by Link-Chat protocol

set -e

echo "=========================================="
echo "  Link-Chat MACVLAN Network Setup"
echo "=========================================="
echo ""
echo "Note: Link-Chat uses Layer 2 (MAC addresses only)"
echo "IP configuration is for Docker management, not the chat protocol"
echo ""

# Network name
NETWORK_NAME="linkchat-macvlan"

# Check if network already exists
if docker network ls | grep -q "$NETWORK_NAME"; then
    echo "⚠️  Network '$NETWORK_NAME' already exists"
    echo ""
    read -p "Remove and recreate? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "Removing existing network..."
        docker network rm "$NETWORK_NAME"
    else
        echo "Using existing network"
        docker network inspect "$NETWORK_NAME"
        exit 0
    fi
fi

# Auto-detect network settings
echo "🔍 Detecting network configuration..."
echo ""

# Get default interface
DEFAULT_IFACE=$(ip route | grep default | head -n1 | awk '{print $5}')
if [ -z "$DEFAULT_IFACE" ]; then
    echo "❌ Could not detect default network interface"
    echo "Please specify manually"
    read -p "Interface name (e.g., eth0, wlan0): " DEFAULT_IFACE
fi

# Get default gateway
DEFAULT_GW=$(ip route | grep default | head -n1 | awk '{print $3}')
if [ -z "$DEFAULT_GW" ]; then
    echo "❌ Could not detect default gateway"
    read -p "Gateway IP (e.g., 192.168.1.1): " DEFAULT_GW
fi

# Calculate subnet from gateway (assume /24)
SUBNET=$(echo $DEFAULT_GW | cut -d. -f1-3).0/24

echo "Detected configuration:"
echo "  Interface: $DEFAULT_IFACE"
echo "  Gateway:   $DEFAULT_GW"
echo "  Subnet:    $SUBNET"
echo ""

# Get base IP for container range
BASE_IP=$(echo $DEFAULT_GW | cut -d. -f1-3)

# Use .96-.103 range for containers (8 IPs, aligned to /29)
# /29 requires IP range to be aligned to multiples of 8
IP_RANGE="${BASE_IP}.96/29"

echo "Container IP range: ${BASE_IP}.96 - ${BASE_IP}.103"
echo "(Remember: IPs are for Docker only, Link-Chat uses Layer 2/MAC)"
echo ""

# Confirm
read -p "Proceed with these settings? (Y/n): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]] && [[ ! -z $REPLY ]]; then
    echo "Aborted"
    exit 1
fi

# Create MACVLAN network
echo ""
echo "Creating MACVLAN network..."

docker network create -d macvlan \
    --subnet="$SUBNET" \
    --gateway="$DEFAULT_GW" \
    --ip-range="$IP_RANGE" \
    -o parent="$DEFAULT_IFACE" \
    "$NETWORK_NAME"

echo ""
echo "✅ MACVLAN network created successfully!"
echo ""
echo "Network details:"
docker network inspect "$NETWORK_NAME" | grep -A 10 "IPAM"
echo ""
echo "📝 Key Information for Link-Chat:"
echo "  • Containers will use interface: eth0"
echo "  • Each container gets unique MAC address (Layer 2)"
echo "  • Link-Chat protocol operates at Layer 2 (MAC-based)"
echo "  • IP addresses are Docker management only"
echo ""
echo "Next steps:"
echo "  1. Run container: ./docker/run-macvlan.sh"
echo "  2. In Link-Chat GUI: Connect to interface 'eth0'"
echo "  3. Your MAC address will be shown in the GUI"
echo ""
