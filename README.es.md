# Link-Chat

🇬🇧 [Read in English](README.md) · 🇪🇸 Español (estás aquí)

![Python](https://img.shields.io/badge/Python-3.13%2B-3776AB?logo=python&logoColor=white)
![Flutter](https://img.shields.io/badge/Flutter-3.47-02569B?logo=flutter&logoColor=white)
![Dart](https://img.shields.io/badge/Dart-3.13-0175C2?logo=dart&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-ready-2496ED?logo=docker&logoColor=white)
![Platforms](https://img.shields.io/badge/platforms-Linux%20%7C%20Android%20%7C%20iOS-lightgrey)

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

## Índice

- [Requisitos del curso](#requisitos-del-curso)
- [Estructura del repositorio](#estructura-del-repositorio)
- [Cómo correr cada cliente](#cómo-correr-cada-cliente)
- [Arquitectura en una línea](#arquitectura-en-una-línea)
- [Piezas interesantes del código](#piezas-interesantes-del-código)
- [Autores](#autores)

## Requisitos del curso

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
├── docker/              # Dockerfiles, docker-compose.yml y scripts de despliegue
├── docs/                # RUNNING_APP.md, GUION_EXPOSICION.md
├── req/linkchat.md      # Enunciado original de la asignatura
│
└── mobile/              # Cliente Flutter (Android/iOS)
    ├── lib/network/     # Descubrimiento UDP, conexión TCP, cifrado, framing
    ├── lib/services/    # Identidad, persistencia de chat, transferencia de archivos
    ├── lib/ui/          # Pantallas (pares, chat, ajustes)
    ├── test/            # Unit tests + integración de dos peers reales por socket
    └── SETUP.md         # Cómo generar android/ios, compilar y probar
```

## Cómo correr cada cliente

- **Escritorio**: ver [`docs/RUNNING_APP.md`](docs/RUNNING_APP.md) (scripts
  de Docker en [`docker/`](docker): `build_images.sh`, `create_network.sh`,
  `run_container.sh`, `deploy_linkchat.sh`). También corre directo con
  `python main.py` si tenés permisos de socket raw (root/CAP_NET_RAW) en
  Linux.
- **Móvil**: ver [`mobile/SETUP.md`](mobile/SETUP.md) — instalar el SDK de
  Flutter, generar `android/`/`ios/`, `flutter pub get`, y correr en dos
  dispositivos en la misma WiFi para ver el descubrimiento y la mensajería
  en acción.

## Arquitectura en una línea

- **Escritorio**: Ethernet frame → framing manual (flags + bit-stuffing +
  CRC16) → AEAD ChaCha20-Poly1305 con PSK global → ACK con reintentos
  manuales, porque a nivel de enlace no hay ninguna garantía de entrega.
- **Móvil**: UDP para descubrimiento (beacons), una conexión TCP por par
  para todo lo demás → framing simple con prefijo de longitud → handshake
  X25519 por conexión → AEAD ChaCha20-Poly1305 con clave de sesión → sin
  ACK/retry manual para los datos, porque TCP ya garantiza entrega
  ordenada y completa.

## Piezas interesantes del código

Algunos puntos de entrada si querés ver el proyecto sin leerlo entero:

- [`app/backend/core/raw_socket.py`](app/backend/core/raw_socket.py) —
  socket AF_PACKET crudo, filtrado por EtherType propio, sin tocar IP/TCP/UDP.
- [`app/backend/utils/frame_helper.py`](app/backend/utils/frame_helper.py) —
  framing manual con flags, bit-stuffing, CRC16 y cifrado AEAD, porque a
  nivel de enlace no hay nada de eso gratis.
- [`app/backend/core/file_transfer.py`](app/backend/core/file_transfer.py)
  ([línea `recent_seqs`](app/backend/core/file_transfer.py#L441)) —
  protocolo de transferencia con ventana deslizante; ahí está el fix de un
  bug real de corrupción por chunks duplicados que encontré corriendo dos
  contenedores Docker reales uno contra el otro
  ([commit `7694c3b`](https://github.com/JuanCMath/Link-Chat/commit/7694c3b)).
- [`mobile/lib/network/crypto_session.dart`](mobile/lib/network/crypto_session.dart) —
  handshake X25519 + HKDF + ChaCha20-Poly1305 negociado por conexión, en vez
  del PSK global fijo del cliente de escritorio.
- [`mobile/lib/network/peer_connection.dart`](mobile/lib/network/peer_connection.dart#L52)
  (uso de `asyncMap`) — fix de una condición de carrera real: frames
  descifrados fuera de orden cuando llegan varios juntos en una misma
  lectura TCP.
- [`mobile/test/two_peers_integration_test.dart`](mobile/test/two_peers_integration_test.dart) —
  test de integración que levanta dos peers reales hablando por socket UDP/TCP
  de verdad (sin mocks); así se encontraron los dos bugs de arriba.

## Autores

- [Sebastian González Alfonso](https://t.me/sebagonz106)
- [Juan Carlos Carmenate Díaz](https://t.me/Juank404)
