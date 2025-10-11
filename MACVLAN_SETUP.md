# MACVLAN Networking Setup for Link-Chat

## What is MACVLAN?

MACVLAN is a Docker network driver that assigns each container its own **unique MAC address** on the physical network. This makes containers appear as separate physical devices on your network, enabling true **Layer 2 communication**.

### Why MACVLAN for Link-Chat?

Link-Chat is a **pure Layer 2 application**:
- ✅ Uses **MAC addresses only** (no IP addresses)
- ✅ Sends raw Ethernet frames with custom EtherType
- ✅ Requires **AF_PACKET raw sockets**
- ✅ Needs direct access to network hardware

**MACVLAN Solution:**
- Each container gets a unique MAC address
- Containers appear as physical devices on the network
- IP addresses are assigned **only for Docker's management** (Link-Chat ignores them)
- Enables Layer 2 communication between:
  - Container ↔ Container
  - Container ↔ Physical PCs on the same network

---

## Prerequisites

### Platform Requirements

| Platform | Support | Notes |
|----------|---------|-------|
| **Linux (native)** | ✅ Full support | Best performance, direct hardware access |
| **Windows WSL2** | ✅ Supported | Run all commands inside WSL2 |
| **Docker Desktop (Windows/Mac)** | ⚠️ Limited | VM isolation blocks raw packets |

### Network Requirements

- **Physical network access** (Ethernet or WiFi)
- **Network administrator privileges** (to create MACVLAN network)
- **Same network segment** for all communicating devices
- ⚠️ Some WiFi networks may block MACVLAN (due to MAC filtering)

---

## Quick Start

### 1. Setup MACVLAN Network (One-Time)

**On Linux:**
```bash
cd /path/to/Link-Chat
./docker/setup-macvlan.sh
```

**On Windows (from PowerShell):**
```powershell
cd D:\path\to\Link-Chat
.\docker\setup-macvlan.ps1
```

This script will:
- Auto-detect your active network interface (eth0, wlan0, etc.)
- Detect gateway and subnet
- Create Docker network named `linkchat-macvlan`
- Reserve IP range `.100-.107` for containers (Docker management only)

**Example Output:**
```
🌐 Creating MACVLAN network for Link-Chat (Layer 2 Chat)...

Detected network configuration:
  Interface: eth0
  Gateway: 192.168.1.1
  Subnet: 192.168.1.0/24
  Container IP Range: 192.168.1.100-192.168.1.107

⚠️  IMPORTANT: IPs are for Docker management only!
    Link-Chat operates at Layer 2 using MAC addresses.

Creating MACVLAN network...
✅ MACVLAN network 'linkchat-macvlan' created successfully!
```

### 2. Run Single Container

**On Linux:**
```bash
./docker/run-macvlan.sh
```

**On Windows (from PowerShell):**
```powershell
.\docker\run-macvlan.ps1
```

This will:
- Build the Docker image if needed
- Start Link-Chat GUI with MACVLAN networking
- Display the container's MAC address
- Set up X11 forwarding for GUI

**Example Output:**
```
🌐 Starting Link-Chat with MACVLAN networking...

📧 Container MAC Address: aa:bb:cc:dd:ee:ff

✅ Link-Chat is running!
   Use interface: eth0
   Layer 2 communication enabled
```

### 3. Run Multiple Containers (Testing)

To test Layer 2 communication between containers:

```bash
docker-compose -f docker-compose.macvlan.yml up
```

This starts **3 Link-Chat instances**, each with:
- Unique MAC address
- Separate GUI window
- Ability to communicate via Layer 2

**Shutdown:**
```bash
docker-compose -f docker-compose.macvlan.yml down
```

---

## Using Link-Chat with MACVLAN

### In the GUI

1. **Select Interface:** Choose `eth0` (this is your MACVLAN interface)
2. **Start Backend:** Click "Iniciar Backend"
3. **Check MAC Address:** Your container's MAC is shown in terminal output
4. **Send Messages:** Use destination MAC addresses to communicate

### Finding MAC Addresses

**Inside container:**
```bash
cat /sys/class/net/eth0/address
```

**From host:**
```bash
docker network inspect linkchat-macvlan
```

**Other physical PCs:**
```bash
ip link show        # Linux
ipconfig /all       # Windows
ifconfig            # macOS
```

---

## Architecture

### How MACVLAN Works

