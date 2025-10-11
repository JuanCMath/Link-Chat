# Run Link-Chat with MACVLAN networking (Windows/WSL2)

$ErrorActionPreference = "Stop"

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "  Link-Chat MACVLAN Runner" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

# Check if running in Windows
if ($env:OS -eq "Windows_NT") {
    Write-Host "Windows detected - delegating to WSL2..." -ForegroundColor Cyan
    Write-Host ""
    
    # Check WSL
    try {
        wsl --status | Out-Null
    } catch {
        Write-Host "❌ WSL2 is not installed" -ForegroundColor Red
        exit 1
    }
    
    # Check VcXsrv
    $vcxsrv = Get-Process vcxsrv -ErrorAction SilentlyContinue
    if (-not $vcxsrv) {
        Write-Host "⚠️  VcXsrv is not running" -ForegroundColor Yellow
        Write-Host ""
        Write-Host "For GUI support, start VcXsrv with:" -ForegroundColor Gray
        Write-Host '  & "C:\Program Files\VcXsrv\vcxsrv.exe" :0 -multiwindow -clipboard -wgl -ac' -ForegroundColor Gray
        Write-Host ""
        $continue = Read-Host "Continue without GUI? (y/N)"
        if ($continue -ne "y") {
            exit 0
        }
    }
    
    # Get WSL path
    $currentPath = (Get-Location).Path
    $wslPath = $currentPath -replace '^([A-Z]):', '/mnt/$1' -replace '\\', '/'
    $wslPath = $wslPath.ToLower()
    
    Write-Host "Running in WSL2..." -ForegroundColor Green
    Write-Host ""
    
    # Run bash script in WSL
    wsl bash "$wslPath/docker/run-macvlan.sh"
    
    exit $LASTEXITCODE
}

Write-Host "Please run the bash version:" -ForegroundColor Yellow
Write-Host "  ./docker/run-macvlan.sh" -ForegroundColor Gray
