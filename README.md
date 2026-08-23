# Link-Chat

Mensajería punto a punto con transferencia de archivos, sin depender de ningún
servidor central. El proyecto tiene dos clientes:

1. **Link-Chat (escritorio)** — el proyecto original de la asignatura *Redes
   de Computadoras*: mensajería a **nivel de enlace** (sockets raw
   AF_PACKET/Ethernet, EtherType propio `0x88B5`), sin usar ninguna capa de
   red superior ni bibliotecas externas al lenguaje. Corre en Linux/Docker
   sobre una interfaz física o virtualizada.
2. **Link-Chat Mobile** — la evolución del mismo problema (mensajería +
   archivos, punto a punto, sin servidor) llevada a **teléfono** en Flutter.
   Los sockets raw no existen en un teléfono normal (iOS los prohíbe,
   Android los restringe a root), así que este cliente reimplementa el
   mismo espíritu sobre IP: descubrimiento por broadcast UDP en la misma
   WiFi/LAN, conexión TCP por par, y cifrado end-to-end negociado por
   conexión (X25519 + ChaCha20-Poly1305) en vez del PSK global fijo del
   proyecto original.

## Requisitos del curso — estado

A partir de [`req/linkchat.md`](req/linkchat.md):

| Requisito | Estado |
|---|---|
| Mensajería ordenador a ordenador | ✅ |
| Intercambio de archivos punto a punto | ✅ |
| Interfaz de consola | ✅ |
| Docker (red virtualizada) + red física | ✅ |
| Cualquier tamaño de archivo/mensaje | ✅ (chunking + ACK/retry) |
| Identificación automática de pares | ✅ (beacons) |
| Mensajería de uno a todos | ✅ (`/sendtoall`) |
| Envío/recepción de carpetas | ✅ (`/senddir`, tar.gz) |
| Capa de seguridad | ✅ (ChaCha20-Poly1305 AEAD) |
| Interfaz visual (GUI, UX, fluidez, manejo de errores) | ✅ (PyQt6) |
| Creatividad | ✅ **Link-Chat Mobile** — la misma idea, reconstruida desde cero para funcionar en un teléfono |

## Estructura del repositorio

```
Link-Chat/
├── app/                 # Cliente de escritorio (Python, sockets raw)
│   ├── backend/         # Protocolo, descubrimiento, transferencia, cifrado
│   ├── frontend/        # Consola
│   └── gui_pyqt6/       # Interfaz gráfica
├── main.py              # Entry point del cliente de escritorio
├── docker-compose.yml, dockerfile*, *.sh   # Despliegue en Docker
├── req/linkchat.md      # Enunciado original de la asignatura
├── RUNNING_APP.md       # Cómo correr el cliente de escritorio
│
└── mobile/              # Cliente Flutter (Android/iOS)
    ├── lib/network/     # Descubrimiento UDP, conexión TCP, cifrado, framing
    ├── lib/services/    # Identidad, persistencia de chat, transferencia de archivos
    ├── lib/ui/          # Pantallas (pares, chat, ajustes)
    ├── test/            # Unit tests + integración de dos peers reales por socket
    └── SETUP.md         # Cómo generar android/ios, compilar y probar
```

## Cómo correr cada cliente

- **Escritorio**: ver [`RUNNING_APP.md`](RUNNING_APP.md) (scripts de Docker:
  `build_images.sh`, `create_network.sh`, `run_container.sh`,
  `deploy_linkchat.sh`). También corre directo con `python main.py` si tenés
  permisos de socket raw (root/CAP_NET_RAW) en Linux.
- **Móvil**: ver [`mobile/SETUP.md`](mobile/SETUP.md) — instalar el SDK de
  Flutter, generar `android/`/`ios/`, `flutter pub get`, y correr en dos
  dispositivos en la misma WiFi para ver el descubrimiento y la mensajería
  en acción. El protocolo de red (descubrimiento, cifrado, transferencia de
  archivos) ya está probado de punta a punta sobre sockets reales en
  [`mobile/test/two_peers_integration_test.dart`](mobile/test/two_peers_integration_test.dart).

## Arquitectura en una línea

- **Escritorio**: Ethernet frame → framing manual (flags + bit-stuffing +
  CRC16) → AEAD ChaCha20-Poly1305 con PSK global → ACK con reintentos
  manuales, porque a nivel de enlace no hay ninguna garantía de entrega.
- **Móvil**: UDP para descubrimiento (beacons), una conexión TCP por par
  para todo lo demás → framing simple con prefijo de longitud → handshake
  X25519 por conexión → AEAD ChaCha20-Poly1305 con clave de sesión → sin
  ACK/retry manual para los datos, porque TCP ya garantiza entrega
  ordenada y completa.

## Autores

- [Sebastian González Alfonso](https://t.me/sebagonz106)
- [Juan Carlos Carmenate Díaz](https://t.me/Juank404)
