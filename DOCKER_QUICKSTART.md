# Link-Chat Docker Quick Start

Get Link-Chat running in Docker with MACVLAN networking in **3 steps**.

---

## Prerequisites

- ✅ Docker installed
- ✅ Linux or Windows WSL2
- ✅ X11 server running (VcXsrv on Windows)
- ✅ Physical network access (Ethernet or WiFi)

---

## Step 1: One-Time Setup

**On Linux:**
```bash
cd /path/to/Link-Chat
./docker/setup-macvlan.sh
```

**On Windows:**
```powershell
# From PowerShell
wsl

# Inside WSL2
cd /mnt/d/UH/Año\ 3/Redes/Link-Chat
./docker/setup-macvlan.sh
```

**Or use PowerShell wrapper:**
```powershell
.\docker\setup-macvlan.ps1
```

This creates a Docker MACVLAN network that gives each container a unique MAC address on your physical network.

---

## Step 2: Start Link-Chat

**On Linux:**
```bash
./docker/run-macvlan.sh
```

**On Windows (from WSL2):**
```bash
./docker/run-macvlan.sh
```

**Or use PowerShell wrapper:**
```powershell
.\docker\run-macvlan.ps1
```

**Expected Output:**
```
🌐 Starting Link-Chat with MACVLAN networking...

📧 Container MAC Address: aa:bb:cc:dd:ee:ff

✅ Link-Chat is running!
   Use interface: eth0
   Layer 2 communication enabled
```

---

## Step 3: Use Link-Chat

1. **GUI opens automatically**
2. **Select interface:** `eth0`
3. **Click:** "Iniciar Backend"
4. **Note your MAC address** (shown in terminal)
5. **Start chatting!** Use destination MAC addresses

---

## Testing with Multiple Containers

To test Layer 2 communication between containers:

```bash
docker-compose -f docker-compose.macvlan.yml up
```

This starts **3 Link-Chat instances** you can test with.

**Shutdown:**
```bash
docker-compose -f docker-compose.macvlan.yml down
```

---

## Troubleshooting

### GUI doesn't appear

**On Windows:** Make sure VcXsrv is running:
```powershell
# Start VcXsrv with these options:
# -multiwindow -ac
```

### "Network linkchat-macvlan not found"

Run setup first:
```bash
./docker/setup-macvlan.sh
```

### Can't connect to other devices

1. **Check you're using `eth0` interface** (not wlan0, not enp0s3)
2. **Use MAC addresses**, not IP addresses
3. **Ensure devices are on same network segment**
4. **If using WiFi**: Some access points block MACVLAN - try Ethernet instead

### Check your environment

```bash
# Inside container
python -m linkchat.env_check
```

---

## Understanding MACVLAN

Link-Chat is a **Layer 2 application** (uses MAC addresses only).

**MACVLAN gives each container:**
- ✅ Unique MAC address on physical network
- ✅ Direct Layer 2 access for raw Ethernet frames
- ✅ Ability to communicate with other containers AND physical PCs

**IP addresses shown in Docker are for management only** - Link-Chat ignores them!

---

## Full Documentation

For detailed information, see:
- [`MACVLAN_SETUP.md`](./MACVLAN_SETUP.md) - Complete MACVLAN guide
- [`README.md`](./README.md) - Project overview

---

## Quick Commands Reference

```bash
# Setup (once)
./docker/setup-macvlan.sh

# Run single container
./docker/run-macvlan.sh

# Run 3 containers for testing
docker-compose -f docker-compose.macvlan.yml up

# Check environment
python -m linkchat.env_check

# Get your MAC address
cat /sys/class/net/eth0/address

# Clean up
docker-compose -f docker-compose.macvlan.yml down
docker network rm linkchat-macvlan
```

---

**Happy chatting at Layer 2! 🚀**
