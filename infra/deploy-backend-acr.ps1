# Weaver Complete Deployment - Container Apps with ACR Build
# Now that ACR is Standard tier, this should work

$ErrorActionPreference = "Continue"
$AZ = "C:\Program Files\Microsoft SDKs\Azure\CLI2\wbin\az.cmd"

$RESOURCE_GROUP = "weaver-rg"
$LOCATION = "centralindia"
$ACR_NAME = "weaveracr"
$CONTAINER_APP = "weaver-backend"
$ENVIRONMENT = "weaver-env"

Write-Host "========================================" -ForegroundColor Green
Write-Host "Weaver Container Apps Deployment" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green

# Get paths
$scriptDir = if ($PSScriptRoot) { $PSScriptRoot } else { Get-Location }
$parentPath = Split-Path -Parent $scriptDir
$backendPath = "$parentPath\backend"

Write-Host "Backend path: $backendPath" -ForegroundColor Cyan

# Get managed identity
$IDENTITY_ID = & $AZ identity show --name weaver-backend-identity --resource-group $RESOURCE_GROUP --query id -o tsv
$IDENTITY_CLIENT_ID = & $AZ identity show --name weaver-backend-identity --resource-group $RESOURCE_GROUP --query clientId -o tsv

Write-Host "Identity ID: $IDENTITY_CLIENT_ID" -ForegroundColor Cyan

# Build image in ACR (now should work with Standard SKU)
Write-Host "`nBuilding Docker image in ACR (takes 5-10 minutes)..." -ForegroundColor Yellow
$imageTag = "v1.0-$(Get-Date -Format 'yyyyMMdd-HHmmss')"

& $AZ acr build --registry $ACR_NAME --image "weaver-backend:$imageTag" --image "weaver-backend:latest" --file "$backendPath\Dockerfile" $backendPath

Write-Host "Image built: weaveracr.azurecr.io/weaver-backend:$imageTag" -ForegroundColor Green

# Check Container Apps Environment
$envExists = & $AZ containerapp env show --name $ENVIRONMENT --resource-group $RESOURCE_GROUP 2>$null
if (-not $envExists) {
    Write-Host "Creating Container Apps Environment..." -ForegroundColor Yellow
    & $AZ containerapp env create --name $ENVIRONMENT --resource-group $RESOURCE_GROUP --location $LOCATION
}

# Deploy/Update Container App
$appExists = & $AZ containerapp show --name $CONTAINER_APP --resource-group $RESOURCE_GROUP 2>$null
if ($appExists) {
    Write-Host "Updating Container App with new image..." -ForegroundColor Yellow
    & $AZ containerapp update --name $CONTAINER_APP --resource-group $RESOURCE_GROUP --image "weaveracr.azurecr.io/weaver-backend:$imageTag"
} else {
    Write-Host "Creating Container App..." -ForegroundColor Yellow
    & $AZ containerapp create --name $CONTAINER_APP --resource-group $RESOURCE_GROUP --environment $ENVIRONMENT --image "weaveracr.azurecr.io/weaver-backend:$imageTag" --target-port 8000 --ingress external --registry-server weaveracr.azurecr.io --registry-identity $IDENTITY_ID --user-assigned $IDENTITY_ID --min-replicas 1 --max-replicas 3 --cpu 0.5 --memory 1Gi --env-vars "KEY_VAULT_URL=https://weaver-kv-ijbkmp25.vault.azure.net/" "AZURE_CLIENT_ID=$IDENTITY_CLIENT_ID" "BLOB_STORAGE_ACCOUNT=weaverstorageprod"
}

# Get URL
$BACKEND_URL = & $AZ containerapp show --name $CONTAINER_APP --resource-group $RESOURCE_GROUP --query "properties.configuration.ingress.fqdn" -o tsv

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "Backend Deployed!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Backend URL: https://$BACKEND_URL" -ForegroundColor Cyan
Write-Host "Health Check: https://$BACKEND_URL/health" -ForegroundColor Cyan
Write-Host ""
Write-Host "Test with: curl https://$BACKEND_URL/health" -ForegroundColor White
Write-Host ""
