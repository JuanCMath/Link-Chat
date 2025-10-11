# Quick Start - Integration Testing

## ✅ YES! Your Code Can Access Docker's MAC Addresses

Docker assigns each container a **unique MAC address** (e.g., `02:42:ac:14:00:0a`), and your code **automatically detects it** via `/sys/class/net/eth0/address`. No configuration needed!

**How it works:**
1. Docker creates virtual `eth0` with unique MAC
2. Your `AFPacketMediumEthWifi` reads MAC from `/sys/class/net/eth0/address`
3. Stored in `backend.local_mac` - used for all frame construction
4. Containers communicate using these MACs at Layer 2

See **DOCKER_MAC_ACCESS.md** for complete technical details.

---

## TL;DR - Test Communication Between Two Containers

```powershell
# 1. Start Docker Desktop

# 2. Run this script
.\start-integration-test.ps1

# 3. Open Alice's shell (in this terminal)
docker exec -it linkchat-alice python /app/test_container.py

# 4. Open Bob's shell (in another terminal)
docker exec -it linkchat-bob python /app/test_container.py

# 5. Send message from Alice to Bob
# In Alice's terminal, type:
1                              # Command 1: Send message
02:42:ac:14:00:0b             # Bob's MAC (shown in Alice's output)
Hello Bob!                     # Your message

# 6. See message appear in Bob's terminal! 🎉
```

---

## What Gets Created

```
Your PC
├── Alice Container (172.20.0.10)
│   ├── MAC: 02:42:ac:14:00:0a
│   └── Downloads: ./downloads-alice/
│
├── Bob Container (172.20.0.11)
│   ├── MAC: 02:42:ac:14:00:0b
│   └── Downloads: ./downloads-bob/
│
└── Virtual Network (172.20.0.0/16)
    └── Bridge connecting Alice ↔ Bob
```

---

## Interactive Commands

Once in test script (`test_container.py`):

| Command | Action |
|---------|--------|
| `1` | Send message to another node |
| `2` | Send file to another node |
| `3` | List network interfaces |
| `4` | Show backend info |
| `5` | Create test file |
| `q` | Quit |

---

## Example Session

**Terminal 1 (Alice):**
```
> 5                           # Create test file
Filename: demo.txt
Size in KB: 50
✅ Created /app/demo.txt

> 2                           # Send file
Destination MAC: 02:42:ac:14:00:0b  # Bob
File path: /app/demo.txt
📦 demo.txt: 25600/51200 bytes (50.0%)
📦 demo.txt: 51200/51200 bytes (100.0%)
✅ File sent!
```

**Terminal 2 (Bob):**
```
📦 demo.txt: 25600/51200 bytes (50.0%)
📦 demo.txt: 51200/51200 bytes (100.0%)
📁 demo.txt: ✅ Success

# File saved in /app/downloads/demo.txt
```

---

## Testing GUI (Optional, Advanced)

Requires **VcXsrv** on Windows:

1. Install VcXsrv from https://sourceforge.net/projects/vcxsrv/
2. Launch with "Disable access control" checked
3. Edit `docker-compose.test.yml`: change `QT_QPA_PLATFORM=offscreen` to `QT_QPA_PLATFORM=xcb`
4. Restart containers: `docker-compose -f docker-compose.test.yml up`

**Note:** GUI may be unstable on Windows. Interactive shell is recommended.

---

## Cleanup

```powershell
# Stop containers
docker-compose -f docker-compose.test.yml down

# Remove download folders
rm -r downloads-alice, downloads-bob

# Remove Docker network
docker network rm linkchat-net
```

---

## Troubleshooting

**No messages received?**
```bash
# Inside container, check network
ip link show eth0
tcpdump -i eth0 -XX ether proto 0x88B5
```

**Permission denied?**
- Make sure Docker Desktop is running
- Check containers have NET_RAW capability

**Wrong MAC address?**
- Get from container startup output
- Or run: `ip link show eth0 | grep link/ether`

---

## Full Documentation

See **INTEGRATION_TESTING.md** for complete guide.
