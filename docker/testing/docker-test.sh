#!/bin/bash
# Script to run tests in Docker container (Linux environment)

set -e

echo "Building test container..."
docker build -f Dockerfile.test -t linkchat-test .

echo ""
echo "Running tests in Alpine Linux container..."
docker run --rm linkchat-test

echo ""
echo "✅ All tests passed in Linux environment!"
