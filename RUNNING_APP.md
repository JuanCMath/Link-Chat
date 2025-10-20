RUNNING_APP.md
===============

Cómo ejecutar Link-Chat con los scripts incluidos

Resumen
-------
Este repositorio contiene tres scripts principales para trabajar con Docker:

- `build_images.sh`  - Construye las imágenes Docker: la imagen base (`linkchat-base`) y la imagen de la aplicación (`linkchat`).
- `create_network.sh` - Crea la red Docker que usarán los contenedores (`bridge` por defecto; soporta `macvlan` y `host`).
- `run_container.sh` - Ejecuta un contenedor de Link-Chat con nombre, volumen `/data` y variables de entorno.

Los scripts están pensados para ejecutarse desde WSL o una shell compatible con Bash. Son intencionalmente simples y documentados línea a línea.

Requisitos previos
------------------
- Docker instalado y funcionando en el host.
- Permisos para ejecutar Docker (miembro del grupo `docker` o uso de sudo).
- Para `macvlan`, la interfaz padre (`PARENT`) debe existir y soportar macvlan (no todas las interfaces Wi‑Fi lo hacen).

Scripts y ejemplos
------------------

1) Construir las imágenes

El script `build_images.sh` compila dos imágenes:

```bash
chmod +x build_images.sh
./build_images.sh
```

- `docker build -f dockerfile.base -t linkchat-base .`  
  Construye la imagen base que instala dependencias del sistema (por ejemplo `iproute2`) y paquetes Python necesarios.

- `docker build -f Dockerfile -t linkchat .`  
  Construye la imagen de la aplicación que copia el código y establece el ENTRYPOINT (ejecuta `python main.py`).

2) Crear la red Docker

El script `create_network.sh` crea una red según el modo elegido.
# Ejecutar Link-Chat (Guía rápida)

Esta guía explica, de forma clara y directa, cómo iniciar una instancia de Link-Chat en Docker. Está pensada para usuarios finales que desean ejecutar la aplicación con los comandos incluidos en el repositorio.

Resumen rápido
--------------
Link-Chat puede ejecutarse localmente dentro de un contenedor Docker. El repositorio incluye tres scripts auxiliares y un script de despliegue que los combina:

- `build_images.sh` — crea las imágenes Docker necesarias.
- `create_network.sh` — configura la red Docker a usar (opciones: `bridge`, `host`, `macvlan`).
- `run_container.sh` — inicia la aplicación dentro de un contenedor, montando la carpeta de datos.
- `deploy_linkchat.sh` — comando único para ejecutar los pasos anteriores en orden.

Comenzar
------------------------
1. Hacer ejecutables los scripts (solo la primera vez):

```bash
chmod +x build_images.sh create_network.sh run_container.sh deploy_linkchat.sh
```

El script debe tener una shebang (por ejemplo `#!/usr/bin/env bash`) en la primera línea para que el kernel sepa qué intérprete usar cuando se ejecute directamente. Puede ejecutarse el script alternativamente usando `bash build_images.sh`

2. Ejecutar el despliegue completo:

```bash
./deploy_linkchat.sh MyNode ./data/MyNode linknet
```

```bash
export PARENT=eth0
./deploy_linkchat.sh MyNode ./data/MyNode macvlan
```

Este comando realiza, en orden: construir las imágenes, crear la red `linknet` (modo `bridge` por defecto) y arrancar un contenedor llamado `MyNode` con los datos persistidos en `./data/MyNode`.

3. Alternativa: ejecutar pasos por separado

- Construir imágenes:

```bash
./build_images.sh
```

- Crear red (bridge por defecto):

```bash
./create_network.sh
```

- Iniciar contenedor:

```bash
./run_container.sh MyNode ./data/MyNode linknet
```

Opciones de red
-----------------------------------------
- bridge (predeterminado): aislamiento seguro y sencillo para conexión de prueba entre contenedores locales. Recomendado para la mayoría de usuarios.
- host: el contenedor comparte la pila de red del host. Útil para pruebas avanzadas, pero menos aislado.
- macvlan: el contenedor obtiene una IP en la misma LAN que el host. Avanzado — exige conocimientos de red y una interfaz física compatible.

Dónde se almacenan los datos
----------------------------
El contenedor usa la ruta `/data` para almacenar pares, bandeja de entrada de archivos y descargas. Al ejecutar con `./run_container.sh MyNode ./data/MyNode ...`, esos datos permanecen en `./data/MyNode` en el host.

Cambiar el nombre del nodo
--------------------------
Para cambiar cómo se identifica su instancia en la red, pase un nombre de contenedor distinto (por ejemplo `MyNode`) al ejecutar `deploy_linkchat.sh` o `run_container.sh`.

Problemas comunes y soluciones rápidas
------------------------------------
- Docker no encontrado: instale Docker y asegúrese de que el servicio esté activo.
- Permisos: si recibe errores de permiso, pruebe `sudo` o agregue su usuario al grupo `docker`.
- macvlan no funciona: verifique que su interfaz (`PARENT`) soporte macvlan; muchas interfaces Wi‑Fi no lo hacen.


Ayuda y soporte
---------------
Si necesita más detalles técnicos o desea modificar la configuración, consulte los archivos de script en el repositorio o contacte al equipo responsable:
- [Sebastian González Alfonso](https://t.me/sebagonz106)
- [Juan Carlos Carmenate Díaz](https://t.me/Juank404) 
