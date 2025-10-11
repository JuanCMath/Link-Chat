# Link-Chat Project Structure

## 📁 Directory Organization

This document explains the organized structure of the Link-Chat project.

---

## Root Directory Structure

```
Link-Chat/
├── linkchat/               # Source code
│   ├── app/               # GUI application
│   ├── link/              # Link layer protocol implementation
│   └── backend.py         # Main backend controller
│
├── tests/                 # Unit tests
│   ├── test_file_transfer.py
│   ├── test_message_protocol.py
│   ├── test_transfer_metadata.py
│   └── test_transfer_reliability.py
│
├── docker/                # 🐳 Docker configurations
│   ├── production/       # Production deployment
│   └── testing/          # Development & testing
│
├── docs/                  # 📚 Documentation
│   ├── testing/          # Testing guides
│   ├── docker/           # Docker guides
│   └── development/      # Development docs
│
├── Req/                   # Requirements & specifications
├── pyproject.toml         # Python project configuration
└── uv.lock               # Dependency lockfile
```

---

## 🐳 Docker Directory (`docker/`)

### `docker/production/`
**Purpose:** Deployment in real environments (Linux hosts, physical networks)

| File | Description | Use Case |
|------|-------------|----------|
| `Dockerfile` | Production image with PyQt6 | Deploy on Linux with GUI |
| `docker-compose.yml` | Host networking setup | Single node on physical interface |
| `docker-run.sh` | Quick start script | Launch production container |

**When to use:**
- ✅ Running on actual Linux hardware
- ✅ Accessing physical network interfaces (eth0, wlan0)
- ✅ Production deployment with GUI

### `docker/testing/`
**Purpose:** Testing and development on Windows/macOS

| File | Description | Use Case |
|------|-------------|----------|
| `Dockerfile.test` | Unit testing (Alpine Linux) | Run pytest in Linux environment |
| `Dockerfile.interactive` | Integration testing with tools | Multi-container communication tests |
| `docker-compose.test.yml` | Two-node network simulation | Test Alice ↔ Bob communication |
| `test_container.py` | Interactive test script | Manual testing inside containers |
| `docker-test.ps1` | Windows unit test runner | Run unit tests on Windows |
| `docker-test.sh` | Linux/macOS unit test runner | Run unit tests on Unix |
| `start-integration-test.ps1` | Windows integration test setup | Test communication on Windows |

**When to use:**
- ✅ Unit testing on Windows (no fcntl module)
- ✅ Integration testing (2+ containers)
- ✅ Development and debugging

---

## 📚 Documentation Directory (`docs/`)

### `docs/testing/`
**Testing Documentation**

| File | Description |
|------|-------------|
| `TESTING_GUIDE.md` | Complete testing documentation |
| `TESTING_STRATEGY.md` | Testing strategy and implementation details |
| `QUICK_TEST_README.md` | Quick reference for unit tests |
| `INTEGRATION_TESTING.md` | Multi-container integration testing guide |
| `QUICK_INTEGRATION_TEST.md` | Quick start for integration tests |

### `docs/docker/`
**Docker Documentation**

| File | Description |
|------|-------------|
| `DOCKER_DEPLOYMENT_GUIDE.md` | Production deployment guide |
| `DOCKER_QUICKREF.md` | Quick reference for Docker commands |
| `DOCKER_CHALLENGES.md` | Known issues and solutions |
| `DOCKER_MAC_ACCESS.md` | Technical: How code accesses Docker MACs |

### `docs/development/`
**Development Documentation**

| File | Description |
|------|-------------|
| `REFACTORING_SUMMARY.md` | Module refactoring documentation |
| `INTEGRATION_SUMMARY.md` | ⚠️ DEPRECATED - Old architecture |

**Other Documentation** (kept in root for visibility):
- `IMPLEMENTATION_PLAN.md` - Feature implementation status
- `PEER_DISCOVERY_PROPOSAL.md` - Peer discovery design
- `GUI_INTEGRATION_GUIDE.md` - GUI integration guide
- `QUICK_START_GUIDE.md` - General quick start
- `LAYER2_PURITY.md` - Layer 2 design principles

---

## Quick Start

### 1. Unit Testing (Windows)
```powershell
.\docker\testing\docker-test.ps1
```

### 2. Integration Testing (Windows)
```powershell
.\docker\testing\start-integration-test.ps1
```

### 3. Production Deployment (Linux)
```bash
cd docker/production
./docker-run.sh
```

---

## File Categories

### Docker Files
- **Production:** `docker/production/*`
- **Testing:** `docker/testing/*`

### Documentation
- **Testing:** `docs/testing/*`
- **Docker:** `docs/docker/*`
- **Development:** `docs/development/*`
- **General:** Root `*.md` files

### Source Code
- **Application:** `linkchat/`
- **Tests:** `tests/`

---

## Navigation Guide

**I want to...**

| Goal | Go to |
|------|-------|
| Run unit tests | `docker/testing/` → Run `docker-test.ps1` |
| Test communication | `docker/testing/` → Run `start-integration-test.ps1` |
| Deploy to production | `docker/production/` → Run `docker-run.sh` |
| Learn about testing | `docs/testing/TESTING_GUIDE.md` |
| Learn about Docker | `docs/docker/DOCKER_DEPLOYMENT_GUIDE.md` |
| Understand refactoring | `docs/development/REFACTORING_SUMMARY.md` |
| See development history | `docs/development/` |

---

## Summary

**Before reorganization:** 20+ files scattered in root directory  
**After reorganization:** Clean structure with 3 main directories

✅ **docker/** - All Docker configurations  
✅ **docs/** - All documentation  
✅ **Clear separation** - Production vs Testing vs Development

**Everything is now organized by purpose and use case!**
