# Alpine Docker Images for Link-Chat

## Overview

This directory contains **Alpine Linux** variants of the Link-Chat Docker images. Alpine images are **smaller** (600-700 MB vs 800 MB for Debian) but take **longer to build initially** due to PyQt6 compilation from source.

## 🎯 When to Use Alpine vs Debian

### Use Alpine if:
- ✅ Image size is critical (limited disk space, faster downloads)
- ✅ Production deployment (smaller attack surface)
- ✅ You can afford a **one-time 40-60 minute build** for the base image

### Use Debian if:
- ✅ Development speed is priority
- ✅ You need **fast initial setup** (5-10 minute base build)
- ✅ Image size is not a concern

## 📦 Available Alpine Images

| Image | Purpose | Size | Build Time (with base) |
|-------|---------|------|----------------------|
| `linkchat-base-alpine` | Base image with all dependencies | ~600-700 MB | **40-60 minutes** (one-time) |
| `linkchat-interactive-alpine` | Development environment | ~600-700 MB | **30 seconds** |
| `linkchat-production-alpine` | Production deployment | ~500-600 MB | **30 seconds** |

## 🚀 Quick Start

### Option 1: Build Only Alpine Images (Recommended)

```powershell
# Windows PowerShell
.\docker\build-all.ps1 alpine

# Linux/Mac Bash
./docker/build-all.sh alpine
```

This builds:
1. Alpine base image (40-60 minutes)
2. Alpine interactive image (30 seconds)
3. Alpine production image (30 seconds)

### Option 2: Build Individual Images

```powershell
# Build Alpine base first (REQUIRED, one-time only)
.\docker\build-all.ps1 base-alpine

# Then build derived images (fast)
.\docker\build-all.ps1 interactive-alpine
.\docker\build-all.ps1 production-alpine
```

### Option 3: Build Everything (Debian + Alpine)

```powershell
.\docker\build-all.ps1 all  # Takes 60-90 minutes total
```

## 📋 Step-by-Step Alpine Setup

### Step 1: Build the Base Image (One-Time, 40-60 minutes)

```bash
docker build -f docker/base/Dockerfile.base.alpine -t linkchat-base-alpine:latest .
```

**What this does:**
- Installs Alpine system packages (Qt6, mesa, xcb-util, etc.)
- **Compiles PyQt6 from source** (this takes most of the time)
- Installs development tools (gcc, g++, make)
- Downloads ~200 MB from the internet

**You only need to do this ONCE!** After this, subsequent builds are fast.

### Step 2: Build Interactive Image (30 seconds)

```bash
docker build -f docker/testing/Dockerfile.interactive.alpine -t linkchat-interactive-alpine .
```

**What this does:**
- Uses pre-built base image (no compilation!)
- Copies your code into the container
- Installs in development mode (`pip install -e .`)

### Step 3: Build Production Image (30 seconds)

```bash
docker build -f docker/production/Dockerfile.alpine -t linkchat-production-alpine .
```

**What this does:**
- Uses pre-built base image
- Copies your code
- Installs normally (`pip install .`)
- **Removes build dependencies** to reduce size

## 🎮 Running Alpine Images

### Interactive Development

```bash
# Basic shell
docker run -it --rm linkchat-interactive-alpine

# With GUI support (requires X11 server on Windows)
docker run -it --rm \
  -e DISPLAY=host.docker.internal:0 \
  linkchat-interactive-alpine \
  python -m linkchat.app.qt_main
```

### Production Deployment

```bash
docker run -it --rm linkchat-production-alpine
```

## 🔄 Rebuilding After Code Changes

Since you're using the **base image pattern**, rebuilding after code changes is **SUPER FAST**:

```bash
# Only rebuild the layer that changed (30 seconds)
docker build -f docker/testing/Dockerfile.interactive.alpine -t linkchat-interactive-alpine .
```