```
Physical Network (192.168.1.0/24)
│
├── Router/Gateway (192.168.1.1)
│   └── MAC: aa:aa:aa:aa:aa:aa
│
├── Host PC (192.168.1.50)
│   └── MAC: bb:bb:bb:bb:bb:bb
│
├── Container 1 via MACVLAN
│   ├── IP: 192.168.1.100 (Docker management only)
│   └── MAC: cc:cc:cc:cc:cc:cc ← Link-Chat uses this!
│
├── Container 2 via MACVLAN
│   ├── IP: 192.168.1.101 (Docker management only)
│   └── MAC: dd:dd:dd:dd:dd:dd ← Link-Chat uses this!
│
└── External PC (192.168.1.75)
    └── MAC: ee:ee:ee:ee:ee:ee
```

### Layer 2 vs Layer 3

| Aspect | Link-Chat (Layer 2) | Traditional Apps (Layer 3) |
|--------|---------------------|---------------------------|
| **Addressing** | MAC addresses | IP addresses |
| **Protocol** | Custom EtherType | TCP/UDP/IP |
| **Routing** | Same network segment only | Can route across networks |
| **Docker Networking** | Needs MACVLAN or host mode | Works with bridge mode |

**Key Point:** The IP addresses assigned to MACVLAN containers are **irrelevant to Link-Chat**. They exist only so Docker can manage the network. Link-Chat sends Ethernet frames directly using MAC addresses.

---

## Troubleshooting

### ❌ "Network linkchat-macvlan not found"

**Solution:** Run the setup script first:
```bash
./docker/setup-macvlan.sh
```

### ❌ Container can't connect to other containers

**Check 1:** Are they on the same MACVLAN network?
```bash
docker network inspect linkchat-macvlan
```

**Check 2:** Are you using the correct interface (`eth0`)?

**Check 3:** Are you using MAC addresses (not IP addresses)?

### ❌ Can't communicate with external PCs

**Check 1:** Is the external PC on the same network segment?
```bash
ping 192.168.1.75  # Test connectivity
```

**Check 2:** Is firewall blocking raw packets on external PC?

**Check 3:** If using WiFi, does the access point allow multiple MACs per device?
- Some WiFi networks block MACVLAN due to security policies
- Try Ethernet connection instead
- Or configure AP to allow MAC spoofing/multiple MACs

### ❌ "Operation not permitted" when creating network

**Solution:** Need sudo/admin privileges:
```bash
sudo ./docker/setup-macvlan.sh
```

### ⚠️ GUI doesn't appear

**Check 1:** Is X11 forwarding configured?
```bash
# On Windows: Start VcXsrv with -multiwindow -ac
```

**Check 2:** Is DISPLAY set correctly?
```bash
echo $DISPLAY  # Should show something like :0 or host.docker.internal:0
```

**Solution:** Set QT platform explicitly:
```bash
export QT_QPA_PLATFORM=xcb
```

### ⚠️ WiFi Not Working

**Problem:** Many WiFi access points block MACVLAN due to:
- MAC address filtering
- Client isolation mode
- Security policies preventing MAC spoofing

**Solutions:**
1. **Use Ethernet connection** (recommended)
2. Configure WiFi AP to allow multiple MACs per client
3. Disable "client isolation" on WiFi router
4. Use `--network host` mode (Linux only, loses container isolation)

---

## Advanced Configuration

### Custom Network Settings

Edit `docker/setup-macvlan.sh` to customize:

```bash
# Use specific interface
IFACE="wlan0"

# Custom IP range (Docker management only)
IP_RANGE="192.168.1.200/29"  # .200-.207

# Custom subnet
SUBNET="192.168.1.0/24"
GW="192.168.1.1"
```

### Static MAC Addresses

In `docker-compose.macvlan.yml`, you can assign specific MACs:

```yaml
services:
  linkchat1:
    networks:
      linkchat-macvlan:
        mac_address: 02:42:ac:11:00:02
```

### Multiple Physical Interfaces

If you have both Ethernet and WiFi, create separate networks:

```bash
# Ethernet MACVLAN
docker network create -d macvlan \
  --subnet=192.168.1.0/24 \
  --gateway=192.168.1.1 \
  --ip-range=192.168.1.100/29 \
  -o parent=eth0 \
  linkchat-eth

# WiFi MACVLAN (if supported)
docker network create -d macvlan \
  --subnet=192.168.1.0/24 \
  --gateway=192.168.1.1 \
  --ip-range=192.168.1.110/29 \
  -o parent=wlan0 \
  linkchat-wifi
```

---

## Platform-Specific Notes

### Linux Native

✅ **Best platform for MACVLAN**
- Direct hardware access
- No virtualization overhead
- Full raw packet support

