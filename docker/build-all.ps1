# Link-Chat Docker Build Script (PowerShell)
# Builds base image first, then derived images for fast rebuilds

param(
    [Parameter(Mandatory=$false)]
    [ValidateSet("all", "base", "base-alpine", "test", "interactive", "interactive-alpine", "production", "production-alpine", "debian", "alpine")]
    [string]$Target = "all",
    
    [Parameter(Mandatory=$false)]
    [switch]$NoCache
)

$ErrorActionPreference = "Stop"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Link-Chat Docker Build Script" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

function Build-BaseImage {
    Write-Host "[1/4] Building BASE image (linkchat-base)..." -ForegroundColor Yellow
    Write-Host "  This includes all system dependencies and PyQt6" -ForegroundColor Gray
    Write-Host "  Size: ~800MB | Time: ~5-10 minutes" -ForegroundColor Gray
    Write-Host ""
    
    $buildArgs = @("build", "-f", "docker/base/Dockerfile.base", "-t", "linkchat-base:latest")
    if ($NoCache) {
        $buildArgs += "--no-cache"
    }
    $buildArgs += "."
    
    & docker $buildArgs
    
    if ($LASTEXITCODE -ne 0) {
        Write-Host "❌ Base image build failed!" -ForegroundColor Red
        exit 1
    }
    Write-Host "✅ Base image built successfully!" -ForegroundColor Green
    Write-Host ""
}

function Build-TestImage {
    Write-Host "[2/4] Building TEST image (linkchat-test)..." -ForegroundColor Yellow
    Write-Host "  Fast build using base image" -ForegroundColor Gray
    Write-Host "  Size: ~800MB | Time: ~30 seconds" -ForegroundColor Gray
    Write-Host ""
    
    $buildArgs = @("build", "-f", "docker/testing/Dockerfile.test.new", "-t", "linkchat-test")
    if ($NoCache) {
        $buildArgs += "--no-cache"
    }
    $buildArgs += "."
    
    & docker $buildArgs
    
    if ($LASTEXITCODE -ne 0) {
        Write-Host "❌ Test image build failed!" -ForegroundColor Red
        exit 1
    }
    Write-Host "✅ Test image built successfully!" -ForegroundColor Green
    Write-Host ""
}

function Build-InteractiveImage {
    Write-Host "[3/4] Building INTERACTIVE image (linkchat-interactive)..." -ForegroundColor Yellow
    Write-Host "  Fast build using base image" -ForegroundColor Gray
    Write-Host "  Size: ~800MB | Time: ~30 seconds" -ForegroundColor Gray
    Write-Host ""
    
    $buildArgs = @("build", "-f", "docker/testing/Dockerfile.interactive.new", "-t", "linkchat-interactive")
    if ($NoCache) {
        $buildArgs += "--no-cache"
    }
    $buildArgs += "."
    
    & docker $buildArgs
    
    if ($LASTEXITCODE -ne 0) {
        Write-Host "❌ Interactive image build failed!" -ForegroundColor Red
        exit 1
    }
    Write-Host "✅ Interactive image built successfully!" -ForegroundColor Green
    Write-Host ""
}

function Build-ProductionImage {
    Write-Host "[4/4] Building PRODUCTION image (linkchat-production)..." -ForegroundColor Yellow
    Write-Host "  Fast build using base image" -ForegroundColor Gray
    Write-Host "  Size: ~800MB | Time: ~30 seconds" -ForegroundColor Gray
    Write-Host ""
    
    $buildArgs = @("build", "-f", "docker/production/Dockerfile.new", "-t", "linkchat-production")
    if ($NoCache) {
        $buildArgs += "--no-cache"
    }
    $buildArgs += "."
    
    & docker $buildArgs
    
    if ($LASTEXITCODE -ne 0) {
        Write-Host "❌ Production image build failed!" -ForegroundColor Red
        exit 1
    }
    Write-Host "✅ Production image built successfully!" -ForegroundColor Green
    Write-Host ""
}

function Build-AlpineBase {
    Write-Host "[5/8] Building ALPINE BASE image (linkchat-base-alpine)..." -ForegroundColor Yellow
    Write-Host "  ⚠️  WARNING: This takes 40-60 minutes (PyQt6 compilation)" -ForegroundColor Red
    Write-Host "  But only needs to be done ONCE!" -ForegroundColor Gray
    Write-Host "  Size: ~600-700 MB | Time: ~40-60 minutes" -ForegroundColor Gray
    Write-Host ""
    
    $buildArgs = @("build", "-f", "docker/base/Dockerfile.base.alpine", "-t", "linkchat-base-alpine:latest")
    if ($NoCache) {
        $buildArgs += "--no-cache"
    }
    $buildArgs += "."
    
    & docker $buildArgs
    
    if ($LASTEXITCODE -ne 0) {
        Write-Host "❌ Alpine base image build failed!" -ForegroundColor Red
        exit 1
    }
    Write-Host "✅ Alpine base image built successfully!" -ForegroundColor Green
    Write-Host ""
}

