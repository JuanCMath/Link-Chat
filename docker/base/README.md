# 🚀 Fast Docker Builds with Base Image

## Overview

This Docker setup uses a **layered approach** for fast rebuilds:

1. **Base Image** (`linkchat-base`) - Contains all dependencies (built once)
2. **Derived Images** - Copy only code (rebuild in seconds)

> **📚 Looking for the complete guide?** See [DOCKER_GUIDE.md](../DOCKER_GUIDE.md) for comprehensive documentation.
> 
> **📦 Want Alpine images?** See [ALPINE_SETUP.md](../ALPINE_SETUP.md) for smaller production images.

---

## 📦 Image Structure

### Debian Images (This File)

```
linkchat-base:latest (800MB) - Debian Bookworm
├── Python 3.13
├── PyQt6 + all GUI libraries (binary wheels)
├── pytest + testing tools
├── Network tools (tcpdump, etc.)
└── Development tools (vim, nano, git)
    │
    ├── linkchat-test (800MB)
    │   └── + Your code + tests
    │
    ├── linkchat-interactive (800MB)
    │   └── + Your code (dev mode)
    │
    └── linkchat-production (800MB)
        └── + Your code (optimized)
```

### Alpine Images (See [ALPINE_SETUP.md](../ALPINE_SETUP.md))

```
linkchat-base-alpine:latest (680MB) - Alpine 3.19
├── Python 3.13
├── PyQt6 + all GUI libraries (compiled from source)
└── All dependencies
    │
    ├── linkchat-interactive-alpine (680MB)
    │   └── + Your code (dev mode)
    │
    └── linkchat-production-alpine (550MB)
        └── + Your code (cleaned up)
```

---

## ⚡ Build Times Comparison

### Without Base Image (Old Method):
- **First build:** 5-10 minutes
- **Code change rebuild:** 5-10 minutes ❌ (reinstalls everything)

### With Base Image (New Method):
- **First build (base):** 5-10 minutes (once)
- **First build (derived):** 30 seconds
- **Code change rebuild:** 30 seconds ✅ (only copies code)

**Result:** 10x faster rebuilds! 🎉

---

## 🛠️ Quick Start

### Step 1: Build Base Image (Once)

**Windows PowerShell:**
```powershell
.\docker\build-all.ps1 base
```

**Linux/Mac:**
```bash
chmod +x docker/build-all.sh
./docker/build-all.sh base
```

**Manual:**
```bash
docker build -f docker/base/Dockerfile.base -t linkchat-base:latest .
```

### Step 2: Build Derived Images

**Build all images:**
```powershell
# Windows
.\docker\build-all.ps1 all

# Linux/Mac
./docker/build-all.sh all
```

**Build specific image:**
```powershell
# Windows
.\docker\build-all.ps1 test          # Build test image only
.\docker\build-all.ps1 interactive   # Build interactive image only
.\docker\build-all.ps1 production    # Build production image only

# Linux/Mac
./docker/build-all.sh test
./docker/build-all.sh interactive
./docker/build-all.sh production
```

---

## 🔄 Workflow for Code Changes

When you modify Python code:

```powershell
# Rebuild only the interactive image (30 seconds)
docker build -f docker/testing/Dockerfile.interactive.new -t linkchat-interactive .

# Run it
docker run -it --rm linkchat-interactive
```

**No need to rebuild the base image!** Dependencies haven't changed.

---

## 📋 Usage Examples

### Run Unit Tests
```powershell
docker run --rm linkchat-test
```

### Interactive Development
```powershell
docker run -it --rm linkchat-interactive /bin/bash
```

### Run GUI (with X11 server)
```powershell
docker run -it --rm `
  -e DISPLAY=host.docker.internal:0 `
  -e QT_QPA_PLATFORM=xcb `
  linkchat-interactive `
  python -m linkchat.app.qt_main
```

### Production Deployment
```powershell
docker run -it --rm `
  --network host `
  -e INTERFACE=eth0 `
  linkchat-production
```

---

## 🔧 Build Options

### Rebuild Without Cache
```powershell
# Windows
.\docker\build-all.ps1 all -NoCache

# Linux/Mac
./docker/build-all.sh all --no-cache
```

### Check Image Sizes
```powershell
docker images | Select-String "linkchat"
```

### Remove Old Images
```powershell
# Remove all linkchat images
docker rmi $(docker images -q linkchat*)

