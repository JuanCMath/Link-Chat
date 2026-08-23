# Guion de exposición — Link-Chat

Enfoque: demo en vivo del cliente de escritorio + recorrido de código del
cliente móvil (sin correrlo en vivo).

## Parte 1 — Demo en vivo (escritorio)

Dos terminales, dos nodos Docker en la misma red virtual.

### Setup (antes de la clase, para no perder tiempo en vivo)

```bash
chmod +x build_images.sh create_network.sh run_container.sh deploy_linkchat.sh
./deploy_linkchat.sh NodoA ./data/NodoA linknet
```

En otra terminal:

```bash
./run_container.sh NodoB ./data/NodoB linknet
```

Esto entra directo a la consola interactiva de cada nodo (`docker attach` lo
hace `run_container.sh`; si no, `docker attach NodoA` / `docker attach NodoB`).

### Guion de comandos (decir en voz alta qué requisito cubre cada uno)

En **NodoA**:
```
/me
```
→ Muestra la MAC y el nombre del nodo — identificación en la red.

```
/peers
```
→ Debería aparecer NodoB solo, sin configurar nada — **descubrimiento
automático** por beacons cada 5s (bonus 0.25).

```
/peer NodoB
Hola desde NodoA!
```
→ Mensajería punto a punto (requisito mínimo). Mostrar en NodoB que llega
con `[rx ... → ...]`.

```
/sendfile NodoB /data/algun_archivo.bin
```
→ Transferencia de archivo (requisito mínimo + "cualquier tamaño", bonus
0.5 — usar un archivo de varios MB para que se note el chunking).

```
/senddir NodoB /data/alguna_carpeta
```
→ Envío de carpetas completas (bonus 0.25) — se empaqueta en `.tar.gz`, se
manda, y se desempaqueta solo del otro lado reemplazando la carpeta.

```
/sendtoall Hola a todos!
```
→ Mensajería de uno a todos (bonus 0.25) — con un tercer nodo conectado se
nota mejor.

Mencionar sin necesariamente mostrar el JSON: cada frame va cifrado con
**ChaCha20-Poly1305** (capa de seguridad, bonus 0.5) — se puede abrir
[`app/backend/utils/frame_helper.py`](app/backend/utils/frame_helper.py) un
momento para señalar `encode_frame`/`decode_frame`.

Si da tiempo, abrir la **GUI** (`python -m app.gui_pyqt6.gui` o elegir "y"
al arrancar `main.py`) para mostrar la interfaz visual (bonus 1.0 en sus
cuatro sub-criterios: interfaz alternativa, UX, fluidez, manejo de errores).

### Qué decir sobre la arquitectura mientras corre

Todo esto pasa **a nivel de enlace** (Ethernet, EtherType `0x88B5`), sin
tocar IP ni TCP/UDP — por eso corre en Docker con `--cap-add NET_RAW` y por
eso el envío/recepción tiene que resolver a mano cosas que en capas
superiores da gratis el sistema operativo: framing con flags y bit-stuffing,
CRC16, ACK con reintentos. Eso es justo el gancho para pasar a la parte 2.

## Parte 2 — Recorrido de código (móvil, sin correr)

Frase de transición: *"Sockets raw no existen en un teléfono — iOS los
prohíbe, Android los restringe a root. Así que en vez de forzarlo, rehicimos
el mismo problema (mensajería + archivos, punto a punto, sin servidor) sobre
lo que sí hay en un teléfono: WiFi normal."*

Mostrar en este orden (todo dentro de [`mobile/`](mobile)):

1. **[`lib/network/discovery_service.dart`](mobile/lib/network/discovery_service.dart)**
   — comparar con
   [`app/backend/peer_management/peer_discovery.py`](app/backend/peer_management/peer_discovery.py)
   del escritorio: misma idea (beacon periódico + registro de pares), pero
   `broadcast UDP` en vez de frame Ethernet, porque un teléfono no puede
   abrir un socket raw.

2. **[`lib/network/crypto_session.dart`](mobile/lib/network/crypto_session.dart)**
   — la mejora real de seguridad: el escritorio usa una **clave
   pre-compartida global** (`LINKCHAT_PSK`); el móvil negocia una clave de
   sesión distinta **por conexión** con un handshake X25519 (Diffie-Hellman
   en curva elíptica) + HKDF, y recién ahí cifra con ChaCha20-Poly1305 igual
   que el escritorio.

3. **[`lib/network/peer_connection.dart`](mobile/lib/network/peer_connection.dart)**
   línea del `asyncMap` — contar la historia corta: al escribir un test que
   hacía correr dos peers reales hablando por socket, apareció un bug de
   concurrencia real (un frame de "archivo completo" se procesaba antes que
   el último pedazo del archivo si llegaban juntos en la misma lectura TCP).
   Buen momento para mostrar
   [`test/two_peers_integration_test.dart`](mobile/test/two_peers_integration_test.dart)
   y decir que ese test corre dos "dispositivos" completos en la misma
   máquina, con sockets de verdad, no mocks — y que fue así como se encontró
   el bug.

4. **[`lib/services/file_transfer_service.dart`](mobile/lib/services/file_transfer_service.dart)**
   — mencionar por qué es más simple que el del escritorio
   ([`app/backend/core/file_transfer.py`](app/backend/core/file_transfer.py)):
   TCP ya garantiza orden y entrega, así que no hace falta ventana
   deslizante ni ACK/retry manual por chunk — solo el handshake de
   oferta/aceptación.

5. Cerrar con una pantalla de la UI (`lib/ui/chat_screen.dart` o una captura)
   para que se vea que no quedó solo en la capa de red.

### Un par de preguntas que probablemente hagan (y respuesta corta)

- **"¿Por qué no reusaron el mismo protocolo?"** — porque el protocolo
  original depende de que cada `recv()` devuelva un frame completo (eso da
  gratis AF_PACKET); sobre TCP eso no existe, así que hubo que rediseñar el
  framing, aunque el cifrado (ChaCha20-Poly1305) se mantuvo como idea.
- **"¿Funciona por datos móviles?"** — no, mismo alcance que el original:
  requiere estar en la misma red local (WiFi), no hay NAT traversal ni
  servidor de señalización.
- **"¿Lo probaron de verdad?"** — sí, ver
  [`mobile/test/two_peers_integration_test.dart`](mobile/test/two_peers_integration_test.dart):
  dos peers reales, sockets reales, sin mocks, incluyendo el bug que
  encontró.
