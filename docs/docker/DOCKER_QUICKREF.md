# Docker Quick Reference - Link-Chat

## Prerequisites
- **Linux host** (AF_PACKET is Linux-only)
- Docker installed
- X11 server running (for GUI)

## Quick Start (Easiest)

```bash
chmod +x docker-run.sh
./docker-run.sh
```

## Manual Commands

### Build Image
```bash
docker build -t linkchat:latest .
```

### Run (X11 Forwarding)
```bash
# Allow X11 access
xhost +local:docker

# Run container
docker run -it --rm \
  --network host \
  --cap-add=NET_RAW \
  --cap-add=NET_ADMIN \
  -e DISPLAY=$DISPLAY \
  -v /tmp/.X11-unix:/tmp/.X11-unix:rw \
  -v $(pwd)/downloads:/app/downloads \
  linkchat:latest

# Cleanup
xhost -local:docker
```

### Using Docker Compose
```bash
# Start
docker-compose up

# Stop
docker-compose down

# Rebuild
docker-compose up --build
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DISPLAY` | `:0` | X11 display |
| `INTERFACE` | `wlan0` | Network interface |
| `QT_QPA_PLATFORM` | `xcb` | Qt platform |

**Usage:**
```bash
INTERFACE=eth0 docker-compose up
```

## Troubleshooting

### ❌ "Permission denied" on socket
**Fix:** Add capabilities:
```bash
docker run --cap-add=NET_RAW --cap-add=NET_ADMIN ...
```

### ❌ "Cannot connect to X server"
**Fix:** Allow Docker X11 access:
```bash
xhost +local:docker
```

### ❌ "No such device: wlan0"
**Fix:** Use host networking:
```bash
docker run --network host ...
```

Or specify correct interface:
```bash
INTERFACE=eth0 docker-compose up
```

### ❌ "ImportError: PyQt6"
**Fix:** Rebuild image:
```bash
docker-compose build --no-cache
```

## Debugging

### List interfaces inside container
```bash
docker exec -it linkchat-app ip link show
```

### Test raw socket creation
```bash
docker exec -it linkchat-app python3 -c "
import socket
s = socket.socket(socket.AF_PACKET, socket.SOCK_RAW, 0)
print('✅ Socket created')
s.close()
"
```

### Check X11 connection
```bash
docker exec -it linkchat-app echo \$DISPLAY
```

### View logs
```bash
docker logs linkchat-app
```

## Alpine Alternative

If you prefer Alpine (smaller image):

**Build:**
```bash
docker build -f Dockerfile.alpine -t linkchat:alpine .
```

**Note:** PyQt6 support on Alpine is limited. Debian recommended.

## Production Deployment

For headless/remote servers, see `DOCKER_DEPLOYMENT_GUIDE.md` section on VNC setup.

## Common Workflows

### Development
```bash
# Build and run with live code changes
docker run -it --rm \
  --network host \
  --cap-add=NET_RAW \
  -e DISPLAY=$DISPLAY \
  -v /tmp/.X11-unix:/tmp/.X11-unix:rw \
  -v $(pwd)/linkchat:/app/linkchat:ro \
  linkchat:latest
```

### Testing on specific interface
```bash
INTERFACE=eth0 ./docker-run.sh
```

### Persistent downloads
```bash
mkdir -p downloads
docker run ... -v $(pwd)/downloads:/app/downloads ...
```

## Security Notes

⚠️ **CAP_NET_RAW** grants significant network privileges  
⚠️ **--network host** bypasses Docker network isolation  
⚠️ **xhost +local:docker** allows containers to access display

**Recommended for production:**
- Use VNC instead of X11 forwarding
- Limit to specific interfaces with network namespaces
- Run in isolated network segments
