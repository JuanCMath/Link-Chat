# Production Docker Configuration

Deploy Link-Chat on Linux systems with access to physical network interfaces.

---

## Files

- **`Dockerfile`** - Production image with PyQt6
- **`docker-compose.yml`** - Host networking configuration  
- **`docker-run.sh`** - Quick start script

---

## Quick Start

```bash
./docker-run.sh
```

Or manually:

```bash
docker build -t linkchat:latest .
docker run --rm -it \
  --network host \
  --cap-add NET_RAW \
  --cap-add NET_ADMIN \
  -e DISPLAY=$DISPLAY \
  -v /tmp/.X11-unix:/tmp/.X11-unix \
  linkchat:latest
```

---

## Requirements

- Linux host (Ubuntu, Debian, etc.)
- Docker installed
- X server running (for GUI)
- Physical network interface (eth0, wlan0)

---

## Configuration

Edit environment variables in `docker-compose.yml`:

```yaml
environment:
  - INTERFACE=wlan0    # Your network interface
  - DISPLAY=:0         # Your X display
```

---

## See Also

- **Deployment guide:** `../../docs/docker/DOCKER_DEPLOYMENT_GUIDE.md`
- **Quick reference:** `../../docs/docker/DOCKER_QUICKREF.md`
