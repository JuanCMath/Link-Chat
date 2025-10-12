#!/bin/bash
# Run Link-Chat with MACVLAN networking
# Container will have unique MAC address for Layer 2 communication

set -e

NETWORK_NAME="linkchat-macvlan"
MODE=${LINKCHAT_MODE:-gui}

echo "Starting Link-Chat on MACVLAN network"
echo

# Check if network exists
if ! docker network ls | grep -q "$NETWORK_NAME"; then
    echo "MACVLAN network '$NETWORK_NAME' not found."
    echo "Run ./docker/setup-macvlan.sh first."
    echo
    exit 1
fi

# Check if image exists
if ! docker image inspect linkchat-interactive &> /dev/null; then
    echo "Image 'linkchat-interactive' not found."
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

# Show quick network summary
SUBNET=$(docker network inspect "$NETWORK_NAME" | grep -A 4 "Config" | grep "Subnet" | awk -F'"' '{print $4}')
echo "Using network $NETWORK_NAME ($SUBNET)."
echo "Container interface: eth0"
echo

if [ "$MODE" = "gui" ]; then
    xhost +local:docker > /dev/null 2>&1 || true
    DISPLAY_FLAGS=(
        -e "DISPLAY=$DISPLAY"
        -e "QT_QPA_PLATFORM=xcb"
        -v /tmp/.X11-unix:/tmp/.X11-unix:rw
    )
    START_COMMAND="python -m linkchat.app.qt_main"
else
    DISPLAY_FLAGS=()
    START_COMMAND="python -m linkchat.app.cli_main"
fi

echo "Launching container (mode: $MODE)..."
echo

docker run -it --rm \
    --network "$NETWORK_NAME" \
    --cap-add=NET_ADMIN \
    --cap-add=NET_RAW \
    "${DISPLAY_FLAGS[@]}" \
    --env "LINKCHAT_INTERFACE=eth0" \
    --name linkchat-instance-1 \
    linkchat-interactive \
    bash -c "
        ip link set eth0 up
        echo 'eth0 status: ' \$(ip link show eth0 | grep -o 'state [A-Z]*' | awk '{print \$2}')
        echo 'MAC: ' \$(cat /sys/class/net/eth0/address)
        echo 'Docker IP: ' \$(ip addr show eth0 | grep 'inet ' | awk '{print \$2}')
        echo
        echo "Starting Link-Chat (${MODE} mode)."
        echo
        $START_COMMAND
    "

if [ "$MODE" = "gui" ]; then
    xhost -local:docker > /dev/null 2>&1 || true
fi

echo
echo "Container stopped."
