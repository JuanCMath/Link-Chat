# Link-Chat Mobile — puesta en marcha

Este cliente Flutter vive en `Link-Chat/mobile/` y es independiente del
proyecto de escritorio/curso en `Link-Chat/app/` (sockets raw, no lo toca).

**Estado actual**: se instaló Flutter 3.47.1 / Dart 3.13.1 en el entorno de
desarrollo y ya se corrió todo el ciclo de verificación estática:
`flutter create` generó `android/` e `ios/` reales (no a mano), los permisos
de [`platform_snippets/`](platform_snippets) ya están aplicados en
`android/app/src/main/AndroidManifest.xml` e `ios/Runner/Info.plist`,
`flutter pub get` resolvió las 88 dependencias sin conflictos y `flutter
analyze` no reporta issues.

Además de los tests unitarios de framing y criptografía, hay un test de
integración real en
[`test/two_peers_integration_test.dart`](test/two_peers_integration_test.dart)
que levanta dos peers completos (identidad, `ConnectionManager`,
`FileTransferService`) como procesos reales en esta máquina y los hace
hablar por sockets UDP/TCP de verdad — sin mocks de red: descubrimiento por
beacon UDP, handshake X25519, cifrado ChaCha20-Poly1305, un mensaje de chat
y una transferencia de archivo de 200KB verificada byte a byte. Esa prueba
encontró y confirmó arreglar un bug real de concurrencia: `PeerConnection`
procesaba cada frame descifrado con un callback `async` sin garantizar
orden, así que un frame `FILE_DONE` podía completarse antes que el último
`FILE_CHUNK` si ambos llegaban juntos en una misma lectura TCP (algo común
en LAN rápida) — corregido en
[`lib/network/peer_connection.dart`](lib/network/peer_connection.dart)
usando `asyncMap` en vez de `listen` para procesar los frames en orden. Es
decir: no es solo código revisado y con lint limpio, es un protocolo que se
probó de verdad hablando consigo mismo por la red y ya tuvo un bug real
encontrado y arreglado gracias a eso.

Lo que sigue faltando es exactamente lo que ningún entorno de desarrollo
puede simular por sí solo: correr la app en dos **dispositivos** reales en
la misma WiFi, con la UI real, para confirmar que el descubrimiento y la
mensajería se sienten bien de punta a punta.

Nota sobre Android: el SDK de Android presente tiene las plataformas
`android-34`/`36.1` y `adb`, pero le falta el componente `cmdline-tools` y no
tiene ningún system-image, así que no hay forma de compilar un APK ni de
crear un emulador (AVD) ahí mismo todavía — y aunque lo hubiera, dos
emuladores Android por separado normalmente no comparten el mismo dominio de
broadcast, así que el descubrimiento UDP no funcionaría entre ellos de todas
formas. La prueba real solo tiene sentido con dispositivos físicos.

## 1. Requisitos (en tu propia máquina)

- Flutter SDK (canal stable) instalado y en el PATH — `flutter --version`
  debe funcionar.
- Para Android: Android Studio o solo el SDK + un emulador o teléfono con
  depuración USB.
- Para iOS: Xcode (solo en macOS) + un simulador o iPhone.

## 2. Instalar dependencias y compilar

```bash
flutter pub get
flutter analyze
flutter test
```

Deberían pasar sin cambios (ya se corrieron aquí); repetirlos en tu máquina
solo confirma que tu propio SDK/versiones de paquetes se llevan igual de
bien con el código.

## 3. Probar el flujo punto-a-punto real

Se necesitan **dos dispositivos** en la misma red WiFi (dos teléfonos
físicos son lo más confiable; dos emuladores Android en modo bridge también
sirven si el host lo permite):

```bash
flutter run -d <device-id-1>   # en una terminal
flutter run -d <device-id-2>   # en otra
```

(`flutter devices` lista los ids disponibles.)

En ambos deberían aparecer el uno al otro en la lista de pares en unos
segundos (beacon UDP cada ~3s, puerto 47500). Desde ahí:

1. Tocar un peer para abrir el chat y mandar un mensaje de texto.
2. Confirmar que el estado del mensaje pasa de reloj → check → doble check
   (enviado → entregado).
3. Adjuntar un archivo pequeño (📎) y aceptar la oferta en el otro
   dispositivo; verificar la barra de progreso y que el archivo llega a
   `Documentos de la app/inbox/`.
4. Probar "Enviar a todos" con más de un peer conectado.

## Limitaciones conocidas (ver plan)

- La app debe estar en primer plano para descubrir pares y mantener
  conexiones — iOS suspende sockets en background y Android los restringe
  sin un foreground service (no implementado en esta v1).
- El descubrimiento solo funciona dentro del mismo segmento WiFi/LAN (no hay
  NAT traversal ni servidor de señalización).
- Transferencia de carpetas completas no está soportada en móvil (sí sigue
  disponible en el cliente de escritorio).
