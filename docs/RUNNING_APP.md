# Ejecutar Link-Chat (Guía rápida)

Cómo iniciar una instancia de Link-Chat en Docker con los scripts incluidos
en [`docker/`](../docker).

## Resumen

Cuatro scripts, pensados para correr desde una shell compatible con Bash
(WSL, Git Bash, Linux/macOS), **siempre desde dentro de la carpeta `docker/`**:

- `build_images.sh` — construye las imágenes Docker: la base (`linkchat-base`)
  y la de la aplicación (`linkchat`).
- `create_network.sh` — crea la red Docker que usarán los contenedores
  (`bridge` por defecto; soporta `macvlan` y `host`).
- `run_container.sh` — ejecuta un contenedor de Link-Chat con nombre, volumen
  `/data` y variables de entorno.
- `deploy_linkchat.sh` — comando único que ejecuta los tres pasos anteriores
  en orden.

## Requisitos previos

- Docker instalado y funcionando en el host.
- Permisos para ejecutar Docker (miembro del grupo `docker` o uso de `sudo`).
- Para `macvlan`, la interfaz padre (`PARENT`) debe existir y soportar
  macvlan (no todas las interfaces WiFi lo hacen).

## Empezar

1. Hacer ejecutables los scripts (solo la primera vez):

   ```bash
   cd docker
   chmod +x build_images.sh create_network.sh run_container.sh deploy_linkchat.sh
   ```

2. Ejecutar el despliegue completo:

   ```bash
   ./deploy_linkchat.sh MyNode ../data/MyNode linknet
   ```

   Con `macvlan`:

   ```bash
   export PARENT=eth0
   ./deploy_linkchat.sh MyNode ../data/MyNode macvlan
   ```

   Esto construye las imágenes, crea la red `linknet` (modo `bridge` por
   defecto) y arranca un contenedor llamado `MyNode` con los datos
   persistidos en `data/MyNode` en la raíz del repo.

3. Alternativa: ejecutar los pasos por separado

   ```bash
   ./build_images.sh
   ./create_network.sh
   ./run_container.sh MyNode ../data/MyNode linknet
   ```

## Opciones de red

- **bridge** (predeterminado): aislamiento seguro y sencillo, ideal para
  probar entre contenedores locales.
- **host**: el contenedor comparte la pila de red del host. Útil para
  pruebas avanzadas, pero menos aislado.
- **macvlan**: el contenedor obtiene una IP en la misma LAN que el host.
  Avanzado — exige una interfaz física compatible.

## Dónde se almacenan los datos

El contenedor usa `/data` para pares, bandeja de entrada de archivos y
descargas. Con `./run_container.sh MyNode ../data/MyNode ...`, esos datos
quedan en `data/MyNode` en la raíz del repo (el segundo argumento es
relativo a la carpeta `docker/`, por eso el `../`).

## Cambiar el nombre del nodo

Pasá un nombre de contenedor distinto (por ejemplo `MyNode`) al ejecutar
`deploy_linkchat.sh` o `run_container.sh`.

## Problemas comunes

- **Docker no encontrado**: instalá Docker y asegurate de que el servicio
  esté activo.
- **Permisos**: si recibís errores de permiso, probá `sudo` o agregá tu
  usuario al grupo `docker`.
- **macvlan no funciona**: verificá que tu interfaz (`PARENT`) soporte
  macvlan; muchas interfaces WiFi no lo hacen.

## Ayuda y soporte

- [Sebastian González Alfonso](https://t.me/sebagonz106)
- [Juan Carlos Carmenate Díaz](https://t.me/Juank404)
