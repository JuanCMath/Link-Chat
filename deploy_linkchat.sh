#!/usr/bin/env bash


# deploy_linkchat.sh
# ------------------
# Wrapper simple que integra los tres pasos principales:
# 1) build_images.sh
# 2) create_network.sh
# 3) run_container.sh
#
# Uso:
#   ./deploy_linkchat.sh [container_name] [host_data_dir] [network_mode]
# Ejemplo:
#   ./deploy_linkchat.sh MyNode ./data/MyNode linknet
#

set -eu

NAME=${1:-LinkChatNode}
HOST_DATA_DIR=${2:-./data/Local}
NETWORK=${3:-linknet}
PARENT=${PARENT:-eth0}

printf '[deploy] 1/3 -> build_images.sh (construir imágenes)\n'
./build_images.sh

printf '[deploy] 2/3 -> create_network.sh %s (crear red)\n' "$NETWORK"
./create_network.sh "$NETWORK"

printf '[deploy] 3/3 -> run_container.sh %s %s %s (lanzar contenedor)\n' "$NAME" "$HOST_DATA_DIR" "$NETWORK"
./run_container.sh "$NAME" "$HOST_DATA_DIR" "$NETWORK"

printf '[deploy] terminado.\n'

