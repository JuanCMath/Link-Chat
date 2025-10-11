# Link-Chat

A Layer 2 Ethernet chat application using custom protocol over raw sockets.

## Overview

Link-Chat operates at **OSI Layer 2** (Data Link Layer), using:
- **MAC addresses** for addressing (no IP addresses)
- **Custom EtherType** for protocol identification
- **AF_PACKET raw sockets** for frame transmission/reception
- **CSMA/CD** for media access control

---

## ⚠️ Platform Requirements

Link-Chat requires **raw packet access** which is only available on:

| Platform | Support | Notes |
|----------|---------|-------|
| **Linux (native)** | ✅ **Fully Supported** | Recommended |
| **Linux in VM** | ✅ Supported | Bridged networking required |
| **WSL2** | ⚠️ **Limited** | Loopback only - [see limitations](./WSL2_LIMITATIONS.md) |
| **Windows** | ❌ Not supported | No AF_PACKET |
| **macOS** | ❌ Not supported | No AF_PACKET |

**For development on Windows**: Use Ubuntu VM or test with loopback interface  
**For production/demo**: Use native Linux or Linux VM

See [WSL2_LIMITATIONS.md](./WSL2_LIMITATIONS.md) for detailed platform information.

---

## Quick Start

### Docker Deployment (Linux Only)

**Requirements:**
- Native Linux OS (Ubuntu, Debian, Fedora, etc.)
- Docker installed
- Physical network adapter (Ethernet or WiFi)

```bash
# 1. Setup MACVLAN network (one-time)
./docker/setup-macvlan.sh

# 2. Run Link-Chat
./docker/run-macvlan.sh

# 3. In GUI, select your interface (e.g., eth0)
```

See [DOCKER_QUICKSTART.md](./DOCKER_QUICKSTART.md) for detailed instructions.

### Direct Installation (Linux)

```bash
# 1. Install dependencies
pip install -e .

# 2. Run with sudo (required for raw sockets)
sudo python -m linkchat.app.qt_main

# 3. Select network interface and connect
```

---

## Project Structure

```
Link-Chat/
├── linkchat/               # Main application package
│   ├── app/                # GUI application
│   │   ├── qt_main.py      # Entry point
│   │   └── gui/            # PyQt6 GUI components
│   └── link/               # Link layer implementation
│       ├── link_layer.py   # Main link layer logic
│       ├── af_packet_medium_eth_wifi.py  # Raw socket medium
│       ├── framing.py      # Frame encoding/decoding
│       ├── checksum.py     # Error detection
│       └── csma_persistente.py  # CSMA/CD
│
├── docker/                 # Docker configurations
│   ├── setup-macvlan.sh    # MACVLAN network setup
│   ├── run-macvlan.sh      # Run container with MACVLAN
│   └── testing/            # Development images
│
├── docs/                   # Additional documentation
├── tests/                  # Unit tests
│
├── DOCKER_QUICKSTART.md    # Docker quick start guide
├── MACVLAN_SETUP.md        # Detailed MACVLAN documentation
├── WSL2_LIMITATIONS.md     # Platform limitations explained
└── docker-compose.macvlan.yml  # Multi-container testing
```

---

## Features

### Layer 2 Protocol
- **Custom EtherType**: 0x88B5
- **MAC-based addressing**: No IP configuration needed
- **Frame structure**: Header + Payload + CRC32 checksum
- **Sequence numbers**: For reliability and ordering

### Media Access
- **CSMA/CD**: Carrier sense multiple access with collision detection
- **Carrier sense timeout**: Configurable wait time
- **Exponential backoff**: On collision detection

### GUI Application (PyQt6)
- Network interface selection
- Peer discovery and listing  
- Chat interface with message history
- Real-time status updates
- Connection management

### Docker Support
- **MACVLAN networking**: Each container gets unique MAC address
- **Multi-container testing**: Run 2-3 instances simultaneously
- **Layer 2 communication**: Containers appear as physical devices
- **Platform**: Native Linux required (see WSL2 limitations)

---

## Documentation

- **[DOCKER_QUICKSTART.md](./DOCKER_QUICKSTART.md)** - Get started with Docker in 3 steps
- **[MACVLAN_SETUP.md](./MACVLAN_SETUP.md)** - Complete MACVLAN networking guide
- **[WSL2_LIMITATIONS.md](./WSL2_LIMITATIONS.md)** - Platform requirements and limitations
- **[MACVLAN_IMPLEMENTATION.md](./MACVLAN_IMPLEMENTATION.md)** - Implementation details

---

## Usage Examples