**Bandwidth usage:**
- First time: ~200 MB (Alpine base packages)
- After code change: **~2 MB** (just your code!)

## 🛠️ Technical Details

### Why PyQt6 Compilation Takes So Long

Alpine uses **musl libc** instead of **glibc**, which means:
- PyQt6 binary wheels (pre-compiled) don't work
- Must compile from source using `pip install --no-binary :all:`
- Compilation involves building Qt bindings for Python (thousands of files)

**Build stages:**
1. Download source (5 min)
2. Configure build (5 min)
3. Compile C++ extensions (30-50 min)
4. Install (5 min)

### What's Different from Debian

| Aspect | Debian | Alpine |
|--------|--------|--------|
| Base OS | python:3.13-slim (Ubuntu) | python:3.13-alpine |
| C Library | glibc | musl libc |
| Package Manager | apt | apk |
| PyQt6 Install | Binary wheel (fast) | Source compilation (slow) |
| System Packages | ~35 packages | ~40 packages |
| Final Size | ~800 MB | ~600-700 MB |

### Dependencies Installed

**Build-time only** (removed in production):
- gcc, g++, make, cmake
- Qt6 development headers
- Mesa development files

**Runtime** (kept in all images):
- Qt6 libraries (qtbase, qtdeclarative, etc.)
- Mesa (OpenGL/EGL)
- xcb-util (X11 support)
- Network tools (tcpdump, ethtool)

## 🐛 Troubleshooting

### "linkchat-base-alpine:latest not found"

You need to build the base image first:

```bash
docker build -f docker/base/Dockerfile.base.alpine -t linkchat-base-alpine:latest .
```

### Build Timeout / Very Slow

PyQt6 compilation can take 40-60 minutes depending on your CPU. This is **normal** for Alpine. If you need faster builds, use Debian images instead.

### Out of Memory During Build

Increase Docker memory limit to at least **4 GB**:
- Docker Desktop → Settings → Resources → Memory

### GUI Not Working

Make sure you have an X11 server running on Windows:
1. Install VcXsrv or Xming
2. Start with "Disable access control" checked
3. Use `-e DISPLAY=host.docker.internal:0` when running

## 📊 Size Comparison

```
REPOSITORY                          SIZE
linkchat-base-alpine                680 MB   (Alpine, all deps)
linkchat-interactive-alpine         680 MB   (Alpine, dev mode)
linkchat-production-alpine          550 MB   (Alpine, cleaned)

linkchat-base                       800 MB   (Debian, all deps)
linkchat-interactive                800 MB   (Debian, dev mode)
linkchat-production                 800 MB   (Debian, normal)
```

**Savings:** ~150-250 MB per image with Alpine

## 🎓 Best Practices

1. **Build base image on fast connection** - It downloads ~200 MB
2. **Use Debian for development** - Faster iteration
3. **Use Alpine for production** - Smaller deployment
4. **Don't rebuild base unless dependencies change**
5. **Keep base image tagged** - Never lose the compiled PyQt6!

## 📝 Files

```
docker/
├── base/
│   ├── Dockerfile.base           # Debian base
│   └── Dockerfile.base.alpine    # Alpine base (THIS ONE)
├── testing/
│   ├── Dockerfile.interactive.alpine
│   └── Dockerfile.test.new
├── production/
│   └── Dockerfile.alpine
├── build-all.ps1                 # Windows build script
├── build-all.sh                  # Linux/Mac build script
└── ALPINE_SETUP.md              # This file
```

## 🚦 Summary

**TL;DR:**
1. Build Alpine base once: `.\docker\build-all.ps1 base-alpine` (40-60 min)
2. Build other images fast: `.\docker\build-all.ps1 alpine` (1 min total)
3. Enjoy **30-second rebuilds** after code changes!
4. Benefit from **smaller images** (~150 MB savings)

**Trade-off:** Initial 40-60 minute build → Permanent fast rebuilds + smaller images