function Build-AlpineInteractive {
    Write-Host "[6/8] Building ALPINE INTERACTIVE image (linkchat-interactive-alpine)..." -ForegroundColor Yellow
    Write-Host "  Fast build using Alpine base image" -ForegroundColor Gray
    Write-Host "  Size: ~600-700 MB | Time: ~30 seconds" -ForegroundColor Gray
    Write-Host ""
    
    $buildArgs = @("build", "-f", "docker/testing/Dockerfile.interactive.alpine", "-t", "linkchat-interactive-alpine")
    if ($NoCache) {
        $buildArgs += "--no-cache"
    }
    $buildArgs += "."
    
    & docker $buildArgs
    
    if ($LASTEXITCODE -ne 0) {
        Write-Host "❌ Alpine interactive image build failed!" -ForegroundColor Red
        exit 1
    }
    Write-Host "✅ Alpine interactive image built successfully!" -ForegroundColor Green
    Write-Host ""
}

function Build-AlpineProduction {
    Write-Host "[7/8] Building ALPINE PRODUCTION image (linkchat-production-alpine)..." -ForegroundColor Yellow
    Write-Host "  Fast build using Alpine base image" -ForegroundColor Gray
    Write-Host "  Size: ~500-600 MB (smaller after cleanup) | Time: ~30 seconds" -ForegroundColor Gray
    Write-Host ""
    
    $buildArgs = @("build", "-f", "docker/production/Dockerfile.alpine", "-t", "linkchat-production-alpine")
    if ($NoCache) {
        $buildArgs += "--no-cache"
    }
    $buildArgs += "."
    
    & docker $buildArgs
    
    if ($LASTEXITCODE -ne 0) {
        Write-Host "❌ Alpine production image build failed!" -ForegroundColor Red
        exit 1
    }
    Write-Host "✅ Alpine production image built successfully!" -ForegroundColor Green
    Write-Host ""
}

# Main build logic
switch ($Target) {
    "base" {
        Build-BaseImage
    }
    "base-alpine" {
        Build-AlpineBase
    }
    "test" {
        Build-TestImage
    }
    "interactive" {
        Build-InteractiveImage
    }
    "interactive-alpine" {
        Build-AlpineInteractive
    }
    "production" {
        Build-ProductionImage
    }
    "production-alpine" {
        Build-AlpineProduction
    }
    "debian" {
        Build-BaseImage
        Build-TestImage
        Build-InteractiveImage
        Build-ProductionImage
    }
    "alpine" {
        Build-AlpineBase
        Build-AlpineInteractive
        Build-AlpineProduction
    }
    "all" {
        Write-Host "Building ALL images (Debian + Alpine)..." -ForegroundColor Cyan
        Write-Host "This will take 60-90 minutes total!" -ForegroundColor Yellow
        Write-Host ""
        Build-BaseImage
        Build-TestImage
        Build-InteractiveImage
        Build-ProductionImage
        Build-AlpineBase
        Build-AlpineInteractive
        Build-AlpineProduction
    }
}

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Build Complete!" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Available images:" -ForegroundColor Yellow
& docker images | Select-String "linkchat"
Write-Host ""
Write-Host "Quick Start Commands:" -ForegroundColor Yellow
Write-Host ""
Write-Host "  DEBIAN IMAGES:" -ForegroundColor Cyan
Write-Host "    Run tests:       docker run --rm linkchat-test" -ForegroundColor Gray
Write-Host "    Interactive:     docker run -it --rm linkchat-interactive" -ForegroundColor Gray
Write-Host "    Production:      docker run -it --rm linkchat-production" -ForegroundColor Gray
Write-Host ""
Write-Host "  ALPINE IMAGES (smaller):" -ForegroundColor Cyan
Write-Host "    Interactive:     docker run -it --rm linkchat-interactive-alpine" -ForegroundColor Gray
Write-Host "    Production:      docker run -it --rm linkchat-production-alpine" -ForegroundColor Gray
Write-Host ""
Write-Host "  GUI MODE (requires X11 server):" -ForegroundColor Cyan
Write-Host "    docker run -it --rm -e DISPLAY=host.docker.internal:0 linkchat-interactive python -m linkchat.app.qt_main" -ForegroundColor Gray
Write-Host ""
