#!/bin/bash
# Run Link-Chat with --network host mode
# Container shares WSL2's network namespace directly

set -e

echo "=========================================="
echo "  Link-Chat Host Network Mode"
echo "=========================================="
echo ""

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

# Allow X11 connections
xhost +local:docker > /dev/null 2>&1 || true

echo "🚀 Starting Link-Chat container with host networking..."
echo ""
echo "📝 IMPORTANT:"
echo "  • Container shares WSL2's network namespace"
echo "  • Use WSL2's interface names (eth0, wlan0, etc.)"
echo "  • Container has full network access"
echo ""

# Run container with --network host
docker run -it --rm \
    --network host \
    --cap-add=NET_ADMIN \
    --cap-add=NET_RAW \
    -e DISPLAY=$DISPLAY \
    -e QT_QPA_PLATFORM=xcb \
    -v /tmp/.X11-unix:/tmp/.X11-unix:rw \
    --name linkchat-host-$RANDOM \
    linkchat-interactive \
    bash -c '
        echo "Container network mode: HOST"
        echo "Available interfaces:"
        ip link show | grep "^[0-9]" | awk "{print \$2}" | sed "s/:$//"
        echo ""
        echo "Starting Link-Chat GUI..."
        echo ""
        python -m linkchat.app.qt_main
    '

# Cleanup
xhost -local:docker > /dev/null 2>&1 || true

echo ""
echo "Link-Chat stopped"
