# Quick Deployment Script - Use unique names
# Usage: .\deploy-quick.ps1

$AZ = "C:\Program Files\Microsoft SDKs\Azure\CLI2\wbin\az.cmd"

$RESOURCE_GROUP = "weaver-rg"
$LOCATION = "centralindia"

# Use unique name with random suffix
$RANDOM_SUFFIX = Get-Random -Minimum 1000 -Maximum 9999
$KEY_VAULT_NAME = "weaver-kv-$RANDOM_SUFFIX"

Write-Host "========================================" -ForegroundColor Green
Write-Host "Weaver Quick Deployment" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host "Using Key Vault name: $KEY_VAULT_NAME" -ForegroundColor Cyan
Write-Host ""

# Get existing resources
$identityClientId = & $AZ identity show --name weaver-backend-identity --resource-group $RESOURCE_GROUP --query clientId -o tsv
$identityPrincipalId = & $AZ identity show --name weaver-backend-identity --resource-group $RESOURCE_GROUP --query principalId -o tsv
$identityResourceId = & $AZ identity show --name weaver-backend-identity --resource-group $RESOURCE_GROUP --query id -o tsv

Write-Host "✓ Managed Identity: $identityClientId" -ForegroundColor Green

# Create Key Vault with unique name
Write-Host "`nCreating Key Vault '$KEY_VAULT_NAME'..." -ForegroundColor Yellow
& $AZ keyvault create `
  --name $KEY_VAULT_NAME `
  --resource-group $RESOURCE_GROUP `
  --location $LOCATION `
  --enable-rbac-authorization true

Write-Host "Waiting for Key Vault to be ready..." -ForegroundColor Yellow
Start-Sleep -Seconds 15

$kvId = & $AZ keyvault show --name $KEY_VAULT_NAME --resource-group $RESOURCE_GROUP --query id -o tsv
Write-Host "✓ Key Vault created: $kvId" -ForegroundColor Green

# Grant access
Write-Host "`nGranting access..." -ForegroundColor Yellow
& $AZ role assignment create `
  --assignee $identityPrincipalId `
  --role "Key Vault Secrets User" `
  --scope $kvId

$myObjectId = & $AZ ad signed-in-user show --query id -o tsv
& $AZ role assignment create `
  --assignee $myObjectId `
  --role "Key Vault Secrets Officer" `
  --scope $kvId

Write-Host "Waiting 30 seconds for RBAC..." -ForegroundColor Yellow
Start-Sleep -Seconds 30

# Generate secrets
Write-Host "`nGenerating secrets..." -ForegroundColor Yellow
$jwtSecret = python -c "import secrets; print(secrets.token_hex(32))"
$mfaKey = python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
$kekKey = python -c "import os, base64; print(base64.b64encode(os.urandom(32)).decode())"

& $AZ keyvault secret set --vault-name $KEY_VAULT_NAME --name "JWT-SECRET-KEY" --value $jwtSecret
& $AZ keyvault secret set --vault-name $KEY_VAULT_NAME --name "MFA-ENCRYPTION-KEY" --value $mfaKey
& $AZ keyvault secret set --vault-name $KEY_VAULT_NAME --name "DATA-ENCRYPTION-KEK" --value $kekKey

Write-Host "✓ Secrets created" -ForegroundColor Green

# Create DATABASE-URL secret (you'll need to provide the password)
$dbHost = & $AZ postgres flexible-server show --name weaver-db-prod --resource-group $RESOURCE_GROUP --query fullyQualifiedDomainName -o tsv
Write-Host "`nDatabase host: $dbHost" -ForegroundColor Cyan
Write-Host "Enter PostgreSQL admin password:" -ForegroundColor Yellow
$dbPassword = Read-Host -AsSecureString
$dbPasswordText = [Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($dbPassword))

$databaseUrl = "postgresql://weaverdbadmin:$dbPasswordText@$($dbHost):5432/weaver?sslmode=require"
& $AZ keyvault secret set --vault-name $KEY_VAULT_NAME --name "DATABASE-URL" --value $databaseUrl
Write-Host "✓ DATABASE-URL secret created" -ForegroundColor Green

