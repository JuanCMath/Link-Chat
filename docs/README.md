# Documentation Directory

All Link-Chat documentation organized by category.

---

## Structure

```
docs/
├── testing/          # Testing guides and strategies
├── docker/           # Docker deployment and usage
└── development/      # Development and architecture docs
```

---

## Quick Navigation

### Testing Documentation (`testing/`)
- `TESTING_GUIDE.md` - Complete testing guide
- `TESTING_STRATEGY.md` - Testing approach and details
- `INTEGRATION_TESTING.md` - Multi-container testing
- `QUICK_TEST_README.md` - Quick unit test reference
- `QUICK_INTEGRATION_TEST.md` - Quick integration test reference

### Docker Documentation (`docker/`)
- `DOCKER_DEPLOYMENT_GUIDE.md` - Production deployment
- `DOCKER_QUICKREF.md` - Quick command reference
- `DOCKER_CHALLENGES.md` - Known issues and solutions
- `DOCKER_MAC_ACCESS.md` - Technical: MAC address access

### Development Documentation (`development/`)
- `REFACTORING_SUMMARY.md` - Recent refactoring details
- `INTEGRATION_SUMMARY.md` - ⚠️ DEPRECATED (old architecture)

---

## Recommended Reading Order

### For New Developers
1. `../README.md` (if exists) or `../QUICK_START_GUIDE.md`
2. `development/REFACTORING_SUMMARY.md`
3. `testing/TESTING_GUIDE.md`

### For Testing
1. `testing/QUICK_TEST_README.md`
2. `testing/TESTING_GUIDE.md` (if needed)

### For Deployment
1. `docker/DOCKER_QUICKREF.md`
2. `docker/DOCKER_DEPLOYMENT_GUIDE.md`

### For Debugging
1. `docker/DOCKER_CHALLENGES.md`
2. `testing/INTEGRATION_TESTING.md`

---

## Documentation Categories

**User Guides** (How to use)
- All `QUICK_*.md` files
- `DOCKER_QUICKREF.md`

**Technical Guides** (How it works)
- `DOCKER_MAC_ACCESS.md`
- `development/REFACTORING_SUMMARY.md`

**Reference** (Complete information)
- `TESTING_GUIDE.md`
- `DOCKER_DEPLOYMENT_GUIDE.md`

**Troubleshooting**
- `DOCKER_CHALLENGES.md`
- Testing guides have troubleshooting sections
