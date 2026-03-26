# Weaver Azure Cloud Deployment - Resume Script
# Handles existing resources and continues from where it left off
#
# Usage: .\deploy-resume.ps1

$ErrorActionPreference = "Continue"

# Azure CLI path
$AZ = "C:\Program Files\Microsoft SDKs\Azure\CLI2\wbin\az.cmd"

# Configuration
$RESOURCE_GROUP = "weaver-rg"
$LOCATION = "centralindia"

Write-Host "========================================" -ForegroundColor Green
Write-Host "Weaver Azure Deployment (Resume)" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green

# Get subscription
$SUBSCRIPTION_ID = & $AZ account show --query id -o tsv
Write-Host "Subscription: $SUBSCRIPTION_ID" -ForegroundColor Cyan
Write-Host "Resource Group: $RESOURCE_GROUP" -ForegroundColor Cyan
Write-Host "Location: $LOCATION" -ForegroundColor Cyan
Write-Host ""

# ==============================================================================
# Check existing resources
# ==============================================================================
Write-Host "[Step 1] Checking existing resources..." -ForegroundColor Yellow

$identityClientId = & $AZ identity show --name weaver-backend-identity --resource-group $RESOURCE_GROUP --query clientId -o tsv 2>$null
$identityPrincipalId = & $AZ identity show --name weaver-backend-identity --resource-group $RESOURCE_GROUP --query principalId -o tsv 2>$null
$identityResourceId = & $AZ identity show --name weaver-backend-identity --resource-group $RESOURCE_GROUP --query id -o tsv 2>$null

if ($identityClientId) {
    Write-Host "✓ Managed Identity exists" -ForegroundColor Green
    Write-Host "  Client ID: $identityClientId" -ForegroundColor Cyan
} else {
    Write-Host "✗ Managed Identity not found - creating..." -ForegroundColor Red
    & $AZ identity create --name weaver-backend-identity --resource-group $RESOURCE_GROUP
    $identityClientId = & $AZ identity show --name weaver-backend-identity --resource-group $RESOURCE_GROUP --query clientId -o tsv
    $identityPrincipalId = & $AZ identity show --name weaver-backend-identity --resource-group $RESOURCE_GROUP --query principalId -o tsv
    $identityResourceId = & $AZ identity show --name weaver-backend-identity --resource-group $RESOURCE_GROUP --query id -o tsv
}

$dbHost = & $AZ postgres flexible-server show --name weaver-db-prod --resource-group $RESOURCE_GROUP --query fullyQualifiedDomainName -o tsv 2>$null
if ($dbHost) {
    Write-Host "✓ PostgreSQL server exists: $dbHost" -ForegroundColor Green
} else {
    Write-Host "✗ PostgreSQL not found" -ForegroundColor Red
}

# ==============================================================================
# Fix Key Vault (main issue)
# ==============================================================================
Write-Host "`n[Step 2] Fixing Key Vault..." -ForegroundColor Yellow

# Check if Key Vault exists
$kvExists = & $AZ keyvault show --name weaver-kv --resource-group $RESOURCE_GROUP 2>$null
if (-not $kvExists) {
    Write-Host "Key Vault does not exist. Checking if soft-deleted..." -ForegroundColor Yellow
    
    # Check soft-deleted vaults
    $deletedKvs = & $AZ keyvault list-deleted --query "[?name=='weaver-kv'].{Name:name,Location:properties.location,DeletionDate:properties.deletionDate}" -o json | ConvertFrom-Json
    
    if ($deletedKvs -and $deletedKvs.Count -gt 0) {
        Write-Host "Found soft-deleted Key Vault. Purging..." -ForegroundColor Yellow
        & $AZ keyvault purge --name weaver-kv --location $LOCATION
        Write-Host "Waiting 30 seconds for purge to complete..." -ForegroundColor Yellow
        Start-Sleep -Seconds 30
    }
    
    Write-Host "Creating Key Vault..." -ForegroundColor Yellow
    & $AZ keyvault create `
      --name weaver-kv `
      --resource-group $RESOURCE_GROUP `
      --location $LOCATION `
      --enable-rbac-authorization true
    
    Write-Host "Waiting 15 seconds for Key Vault to be ready..." -ForegroundColor Yellow
    Start-Sleep -Seconds 15
} else {
    Write-Host "✓ Key Vault exists" -ForegroundColor Green
}

