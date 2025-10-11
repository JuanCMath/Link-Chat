# Testing Docker Configuration

Test Link-Chat on Windows/macOS without physical hardware requirements.

---

## Files Overview

### Unit Testing
- `Dockerfile.test` - Alpine Linux with pytest
- `docker-test.ps1` - Windows test runner
- `docker-test.sh` - Linux/macOS test runner

### Integration Testing
- `Dockerfile.interactive` - Full image with debugging tools
- `docker-compose.test.yml` - Two-container network simulation
- `test_container.py` - Interactive test script
- `start-integration-test.ps1` - Automated setup

---

## Unit Testing

**Purpose:** Run pytest in Linux environment (Windows can't run tests natively due to fcntl)

### Quick Start

**Windows:**
```powershell
.\docker-test.ps1
```

**Linux/macOS:**
```bash
./docker-test.sh
```

### What it does
1. Builds Alpine Linux image with pytest
2. Runs all tests in `tests/` directory
3. Shows results

**Expected output:**
```
======================== 31 passed in 1.23s =========================
✅ All tests passed in Linux environment!
```

---

## Integration Testing

**Purpose:** Test communication between two Link-Chat instances

### Quick Start

```powershell
.\start-integration-test.ps1
```

This creates two containers:
- **Alice** (172.20.0.10)
- **Bob** (172.20.0.11)

### Manual Testing

1. **Open Alice's shell:**
   ```powershell
   docker exec -it linkchat-alice python /app/test_container.py
   ```

2. **Open Bob's shell (in another terminal):**
   ```powershell
   docker exec -it linkchat-bob python /app/test_container.py
   ```

3. **Send message from Alice to Bob:**
   ```
   Alice> 1                      # Send message
   Alice> 02:42:ac:14:00:0b     # Bob's MAC
   Alice> Hello Bob!
   
   Bob> 📨 Message from 02:42:ac:14:00:0a: Hello Bob!
   ```

### Cleanup

```powershell
docker-compose -f docker-compose.test.yml down
```

---

## Key Differences

| File | Purpose | Image Size | Use Case |
|------|---------|------------|----------|
| `Dockerfile.test` | Unit tests | ~150 MB | Quick pytest runs |
| `Dockerfile.interactive` | Integration tests | ~1.3 GB | Multi-container testing |

---

## See Also

- **Testing guide:** `../../docs/testing/TESTING_GUIDE.md`
- **Integration testing:** `../../docs/testing/INTEGRATION_TESTING.md`
- **Quick references:** `../../docs/testing/QUICK_*.md`
