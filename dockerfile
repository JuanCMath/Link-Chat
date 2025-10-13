FROM python:3.13-slim

WORKDIR /app
COPY app/ ./

# No librerías externas: usamos solo stdlib
# Para ver MAC y usar AF_PACKET se requieren capacidades de red (compose lo añadirá)

ENTRYPOINT [ "python", "/app/linkchat.py" ]
