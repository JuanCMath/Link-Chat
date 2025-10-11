# Run Link-Chat directly in WSL2 (without Docker)
# This bypasses Docker's AF_PACKET limitations on WSL2

Write-Host "=========================================="
Write-Host "  Link-Chat WSL2 Direct Mode"
Write-Host "=========================================="
Write-Host ""

Write-Host "Starting Link-Chat in WSL2..."
Write-Host "Note: This runs outside Docker to avoid WSL2 networking limitations"
Write-Host ""

# Run in WSL2 with sudo
# Using escaped path to handle special characters
wsl bash -c "cd /mnt/d/UH/Año\ 3/Redes/Link-Chat && export DISPLAY=:0 && sudo python3 -m linkchat.app.qt_main"
