# Quick Integration Test Script for Windows
# Starts two Link-Chat containers and opens interactive shells

Write-Host "🚀 Link-Chat Integration Test Setup" -ForegroundColor Cyan
Write-Host "=" * 60

# Step 1: Build image
Write-Host "`n📦 Building interactive test image..." -ForegroundColor Yellow
docker build -f Dockerfile.interactive -t linkchat-interactive .

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Build failed!" -ForegroundColor Red
    exit 1
}

# Step 2: Create download directories
Write-Host "`n📁 Creating download directories..." -ForegroundColor Yellow
New-Item -ItemType Directory -Force -Path "downloads-alice" | Out-Null
New-Item -ItemType Directory -Force -Path "downloads-bob" | Out-Null

# Step 3: Start containers
Write-Host "`n🌐 Starting containers with virtual network..." -ForegroundColor Yellow
docker-compose -f docker-compose.test.yml up -d

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Failed to start containers!" -ForegroundColor Red
    exit 1
}

# Wait for containers to be ready
Write-Host "`n⏳ Waiting for containers to initialize..." -ForegroundColor Yellow
Start-Sleep -Seconds 3

# Get MAC addresses
Write-Host "`n🏷️  Getting MAC addresses..." -ForegroundColor Yellow
$alice_mac = docker exec linkchat-alice ip link show eth0 | Select-String "link/ether" | ForEach-Object { $_ -replace '.*link/ether\s+(\S+).*', '$1' }
$bob_mac = docker exec linkchat-bob ip link show eth0 | Select-String "link/ether" | ForEach-Object { $_ -replace '.*link/ether\s+(\S+).*', '$1' }

Write-Host "`n" + ("=" * 60) -ForegroundColor Green
Write-Host "✅ Containers are ready!" -ForegroundColor Green
Write-Host ("=" * 60) -ForegroundColor Green
Write-Host ""
Write-Host "📍 Alice (Node 1)" -ForegroundColor Cyan
Write-Host "   IP:  172.20.0.10"
Write-Host "   MAC: $alice_mac"
Write-Host ""
Write-Host "📍 Bob (Node 2)" -ForegroundColor Cyan
Write-Host "   IP:  172.20.0.11"
Write-Host "   MAC: $bob_mac"
Write-Host ""
Write-Host ("=" * 60) -ForegroundColor Green

Write-Host "`n📝 Next steps:" -ForegroundColor Yellow
Write-Host ""
Write-Host "1. Open Alice's shell:" -ForegroundColor White
Write-Host "   docker exec -it linkchat-alice python /app/test_container.py" -ForegroundColor Cyan
Write-Host ""
Write-Host "2. Open Bob's shell in another terminal:" -ForegroundColor White
Write-Host "   docker exec -it linkchat-bob python /app/test_container.py" -ForegroundColor Cyan
Write-Host ""
Write-Host "3. In Alice, send message to Bob:" -ForegroundColor White
Write-Host "   > 1                    # Send message" -ForegroundColor Cyan
Write-Host "   Destination MAC: $bob_mac" -ForegroundColor Cyan
Write-Host "   Message: Hello Bob!" -ForegroundColor Cyan
Write-Host ""
Write-Host "4. See message appear in Bob's terminal!" -ForegroundColor White
Write-Host ""
Write-Host ("=" * 60) -ForegroundColor Green
Write-Host "`n💡 Tip: To stop containers, run:" -ForegroundColor Yellow
Write-Host "   docker-compose -f docker-compose.test.yml down" -ForegroundColor Cyan
Write-Host ""
