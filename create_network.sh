#!/usr/bin/env bash


# create_network.sh
# ------------------
# Crea una red Docker simple para Link-Chat.
# El primer argumento puede ser el tipo de red: bridge (por defecto), macvlan o host.
# - bridge: crea una red bridge llamada 'linknet'
# - macvlan: crea una red macvlan llamada 'linknet_macvlan' (requiere PARENT)
#
# Uso:
#   ./create_network.sh [bridge|macvlan]
# Ejemplos:
#   ./create_network.sh                      # crea red bridge 'linknet'
#   PARENT=eth0 ./create_network.sh macvlan  # crea macvlan con parent eth0

MODE=${1:-bridge}


if [ "$MODE" = "macvlan" ]; then
  # Para macvlan se necesita la interfaz padre
  if [ -z "${PARENT:-}" ]; then
    echo "[network] ERROR: para macvlan debe exportar PARENT (ej. PARENT=eth0)"
    exit 1
  fi

  echo "[network] Creando red macvlan 'linknet_macvlan' con parent=$PARENT"
  
# Asigna a cada contenedor una MAC propia y los coloca en la red parent como si fueran dispositivos físicos
  docker network create -d macvlan --subnet=192.168.100.0/24 --gateway=192.168.100.1 -o parent=$PARENT linknet_macvlan

  echo "[network] creada: linknet_macvlan"
  exit 0
fi

# Default: bridge
echo "[network] Creando red bridge 'linknet' (si no existe)"

if docker network inspect linknet; then

  echo "[network] ya existe la red 'linknet'"

else
  docker network create --driver bridge linknet

  echo "[network] creada: linknet"
fi
