#!/usr/bin/env bash


# build_images.sh
# ----------------
# Construye las imágenes Docker necesarias para Link-Chat:
#  - Imagen base a partir de `dockerfile.base` (tag: linkchat-base)
#  - Imagen de la aplicación a partir de `Dockerfile` (tag: linkchat)

echo "[build] Construyendo imagen base (dockerfile.base -> linkchat-base)"
# Construye la imagen base que instala dependencias del sistema y paquetes Python.
# iproute2 y cryptography se instalan en la capa base.

docker build -f dockerfile.base -t linkchat-base .

echo "[build] Construyendo imagen de la aplicación (Dockerfile -> linkchat)"
# Construye la imagen de la aplicación que copia el código y define el ENTRYPOINT.

docker build -f Dockerfile -t linkchat .

echo "[build] Imágenes listas: linkchat-base, linkchat"
