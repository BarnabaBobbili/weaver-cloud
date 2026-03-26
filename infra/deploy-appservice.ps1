# Weaver Azure Deployment - App Service Version
# Uses Azure App Service which builds from source without ACR Tasks

$ErrorActionPreference = "Continue"
$AZ = "C:\Program Files\Microsoft SDKs\Azure\CLI2\wbin\az.cmd"

$RESOURCE_GROUP = "weaver-rg"
$LOCATION = "centralindia"
$APP_NAME = "weaver-backend-app"
$PLAN_NAME = "weaver-app-plan"

Write-Host "========================================" -ForegroundColor Green
Write-Host "Weaver Backend - App Service Deployment" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green

# Get script path
$scriptDir = if ($PSScriptRoot) { $PSScriptRoot } else { Split-Path -Parent $MyInvocation.MyCommand.Path }
if (-not $scriptDir) { $scriptDir = "E:\MTech\MTech Sem2\Cloud\Project\Weaver\infra" }
$parentPath = Split-Path -Parent $scriptDir
$backendPath = "$parentPath\backend"

Write-Host "Backend path: $backendPath" -ForegroundColor Cyan

# Create App Service Plan
$planExists = & $AZ appservice plan show --name $PLAN_NAME --resource-group $RESOURCE_GROUP 2>$null
if (-not $planExists) {
    Write-Host "Creating App Service Plan..." -ForegroundColor Yellow
    & $AZ appservice plan create --name $PLAN_NAME --resource-group $RESOURCE_GROUP --location $LOCATION --sku B1 --is-linux
} else {
    Write-Host "App Service Plan exists" -ForegroundColor Green
}

# Deploy the web app directly from source
Write-Host "Creating Web App..." -ForegroundColor Yellow

$appExists = & $AZ webapp show --name $APP_NAME --resource-group $RESOURCE_GROUP 2>$null
if (-not $appExists) {
    & $AZ webapp create --name $APP_NAME --resource-group $RESOURCE_GROUP --plan $PLAN_NAME --runtime "PYTHON:3.11"
} else {
    Write-Host "Web App exists" -ForegroundColor Green
}

# Deploy code using TAR (better cross-platform support)
Write-Host "Deploying code to App Service..." -ForegroundColor Yellow

Set-Location $backendPath

# Create startup.txt
Write-Host "Creating startup configuration..." -ForegroundColor Yellow
"gunicorn app.main:app --workers 4 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000" | Out-File -FilePath "$backendPath\startup.txt" -Encoding utf8 -NoNewline

# Create TAR file (better path handling than ZIP)
Write-Host "Creating deployment package..." -ForegroundColor Yellow
$tarPath = "$env:TEMP\weaver-backend.tar.gz"
if (Test-Path $tarPath) { Remove-Item $tarPath -Force }

tar -czf $tarPath -C $backendPath app requirements.txt startup.txt 2>&1

Write-Host "Uploading and building in Azure (this takes 2-3 minutes)..." -ForegroundColor Yellow
& $AZ webapp deploy --name $APP_NAME --resource-group $RESOURCE_GROUP --src-path $tarPath --type tar

# Cleanup
Remove-Item $tarPath -Force
Remove-Item "$backendPath\startup.txt" -Force 2>$null

# Configure startup command
Write-Host "Configuring startup command..." -ForegroundColor Yellow
& $AZ webapp config set --name $APP_NAME --resource-group $RESOURCE_GROUP --startup-file "gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:8000"

# Set environment variables
Write-Host "Setting environment variables..." -ForegroundColor Yellow
& $AZ webapp config appsettings set --name $APP_NAME --resource-group $RESOURCE_GROUP --settings KEY_VAULT_URL="https://weaver-kv-ijbkmp25.vault.azure.net/" BLOB_STORAGE_ACCOUNT="weaverstorageprod" WEBSITES_PORT="8000"

# Enable managed identity
Write-Host "Enabling managed identity..." -ForegroundColor Yellow
& $AZ webapp identity assign --name $APP_NAME --resource-group $RESOURCE_GROUP

# Get the URL
$BACKEND_URL = & $AZ webapp show --name $APP_NAME --resource-group $RESOURCE_GROUP --query "defaultHostName" -o tsv

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "Backend Deployed Successfully!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Backend URL: https://$BACKEND_URL" -ForegroundColor Cyan
Write-Host "Health Check: https://$BACKEND_URL/health" -ForegroundColor Cyan
Write-Host ""
Write-Host "Test with: curl https://$BACKEND_URL/health" -ForegroundColor White

Set-Location $scriptDir
