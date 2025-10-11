# Integration Testing Guide - Multi-Container Network Simulation

## Overview

This guide shows how to test Link-Chat **communication and GUI** using **two Docker containers** on your Windows PC, simulating a real network.

**What you'll test:**
- ✅ Message exchange between two nodes
- ✅ File transfer between containers
- ✅ Folder transfer between containers
- ✅ Network discovery (if implemented)
- ✅ GUI interaction (with X server on Windows)

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│              Your Windows PC                        │
│                                                     │
│  ┌─────────────────────────────────────────────┐  │
│  │   Docker Bridge Network (172.20.0.0/16)    │  │
│  │                                              │  │
│  │   ┌──────────────┐      ┌──────────────┐   │  │
│  │   │   Alice      │      │     Bob      │   │  │
│  │   │ 172.20.0.10  │◄────►│ 172.20.0.11  │   │  │
│  │   │ eth0         │      │ eth0         │   │  │
│  │   │ MAC: aa:...  │      │ MAC: bb:...  │   │  │
│  │   └──────────────┘      └──────────────┘   │  │
│  │         ▲                      ▲            │  │
│  └─────────│──────────────────────│────────────┘  │
│            │                      │                │
│       downloads-alice       downloads-bob          │
└─────────────────────────────────────────────────────┘
```

**Key features:**
- Both containers on **same virtual network** (can see each other)
- Each has **unique MAC address** (Docker assigns automatically)
- Separate **download directories** (no file conflicts)
- **AF_PACKET sockets work** (with NET_RAW capability)

---

## Prerequisites

### Required

1. **Docker Desktop** installed and running
2. **Project files** built into Docker image

### Optional (for GUI on Windows)

3. **VcXsrv** or **Xming** (X server for Windows)
   - Download VcXsrv: https://sourceforge.net/projects/vcxsrv/
   - Or Xming: https://sourceforge.net/projects/xming/

---

## Setup Methods

### Method 1: Interactive Shell Testing (Easiest)

**Best for:** Testing backend communication without GUI complexity

**Steps:**

1. **Build the interactive image:**
   ```powershell
   docker build -f Dockerfile.interactive -t linkchat-test .
   ```

2. **Start the network and containers:**
   ```powershell
   docker-compose -f docker-compose.test.yml up -d
   ```

3. **Open shell in Alice's container:**
   ```powershell
   docker exec -it linkchat-alice bash
   ```

4. **Run test script in Alice:**
   ```bash
   python /app/test_container.py
   ```

5. **In another terminal, open shell in Bob's container:**
   ```powershell
   docker exec -it linkchat-bob bash
   ```

6. **Run test script in Bob:**
   ```bash
   python /app/test_container.py
   ```

7. **Now you can send messages between them!**

---

### Method 2: GUI Testing with X Server (Windows)

**Best for:** Full GUI testing with visual interface

**Setup X Server on Windows:**

1. **Install VcXsrv** from https://sourceforge.net/projects/vcxsrv/

2. **Launch VcXsrv with these settings:**
   - Display number: 0
   - ✅ Multiple windows
   - ✅ Start no client
   - ✅ **Disable access control** (important!)

3. **Allow through Windows Firewall** when prompted

4. **Set DISPLAY environment variable:**
   ```powershell
   $env:DISPLAY = "host.docker.internal:0"
   ```

5. **Start containers with GUI:**
   ```powershell
   # Update docker-compose.test.yml first (change QT_QPA_PLATFORM to xcb)
   docker-compose -f docker-compose.test.yml up
   ```

**Note:** GUI may have issues on Windows. Interactive shell method is more reliable.

---

### Method 3: Manual Container Management

**For advanced users who want full control:**

```powershell
# Create custom network
docker network create --subnet=172.20.0.0/16 linkchat-net

# Run Alice
docker run -it --rm `
  --name alice `
  --network linkchat-net `
  --ip 172.20.0.10 `
  --cap-add NET_RAW `
  --cap-add NET_ADMIN `
  -e INTERFACE=eth0 `
  -e NODE_NAME=Alice `
  -v ${PWD}/downloads-alice:/app/downloads `
  linkchat:latest

# In another terminal, run Bob
docker run -it --rm `
  --name bob `
  --network linkchat-net `
  --ip 172.20.0.11 `
  --cap-add NET_RAW `
  --cap-add NET_ADMIN `
  -e INTERFACE=eth0 `
  -e NODE_NAME=Bob `
  -v ${PWD}/downloads-bob:/app/downloads `
  linkchat:latest
```

---

## Testing Scenarios

### Scenario 1: Send Message from Alice to Bob

**In Alice's container:**
```python
# In test_container.py interactive menu
> 1                          # Send message
Destination MAC: <Bob's MAC> # Get from Bob's startup output
Message: Hello Bob!
✅ Message sent!
```

**In Bob's container:**
```
📨 Message from aa:bb:cc:dd:ee:ff: Hello Bob!
```

### Scenario 2: Send File from Bob to Alice

**Prepare file in Bob:**
```python
> 5                          # Create test file
Filename: test-data.bin
Size in KB: 100
✅ Created /app/test-data.bin (102400 bytes)
```

**Send to Alice:**
```python
> 2                          # Send file
Destination MAC: <Alice's MAC>
File path: /app/test-data.bin
✅ File sent!
```

**Verify in Alice:**
```bash
ls -lh /app/downloads/
# Should see test-data.bin
```

### Scenario 3: Folder Transfer

**Create folder structure in Alice:**
```bash
mkdir -p /app/test-folder/subdir
echo "File 1" > /app/test-folder/file1.txt
echo "File 2" > /app/test-folder/subdir/file2.txt
```

**Send from Python:**
```python
from linkchat.backend import LinkChatBackend

