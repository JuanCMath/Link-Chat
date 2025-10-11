# PowerShell script to run tests in Docker container (Windows)
# Requires: Docker Desktop installed and running

Write-Host "Building test container..." -ForegroundColor Cyan
docker build -f Dockerfile.test -t linkchat-test .

if ($LASTEXITCODE -eq 0) {
    Write-Host "`nRunning tests in Alpine Linux container..." -ForegroundColor Cyan
    docker run --rm linkchat-test
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "`n✅ All tests passed in Linux environment!" -ForegroundColor Green
    } else {
        Write-Host "`n❌ Tests failed!" -ForegroundColor Red
        exit 1
    }
} else {
    Write-Host "`n❌ Docker build failed!" -ForegroundColor Red
    Write-Host "Make sure Docker Desktop is running." -ForegroundColor Yellow
    exit 1
}
