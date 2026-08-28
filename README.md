# Link-Chat

🇬🇧 English (you are here) · 🇪🇸 [Leer en español](README.es.md)

![Python](https://img.shields.io/badge/Python-3.13%2B-3776AB?logo=python&logoColor=white)
![Flutter](https://img.shields.io/badge/Flutter-3.47-02569B?logo=flutter&logoColor=white)
![Dart](https://img.shields.io/badge/Dart-3.13-0175C2?logo=dart&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-ready-2496ED?logo=docker&logoColor=white)
![Platforms](https://img.shields.io/badge/platforms-Linux%20%7C%20Android%20%7C%20iOS-lightgrey)

Peer-to-peer messaging with file transfer, no central server involved.
The project has two clients:

1. **Link-Chat (desktop)** — the original project for the *Computer
   Networks* course: **link-layer** messaging (raw AF_PACKET/Ethernet
   sockets, a custom EtherType `0x88B5`), without using any higher
   network layer or libraries outside the language. Runs on
   Linux/Docker over a physical or virtualized interface.
2. **Link-Chat Mobile** — the same problem (messaging + files,
   peer-to-peer, no server) taken to a **phone** in Flutter. Raw
   sockets don't exist on a regular phone (iOS forbids them, Android
   restricts them to root), so this client reimplements the same
   spirit over IP: UDP broadcast discovery on the same WiFi/LAN, a TCP
   connection per peer, and end-to-end encryption negotiated per
   connection (X25519 + ChaCha20-Poly1305) instead of the original
   project's fixed global PSK.

## Table of contents

- [Course requirements](#course-requirements)
- [Repository structure](#repository-structure)
- [How to run each client](#how-to-run-each-client)
- [Architecture in one line](#architecture-in-one-line)
- [Interesting pieces of code](#interesting-pieces-of-code)
- [Authors](#authors)

## Course requirements

From [`req/linkchat.md`](req/linkchat.md):

| Requirement | Status |
|---|---|
| Computer-to-computer messaging | ✅ |
| Peer-to-peer file exchange | ✅ |
| Console interface | ✅ |
| Docker (virtualized network) + physical network | ✅ |
| Any file/message size | ✅ (chunking + ACK/retry) |
| Automatic peer discovery | ✅ (beacons) |
| One-to-all messaging | ✅ (`/sendtoall`) |
| Folder send/receive | ✅ (`/senddir`, tar.gz) |
| Security layer | ✅ (ChaCha20-Poly1305 AEAD) |
| Visual interface (GUI, UX, smoothness, error handling) | ✅ (PyQt6) |
| Creativity | ✅ **Link-Chat Mobile** — the same idea, rebuilt from scratch to run on a phone |

## Repository structure

```
Link-Chat/
├── app/                 # Desktop client (Python, raw sockets)
│   ├── backend/         # Protocol, discovery, transfer, encryption
│   ├── frontend/        # Console
│   └── gui_pyqt6/       # Graphical interface
├── main.py              # Desktop client entry point
├── docker/              # Dockerfiles, docker-compose.yml, and deploy scripts
├── docs/                # RUNNING_APP.md, GUION_EXPOSICION.md
├── req/linkchat.md      # Original course assignment
│
└── mobile/              # Flutter client (Android/iOS)
    ├── lib/network/     # UDP discovery, TCP connection, encryption, framing
    ├── lib/services/    # Identity, chat persistence, file transfer
    ├── lib/ui/          # Screens (peers, chat, settings)
    ├── test/            # Unit tests + two-real-peer socket integration
    └── SETUP.md         # How to generate android/ios, build, and test
```

## How to run each client

- **Desktop**: see [`docs/RUNNING_APP.md`](docs/RUNNING_APP.md) (Docker
  scripts in [`docker/`](docker): `build_images.sh`, `create_network.sh`,
  `run_container.sh`, `deploy_linkchat.sh`). Also runs directly with
  `python main.py` if you have raw-socket permissions (root/CAP_NET_RAW)
  on Linux.
- **Mobile**: see [`mobile/SETUP.md`](mobile/SETUP.md) — install the
  Flutter SDK, generate `android/`/`ios/`, `flutter pub get`, and run on
  two devices on the same WiFi to see discovery and messaging in action.

## Architecture in one line

- **Desktop**: Ethernet frame → manual framing (flags + bit-stuffing +
  CRC16) → ChaCha20-Poly1305 AEAD with a global PSK → ACK with manual
  retries, because the link layer offers no delivery guarantee at all.
- **Mobile**: UDP for discovery (beacons), one TCP connection per peer
  for everything else → simple length-prefixed framing → X25519
  handshake per connection → ChaCha20-Poly1305 AEAD with a session key
  → no manual ACK/retry for data, because TCP already guarantees
  ordered, complete delivery.

## Interesting pieces of code

A few entry points if you want to see the project without reading it
end to end:

- [`app/backend/core/raw_socket.py`](app/backend/core/raw_socket.py) —
  a raw AF_PACKET socket, filtered by a custom EtherType, without
  touching IP/TCP/UDP.
- [`app/backend/utils/frame_helper.py`](app/backend/utils/frame_helper.py) —
  manual framing with flags, bit-stuffing, CRC16, and AEAD encryption,
  because none of that comes for free at the link layer.
- [`app/backend/core/file_transfer.py`](app/backend/core/file_transfer.py)
  ([line `recent_seqs`](app/backend/core/file_transfer.py#L441)) — a
  sliding-window transfer protocol; that's where the fix lives for a
  real corruption bug from duplicated chunks that I found running two
  real Docker containers against each other
  ([commit `7694c3b`](https://github.com/JuanCMath/Link-Chat/commit/7694c3b)).
- [`mobile/lib/network/crypto_session.dart`](mobile/lib/network/crypto_session.dart) —
  X25519 + HKDF + ChaCha20-Poly1305 handshake negotiated per connection,
  instead of the desktop client's fixed global PSK.
- [`mobile/lib/network/peer_connection.dart`](mobile/lib/network/peer_connection.dart#L52)
  (use of `asyncMap`) — fix for a real race condition: frames decrypted
  out of order when several arrive together in a single TCP read.
- [`mobile/test/two_peers_integration_test.dart`](mobile/test/two_peers_integration_test.dart) —
  an integration test that spins up two real peers talking over real
  UDP/TCP sockets (no mocks); that's how the two bugs above were found.

## Authors

- [Sebastian González Alfonso](https://t.me/sebagonz106)
- [Juan Carlos Carmenate Díaz](https://t.me/Juank404)
