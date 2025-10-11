#!/bin/bash
# Link-Chat Docker Build Script (Bash)
# Builds base image first, then derived images for fast rebuilds

set -e

TARGET="${1:-all}"
NO_CACHE=""

if [ "$2" = "--no-cache" ]; then
    NO_CACHE="--no-cache"
fi

echo "========================================"
echo "  Link-Chat Docker Build Script"
echo "========================================"
echo ""

build_base() {
    echo -e "\033[1;33m[1/4] Building BASE image (linkchat-base)...\033[0m"
    echo -e "\033[0;37m  This includes all system dependencies and PyQt6\033[0m"
    echo -e "\033[0;37m  Size: ~800MB | Time: ~5-10 minutes\033[0m"
    echo ""
    
    docker build $NO_CACHE -f docker/base/Dockerfile.base -t linkchat-base:latest .
    
    echo -e "\033[1;32m✅ Base image built successfully!\033[0m"
    echo ""
}

build_test() {
    echo -e "\033[1;33m[2/4] Building TEST image (linkchat-test)...\033[0m"
    echo -e "\033[0;37m  Fast build using base image\033[0m"
    echo -e "\033[0;37m  Size: ~800MB | Time: ~30 seconds\033[0m"
    echo ""
    
    docker build $NO_CACHE -f docker/testing/Dockerfile.test.new -t linkchat-test .
    
    echo -e "\033[1;32m✅ Test image built successfully!\033[0m"
    echo ""
}

build_interactive() {
    echo -e "\033[1;33m[3/4] Building INTERACTIVE image (linkchat-interactive)...\033[0m"
    echo -e "\033[0;37m  Fast build using base image\033[0m"
    echo -e "\033[0;37m  Size: ~800MB | Time: ~30 seconds\033[0m"
    echo ""
    
    docker build $NO_CACHE -f docker/testing/Dockerfile.interactive.new -t linkchat-interactive .
    
    echo -e "\033[1;32m✅ Interactive image built successfully!\033[0m"
    echo ""
}

build_production() {
    echo -e "\033[1;33m[4/4] Building PRODUCTION image (linkchat-production)...\033[0m"
    echo -e "\033[0;37m  Fast build using base image\033[0m"
    echo -e "\033[0;37m  Size: ~800MB | Time: ~30 seconds\033[0m"
    echo ""
    
    docker build $NO_CACHE -f docker/production/Dockerfile.new -t linkchat-production .
    
    echo -e "\033[1;32m✅ Production image built successfully!\033[0m"
    echo ""
}

build_alpine_base() {
    echo -e "\033[1;33m[5/8] Building ALPINE BASE image (linkchat-base-alpine)...\033[0m"
    echo -e "\033[1;31m  ⚠️  WARNING: This takes 40-60 minutes (PyQt6 compilation)\033[0m"
    echo -e "\033[0;37m  But only needs to be done ONCE!\033[0m"
    echo -e "\033[0;37m  Size: ~600-700 MB | Time: ~40-60 minutes\033[0m"
    echo ""
    
    docker build $NO_CACHE -f docker/base/Dockerfile.base.alpine -t linkchat-base-alpine:latest .
    
    echo -e "\033[1;32m✅ Alpine base image built successfully!\033[0m"
    echo ""
}

build_alpine_interactive() {
    echo -e "\033[1;33m[6/8] Building ALPINE INTERACTIVE image (linkchat-interactive-alpine)...\033[0m"
    echo -e "\033[0;37m  Fast build using Alpine base image\033[0m"
    echo -e "\033[0;37m  Size: ~600-700 MB | Time: ~30 seconds\033[0m"
    echo ""
    
    docker build $NO_CACHE -f docker/testing/Dockerfile.interactive.alpine -t linkchat-interactive-alpine .
    
    echo -e "\033[1;32m✅ Alpine interactive image built successfully!\033[0m"
    echo ""
}

build_alpine_production() {
    echo -e "\033[1;33m[7/8] Building ALPINE PRODUCTION image (linkchat-production-alpine)...\033[0m"
    echo -e "\033[0;37m  Fast build using Alpine base image\033[0m"
    echo -e "\033[0;37m  Size: ~500-600 MB (smaller after cleanup) | Time: ~30 seconds\033[0m"
    echo ""
    
    docker build $NO_CACHE -f docker/production/Dockerfile.alpine -t linkchat-production-alpine .
    
    echo -e "\033[1;32m✅ Alpine production image built successfully!\033[0m"
    echo ""
}

# Main build logic
case "$TARGET" in
    base)
        build_base
        ;;
    base-alpine)
        build_alpine_base
        ;;
    test)
        build_test
        ;;
    interactive)
        build_interactive
        ;;
    interactive-alpine)
        build_alpine_interactive
        ;;
    production)
        build_production
        ;;
    production-alpine)
        build_alpine_production
        ;;
    debian)
        build_base
        build_test
        build_interactive
        build_production
        ;;
    alpine)
        build_alpine_base
        build_alpine_interactive
        build_alpine_production
        ;;
    all)
        echo -e "\033[1;36mBuilding ALL images (Debian + Alpine)...\033[0m"
        echo -e "\033[1;33mThis will take 60-90 minutes total!\033[0m"
        echo ""
        build_base
        build_test
        build_interactive
        build_production
        build_alpine_base
        build_alpine_interactive
        build_alpine_production
        ;;
    *)
        echo "Usage: $0 {all|base|base-alpine|test|interactive|interactive-alpine|production|production-alpine|debian|alpine} [--no-cache]"
        exit 1
        ;;
esac

echo "========================================"
echo "  Build Complete!"
echo "========================================"
echo ""
echo -e "\033[1;33mAvailable images:\033[0m"
docker images | grep linkchat
echo ""
echo -e "\033[1;33mQuick Start Commands:\033[0m"
echo ""
echo -e "\033[1;36m  DEBIAN IMAGES:\033[0m"
echo -e "\033[0;37m    Run tests:       docker run --rm linkchat-test\033[0m"
echo -e "\033[0;37m    Interactive:     docker run -it --rm linkchat-interactive\033[0m"
echo -e "\033[0;37m    Production:      docker run -it --rm linkchat-production\033[0m"
echo ""
echo -e "\033[1;36m  ALPINE IMAGES (smaller):\033[0m"
echo -e "\033[0;37m    Interactive:     docker run -it --rm linkchat-interactive-alpine\033[0m"
echo -e "\033[0;37m    Production:      docker run -it --rm linkchat-production-alpine\033[0m"
echo ""
echo -e "\033[1;36m  GUI MODE (requires X11 server):\033[0m"
echo -e "\033[0;37m    docker run -it --rm -e DISPLAY=host.docker.internal:0 linkchat-interactive python -m linkchat.app.qt_main\033[0m"
echo ""
