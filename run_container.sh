#!/usr/bin/env bash


# run_container.sh
# ----------------
# Lanza un contenedor Link-Chat.
# Argumentos:
#   $1 - Nombre del contenedor (opcional). Default: LinkChatNode
#   $2 - Directorio host a montar en /data (opcional). Default: ./data/Local
#   $3 - Red Docker a usar (opcional). Default: linknet (o 'host' para modo host)
#
# Variables de entorno exportables (si no se pasan, se usan los valores por defecto):
#   NAME, IFACE, ETHERTYPE, BEACON_INTERVAL
#
# Ejemplo simple:
#   ./run_container.sh MyNode ./data/MyNode linknet
#

NAME=${1:-LinkChatNode}
HOST_DATA_DIR=${2:-./data/Local}
NETWORK=${3:-linknet}
IMAGE=${IMAGE:-linkchat}

# Valores por defecto para variables usadas por la app
: ${NAME_ENV:=${NAME}}
: ${IFACE:=${IFACE:-eth0}}
: ${ETHERTYPE:=${ETHERTYPE:-0x88B5}}
: ${BEACON_INTERVAL:=${BEACON_INTERVAL:-5}}

# Aseguramos el directorio de datos en el host (crea los padres si es necesario y no falla si el directorio existe)
mkdir -p "$HOST_DATA_DIR"

# Eliminamos contenedor previo con el mismo nombre para recrearlo limpio
if docker ps -a --format '{{.Names}}' | grep -Eq "^${NAME}$"; then

  echo "[run] eliminando contenedor previo: $NAME"

  docker rm -f "$NAME"
fi


# Si la red es 'host', usamos --network host
if [ "$NETWORK" = "host" ]; then
  NET_ARG="--network=host"
else
  # Allow simple keyword 'macvlan' to refer to the created network name
  if [ "$NETWORK" = "macvlan" ]; then
    NETWORK="linknet_macvlan"
  fi
  NET_ARG="--network=$NETWORK"
fi


# Comando run:
#  --rm         : eliminar el contenedor al salir
#  -it          : interacción + TTY para consola
#  --name       : nombre del contenedor
#  --cap-add    : permisos necesarios para raw sockets (NET_RAW)
#  --network    : red a usar (linknet, linknet_macvlan, o host)
#  -v           : monta datos persistentes en /data
#  -e           : variables de entorno para la aplicación

docker run --rm -it \
  --name "$NAME" \
  --cap-add NET_RAW \
  $NET_ARG \
  -v "$(pwd)/$HOST_DATA_DIR:/data" \
  -e NAME="$NAME_ENV" \
  -e IFACE="$IFACE" \
  -e ETHERTYPE="$ETHERTYPE" \
  -e BEACON_INTERVAL="$BEACON_INTERVAL" \
  $IMAGE