# Get Key Vault ID
$kvId = & $AZ keyvault show --name weaver-kv --resource-group $RESOURCE_GROUP --query id -o tsv
Write-Host "Key Vault ID: $kvId" -ForegroundColor Cyan

# Grant managed identity access
Write-Host "Checking role assignments..." -ForegroundColor Yellow
$existingRole = & $AZ role assignment list --assignee $identityPrincipalId --scope $kvId --query "[?roleDefinitionName=='Key Vault Secrets User']" -o tsv

if (-not $existingRole) {
    Write-Host "Granting managed identity access to Key Vault..." -ForegroundColor Yellow
    & $AZ role assignment create `
      --assignee $identityPrincipalId `
      --role "Key Vault Secrets User" `
      --scope $kvId
    Write-Host "✓ Access granted" -ForegroundColor Green
} else {
    Write-Host "✓ Managed identity already has access" -ForegroundColor Green
}

# Grant current user access
$myObjectId = & $AZ ad signed-in-user show --query id -o tsv
$myRole = & $AZ role assignment list --assignee $myObjectId --scope $kvId --query "[?roleDefinitionName=='Key Vault Secrets Officer']" -o tsv

if (-not $myRole) {
    Write-Host "Granting you access to Key Vault..." -ForegroundColor Yellow
    & $AZ role assignment create `
      --assignee $myObjectId `
      --role "Key Vault Secrets Officer" `
      --scope $kvId
    Write-Host "Waiting 30 seconds for RBAC propagation..." -ForegroundColor Yellow
    Start-Sleep -Seconds 30
    Write-Host "✓ Access granted" -ForegroundColor Green
} else {
    Write-Host "✓ You already have access" -ForegroundColor Green
}

# ==============================================================================
# Create/Check Blob Storage
# ==============================================================================
Write-Host "`n[Step 3] Setting up Blob Storage..." -ForegroundColor Yellow

$storageExists = & $AZ storage account show --name weaverstorageprod --resource-group $RESOURCE_GROUP 2>$null
if ($storageExists) {
    Write-Host "✓ Blob Storage exists" -ForegroundColor Green
} else {
    Write-Host "Creating Blob Storage..." -ForegroundColor Yellow
    & $AZ storage account create `
      --name weaverstorageprod `
      --resource-group $RESOURCE_GROUP `
      --location $LOCATION `
      --sku Standard_LRS `
      --kind StorageV2 `
      --access-tier Hot `
      --allow-blob-public-access false
    
    Write-Host "Waiting for storage account..." -ForegroundColor Yellow
    Start-Sleep -Seconds 10
}

# Create containers
$storageKey = & $AZ storage account keys list --account-name weaverstorageprod --resource-group $RESOURCE_GROUP --query "[0].value" -o tsv

$containers = @("encrypted-payloads", "ml-models", "ml-datasets")
foreach ($container in $containers) {
    $exists = & $AZ storage container exists --name $container --account-name weaverstorageprod --account-key $storageKey --query exists -o tsv
    if ($exists -eq "true") {
        Write-Host "✓ Container '$container' exists" -ForegroundColor Green
    } else {
        Write-Host "Creating container '$container'..." -ForegroundColor Yellow
        & $AZ storage container create --name $container --account-name weaverstorageprod --account-key $storageKey
    }
}

# Grant blob access to managed identity
$storageId = & $AZ storage account show --name weaverstorageprod --resource-group $RESOURCE_GROUP --query id -o tsv
$blobRole = & $AZ role assignment list --assignee $identityPrincipalId --scope $storageId --query "[?roleDefinitionName=='Storage Blob Data Contributor']" -o tsv

if (-not $blobRole) {
    Write-Host "Granting blob access to managed identity..." -ForegroundColor Yellow
    & $AZ role assignment create `
      --assignee $identityPrincipalId `
      --role "Storage Blob Data Contributor" `
      --scope $storageId
} else {
    Write-Host "✓ Managed identity has blob access" -ForegroundColor Green
}