backend = LinkChatBackend(interface="eth0")
backend.start()

bob_mac = bytes.fromhex("...")  # Bob's MAC
backend.send_folder(bob_mac, "/app/test-folder")
```

### Scenario 4: Debugging Network

**Inside container, check network:**
```bash
# Show interfaces
ip link show

# Show MAC addresses
ip link show eth0 | grep link/ether

# Capture packets (in another terminal)
docker exec -it linkchat-alice tcpdump -i eth0 -XX

# Ping test (IP layer, not AF_PACKET)
ping 172.20.0.11
```

---

## Getting MAC Addresses

### Method 1: From Container Startup

When you start the container, the MAC is shown:
```
📡 Interface: eth0
🏷️  MAC Address: 02:42:ac:14:00:0a
```

### Method 2: Query Inside Container

```bash
ip link show eth0 | grep link/ether
# Output: link/ether 02:42:ac:14:00:0a ...
```

### Method 3: From Docker Inspect

```powershell
docker inspect linkchat-alice | Select-String -Pattern "MacAddress"
```

---

## Troubleshooting

### Issue: Containers can't communicate

**Symptoms:**
- Messages not received
- No errors, but nothing happens

**Debug:**
```bash
# In Alice
tcpdump -i eth0 -vv ether proto 0x88B5

# In Bob, send message to Alice
# You should see packets in Alice's tcpdump
```

**Solutions:**
- ✅ Verify both on same network: `docker network inspect linkchat-net`
- ✅ Check MAC addresses are different
- ✅ Verify EtherType matches (0x88B5)
- ✅ Check firewall/capabilities: `NET_RAW` and `NET_ADMIN`

### Issue: "Permission denied" for raw sockets

**Error:**
```
PermissionError: [Errno 1] Operation not permitted
```

**Solution:**
```powershell
# Make sure containers have capabilities
docker-compose -f docker-compose.test.yml down
docker-compose -f docker-compose.test.yml up -d
# Check logs: docker logs linkchat-alice
```

### Issue: GUI doesn't appear (Windows)

**Solutions:**
1. **Check VcXsrv is running** (system tray icon)
2. **Disable access control** in VcXsrv settings
3. **Allow through firewall** when prompted
4. **Use interactive shell instead** - more reliable on Windows

### Issue: Files not appearing in downloads

**Check:**
```bash
# Inside container
ls -la /app/downloads/

# Outside container (Windows)
ls downloads-alice/
ls downloads-bob/
```

**Solution:**
- Create directories first: `mkdir downloads-alice downloads-bob`
- Check volume mounts in docker-compose.test.yml

---

## Cleanup

**Stop containers:**
```powershell
docker-compose -f docker-compose.test.yml down
```

**Remove network:**
```powershell
docker network rm linkchat-net
```

**Clean up downloads:**
```powershell
rm -r downloads-alice, downloads-bob
```

---

## Advanced Testing

### Test with 3+ Nodes

Edit `docker-compose.test.yml` to add Charlie:

```yaml
  charlie:
    image: linkchat:latest
    container_name: linkchat-charlie
    networks:
      linkchat-net:
        ipv4_address: 172.20.0.12
    # ... same config as alice/bob
```

### Network Simulation Tools

**Add latency (simulate slow network):**
```bash
# Inside container
tc qdisc add dev eth0 root netem delay 100ms
```

**Add packet loss:**
```bash
tc qdisc add dev eth0 root netem loss 5%
```

**Remove simulation:**
```bash
tc qdisc del dev eth0 root
```

### Automated Testing Script

Create `integration_test.sh`:
```bash
#!/bin/bash

# Start containers
docker-compose -f docker-compose.test.yml up -d

# Wait for startup
sleep 5

# Get MACs
ALICE_MAC=$(docker exec linkchat-alice ip link show eth0 | grep link/ether | awk '{print $2}')
BOB_MAC=$(docker exec linkchat-bob ip link show eth0 | grep link/ether | awk '{print $2}')

echo "Alice MAC: $ALICE_MAC"
echo "Bob MAC: $BOB_MAC"

# Send test message from Alice to Bob
docker exec linkchat-alice python3 -c "
from linkchat.backend import LinkChatBackend
backend = LinkChatBackend(interface='eth0')
backend.start()
bob_mac = bytes.fromhex('${BOB_MAC//:}')
backend.send_message(bob_mac, 'Test message from Alice')
backend.stop()
"

echo "✅ Integration test complete"
```

---

## Summary

✅ **Two methods available:**
1. **Interactive Shell** - Easiest, most reliable on Windows
2. **GUI with X Server** - Full visual testing (requires VcXsrv)

✅ **Network simulation works via Docker bridge network**  
✅ **Each container has unique MAC address**  
✅ **AF_PACKET sockets work with NET_RAW capability**  
✅ **Can test all features:** messages, files, folders  

**Recommended approach for Windows:**
1. Use **docker-compose.test.yml** with interactive shell
2. Run **test_container.py** in both containers
3. Test communication manually
4. Later, add automated integration tests

**Next steps:**
1. Build image: `docker build -f Dockerfile.interactive -t linkchat-test .`
2. Start network: `docker-compose -f docker-compose.test.yml up -d`
3. Test in Alice: `docker exec -it linkchat-alice python /app/test_container.py`
4. Test in Bob: `docker exec -it linkchat-bob python /app/test_container.py`
5. Send messages between them! 🎉