### Using Docker (Linux)

```bash
# Single container
./docker/run-macvlan.sh
# In GUI: Select 'eth0', click "Iniciar Backend"

# Multiple containers for testing
docker-compose -f docker-compose.macvlan.yml up
# Opens 3 GUI windows, each with unique MAC
```

### Direct on Linux

```bash
# Install dependencies
pip install PyQt6

# Run with sudo (required for AF_PACKET)
sudo python -m linkchat.app.qt_main
```

### Development on WSL2 (Limited)

```bash
# Only works with loopback interface
sudo python -m linkchat.app.qt_main
# In GUI: Select 'lo' interface (NOT eth0)
```

---

## Technical Details

### Protocol Specifications

**EtherType**: `0x88B5` (custom, experimental range)

**Frame Format**:
```
┌─────────────┬──────────┬─────────┬──────────┬─────────┐
│  Dst MAC    │  Src MAC │ EtherType│ Payload  │ CRC32   │
│  (6 bytes)  │ (6 bytes)│ (2 bytes)│ (Variable)│(4 bytes)│
└─────────────┴──────────┴─────────┴──────────┴─────────┘
```

**Link Layer Header** (in payload):
```
- Sequence number (4 bytes)
- Flags (1 byte)
- Data length (2 bytes)
- Application data (variable)
```

### Network Requirements

**Same network segment**: All devices must be on the same Layer 2 broadcast domain
- ✅ Same Ethernet switch
- ✅ Same WiFi access point  
- ❌ Different VLANs
- ❌ Across routers

**Capabilities required**:
- `CAP_NET_RAW`: For AF_PACKET sockets
- `CAP_NET_ADMIN`: For network configuration (optional)

---

## Troubleshooting

### "Network is down" error

**On WSL2**: This is expected - WSL2's eth0 doesn't support AF_PACKET receive operations.  
**Solution**: Use native Linux or test with loopback (`lo`) interface.

See [WSL2_LIMITATIONS.md](./WSL2_LIMITATIONS.md) for details.

### "Permission denied" creating socket

**Cause**: AF_PACKET sockets require elevated privileges  
**Solution**: Run with `sudo` or set capabilities:
```bash
sudo python -m linkchat.app.qt_main
# OR
sudo setcap cap_net_raw+ep $(which python3)
python -m linkchat.app.qt_main
```

### GUI doesn't appear (Docker)

**Check X11 forwarding**:
```bash
# On host (Linux with X11)
xhost +local:docker

# On Windows with VcXsrv
# Start VcXsrv with: -multiwindow -ac
```

### "Network not found" (Docker)

**Solution**: Create MACVLAN network first:
```bash
./docker/setup-macvlan.sh
```

---

## Development

### Running Tests

```bash
# Install test dependencies
pip install -e ".[dev]"

# Run tests
pytest tests/

# Run specific test
pytest tests/test_framing.py
```

### Building Docker Images

```bash
# Build base image
docker build -f docker/base/Dockerfile.base -t linkchat-base .

# Build interactive image
docker build -f docker/testing/Dockerfile.interactive.new -t linkchat-interactive .
```

---

## Contributing

This is a university project. For questions or issues, please contact the project maintainers.

---

## License

[Specify your license here]

---

## Acknowledgments

Built as part of computer networking coursework exploring Layer 2 protocols and raw socket programming.

---

## FAQ

**Q: Can I use this on Windows?**  
A: Not directly. Windows doesn't support AF_PACKET sockets. Use a Linux VM or WSL2 with loopback interface.

**Q: Why does WSL2's eth0 not work?**  
A: WSL2 uses a Hyper-V virtual network adapter that doesn't fully support AF_PACKET operations. See [WSL2_LIMITATIONS.md](./WSL2_LIMITATIONS.md).

**Q: Can containers communicate with physical PCs?**  
A: Yes, on native Linux with MACVLAN. Each container gets a real MAC address on the network.

**Q: Do I need Docker?**  
A: No, you can run Link-Chat directly on Linux with `sudo`. Docker provides isolation and easy multi-instance testing.

**Q: What about IPv6 or modern networking?**  
A: Link-Chat deliberately operates at Layer 2 only - no IP addresses are used. This is educational software demonstrating low-level networking concepts.

---

**For detailed MACVLAN setup**: See [MACVLAN_SETUP.md](./MACVLAN_SETUP.md)  
**For quick Docker start**: See [DOCKER_QUICKSTART.md](./DOCKER_QUICKSTART.md)  
**For platform info**: See [WSL2_LIMITATIONS.md](./WSL2_LIMITATIONS.md)