# ==============================================================================
# Populate Key Vault Secrets
# ==============================================================================
Write-Host "`n[Step 4] Populating Key Vault secrets..." -ForegroundColor Yellow

$secrets = @{
    "JWT-SECRET-KEY" = $null
    "MFA-ENCRYPTION-KEY" = $null
    "DATA-ENCRYPTION-KEK" = $null
    "DATABASE-URL" = $null
}

foreach ($secretName in $secrets.Keys) {
    $exists = & $AZ keyvault secret show --vault-name weaver-kv --name $secretName 2>$null
    if ($exists) {
        Write-Host "✓ Secret '$secretName' exists" -ForegroundColor Green
    } else {
        Write-Host "Secret '$secretName' missing - needs to be created" -ForegroundColor Yellow
    }
}

# Generate missing secrets
Write-Host "`nGenerating missing secrets..." -ForegroundColor Yellow

$jwtExists = & $AZ keyvault secret show --vault-name weaver-kv --name "JWT-SECRET-KEY" 2>$null
if (-not $jwtExists) {
    $jwtSecret = python -c "import secrets; print(secrets.token_hex(32))"
    & $AZ keyvault secret set --vault-name weaver-kv --name "JWT-SECRET-KEY" --value $jwtSecret
    Write-Host "✓ JWT-SECRET-KEY created" -ForegroundColor Green
}

$mfaExists = & $AZ keyvault secret show --vault-name weaver-kv --name "MFA-ENCRYPTION-KEY" 2>$null
if (-not $mfaExists) {
    $mfaKey = python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    & $AZ keyvault secret set --vault-name weaver-kv --name "MFA-ENCRYPTION-KEY" --value $mfaKey
    Write-Host "✓ MFA-ENCRYPTION-KEY created" -ForegroundColor Green
}

$kekExists = & $AZ keyvault secret show --vault-name weaver-kv --name "DATA-ENCRYPTION-KEK" 2>$null
if (-not $kekExists) {
    $kekKey = python -c "import os, base64; print(base64.b64encode(os.urandom(32)).decode())"
    & $AZ keyvault secret set --vault-name weaver-kv --name "DATA-ENCRYPTION-KEK" --value $kekKey
    Write-Host "✓ DATA-ENCRYPTION-KEK created" -ForegroundColor Green
}

$dbUrlExists = & $AZ keyvault secret show --vault-name weaver-kv --name "DATABASE-URL" 2>$null
if (-not $dbUrlExists -and $dbHost) {
    Write-Host "DATABASE-URL missing. Need to create it manually or provide password." -ForegroundColor Yellow
    Write-Host "Format: postgresql://weaverdbadmin:<PASSWORD>@$($dbHost):5432/weaver?sslmode=require" -ForegroundColor Cyan
}

# ==============================================================================
# Container Registry & Build
# ==============================================================================
Write-Host "`n[Step 5] Setting up Container Registry..." -ForegroundColor Yellow

$acrExists = & $AZ acr show --name weaveracr --resource-group $RESOURCE_GROUP 2>$null
if ($acrExists) {
    Write-Host "✓ Container Registry exists" -ForegroundColor Green
} else {
    Write-Host "Creating Container Registry..." -ForegroundColor Yellow
    & $AZ acr create `
      --name weaveracr `
      --resource-group $RESOURCE_GROUP `
      --sku Basic `
      --admin-enabled true
}

# Grant ACR pull access
$acrId = & $AZ acr show --name weaveracr --resource-group $RESOURCE_GROUP --query id -o tsv
$acrRole = & $AZ role assignment list --assignee $identityPrincipalId --scope $acrId --query "[?roleDefinitionName=='AcrPull']" -o tsv

