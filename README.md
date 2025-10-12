# LinkChat

Mensajería P2P y transferencia de archivos en capa de enlace con una GUI moderna en PyQt6. LinkChat se comunica directamente en la Capa 2 (Ethernet/Wi‑Fi) usando tramas personalizadas, CSMA/CA y una ligera capa de fiabilidad. Incluye un servicio de descubrimiento para encontrar pares en la misma LAN y soporta mensajería confiable y transferencias de archivos/carpetas de gran tamaño.

## Características
- Comunicación directa en Capa 2 mediante AF_PACKET (Linux)
- MAC persistente CSMA para evitar colisiones
- Enmarcado con checksum y bit‑stuffing
- Entrega confiable (ACK/Reintentos) para mensajes y chunks de archivos
- Transferencia de archivos y carpetas con progreso y verificación por hash
- Descubrimiento de pares mediante beacons periódicos (callbacks de aparición/expiración)
- Interfaz de escritorio en PyQt6 (opcional)

## Estructura del proyecto
```
linkchat/
  app/                 # Aplicación PyQt6
    qt_main.py
  link/                # SDK de capa de enlace
    core/              # LinkLayer, framing, message protocol
    mac/               # CSMA y parámetros adaptativos
    medium/            # Medios de bajo nivel AF_PACKET
    transfer/          # Transferencia de archivos + fiabilidad + metadatos
    utils/             # Checksums y utilidades de bits
```

## Requisitos
- Python >= 3.11
- Linux (sockets AF_PACKET). En Windows/macOS, usa WSL2/VM Linux para la capa de enlace. La GUI puede ejecutarse, pero el I/O L2 crudo requiere Linux.
- CAP_NET_RAW o root para sockets raw

## Instalación
Usando PowerShell (Windows) o cualquier shell (Linux):

- Librería + GUI
```
pip install -e ".[gui]"
```
- Extras de desarrollo (tests, etc.)
```
pip install -e ".[dev]"
```

## Inicio rápido (librería)
Ejemplo mínimo que conecta LinkLayer, MessageProtocol, FileTransfer y PeerDiscovery. Ajusta interfaz y EtherTypes según tu entorno.

```python
from linkchat.link import LinkLayer, FrameType
from linkchat.link import MessageProtocol, FileTransfer
from linkchat.link import PeerDiscoveryService

ETHERTYPE_DATA = 0x88B5   # Tramas de datos
ETHERTYPE_DISC = 0x88B6   # Tramas de descubrimiento (distintas de datos)
IFACE = "eth0"            # O "wlan0" en Linux

received_msgs = []

def on_message(src_mac: bytes, text: str):
    print(f"< {src_mac.hex(':')}: {text}")
    received_msgs.append((src_mac, text))

# Despachar tramas a protocolos de más alto nivel
mp = None
ft = None

def on_frame(frame):
    mp.handle_frame(frame)
    ft.handle_received_frame(frame)

# Crear la capa de enlace y comenzar a escuchar
ll = LinkLayer(iface=IFACE, ethertype=ETHERTYPE_DATA, on_frame=on_frame)
ll.start_listening()

# Mensajería + transferencia de archivos
mp = MessageProtocol(ll, on_message=on_message)
ft = FileTransfer(ll, download_dir="./downloads")

# Descubrimiento de pares (EtherType separado)
pd = PeerDiscoveryService(interface=IFACE, ethertype=ETHERTYPE_DISC)
pd.start()

# Ejemplo: enviar un mensaje/archivo al peer más reciente
import time
while not pd.summary():
    time.sleep(0.5)
peers = pd.summary()
node_id, _, _ = peers[0]
# Mapear node_id -> mac usando pd.list_peers()
peer = next(p for p in pd.list_peers() if p.node_id == node_id)
mp.send_message(peer.mac, "Hola desde LinkChat")
# ft.send_file(peer.mac, "/ruta/al/archivo.bin")
```

## Ejecutar la GUI
Si instalaste con el extra de GUI:
```
python -m linkchat.app.qt_main
```

## Permisos y notas de red
- Los sockets raw en Linux requieren privilegios elevados. Opciones típicas:
  - Ejecutar con sudo, o
  - Conceder capacidad: `sudo setcap cap_net_raw+ep $(command -v python3)`
- Usa EtherTypes distintos para datos y descubrimiento (p. ej., 0x88B5 y 0x88B6).
- Nombres de interfaz: usa `ip link` para listar (eth0, enp3s0, wlan0, etc.).
- En Wi‑Fi (managed), a menudo se usa SOCK_DGRAM internamente; se maneja automáticamente.

## Pruebas
```
pytest -q
```

## Solución de problemas
- Permiso denegado en el socket: verifica sudo/CAP_NET_RAW.
- No se encuentran pares: asegúrate de estar en el mismo segmento L2, EtherType de descubrimiento coincidente y modo promiscuo si aplica.
- Pérdida de tramas en Wi‑Fi: reduce tamaños de payload/chunk (los parámetros adaptativos se aplican automáticamente según el medio).

## Licencia
MIT

## Agradecimientos
Construido con PyQt6 y sockets AF_PACKET. Diseñado para fines educativos y experimentos en LAN locales; no pensado para redes hostiles.
