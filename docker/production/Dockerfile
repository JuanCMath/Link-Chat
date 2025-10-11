FROM python:3.13-slim

# Install system dependencies for PyQt6
RUN apt-get update && apt-get install -y \
    # PyQt6 GUI dependencies
    libgl1 \
    libglib2.0-0 \
    libdbus-1-3 \
    libxcb-xinerama0 \
    libxcb-icccm4 \
    libxcb-image0 \
    libxcb-keysyms1 \
    libxcb-randr0 \
    libxcb-render-util0 \
    libxcb-shape0 \
    libxkbcommon-x11-0 \
    # EGL and OpenGL ES (REQUIRED for PyQt6)
    libegl1 \
    libgles2 \
    libxcb-glx0 \
    libxcb-cursor0 \
    # X11 libraries
    libx11-xcb1 \
    libxrender1 \
    libxi6 \
    libsm6 \
    libice6 \
    # Fonts for GUI
    fontconfig \
    # Network debugging tools
    net-tools \
    iproute2 \
    iputils-ping \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy dependency files
COPY pyproject.toml ./

# Install Python dependencies
RUN pip install --no-cache-dir PyQt6>=6.6

# Copy application code
COPY linkchat/ ./linkchat/

# Create downloads directory
RUN mkdir -p /app/downloads

# Environment variables
ENV PYTHONUNBUFFERED=1
ENV QT_QPA_PLATFORM=xcb

# Default interface (can be overridden)
ENV INTERFACE=wlan0

# Default command
CMD ["python", "-m", "linkchat.app.qt_main"]