if (-not $acrRole) {
    Write-Host "Granting ACR pull access..." -ForegroundColor Yellow
    & $AZ role assignment create `
      --assignee $identityPrincipalId `
      --role AcrPull `
      --scope $acrId
} else {
    Write-Host "✓ Managed identity has ACR access" -ForegroundColor Green
}

# Build Docker image
Write-Host "`nBuilding Docker image (this will take 5-10 minutes)..." -ForegroundColor Yellow
$parentPath = Split-Path -Parent $PSScriptRoot
& $AZ acr build `
  --registry weaveracr `
  --image weaver-backend:v1.0 `
  --file "$parentPath\backend\Dockerfile" `
  "$parentPath\backend"

Write-Host "`n✓ Docker image built successfully" -ForegroundColor Green

# ==============================================================================
# Deploy Container App
# ==============================================================================
Write-Host "`n[Step 6] Deploying Container App..." -ForegroundColor Yellow

# Create Container Apps Environment
$envExists = & $AZ containerapp env show --name weaver-env --resource-group $RESOURCE_GROUP 2>$null
if ($envExists) {
    Write-Host "✓ Container Apps Environment exists" -ForegroundColor Green
} else {
    Write-Host "Creating Container Apps Environment..." -ForegroundColor Yellow
    & $AZ containerapp env create `
      --name weaver-env `
      --resource-group $RESOURCE_GROUP `
      --location $LOCATION
}

# Deploy/Update Container App
$appExists = & $AZ containerapp show --name weaver-backend --resource-group $RESOURCE_GROUP 2>$null
if ($appExists) {
    Write-Host "Updating Container App..." -ForegroundColor Yellow
    & $AZ containerapp update `
      --name weaver-backend `
      --resource-group $RESOURCE_GROUP `
      --image weaveracr.azurecr.io/weaver-backend:v1.0
} else {
    Write-Host "Creating Container App..." -ForegroundColor Yellow
    & $AZ containerapp create `
      --name weaver-backend `
      --resource-group $RESOURCE_GROUP `
      --environment weaver-env `
      --image weaveracr.azurecr.io/weaver-backend:v1.0 `
      --target-port 8000 `
      --ingress external `
      --registry-server weaveracr.azurecr.io `
      --registry-identity $identityResourceId `
      --user-assigned $identityResourceId `
      --min-replicas 1 `
      --max-replicas 5 `
      --cpu 1.0 `
      --memory 2Gi `
      --env-vars `
        "KEY_VAULT_URL=https://weaver-kv.vault.azure.net/" `
        "AZURE_CLIENT_ID=$identityClientId" `
        "BLOB_STORAGE_ACCOUNT=weaverstorageprod"
}

$backendUrl = & $AZ containerapp show --name weaver-backend --resource-group $RESOURCE_GROUP --query "properties.configuration.ingress.fqdn" -o tsv

# ==============================================================================
# Summary
# ==============================================================================
Write-Host "`n========================================" -ForegroundColor Green
Write-Host "Deployment Complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Backend URL: https://$backendUrl" -ForegroundColor Cyan
Write-Host "Health Check: https://$backendUrl/health" -ForegroundColor Cyan
Write-Host ""
Write-Host "Next Steps:" -ForegroundColor Yellow
Write-Host "1. Test backend: curl https://$backendUrl/health" -ForegroundColor White
Write-Host "2. Set DATABASE-URL secret if missing" -ForegroundColor White
Write-Host "3. Run database migration: python ..\backend\migrations\add_blob_url_column.py" -ForegroundColor White
Write-Host "4. Seed database: python ..\backend\scripts\seed_db.py" -ForegroundColor White
Write-Host ""
Write-Host "View resources: https://portal.azure.com/#resource/subscriptions/$SUBSCRIPTION_ID/resourceGroups/$RESOURCE_GROUP" -ForegroundColor Cyan