**Run commands directly:**
```bash
./docker/setup-macvlan.sh
./docker/run-macvlan.sh
```

### Windows WSL2

✅ **Fully supported**
- WSL2 runs real Linux kernel
- Can access network hardware
- MACVLAN works normally

**Important:** Always run inside WSL2, not Windows PowerShell:
```powershell
# From Windows PowerShell
wsl

# Inside WSL2
cd /mnt/d/path/to/Link-Chat
./docker/setup-macvlan.sh
./docker/run-macvlan.sh
```

**PowerShell Wrappers:** The `.ps1` scripts automatically delegate to WSL2.

### Docker Desktop (Windows/Mac)

⚠️ **Limited Support**

**Problem:** Docker Desktop runs containers inside a VM:
```
Windows/Mac Host → VM (Docker Desktop) → Container
```

This virtualization layer blocks raw packet access.

**Solutions:**
1. **Use WSL2 Docker** (Windows only) - Bypass Docker Desktop
2. **Use Linux VM** (both platforms) - Run Docker in VirtualBox/VMware
3. **Develop on Linux host** (best option)

---

## Security Considerations

### Network Exposure

⚠️ MACVLAN containers are **directly exposed** on the physical network:
- They appear as real devices to routers, firewalls, and network admins
- No NAT protection from Docker bridge
- Same security requirements as physical machines

**Best Practices:**
- Use MACVLAN only on **trusted networks** (home, lab, private networks)
- Avoid on **public WiFi** or untrusted networks
- Consider firewall rules for production deployments
- Limit IP range to minimum needed containers

### Capabilities

The containers run with:
- `CAP_NET_ADMIN` - Manage network configuration
- `CAP_NET_RAW` - Create raw sockets (AF_PACKET)

These are **required** for Link-Chat's Layer 2 operation.

---

## Environment Detection

Link-Chat includes automatic environment detection:

```bash
# Check your environment
python -m linkchat.env_check
```

**Example Output with MACVLAN:**
```
======================================================================
Link-Chat Network Environment Check
======================================================================

Platform: Linux 5.15.0
Running in Docker: True
Running in WSL: True
Using MACVLAN: True
AF_PACKET available: True

🐳 DOCKER CONTAINER DETECTED

🌐 MACVLAN NETWORKING ACTIVE

📧 Container MAC Address: 02:42:ac:11:00:02

✅ Layer 2 Operation Ready!

Your container has a unique MAC address on the physical network.
Link-Chat will communicate using Ethernet frames (Layer 2).

🔍 Key Points:
  • Use interface 'eth0' in Link-Chat GUI
  • IP addresses are for Docker management only
  • Link-Chat operates purely at Layer 2 (MAC addresses)
  • You can communicate with:
    - Other containers on the same MACVLAN network
    - Physical machines on the same network segment
```

---

## Comparison with Alternatives

| Solution | Layer 2 Access | Container Isolation | Cross-Platform | GUI Support |
|----------|----------------|---------------------|----------------|-------------|
| **MACVLAN** | ✅ Full | ✅ Yes | ✅ Linux/WSL2 | ✅ Yes |
| **--network host** | ✅ Full | ❌ No (shares host network) | ❌ Linux only | ✅ Yes |
| **Bridge mode** | ❌ No | ✅ Yes | ✅ All platforms | ✅ Yes |
| **Native WSL2** | ✅ Full | ⚠️ Limited | ✅ Windows only | ⚠️ X11 needed |

**Recommendation:** MACVLAN is the best balance of isolation, functionality, and portability.

---

## References

- [Docker MACVLAN Documentation](https://docs.docker.com/network/macvlan/)
- [AF_PACKET Sockets](https://man7.org/linux/man-pages/man7/packet.7.html)
- [Link-Chat Architecture](./README.md)

---

## Quick Reference

### Essential Commands

```bash
# One-time setup
./docker/setup-macvlan.sh

# Run single container
./docker/run-macvlan.sh

# Run multiple containers
docker-compose -f docker-compose.macvlan.yml up

# Check environment
python -m linkchat.env_check

# Get container MAC
cat /sys/class/net/eth0/address

# Inspect network
docker network inspect linkchat-macvlan

# Remove network
docker network rm linkchat-macvlan
```

### In Link-Chat GUI

1. Interface: **eth0**
2. Backend: Click **"Iniciar Backend"**
3. Destination: Use **MAC addresses** (e.g., `aa:bb:cc:dd:ee:ff`)

---

**Remember:** Link-Chat is **Layer 2 only**. IP addresses shown in Docker are irrelevant. Always use MAC addresses for communication! 🚀
