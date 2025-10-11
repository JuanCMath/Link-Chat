# Setup MACVLAN network for Link-Chat (Windows/WSL2)
# Note: Link-Chat operates at Layer 2 (Ethernet frames with MAC addresses)
# IP addresses are only used by Docker for network management, NOT by Link-Chat protocol

$ErrorActionPreference = "Stop"

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "  Link-Chat MACVLAN Network Setup" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Note: Link-Chat uses Layer 2 (MAC addresses only)" -ForegroundColor Yellow
Write-Host "IP configuration is for Docker management, not the chat protocol" -ForegroundColor Yellow
Write-Host ""

# Check if running in WSL or need to delegate to WSL
if ($env:OS -eq "Windows_NT") {
    Write-Host "Windows detected - delegating to WSL2..." -ForegroundColor Cyan
    Write-Host ""
    
    # Check if WSL is available
    try {
        wsl --status | Out-Null
    } catch {
        Write-Host "❌ WSL2 is not installed or not running" -ForegroundColor Red
        Write-Host ""
        Write-Host "Please install WSL2:" -ForegroundColor Yellow
        Write-Host "  wsl --install" -ForegroundColor Gray
        exit 1
    }
    
    # Get WSL project path
    $currentPath = (Get-Location).Path
    $wslPath = $currentPath -replace '^([A-Z]):', '/mnt/$1' -replace '\\', '/'
    $wslPath = $wslPath.ToLower()
    
    Write-Host "Running setup in WSL2..." -ForegroundColor Green
    Write-Host "Path: $wslPath" -ForegroundColor Gray
    Write-Host ""
    
    # Execute the bash script in WSL
    wsl bash "$wslPath/docker/setup-macvlan.sh"
    
    exit $LASTEXITCODE
}

# If somehow running in WSL PowerShell, inform user
Write-Host "Please run the bash version instead:" -ForegroundColor Yellow
Write-Host "  ./docker/setup-macvlan.sh" -ForegroundColor Gray
