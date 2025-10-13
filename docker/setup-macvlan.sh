#!/bin/bash
# Setup MACVLAN network for Link-Chat
# Note: Link-Chat operates at Layer 2 (Ethernet frames with MAC addresses)
# IP addresses are only used by Docker for network management, NOT by Link-Chat protocol

set -e

echo "Link-Chat MACVLAN setup"
echo "(Link-Chat speaks Layer 2; Docker handles the IP plumbing.)"
echo

# Network name
NETWORK_NAME="linkchat-macvlan"

# Check if network already exists
if docker network ls | grep -q "$NETWORK_NAME"; then
    echo "Network '$NETWORK_NAME' already exists."
    read -p "Remove and recreate? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "Removing existing network..."
        docker network rm "$NETWORK_NAME"
    else
        echo "Reusing existing network."
        docker network inspect "$NETWORK_NAME"
        exit 0
    fi
fi

# Auto-detect network settings
echo "Detecting host network configuration..."
echo

# Get default interface
DEFAULT_IFACE=""
read -p "Interface name (e.g., eth0, wlan0): " DEFAULT_IFACE

# Get default gateway
DEFAULT_GW=$(ip route | grep default | head -n1 | awk '{print $3}')
if [ -z "$DEFAULT_GW" ]; then
    echo "Could not detect default gateway."
    read -p "Gateway IP (e.g., 192.168.1.1): " DEFAULT_GW
fi

# Calculate subnet from gateway (assume /24)
SUBNET=$(echo $DEFAULT_GW | cut -d. -f1-3).0/24

echo "Using:"
echo "  interface: $DEFAULT_IFACE"
echo "  gateway:   $DEFAULT_GW"
echo "  subnet:    $SUBNET"
echo

# Get base IP for container range
BASE_IP=$(echo $DEFAULT_GW | cut -d. -f1-3)

# Use .96-.103 range for containers (8 IPs, aligned to /29)
# /29 requires IP range to be aligned to multiples of 8
IP_RANGE="${BASE_IP}.96/29"

echo "Container IP range: ${BASE_IP}.96 - ${BASE_IP}.103"
echo "(Layer 2 traffic only; IPs are just for Docker.)"
echo

# Confirm
read -p "Proceed with these settings? (Y/n): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]] && [[ ! -z $REPLY ]]; then
    echo "Aborted"
    exit 1
fi

# Create MACVLAN network
echo
echo "Creating MACVLAN network..."

docker network create -d macvlan \
    --subnet="$SUBNET" \
    --gateway="$DEFAULT_GW" \
    --ip-range="$IP_RANGE" \
    -o parent="$DEFAULT_IFACE" \
    "$NETWORK_NAME"

echo
echo "MACVLAN network ready."
docker network inspect "$NETWORK_NAME" | grep -A 6 "IPAM"
echo
echo "Next: ./docker/run-macvlan.sh (use interface eth0 in Link-Chat)."
echo
