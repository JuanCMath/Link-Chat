# MAC Address Access in Docker Containers - Technical Analysis

## TL;DR - YES! Your code can access Docker's MAC addresses ✅

**Short answer:** Your code **automatically detects and uses** the MAC address that Docker assigns to each container. No configuration needed!

---

## How It Works

### Docker's Virtual Network Interfaces

When Docker creates a container with a bridge network, it:

1. ✅ Creates a **virtual Ethernet interface** (`eth0`) inside the container
2. ✅ Assigns a **unique MAC address** to that interface
3. ✅ Makes it accessible via **standard Linux networking APIs**

**Example Docker-assigned MAC:**
```
Container: alice
Interface: eth0
MAC: 02:42:ac:14:00:0a
      ^^    ^^^^^^^^^^^^
      │     └─ Derived from IP (172.20.0.10)
      └─ Docker prefix (02:42)
```

**Docker's MAC format:**
- Prefix: `02:42` (Docker's OUI - Organizationally Unique Identifier)
- Rest: Derived from container's IP address
- **Unique per container** ✅
- **Valid Layer 2 address** ✅

---

## Your Code's MAC Detection

Your code **automatically retrieves** the MAC address using Linux system calls. Here's the flow:

### 1. Initialization Chain

```python
# When you start the backend
backend = LinkChatBackend(interface="eth0")  # Docker's virtual interface
backend.start()

# This creates:
LinkLayer(iface="eth0")
  └─> AFPacketMediumEthWifi(iface="eth0")
       └─> _query_hwaddr()  # Gets MAC from Linux
            └─> Reads /sys/class/net/eth0/address
                 └─> Returns Docker's MAC: 02:42:ac:14:00:0a
```

### 2. MAC Retrieval Method

**File:** `linkchat/link/af_packet_medium_eth_wifi.py` (Lines 289-318)

```python
def _query_hwaddr(self) -> Tuple[bytes, int]:
    """Query the interface's hardware address via sysfs."""
    
    # Read MAC address from sysfs
    mac_path = f"/sys/class/net/{self.iface}/address"
    with open(mac_path, "r") as f:
        mac_str = f.read().strip()  # "02:42:ac:14:00:0a"
    
    # Convert to bytes
    mac = bytes(int(part, 16) for part in mac_str.split(":"))
    # Result: b'\x02\x42\xac\x14\x00\x0a'
    
    return mac, hatype
```

**This works in Docker because:**
- ✅ `/sys/class/net/eth0/address` exists in container
- ✅ Contains Docker-assigned MAC address
- ✅ No special configuration needed
- ✅ Same code works on physical hardware and containers

### 3. Storage and Usage

```python
# Stored in multiple places for easy access
self.hwaddr = mac           # Raw bytes: b'\x02\x42...'
self.src_mac = self.hwaddr  # Alias for frame construction

# Accessible via LinkLayer
link_layer.mac  # Returns: b'\x02\x42\xac\x14\x00\x0a'

# Accessible via Backend
backend.local_mac      # Returns: b'\x02\x42\xac\x14\x00\x0a'
backend.local_mac_str  # Returns: "02:42:ac:14:00:0a"
```

---

## Real Example in Docker

### Container Startup

When you start a container:

```bash
docker run --network linkchat-net --ip 172.20.0.10 linkchat:latest
```

**What Docker does:**
1. Creates virtual `eth0` interface
2. Assigns IP: `172.20.0.10`
3. Generates MAC: `02:42:ac:14:00:0a` (derived from IP)
4. Exposes via `/sys/class/net/eth0/address`

### Your Code's Perspective

```python
# Inside container, your code runs:
medium = AFPacketMediumEthWifi(iface="eth0", ethertype=0x88B5)

# Automatically detects:
medium.src_mac
# => b'\x02\x42\xac\x14\x00\x0a'

medium.ifindex
# => 5 (kernel interface index)

medium.mtu
# => 1500 (Docker bridge MTU)
```

**Verification in container:**

```bash
# Inside container
ip link show eth0
# Output:
# 5: eth0@if6: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500
#     link/ether 02:42:ac:14:00:0a brd ff:ff:ff:ff:ff:ff

cat /sys/class/net/eth0/address
# Output: 02:42:ac:14:00:0a
```

---

## Frame Construction with Docker MACs

### Sending a Frame

When Alice sends to Bob:

```python
# Alice's container
alice_mac = b'\x02\x42\xac\x14\x00\x0a'  # Auto-detected
bob_mac   = b'\x02\x42\xac\x14\x00\x0b'  # Provided by user

# Frame construction (automatic)
header = bob_mac + alice_mac + struct.pack("!H", 0x88B5)
#        ^^^^^^     ^^^^^^^^^
#        dst        src (auto-detected!)
```

**Your code does this automatically:**
```python
# In af_packet_medium_eth_wifi.py, line 195
header = dst_mac + self.src_mac + struct.pack("!H", ethertype)
#                  ^^^^^^^^^^^^^
#                  Docker's MAC (auto-detected)
```

### Reception

When Bob receives:

```python
# Kernel delivers frame to container's eth0
# Frame has:
#   dst_mac = 02:42:ac:14:00:0b (Bob's MAC)
#   src_mac = 02:42:ac:14:00:0a (Alice's MAC)
#   ethertype = 0x88B5

# Your code parses it
dst, src, etype, payload = medium.recv_one()
# src = b'\x02\x42\xac\x14\x00\x0a'  ✅ Alice identified!
```

---

## Why It Works in Docker

### 1. **Virtual Network is Layer 2**

Docker bridge network operates at **Layer 2** (Data Link):
- ✅ Ethernet frames with MAC addresses
- ✅ ARP protocol works
- ✅ Broadcast/multicast supported
- ✅ **Your AF_PACKET sockets see real Ethernet frames**

### 2. **Virtual Interfaces are Real**

From container's perspective, `eth0` is a **real network interface**:
- ✅ Has `/sys/class/net/eth0/` sysfs entries
- ✅ Responds to `ioctl()` calls
- ✅ Supports `AF_PACKET` sockets
- ✅ Has unique MAC address

### 3. **No Code Changes Needed**

Your code uses **standard Linux APIs**:
- ✅ `socket.if_nametoindex("eth0")` → Works
- ✅ `open("/sys/class/net/eth0/address")` → Works
- ✅ `socket(AF_PACKET, SOCK_RAW, ...)` → Works
- ✅ All network operations → Work!

---

## Test Verification

### Get MAC from Running Container

**Method 1: Via test script**
```bash
docker exec -it linkchat-alice python /app/test_container.py

# Output shows:
# 📡 Interface: eth0
# 🏷️  MAC Address: 02:42:ac:14:00:0a
```

**Method 2: Direct query**
```bash
docker exec linkchat-alice ip link show eth0 | grep link/ether
# Output: link/ether 02:42:ac:14:00:0a brd ff:ff:ff:ff:ff:ff
```

**Method 3: From Python inside container**
```python
from linkchat.backend import LinkChatBackend

backend = LinkChatBackend(interface="eth0")
backend.start()

print(f"My MAC (bytes): {backend.local_mac}")
# Output: My MAC (bytes): b'\x02B\xac\x14\x00\n'

print(f"My MAC (string): {backend.local_mac_str}")
# Output: My MAC (string): 02:42:ac:14:00:0a
```

---

## Communication Between Containers

### Alice → Bob Message Flow

```
┌──────────────────────────────────────────────────┐
│ Alice Container (172.20.0.10)                   │
│                                                   │
│ 1. backend.send_message(bob_mac, "Hello")       │
│    ↓                                              │
│ 2. LinkLayer builds frame:                       │
│    dst: 02:42:ac:14:00:0b (Bob)                  │
│    src: 02:42:ac:14:00:0a (Alice - auto!)       │
│    ↓                                              │
│ 3. AF_PACKET socket sends to eth0               │
└────────────────┬──────────────────────────────────┘
                 │
                 │ Docker Bridge Network
                 │ (Layer 2 switching)
                 │
┌────────────────▼──────────────────────────────────┐
│ Bob Container (172.20.0.11)                      │
│                                                   │
│ 1. AF_PACKET socket receives from eth0          │
│    ↓                                              │
│ 2. Kernel delivers frame with:                   │
│    dst: 02:42:ac:14:00:0b (matches Bob's MAC)   │
│    src: 02:42:ac:14:00:0a (Alice's MAC)         │
│    ↓                                              │
│ 3. LinkLayer parses frame                        │
│    ↓                                              │
│ 4. Callback: on_message(alice_mac, "Hello")     │
└───────────────────────────────────────────────────┘
```

**Key points:**
- ✅ Alice's code **auto-detects** its MAC (`02:42:ac:14:00:0a`)
- ✅ Alice **manually specifies** Bob's MAC in send call
- ✅ Bob **receives** frame with Alice's MAC in `src` field
- ✅ Bob can **reply** using `src` as destination

---

## Practical Implications

### 1. **MAC Discovery**

Your code needs to know peer MACs. Two approaches:

**Manual (current):**
```python
# User provides Bob's MAC
bob_mac = bytes.fromhex("02:42:ac:14:00:0b")
backend.send_message(bob_mac, "Hello")
```

**Automatic (via peer discovery):**
```python
# PeerDiscoveryService broadcasts beacons
# Peers announce their MACs automatically
backend.on_peer_available = lambda peer: print(f"Found {peer.mac_str}")
```

### 2. **Container Identification**

Each container has unique MAC:
```python
# Alice: 02:42:ac:14:00:0a
# Bob:   02:42:ac:14:00:0b
# Charlie: 02:42:ac:14:00:0c
```

Allows your code to distinguish senders!

### 3. **No Configuration Needed**

Docker handles everything:
- ✅ MAC assignment (automatic)
- ✅ Interface creation (automatic)
- ✅ Layer 2 routing (automatic)
- ✅ Your code just works! (automatic)

---

## Summary

### Question: "Docker creates its own MAC address. Is my code capable of accessing it?"

### Answer: **YES! Perfectly capable! ✅**

**How your code accesses Docker's MAC:**

1. ✅ **Automatically** via `/sys/class/net/eth0/address`
2. ✅ **Standard Linux API** - same code for Docker and physical hardware
3. ✅ **No configuration needed** - works out of the box
4. ✅ **Stores in `self.src_mac`** - used for all frame construction
5. ✅ **Exposed via `backend.local_mac`** - accessible to application

**What Docker provides:**

1. ✅ **Unique MAC per container** - no collisions
2. ✅ **Valid Layer 2 interface** - AF_PACKET compatible
3. ✅ **Full sysfs support** - MAC is readable
4. ✅ **Bridge network switching** - frames delivered correctly

**Bottom line:**

Your code is **fully compatible** with Docker's virtual networking. The MAC address detection happens automatically during initialization, and Docker's MACs work exactly like physical MACs for your AF_PACKET communication.

**No code changes needed** - it just works! 🎉
