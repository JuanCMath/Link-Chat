# Docker Directory - Overview

This directory contains all Docker-related files for Link-Chat.

---

## Directory Structure

```
docker/
├── production/          # 🚀 Production deployment
│   ├── Dockerfile
│   ├── docker-compose.yml
│   └── docker-run.sh
│
└── testing/            # 🧪 Development & testing
    ├── Dockerfile.test
    ├── Dockerfile.interactive
    ├── docker-compose.test.yml
    ├── test_container.py
    ├── docker-test.ps1
    ├── docker-test.sh
    └── start-integration-test.ps1
```

---

## Production (`production/`)

**Purpose:** Deploy Link-Chat on real Linux hardware with physical network interfaces.

**Files:**
- `Dockerfile` - Full Debian image with PyQt6 and network tools
- `docker-compose.yml` - Host networking configuration
- `docker-run.sh` - Quick start script

**Use when:**
- ✅ Running on Linux PC/server
- ✅ Need access to eth0/wlan0 physical interfaces
- ✅ Production deployment with GUI

**Quick start:**
```bash
cd production
./docker-run.sh
```

---

## Testing (`testing/`)

**Purpose:** Test Link-Chat on Windows/macOS without physical hardware requirements.

### Unit Testing
**Files:**
- `Dockerfile.test` - Alpine Linux with pytest
- `docker-test.ps1` - Windows runner
- `docker-test.sh` - Linux/macOS runner

**Use for:**
- ✅ Running pytest on Windows (avoids fcntl issues)
- ✅ Fast unit tests (~150 MB image)
- ✅ CI/CD pipelines

**Quick start:**
```powershell
# Windows
.\testing\docker-test.ps1

# Linux/macOS
./testing/docker-test.sh
```

### Integration Testing
**Files:**
- `Dockerfile.interactive` - Full image with debugging tools
- `docker-compose.test.yml` - Two-container network (Alice & Bob)
- `test_container.py` - Interactive test script
- `start-integration-test.ps1` - Automated setup

**Use for:**
- ✅ Testing communication between 2+ nodes
- ✅ Simulating network on Windows/macOS
- ✅ Manual testing and debugging

**Quick start:**
```powershell
.\testing\start-integration-test.ps1
```

---

## Key Differences

| Feature | Production | Unit Testing | Integration Testing |
|---------|-----------|--------------|---------------------|
| **Base Image** | Debian | Alpine | Debian |
| **Size** | ~1.2 GB | ~150 MB | ~1.3 GB |
| **Networking** | Host mode | N/A | Bridge network |
| **Purpose** | Real deployment | pytest | Multi-node testing |
| **Platform** | Linux only | Windows/Linux | Windows/Linux |
| **GUI** | ✅ Yes | ❌ No | ⚠️ Optional |

---

## See Also

- **Testing guides:** `../docs/testing/`
- **Docker documentation:** `../docs/docker/`
- **Project structure:** `../PROJECT_STRUCTURE.md`