# Setup Blob Storage
Write-Host "`nChecking Blob Storage..." -ForegroundColor Yellow
$storageExists = & $AZ storage account show --name weaverstorageprod --resource-group $RESOURCE_GROUP 2>$null
if (-not $storageExists) {
    Write-Host "Creating Blob Storage..." -ForegroundColor Yellow
    & $AZ storage account create `
      --name weaverstorageprod `
      --resource-group $RESOURCE_GROUP `
      --location $LOCATION `
      --sku Standard_LRS `
      --kind StorageV2 `
      --access-tier Hot `
      --allow-blob-public-access false
    
    Start-Sleep -Seconds 10
}

$storageKey = & $AZ storage account keys list --account-name weaverstorageprod --resource-group $RESOURCE_GROUP --query "[0].value" -o tsv
& $AZ storage container create --name encrypted-payloads --account-name weaverstorageprod --account-key $storageKey 2>$null
& $AZ storage container create --name ml-models --account-name weaverstorageprod --account-key $storageKey 2>$null
& $AZ storage container create --name ml-datasets --account-name weaverstorageprod --account-key $storageKey 2>$null

$storageId = & $AZ storage account show --name weaverstorageprod --resource-group $RESOURCE_GROUP --query id -o tsv
& $AZ role assignment create `
  --assignee $identityPrincipalId `
  --role "Storage Blob Data Contributor" `
  --scope $storageId 2>$null

Write-Host "✓ Blob Storage ready" -ForegroundColor Green

# Setup Container Registry
Write-Host "`nChecking Container Registry..." -ForegroundColor Yellow
$acrExists = & $AZ acr show --name weaveracr --resource-group $RESOURCE_GROUP 2>$null
if (-not $acrExists) {
    Write-Host "Creating Container Registry..." -ForegroundColor Yellow
    & $AZ acr create `
      --name weaveracr `
      --resource-group $RESOURCE_GROUP `
      --sku Basic `
      --admin-enabled true
}

$acrId = & $AZ acr show --name weaveracr --resource-group $RESOURCE_GROUP --query id -o tsv
& $AZ role assignment create `
  --assignee $identityPrincipalId `
  --role AcrPull `
  --scope $acrId 2>$null

Write-Host "✓ Container Registry ready" -ForegroundColor Green

# Build Docker image
Write-Host "`nBuilding Docker image (5-10 minutes)..." -ForegroundColor Yellow
$parentPath = Split-Path -Parent $PSScriptRoot
& $AZ acr build `
  --registry weaveracr `
  --image weaver-backend:v1.0 `
  --file "$parentPath\backend\Dockerfile" `
  "$parentPath\backend"

Write-Host "`n✓ Image built" -ForegroundColor Green

# Deploy Container App
Write-Host "`nDeploying Container App..." -ForegroundColor Yellow

$envExists = & $AZ containerapp env show --name weaver-env --resource-group $RESOURCE_GROUP 2>$null
if (-not $envExists) {
    & $AZ containerapp env create `
      --name weaver-env `
      --resource-group $RESOURCE_GROUP `
      --location $LOCATION
}

$appExists = & $AZ containerapp show --name weaver-backend --resource-group $RESOURCE_GROUP 2>$null
if ($appExists) {
    & $AZ containerapp update `
      --name weaver-backend `
      --resource-group $RESOURCE_GROUP `
      --image weaveracr.azurecr.io/weaver-backend:v1.0 `
      --set-env-vars `
        "KEY_VAULT_URL=https://$KEY_VAULT_NAME.vault.azure.net/" `
        "AZURE_CLIENT_ID=$identityClientId" `
        "BLOB_STORAGE_ACCOUNT=weaverstorageprod"
} else {
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
        "KEY_VAULT_URL=https://$KEY_VAULT_NAME.vault.azure.net/" `
        "AZURE_CLIENT_ID=$identityClientId" `
        "BLOB_STORAGE_ACCOUNT=weaverstorageprod"
}

$backendUrl = & $AZ containerapp show --name weaver-backend --resource-group $RESOURCE_GROUP --query "properties.configuration.ingress.fqdn" -o tsv

Write-Host "`n========================================" -ForegroundColor Green
Write-Host "DEPLOYMENT COMPLETE!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Key Vault: $KEY_VAULT_NAME" -ForegroundColor Cyan
Write-Host "Backend URL: https://$backendUrl" -ForegroundColor Cyan
Write-Host "Health: https://$backendUrl/health" -ForegroundColor Cyan
Write-Host ""
Write-Host "IMPORTANT: Save this Key Vault name: $KEY_VAULT_NAME" -ForegroundColor Yellow
Write-Host ""
Write-Host "Next: Test with curl https://$backendUrl/health" -ForegroundColor Green