# Remove dangling images
docker image prune
```

---

## 📊 Detailed Image Info

### linkchat-base
- **Purpose:** Foundation with all dependencies
- **Size:** ~800MB
- **Rebuild frequency:** Only when dependencies change
- **Contents:**
  - Python 3.13
  - PyQt6 6.6+
  - All system libraries (EGL, OpenGL, X11)
  - pytest, development tools
  - Network debugging tools

### linkchat-test
- **Purpose:** Run pytest unit tests
- **Size:** ~800MB (same as base)
- **Rebuild frequency:** Every code change
- **Build time:** ~30 seconds
- **Run:** `docker run --rm linkchat-test`

### linkchat-interactive
- **Purpose:** Development and debugging
- **Size:** ~800MB
- **Rebuild frequency:** Every code change
- **Build time:** ~30 seconds
- **Features:**
  - Development mode (`pip install -e .`)
  - Interactive shell
  - All debugging tools

### linkchat-production
- **Purpose:** Production deployment
- **Size:** ~800MB
- **Rebuild frequency:** Every release
- **Build time:** ~30 seconds
- **Optimizations:**
  - Production install (no dev mode)
  - Minimal layers

---

## 🎯 When to Rebuild Base Image

Rebuild `linkchat-base` when:
- ✅ Adding new Python packages (e.g., new dependency in pyproject.toml)
- ✅ Adding system libraries (e.g., new apt packages)
- ✅ Upgrading Python version
- ✅ Upgrading PyQt6 version

**Don't rebuild for:**
- ❌ Code changes in `linkchat/` directory
- ❌ Test changes
- ❌ Configuration changes

---

## 🐛 Troubleshooting

### Issue: "linkchat-base not found"
**Solution:** Build the base image first:
```powershell
.\docker\build-all.ps1 base
```

### Issue: "libEGL.so.1 not found"
**Solution:** The base image already includes this. Rebuild base:
```powershell
.\docker\build-all.ps1 base -NoCache
```

### Issue: Builds are still slow
**Check:**
```powershell
# Verify base image exists
docker images linkchat-base

# Should show:
# REPOSITORY      TAG       IMAGE ID       CREATED         SIZE
# linkchat-base   latest    abc123def456   10 minutes ago  800MB
```

If not found, build it first!

---

## 📁 File Structure

```
docker/
├── base/
│   └── Dockerfile.base           # Base image with dependencies
│
├── testing/
│   ├── Dockerfile.test.new       # Test image (uses base)
│   └── Dockerfile.interactive.new # Interactive image (uses base)
│
├── production/
│   └── Dockerfile.new            # Production image (uses base)
│
├── build-all.ps1                 # Windows build script
└── build-all.sh                  # Linux/Mac build script
```

---

## ✅ Migration from Old Dockerfiles

### Old Files (Standalone):
- `docker/testing/Dockerfile.test` (Alpine, no base)
- `docker/testing/Dockerfile.interactive` (Debian, no base)
- `docker/production/Dockerfile` (Debian, no base)

### New Files (Using Base):
- `docker/base/Dockerfile.base` (Shared base)
- `docker/testing/Dockerfile.test.new` (Uses base)
- `docker/testing/Dockerfile.interactive.new` (Uses base)
- `docker/production/Dockerfile.new` (Uses base)

**Keep both for now!** Test the new ones, then replace old files when satisfied.

---

## 🎉 Benefits Summary

✅ **10x faster rebuilds** (30s vs 5-10min)  
✅ **Less bandwidth** (only code layers downloaded)  
✅ **Consistent dependencies** across all images  
✅ **Easier maintenance** (update base once)  
✅ **Smaller storage** (Docker caches shared base layer)  

---

## 📝 Example Workflow

```powershell
# Day 1: Initial setup (10 minutes)
.\docker\build-all.ps1 all

# Day 2: Fixed a bug in file_transfer.py (30 seconds)
docker build -f docker/testing/Dockerfile.interactive.new -t linkchat-interactive .
docker run --rm linkchat-test  # Verify tests pass

# Day 3: Added logging to backend.py (30 seconds)
docker build -f docker/testing/Dockerfile.interactive.new -t linkchat-interactive .
docker run -it --rm linkchat-interactive

# Day 7: Added new dependency (pytest-mock) (10 minutes)
# Edit docker/base/Dockerfile.base, add pytest-mock
.\docker\build-all.ps1 all  # Rebuild everything
```

---

Happy fast building! 🚀
