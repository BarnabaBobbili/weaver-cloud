# Manual Docker Build and Push
# Since you can't use ACR Tasks, build locally and push to ACR

$AZ = "C:\Program Files\Microsoft SDKs\Azure\CLI2\wbin\az.cmd"
$RESOURCE_GROUP = "weaver-rg"

Write-Host "========================================" -ForegroundColor Green
Write-Host "Manual Docker Build and Push" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green

# Get script path
$scriptDir = Get-Location
$parentPath = Split-Path -Parent $scriptDir
$backendPath = "$parentPath\backend"

Write-Host "Backend path: $backendPath" -ForegroundColor Cyan

# Check Docker is running
try {
    docker version | Out-Null
} catch {
    Write-Host "ERROR: Docker is not running. Please start Docker Desktop." -ForegroundColor Red
    exit 1
}

# Login to ACR
Write-Host "`nLogging into Azure Container Registry..." -ForegroundColor Yellow
& $AZ acr login --name weaveracr

# Build image
Write-Host "Building Docker image..." -ForegroundColor Yellow
$imageTag = "v1.0-$(Get-Date -Format 'yyyyMMdd-HHmmss')"
docker build -t "weaveracr.azurecr.io/weaver-backend:$imageTag" -t "weaveracr.azurecr.io/weaver-backend:latest" $backendPath

# Push to ACR
Write-Host "Pushing to ACR..." -ForegroundColor Yellow
docker push "weaveracr.azurecr.io/weaver-backend:$imageTag"
docker push "weaveracr.azurecr.io/weaver-backend:latest"

# Update Container App
Write-Host "Updating Container App..." -ForegroundColor Yellow
& $AZ containerapp update --name weaver-backend --resource-group $RESOURCE_GROUP --image "weaveracr.azurecr.io/weaver-backend:$imageTag"

# Get URL
$BACKEND_URL = & $AZ containerapp show --name weaver-backend --resource-group $RESOURCE_GROUP --query "properties.configuration.ingress.fqdn" -o tsv

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "Deployment Complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Backend URL: https://$BACKEND_URL" -ForegroundColor Cyan
Write-Host "Health: https://$BACKEND_URL/health" -ForegroundColor Cyan
