# 📁 Link-Chat - File Organization Index

All files have been organized into logical directories. Use this index to find what you need.

---

## 🗂️ Project Structure

```
Link-Chat/
├── 📦 linkchat/              Source code
├── 🧪 tests/                 Unit tests  
├── 🐳 docker/                Docker configurations
│   ├── production/          Production deployment
│   └── testing/             Development & testing
├── 📚 docs/                  Documentation
│   ├── testing/             Testing guides
│   ├── docker/              Docker guides
│   └── development/         Architecture docs
└── 📋 Req/                   Requirements
```

---

## 🎯 Quick Access

### I want to...

| Goal | Location | File |
|------|----------|------|
| **Run unit tests** | `docker/testing/` | `docker-test.ps1` |
| **Test communication** | `docker/testing/` | `start-integration-test.ps1` |
| **Deploy to production** | `docker/production/` | `docker-run.sh` |
| **Learn testing** | `docs/testing/` | `TESTING_GUIDE.md` |
| **Learn Docker** | `docs/docker/` | `DOCKER_DEPLOYMENT_GUIDE.md` |
| **Understand code** | `docs/development/` | `REFACTORING_SUMMARY.md` |

---

## 📂 Directory Details

### `docker/` - All Docker Files

**Production Deployment:**
- `docker/production/Dockerfile` - Production image
- `docker/production/docker-compose.yml` - Host networking setup
- `docker/production/docker-run.sh` - Quick start script

**Testing & Development:**
- `docker/testing/Dockerfile.test` - Unit testing (Alpine)
- `docker/testing/Dockerfile.interactive` - Integration testing (Debian)
- `docker/testing/docker-compose.test.yml` - Two-container network
- `docker/testing/test_container.py` - Interactive test script
- `docker/testing/docker-test.ps1` - Windows unit test runner
- `docker/testing/start-integration-test.ps1` - Integration test setup

### `docs/` - All Documentation

**Testing Documentation:**
- `docs/testing/TESTING_GUIDE.md` - Complete testing guide
- `docs/testing/TESTING_STRATEGY.md` - Implementation details
- `docs/testing/INTEGRATION_TESTING.md` - Multi-container testing
- `docs/testing/QUICK_TEST_README.md` - Quick unit test reference
- `docs/testing/QUICK_INTEGRATION_TEST.md` - Quick integration reference

**Docker Documentation:**
- `docs/docker/DOCKER_DEPLOYMENT_GUIDE.md` - Production deployment
- `docs/docker/DOCKER_QUICKREF.md` - Quick command reference
- `docs/docker/DOCKER_CHALLENGES.md` - Known issues & solutions
- `docs/docker/DOCKER_MAC_ACCESS.md` - Technical: MAC address access

**Development Documentation:**
- `docs/development/REFACTORING_SUMMARY.md` - Recent refactoring
- `docs/development/INTEGRATION_SUMMARY.md` - ⚠️ DEPRECATED

---

## 🚀 Quick Commands

### Unit Testing (Windows)
```powershell
.\docker\testing\docker-test.ps1
```

### Integration Testing (Windows)
```powershell
.\docker\testing\start-integration-test.ps1
```

### Production (Linux)
```bash
cd docker/production
./docker-run.sh
```

---

## 📖 Documentation Map

```
docs/
├── testing/
│   ├── TESTING_GUIDE.md              ⭐ Start here for testing
│   ├── QUICK_TEST_README.md          Quick unit test reference
│   ├── INTEGRATION_TESTING.md        Multi-container testing
│   ├── QUICK_INTEGRATION_TEST.md     Quick integration reference
│   └── TESTING_STRATEGY.md           Implementation details
│
├── docker/
│   ├── DOCKER_QUICKREF.md            ⭐ Start here for Docker
│   ├── DOCKER_DEPLOYMENT_GUIDE.md    Complete deployment guide
│   ├── DOCKER_MAC_ACCESS.md          Technical deep-dive
│   └── DOCKER_CHALLENGES.md          Troubleshooting
│
└── development/
    ├── REFACTORING_SUMMARY.md        ⭐ Recent code changes
    └── INTEGRATION_SUMMARY.md        DEPRECATED - old docs
```

---

## 🎓 Learning Path

### New to the Project?
1. Read `PROJECT_STRUCTURE.md` (this file)
2. Read `docs/development/REFACTORING_SUMMARY.md`
3. Read `docs/testing/QUICK_TEST_README.md`

### Need to Test?
1. Read `docs/testing/QUICK_TEST_README.md`
2. Run `docker/testing/docker-test.ps1`

### Need to Deploy?
1. Read `docs/docker/DOCKER_QUICKREF.md`
2. Follow `docs/docker/DOCKER_DEPLOYMENT_GUIDE.md`

### Debugging Issues?
1. Check `docs/docker/DOCKER_CHALLENGES.md`
2. Check testing guides for troubleshooting sections

---

## 📝 Root Directory Files (Kept for Visibility)

These important docs remain in the root:
- `PROJECT_STRUCTURE.md` - This file
- `IMPLEMENTATION_PLAN.md` - Feature status
- `PEER_DISCOVERY_PROPOSAL.md` - Peer discovery design
- `GUI_INTEGRATION_GUIDE.md` - GUI integration
- `QUICK_START_GUIDE.md` - General quick start
- `LAYER2_PURITY.md` - Design principles
- `pyproject.toml` - Python configuration
- `uv.lock` - Dependencies

---

## ✅ Organization Benefits

**Before:**
- ❌ 20+ files in root directory
- ❌ Hard to find what you need
- ❌ Unclear which Docker file for what purpose

**After:**
- ✅ Clear directory structure
- ✅ Files grouped by purpose
- ✅ Easy navigation with READMEs
- ✅ Separate production vs testing
- ✅ Documentation categorized

---

## 🆘 Still Lost?

**Find a file:**
1. Check this index
2. Check `docker/README.md` for Docker files
3. Check `docs/README.md` for documentation

**Not sure what to read:**
- Quick reference → Any `QUICK_*.md` file
- Complete guide → Any file without QUICK
- Troubleshooting → `*_CHALLENGES.md` or `*_GUIDE.md`

**Everything is now organized and documented!** 🎉
