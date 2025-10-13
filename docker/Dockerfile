# Console-focused Dockerfile for exercising Link-Chat without the GUI
# Build with:
#   docker build -f docker/testing/Dockerfile.console -t linkchat-console .
# Run (with MACVLAN or host networking as appropriate):
#   docker run --rm -it --net linkchat-macvlan --cap-add=NET_ADMIN --cap-add=NET_RAW \
#       -e LINKCHAT_INTERFACE=eth0 linkchat-console

FROM linkchat-base:latest

LABEL description="Console test image for Link-Chat"

COPY pyproject.toml ./
COPY linkchat/ ./linkchat/

RUN pip install --no-cache-dir -e .

ENV LINKCHAT_INTERFACE=eth0 \
    LINKCHAT_NODE="docker-cli" \
    LINKCHAT_DOWNLOAD_DIR=/app/downloads \
    PYTHONUNBUFFERED=1

WORKDIR /app

CMD ["python", "-m", "linkchat.app.cli_main"]
