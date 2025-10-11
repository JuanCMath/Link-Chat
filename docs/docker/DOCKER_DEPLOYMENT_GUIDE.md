# Docker Deployment Guide - Link-Chat on Alpine Linux

## Table of Contents
- [Compatibility Analysis](#compatibility-analysis)
- [Potential Issues](#potential-issues)
- [Solution Architecture](#solution-architecture)
- [Step-by-Step Setup](#step-by-step-setup)
- [Testing & Verification](#testing--verification)
- [Troubleshooting](#troubleshooting)

---

## Compatibility Analysis

### ✅ **What Works Out of the Box**

| Component | Alpine Compatible | Notes |
|-----------|-------------------|-------|
| Python 3.13 | ✅ Yes | Available in Alpine repos |
| AF_PACKET sockets | ✅ Yes | Linux kernel feature, works in containers |
| Raw socket support | ✅ Yes | With proper capabilities |
| Threading | ✅ Yes | Standard library, no issues |
| PyQt6 | ⚠️ Partial | Requires X11 or headless setup |

### ⚠️ **Critical Requirements**

1. **Linux Kernel Features**
   - AF_PACKET is a **Linux-specific** socket family
   - **Must run on Linux host** (not Windows/macOS Docker Desktop without special config)
   - Container needs access to host network stack

2. **Network Mode**
   - **Cannot use default bridge networking**
   - Must use `--network host` to access physical interfaces
   - Alternative: `macvlan` or `ipvlan` for isolated containers

3. **Capabilities**
   - Requires `CAP_NET_RAW` and `CAP_NET_ADMIN` capabilities
   - Standard user containers won't work without these

4. **GUI Challenges**
   - PyQt6 needs X11 server or Wayland compositor
   - Options: X11 forwarding, VNC, headless with Xvfb, or web-based GUI

---

## Potential Issues

### 🚨 **Issue 1: Alpine musl libc vs glibc**

**Problem:** Alpine uses `musl` instead of `glibc`. Some Python binary wheels (especially for Qt) are compiled against glibc.

**Impact:** PyQt6 wheels might not install or crash at runtime.

**Solutions:**
- Use Alpine-specific packages: `py3-qt6` from Alpine repos
- OR switch to Debian-based image (`python:3.13-slim`)
- OR build PyQt6 from source (slow, complex)

### 🚨 **Issue 2: Network Interface Access**

**Problem:** Docker bridge networking creates virtual interfaces, not real hardware.

**Impact:** AF_PACKET won't see host's `eth0`/`wlan0`.

**Solution:** Use `--network host` mode (see below).

### 🚨 **Issue 3: X11 Display for GUI**

**Problem:** Containers don't have display by default.

**Impact:** PyQt6 windows won't render.

**Solutions:**
- **X11 forwarding** (easiest for development)
- **VNC server** inside container (best for production)
- **Headless mode** with virtual display (for automated testing)
- **Web interface** (future improvement)

### 🚨 **Issue 4: Permissions**

**Problem:** CAP_NET_RAW required for raw sockets.

**Impact:** Permission denied on socket creation.

**Solution:** Add `--cap-add=NET_RAW --cap-add=NET_ADMIN` to docker run.

---

## Solution Architecture

### Recommended Approach: Debian Base + Host Networking

```
┌─────────────────────────────────────────────┐
│         Docker Host (Linux)                 │
│  ┌────────────────────────────────────┐     │
│  │  Container (python:3.13-slim)      │     │
│  │                                    │     │
│  │  ┌──────────────┐                 │     │
│  │  │  Link-Chat   │                 │     │
│  │  │  + PyQt6     │                 │     │
│  │  └──────┬───────┘                 │     │
│  │         │ AF_PACKET                │     │
│  │         ↓                          │     │
│  │  (shares host network namespace)  │     │
│  └─────────┼──────────────────────────┘     │
│            │                                 │
│            ↓                                 │
│      eth0 / wlan0                           │
│    (physical interface)                     │
└─────────────────────────────────────────────┘
```

**Why this works:**
- `--network host` gives container direct access to host interfaces
- Debian base ensures PyQt6 compatibility
- X11 forwarding enables GUI rendering on host display

---

## Step-by-Step Setup

### Option A: Debian Base (Recommended for GUI)

#### 1. Create Dockerfile

**File:** `Dockerfile.debian`

```dockerfile
FROM python:3.13-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    # PyQt6 dependencies
    libgl1 \
    libglib2.0-0 \
    libdbus-1-3 \
    libxcb-xinerama0 \
    libxcb-icccm4 \
    libxcb-image0 \
    libxcb-keysyms1 \
    libxcb-randr0 \
    libxcb-render-util0 \
    libxcb-shape0 \
    libxkbcommon-x11-0 \
    # Network utilities for debugging
    net-tools \
    iproute2 \
    iputils-ping \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy project files
COPY pyproject.toml uv.lock ./
COPY linkchat/ ./linkchat/

# Install Python dependencies
RUN pip install --no-cache-dir PyQt6>=6.6

# Create downloads directory
RUN mkdir -p /app/downloads

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV QT_QPA_PLATFORM=xcb

# Default command
CMD ["python", "-m", "linkchat.app.qt_main"]
```

#### 2. Build Image

```bash
docker build -f Dockerfile.debian -t linkchat:latest .
```

#### 3. Run with X11 Forwarding (Linux Host)

```bash
# Allow container to connect to X server
xhost +local:docker

# Run container
docker run -it --rm \
  --network host \
  --cap-add=NET_RAW \
  --cap-add=NET_ADMIN \
  -e DISPLAY=$DISPLAY \
  -v /tmp/.X11-unix:/tmp/.X11-unix:rw \
  -v $(pwd)/downloads:/app/downloads \
  linkchat:latest

# After testing, restore X security
xhost -local:docker
```

**Explanation:**
- `--network host`: Share host network interfaces
- `--cap-add=NET_RAW`: Allow raw socket creation
- `-e DISPLAY`: Pass X display variable
- `-v /tmp/.X11-unix`: Mount X11 socket

---

### Option B: Alpine Base (Smaller, More Complex)

#### 1. Create Dockerfile

**File:** `Dockerfile.alpine`

```dockerfile
FROM python:3.13-alpine

# Install system dependencies
RUN apk add --no-cache \
    # Build dependencies
    gcc \
    g++ \
    musl-dev \
    linux-headers \
    # PyQt6 from Alpine repos
    py3-qt6 \
    qt6-qtbase-x11 \
    # Network utilities
    net-tools \
    iproute2 \
    iputils

# Set working directory
WORKDIR /app

# Copy project files
COPY pyproject.toml ./
COPY linkchat/ ./linkchat/

# Create symbolic link for system PyQt6
RUN ln -s /usr/lib/python3.*/site-packages/PyQt6 \
    /usr/local/lib/python3.13/site-packages/PyQt6

# Create downloads directory
RUN mkdir -p /app/downloads

# Set environment
ENV PYTHONUNBUFFERED=1
ENV QT_QPA_PLATFORM=xcb

CMD ["python3", "-m", "linkchat.app.qt_main"]
```

#### 2. Build and Run

```bash
docker build -f Dockerfile.alpine -t linkchat:alpine .

docker run -it --rm \
  --network host \
  --cap-add=NET_RAW \
  --cap-add=NET_ADMIN \
  -e DISPLAY=$DISPLAY \
  -v /tmp/.X11-unix:/tmp/.X11-unix:rw \
  linkchat:alpine
```

---

### Option C: Headless with VNC (Production)

For remote access or automated deployments:

#### 1. Dockerfile with VNC

**File:** `Dockerfile.vnc`

```dockerfile
FROM python:3.13-slim

# Install X11, VNC, and window manager
RUN apt-get update && apt-get install -y \
    # X11 and VNC
    xvfb \
    x11vnc \
    fluxbox \
    # PyQt6 dependencies
    libgl1 \
    libglib2.0-0 \
    libdbus-1-3 \
    libxcb-xinerama0 \
    libxcb-icccm4 \
    libxcb-image0 \
    libxcb-keysyms1 \
    libxcb-randr0 \
    libxcb-render-util0 \
    libxcb-shape0 \
    libxkbcommon-x11-0 \
    net-tools \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml uv.lock ./
COPY linkchat/ ./linkchat/

RUN pip install --no-cache-dir PyQt6>=6.6

# VNC startup script
COPY docker/start-vnc.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/start-vnc.sh

ENV DISPLAY=:99
ENV VNC_PORT=5900

EXPOSE 5900

CMD ["/usr/local/bin/start-vnc.sh"]
```

#### 2. VNC Startup Script

**File:** `docker/start-vnc.sh`

```bash
#!/bin/bash
set -e

# Start virtual framebuffer
Xvfb :99 -screen 0 1024x768x24 &
sleep 2

# Start window manager
fluxbox &
sleep 1

# Start VNC server
x11vnc -display :99 -forever -shared -rfbport 5900 -nopw &

# Wait for VNC to start
sleep 2

# Launch Link-Chat
python -m linkchat.app.qt_main
```

#### 3. Run and Connect

```bash
docker run -d \
  --name linkchat-vnc \
  --network host \
  --cap-add=NET_RAW \
  --cap-add=NET_ADMIN \
  -p 5900:5900 \
  linkchat:vnc

# Connect with VNC client
vncviewer localhost:5900
```

---

## Docker Compose Setup

For easier orchestration:

**File:** `docker-compose.yml`

```yaml
version: '3.8'

services:
  linkchat:
    build:
      context: .
      dockerfile: Dockerfile.debian
    image: linkchat:latest
    container_name: linkchat-app
    
    # Host networking for interface access
    network_mode: host
    
    # Required capabilities
    cap_add:
      - NET_RAW
      - NET_ADMIN
    
    # X11 forwarding
    environment:
      - DISPLAY=${DISPLAY}
      - QT_QPA_PLATFORM=xcb
      - INTERFACE=${INTERFACE:-wlan0}
    
    volumes:
      - /tmp/.X11-unix:/tmp/.X11-unix:rw
      - ./downloads:/app/downloads
    
    # Keep container running
    stdin_open: true
    tty: true
    
    # Restart policy
    restart: unless-stopped

  # Optional: VNC-enabled version
  linkchat-vnc:
    build:
      context: .
      dockerfile: Dockerfile.vnc
    image: linkchat:vnc
    container_name: linkchat-vnc
    network_mode: host
    cap_add:
      - NET_RAW
      - NET_ADMIN
    ports:
      - "5900:5900"
    restart: unless-stopped
```

**Usage:**

```bash
# Start with X11
docker-compose up linkchat

# Start with VNC
docker-compose up linkchat-vnc
```

---

## Testing & Verification

### Step 1: Verify Container Networking

```bash
# Inside container
docker exec -it linkchat-app bash

# List interfaces (should see host's eth0/wlan0)
ip link show

# Check for required interfaces
ip addr show wlan0
```

### Step 2: Test Raw Socket Creation

```bash
# Inside container
python3 -c "
import socket
sock = socket.socket(socket.AF_PACKET, socket.SOCK_RAW, socket.htons(0x88B5))
print('✅ AF_PACKET socket created successfully')
sock.close()
"
```

### Step 3: Test GUI Display

```bash
# Simple Qt test
python3 -c "
from PyQt6.QtWidgets import QApplication, QLabel
import sys
app = QApplication(sys.argv)
label = QLabel('✅ PyQt6 works!')
label.show()
print('GUI window should appear')
"
```

### Step 4: Run Link-Chat

```bash
# Inside container
python -m linkchat.app.qt_main
```

---

## Troubleshooting

### Problem: "Permission denied" on socket creation

**Symptoms:**
```
OSError: [Errno 1] Operation not permitted
```

**Solutions:**
```bash
# 1. Check capabilities
docker run ... --cap-add=NET_RAW --cap-add=NET_ADMIN ...

# 2. Or run privileged (NOT recommended for production)
docker run ... --privileged ...
```

---

### Problem: "Cannot connect to X server"

**Symptoms:**
```
qt.qpa.xcb: could not connect to display
```

**Solutions:**

**Linux:**
```bash
# Allow Docker to connect
xhost +local:docker

# Verify DISPLAY variable
echo $DISPLAY  # Should be :0 or :1

# Check X11 socket mount
docker run ... -v /tmp/.X11-unix:/tmp/.X11-unix:rw ...
```

**Remote/Headless:**
```bash
# Use VNC image instead
docker-compose up linkchat-vnc
```

---

### Problem: "No such device" for interface

**Symptoms:**
```
OSError: [Errno 19] No such device: wlan0
```

**Solutions:**
```bash
# 1. Verify host networking
docker run ... --network host ...

# 2. List available interfaces on host
ip link show

# 3. Check interface exists in container
docker exec linkchat-app ip link show

# 4. If using bridge mode, won't work - must use host mode
```

---

### Problem: PyQt6 import fails on Alpine

**Symptoms:**
```
ImportError: libQt6Core.so.6: cannot open shared object file
```

**Solutions:**
```bash
# Option 1: Use Debian base
docker build -f Dockerfile.debian ...

# Option 2: Install Alpine packages
apk add py3-qt6 qt6-qtbase-x11

# Option 3: Use system Python's PyQt6
ln -s /usr/lib/python3.*/site-packages/PyQt6 ...
```

---

### Problem: Container can't see host Wi-Fi

**Cause:** Wi-Fi interfaces in managed mode may not work with AF_PACKET from containers.

**Solutions:**
```bash
# 1. Use Ethernet instead
INTERFACE=eth0 docker-compose up

# 2. Put Wi-Fi in monitor mode (advanced)
sudo ip link set wlan0 down
sudo iw wlan0 set monitor control
sudo ip link set wlan0 up

# 3. Use macvlan (creates virtual MAC)
docker network create -d macvlan \
  --subnet=192.168.1.0/24 \
  --gateway=192.168.1.1 \
  -o parent=wlan0 linkchat-net
```

---

## Best Practices

### 1. Use Multi-Stage Builds

```dockerfile
# Build stage
FROM python:3.13-slim as builder
RUN pip install --user PyQt6

# Runtime stage
FROM python:3.13-slim
COPY --from=builder /root/.local /root/.local
COPY linkchat/ ./linkchat/
CMD ["python", "-m", "linkchat.app.qt_main"]
```

### 2. Health Checks

```yaml
# In docker-compose.yml
healthcheck:
  test: ["CMD", "python", "-c", "import socket; s=socket.socket(socket.AF_PACKET, socket.SOCK_RAW, 0); s.close()"]
  interval: 30s
  timeout: 10s
  retries: 3
```

### 3. Logging

```dockerfile
ENV PYTHONUNBUFFERED=1
CMD ["python", "-u", "-m", "linkchat.app.qt_main"]
```

---

## Summary

### ✅ Recommended Setup for Development

```bash
# Use Debian base with X11 forwarding
docker build -f Dockerfile.debian -t linkchat .
xhost +local:docker
docker run -it --rm \
  --network host \
  --cap-add=NET_RAW \
  --cap-add=NET_ADMIN \
  -e DISPLAY=$DISPLAY \
  -v /tmp/.X11-unix:/tmp/.X11-unix:rw \
  linkchat
```

### ✅ Recommended Setup for Production

```bash
# Use VNC for remote access
docker-compose up linkchat-vnc
# Access via VNC client on port 5900
```

### ⚠️ Key Points

1. **Must use Linux host** (AF_PACKET is Linux-only)
2. **Must use host networking** (`--network host`)
3. **Must add capabilities** (`--cap-add=NET_RAW`)
4. **Debian base easier** than Alpine for PyQt6
5. **X11 or VNC required** for GUI rendering

---

## Next Steps

1. Choose Dockerfile variant (Debian recommended)
2. Build image
3. Test with `docker run` first
4. Migrate to `docker-compose` for production
5. Consider web interface for easier deployment
