# Link-Chat Docker Complete Guide

## 📋 Table of Contents

1. [Quick Start](#quick-start)
2. [Image Variants](#image-variants)
3. [Build Scripts](#build-scripts)
4. [Debian vs Alpine](#debian-vs-alpine)
5. [GUI Support](#gui-support)
6. [Networking](#networking)
7. [Development Workflow](#development-workflow)
8. [Troubleshooting](#troubleshooting)

## 🚀 Quick Start

### Fastest Way to Get Started (Debian)

```powershell
# Build Debian base + all images (10-15 minutes total)
.\docker\build-all.ps1 debian

# Run interactive shell
docker run -it --rm linkchat-interactive
```

### Smallest Images (Alpine)

```powershell
# Build Alpine base + all images (45-60 minutes first time)
.\docker\build-all.ps1 alpine

# Run interactive shell
docker run -it --rm linkchat-interactive-alpine
```

### Just Run Tests

```powershell
# Build and run tests (standalone, no base needed)
docker build -f docker/testing/Dockerfile.test -t linkchat-test .
docker run --rm linkchat-test
```

## 📦 Image Variants

### Base Images (Build Once, Use Forever)

| Image | Base OS | Size | Build Time | Purpose |
|-------|---------|------|------------|---------|
| `linkchat-base:latest` | Debian Bookworm | ~800 MB | 5-10 min | Fast development |
| `linkchat-base-alpine:latest` | Alpine 3.19 | ~680 MB | 40-60 min | Small production |

**What's in the base:**
- Python 3.13
- PyQt6 6.6+ (binary wheel for Debian, compiled for Alpine)
- All 35+ system dependencies (EGL, OpenGL, X11, etc.)
- Network tools (tcpdump, ethtool, iproute2)
- Development tools (gcc, g++, vim, nano, git)

### Derived Images (Rebuild in 30 Seconds)

| Image | Based On | Size | Use Case |
|-------|----------|------|----------|
| `linkchat-test` | Alpine (standalone) | ~150 MB | Unit tests only |
| `linkchat-interactive` | linkchat-base | ~800 MB | Development with GUI |
| `linkchat-production` | linkchat-base | ~800 MB | Production deployment |
| `linkchat-interactive-alpine` | linkchat-base-alpine | ~680 MB | Dev (smaller) |
| `linkchat-production-alpine` | linkchat-base-alpine | ~550 MB | Prod (smallest) |

## 🛠️ Build Scripts

### PowerShell (Windows)

```powershell
# Build specific target
.\docker\build-all.ps1 <target>

# Build with no cache
.\docker\build-all.ps1 <target> -NoCache
```

### Bash (Linux/Mac)

```bash
# Build specific target
./docker/build-all.sh <target>

# Build with no cache
./docker/build-all.sh <target> --no-cache
```

### Available Targets

| Target | Description | Time |
|--------|-------------|------|
| `all` | Build EVERYTHING (Debian + Alpine) | 60-90 min |
| `debian` | Build all Debian images | 10-15 min |
| `alpine` | Build all Alpine images | 45-60 min |
| `base` | Build Debian base only | 5-10 min |
| `base-alpine` | Build Alpine base only | 40-60 min |
| `test` | Build test image only | 2-5 min |
| `interactive` | Build Debian interactive | 30 sec (needs base) |
| `interactive-alpine` | Build Alpine interactive | 30 sec (needs base-alpine) |
| `production` | Build Debian production | 30 sec (needs base) |
| `production-alpine` | Build Alpine production | 30 sec (needs base-alpine) |

### Examples

```powershell
# Recommended: Build Debian images for development
.\docker\build-all.ps1 debian

# Recommended: Build Alpine images for production
.\docker\build-all.ps1 alpine

# Build only what you need
.\docker\build-all.ps1 base          # Just the base
.\docker\build-all.ps1 interactive   # Then interactive

# Force rebuild from scratch
.\docker\build-all.ps1 base -NoCache
```

## ⚖️ Debian vs Alpine

### Quick Comparison

|  | Debian | Alpine |
|---|--------|--------|
| **Base OS** | Ubuntu-based | musl libc |
| **Image Size** | ~800 MB | ~550-680 MB |
| **Initial Build** | 5-10 minutes | 40-60 minutes |
| **Rebuild Time** | 30 seconds | 30 seconds |
| **PyQt6 Install** | Binary wheel | Source compilation |
| **Best For** | Development | Production |
| **Downloads** | ~340 MB | ~200 MB |

### Detailed Comparison

#### Debian (python:3.13-slim)

**Pros:**
- ✅ **Fast initial setup** (5-10 minutes)
- ✅ **Binary PyQt6 wheels** (no compilation)
- ✅ **Well-tested** with most Python packages
- ✅ **Easier debugging** (more familiar environment)

**Cons:**
- ❌ Larger image size (~800 MB)
- ❌ More packages = larger attack surface

**Recommended for:**
- Development and testing
- Quick iteration
- When build speed matters more than image size

#### Alpine (python:3.13-alpine)

**Pros:**
- ✅ **Smaller images** (~150-250 MB savings)
- ✅ **Smaller attack surface** (security)
- ✅ **Lower disk usage** (important for CI/CD)
- ✅ **Faster downloads** after initial build

**Cons:**
- ❌ **Slow initial build** (40-60 minutes)
- ❌ Must compile PyQt6 from source
- ❌ musl libc can cause compatibility issues

**Recommended for:**
- Production deployment
- When disk space is limited
- When you can afford one-time long build

### Decision Matrix

**Choose Debian if:**
- 👨‍💻 You're developing/debugging
- ⏱️ You need to start quickly
- 🔄 You rebuild frequently
- 💾 Disk space is not a concern

**Choose Alpine if:**
- 🚀 You're deploying to production
- 💰 You have limited bandwidth
- 📦 Image size matters
- ⏳ You can wait 40-60 min once

**My Recommendation:**
- **Development:** Use Debian (`.\docker\build-all.ps1 debian`)
- **Production:** Use Alpine (`.\docker\build-all.ps1 alpine`)
- **Best of both:** Build Debian first for dev, Alpine later for prod

## 🖥️ GUI Support

All images (except `linkchat-test`) support PyQt6 GUI applications.

### Requirements

1. **X11 Server on Windows**
   - Install [VcXsrv](https://sourceforge.net/projects/vcxsrv/) or [Xming](https://sourceforge.net/projects/xming/)
   - Start with "Disable access control" enabled
   - Use display number 0

2. **X11 Server on Linux**
   - Usually already available
   - Allow Docker to connect: `xhost +local:docker`

3. **macOS (XQuartz)**
   - Install [XQuartz](https://www.xquartz.org/)
   - Allow network connections

### Running GUI Applications

```bash
# Windows (VcXsrv/Xming running on display :0)
docker run -it --rm \
  -e DISPLAY=host.docker.internal:0 \
  linkchat-interactive \
  python -m linkchat.app.qt_main

# Linux
docker run -it --rm \
  -e DISPLAY=$DISPLAY \
  -v /tmp/.X11-unix:/tmp/.X11-unix \
  linkchat-interactive \
  python -m linkchat.app.qt_main

# macOS (XQuartz)
docker run -it --rm \
  -e DISPLAY=host.docker.internal:0 \
  linkchat-interactive \
  python -m linkchat.app.qt_main
```

### GUI Troubleshooting

**Error: "cannot open display"**
```bash
# Make sure X11 server is running
# Windows: Check VcXsrv/Xming in system tray
# Linux: echo $DISPLAY should show :0 or :1
# macOS: XQuartz must be running
```

**Error: "libEGL.so.1: cannot open shared object file"**
```bash
# This was fixed in the Dockerfiles
# If you see this, rebuild the image:
docker build -f docker/testing/Dockerfile.interactive.new -t linkchat-interactive .
```

## 🌐 Networking

### Raw Socket Requirements

Link-Chat uses **AF_PACKET** raw sockets, which require:

1. **Linux kernel** (Docker on Windows uses Linux VM)
2. **CAP_NET_RAW capability** or root privileges
3. **Host network mode** (recommended)

### Running with Network Access

```bash
# Host network mode (recommended)
docker run -it --rm \
  --network host \
  --cap-add=NET_ADMIN \
  --cap-add=NET_RAW \
  linkchat-interactive

# With specific interface
docker run -it --rm \
  --network host \
  --cap-add=NET_ADMIN \
  --cap-add=NET_RAW \
  -e LINKCHAT_INTERFACE=eth0 \
  linkchat-interactive
```

### Available Network Interfaces

Inside the container:
```bash
# List all interfaces
ip link show

# Common interfaces:
# - eth0: Ethernet
# - wlan0: WiFi
# - lo: Loopback (testing only)
```

## 💻 Development Workflow

### Recommended Workflow

1. **Initial Setup (Once)**
   ```powershell
   # Build Debian base (5-10 minutes)
   .\docker\build-all.ps1 base
   ```

2. **Start Development Container**
   ```bash
   docker run -it --rm \
     -v ${PWD}:/workspace \
     -w /workspace \
     linkchat-interactive \
     bash
   ```

3. **Make Changes Outside Container**
   - Edit files in your IDE/editor
   - Changes reflected immediately (volume mount)

4. **Test Inside Container**
   ```bash
   # Inside container
   python -m pytest tests/
   python -m linkchat.app.qt_main
   ```

5. **Rebuild Only When Dependencies Change**
   ```powershell
   # If you added new packages to pyproject.toml
   .\docker\build-all.ps1 interactive
   ```

### Volume Mounting for Live Development

```bash
# Mount current directory
docker run -it --rm \
  -v ${PWD}:/app \
  -w /app \
  linkchat-interactive \
  bash

# Now changes to code are instant!
# No need to rebuild for code changes
```

### Testing Workflow

```bash
# Run all tests
docker run --rm linkchat-test

# Run specific test file
docker run --rm linkchat-interactive \
  python -m pytest tests/test_checksum.py

# Run with coverage
docker run --rm linkchat-interactive \
  python -m pytest --cov=linkchat tests/
```

## 🐛 Troubleshooting

### Build Issues

**"linkchat-base:latest not found"**
```bash
# You need to build the base image first
.\docker\build-all.ps1 base
```

**"ERROR: failed to solve: dockerfile parse error"**
```bash
# Make sure you're in the project root directory
cd "d:\UH\Año 3\Redes\Link-Chat"
```

**Build very slow / timeout**
```bash
# For Alpine: 40-60 minutes is normal for first build
# Increase Docker resources:
# Docker Desktop → Settings → Resources
# - CPUs: 4+
# - Memory: 4 GB+
```

### Runtime Issues

**"No module named 'linkchat'"**
```bash
# Make sure package is installed
docker run --rm linkchat-interactive pip list | grep linkchat

# Should show: linkchat 0.1.0
```

**"Permission denied" for network operations**
```bash
# Add network capabilities
docker run --rm \
  --cap-add=NET_ADMIN \
  --cap-add=NET_RAW \
  linkchat-interactive
```

**Tests failing (6 tests fail)**
```bash
# Known issue: 6 integration tests fail
# These are being worked on:
# - test_encode_decode_with_framing
# - test_send_receive_small_file
# - test_complete_workflow
# All 45+ unit tests pass ✅
```

### Image Size Issues

**Images taking too much disk space**
```bash
# Clean up old images
docker image prune -a

# Remove specific image
docker rmi linkchat-interactive

# See disk usage
docker system df
```

### Network Issues

**Cannot see network interfaces**
```bash
# Must use host network mode
docker run --rm --network host linkchat-interactive ip link show
```

**"No such device" error**
```bash
# Interface name might be different in container
# Check available interfaces:
docker run --rm --network host linkchat-interactive ip link show
```

## 📊 Disk Usage Summary

```
After building all images:

DEBIAN IMAGES:
linkchat-base           800 MB   (base with all deps)
linkchat-test           150 MB   (Alpine, no base)
linkchat-interactive    800 MB   (shares base layers)
linkchat-production     800 MB   (shares base layers)

ALPINE IMAGES:
linkchat-base-alpine    680 MB   (base with compiled PyQt6)
linkchat-interactive-alpine  680 MB   (shares alpine base)
linkchat-production-alpine   550 MB   (cleaned up)

TOTAL: ~4-5 GB

With layer sharing:
- Debian images share ~800 MB of layers
- Alpine images share ~680 MB of layers
- Actual disk usage: ~2-3 GB
```

## 🎓 Best Practices

1. **Always build base image first**
   ```powershell
   .\docker\build-all.ps1 base  # or base-alpine
   ```

2. **Use volume mounts for development**
   ```bash
   docker run -v ${PWD}:/app ...
   ```

3. **Tag your base images**
   ```bash
   docker tag linkchat-base:latest linkchat-base:$(date +%Y%m%d)
   ```

4. **Clean up regularly**
   ```bash
   docker system prune -a
   ```

5. **Use appropriate image for task**
   - Tests: `linkchat-test` (smallest)
   - Dev: `linkchat-interactive` (Debian, fast)
   - Prod: `linkchat-production-alpine` (Alpine, small)

6. **Don't rebuild base unless necessary**
   - Code changes: Just rebuild derived images (30 sec)
   - New dependencies: Rebuild base + derived

## 📚 Additional Resources

- [Base Images Documentation](base/README.md)
- [Alpine Setup Guide](ALPINE_SETUP.md)
- [Dependency Verification](DEPENDENCY_VERIFICATION.md)

## 🆘 Getting Help

If you encounter issues:

1. Check this guide first
2. Check build script output for specific errors
3. Verify Docker resources (CPU, Memory)
4. Check Docker version: `docker --version` (need 20.10+)
5. Try rebuilding with `--no-cache`

## 📝 Summary

**Quick Start:**
```powershell
# Development (recommended)
.\docker\build-all.ps1 debian

# Production (smaller images)
.\docker\build-all.ps1 alpine

# Run tests
docker run --rm linkchat-test

# Interactive development
docker run -it --rm linkchat-interactive
```

**Remember:**
- Debian = Fast build, larger images (development)
- Alpine = Slow first build, smaller images (production)
- Base images = Build once, use forever
- Code changes = 30 second rebuilds
