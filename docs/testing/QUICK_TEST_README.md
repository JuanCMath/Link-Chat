# Quick Test Reference

## TL;DR - Run Tests Now

```powershell
# 1. Start Docker Desktop (check system tray)

# 2. Run this command
.\docker-test.ps1
```

**Expected result:** `✅ All tests passed in Linux environment!`

---

## What Was Added

- ✅ `Dockerfile.test` - Alpine Linux test container
- ✅ `docker-test.ps1` - Windows test runner
- ✅ `docker-test.sh` - Linux/macOS test runner  
- ✅ `tests/test_transfer_metadata.py` - 17 tests for metadata module
- ✅ `tests/test_transfer_reliability.py` - 8 tests for reliability module
- ✅ Updated `tests/test_file_transfer.py` - Fixed for new architecture

**Total:** 31 unit tests

---

## Manual Docker Commands

```powershell
# Build test image
docker build -f Dockerfile.test -t linkchat-test .

# Run all tests
docker run --rm linkchat-test

# Run specific test file
docker run --rm linkchat-test pytest tests/test_transfer_metadata.py -v
```

---

## Why Docker?

**Problem:** Link-Chat uses Linux-only `fcntl` module  
**Solution:** Docker provides real Linux environment on Windows  
**Benefit:** Tests run in Alpine Linux (~150 MB image)

---

## Troubleshooting

**Docker not running:**
```
ERROR: ... cannot find the file specified
```
→ Start Docker Desktop from Start Menu

**Tests fail:**
```
❌ Tests failed!
```
→ Check error output, may need code fixes

**Build too slow:**
```powershell
docker system prune -a  # Clean cache
```

---

## Full Documentation

- **TESTING_GUIDE.md** - Complete testing documentation
- **TESTING_STRATEGY.md** - Strategy and implementation details
