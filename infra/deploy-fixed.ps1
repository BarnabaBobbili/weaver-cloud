# Weaver Azure Cloud Deployment Script (PowerShell) - Fixed Version
# Handles existing resources and continues deployment
#
# Prerequisites:
# - Azure CLI installed
# - Logged in (az login)
# - Subscription set (az account set --subscription <id>)
#
# Usage: .\deploy-fixed.ps1

$ErrorActionPreference = "Continue"

# Azure CLI path
$AZ = "C:\Program Files\Microsoft SDKs\Azure\CLI2\wbin\az.cmd"

# Configuration
$RESOURCE_GROUP = "weaver-rg"
$LOCATION = "centralindia"
$SUBSCRIPTION_ID = (& $AZ account show --query id -o tsv)

Write-Host "========================================" -ForegroundColor Green
Write-Host "Weaver Azure Deployment (Resume)" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host "Subscription: $SUBSCRIPTION_ID" -ForegroundColor Cyan
Write-Host "Resource Group: $RESOURCE_GROUP" -ForegroundColor Cyan
Write-Host "Location: $LOCATION" -ForegroundColor Cyan
Write-Host ""

# ==============================================================================
# Phase 1: Foundation and Identity
# ==============================================================================
Write-Host "[Phase 1] Checking foundation..." -ForegroundColor Yellow

# Check resource group
$rgExists = & $AZ group exists --name $RESOURCE_GROUP
if ($rgExists -eq "true") {
    Write-Host "Resource group exists" -ForegroundColor Green
} else {
    Write-Host "Creating resource group..." -ForegroundColor Yellow
    & $AZ group create --name $RESOURCE_GROUP --location $LOCATION
}

# Register providers (idempotent)
Write-Host "Ensuring Azure providers are registered..." -ForegroundColor Yellow
$providers = @(
    "Microsoft.App",
    "Microsoft.ContainerRegistry",
    "Microsoft.DBforPostgreSQL",
    "Microsoft.KeyVault",
    "Microsoft.ServiceBus",
    "Microsoft.Storage",
    "Microsoft.Web",
    "Microsoft.Insights"
)

foreach ($provider in $providers) {
    $status = & $AZ provider show --namespace $provider --query "registrationState" -o tsv 2>$null
    if ($status -ne "Registered") {
        Write-Host "Registering $provider..." -ForegroundColor Yellow
        & $AZ provider register --namespace $provider
    } else {
        Write-Host "$provider already registered" -ForegroundColor Green
    }
}

# Check Managed Identity
$identityExists = & $AZ identity show --name weaver-backend-identity --resource-group $RESOURCE_GROUP 2>$null
if ($identityExists) {
    Write-Host "Managed Identity exists" -ForegroundColor Green
    $IDENTITY_CLIENT_ID = & $AZ identity show --name weaver-backend-identity --resource-group $RESOURCE_GROUP --query clientId -o tsv
    $IDENTITY_PRINCIPAL_ID = & $AZ identity show --name weaver-backend-identity --resource-group $RESOURCE_GROUP --query principalId -o tsv
    $IDENTITY_RESOURCE_ID = & $AZ identity show --name weaver-backend-identity --resource-group $RESOURCE_GROUP --query id -o tsv
} else {
    Write-Host "Creating Managed Identity..." -ForegroundColor Yellow
    & $AZ identity create --name weaver-backend-identity --resource-group $RESOURCE_GROUP
    $IDENTITY_CLIENT_ID = & $AZ identity show --name weaver-backend-identity --resource-group $RESOURCE_GROUP --query clientId -o tsv
    $IDENTITY_PRINCIPAL_ID = & $AZ identity show --name weaver-backend-identity --resource-group $RESOURCE_GROUP --query principalId -o tsv
    $IDENTITY_RESOURCE_ID = & $AZ identity show --name weaver-backend-identity --resource-group $RESOURCE_GROUP --query id -o tsv
}

Write-Host "Managed Identity:" -ForegroundColor Green
Write-Host "  Client ID: $IDENTITY_CLIENT_ID" -ForegroundColor Cyan
Write-Host "  Principal ID: $IDENTITY_PRINCIPAL_ID" -ForegroundColor Cyan

# ==============================================================================
# Phase 2: Data Layer
# ==============================================================================
Write-Host "`n[Phase 2] Setting up data layer..." -ForegroundColor Yellow

# Check/Create Key Vault
$kvExists = & $AZ keyvault show --name weaver-kv-ijbkmp25 2>$null
if (-not $kvExists) {
    # Check if soft-deleted
    Write-Host "Checking for soft-deleted Key Vault..." -ForegroundColor Yellow
    $deletedKv = & $AZ keyvault list-deleted --query "[?name=='weaver-kv-ijbkmp25']" -o tsv
    if ($deletedKv) {
        Write-Host "Purging soft-deleted Key Vault..." -ForegroundColor Yellow
        & $AZ keyvault purge --name weaver-kv-ijbkmp25 --location $LOCATION
        Start-Sleep -Seconds 10
    }
    
    Write-Host "Creating Key Vault..." -ForegroundColor Yellow
    & $AZ keyvault create --name weaver-kv-ijbkmp25 --resource-group $RESOURCE_GROUP --location $LOCATION --enable-rbac-authorization true
    
    Start-Sleep -Seconds 10
} else {
    Write-Host "Key Vault exists" -ForegroundColor Green
}

# Grant access to managed identity
$KV_ID = & $AZ keyvault show --name weaver-kv-ijbkmp25 --resource-group $RESOURCE_GROUP --query id -o tsv
Write-Host "Key Vault ID: $KV_ID" -ForegroundColor Cyan

# Check if role assignment already exists
$existingRole = & $AZ role assignment list --assignee $IDENTITY_PRINCIPAL_ID --scope $KV_ID --query "[?roleDefinitionName=='Key Vault Secrets User']" -o tsv

if (-not $existingRole) {
    Write-Host "Granting managed identity access to Key Vault..." -ForegroundColor Yellow
    & $AZ role assignment create --assignee $IDENTITY_PRINCIPAL_ID --role "Key Vault Secrets User" --scope $KV_ID
} else {
    Write-Host "Managed identity already has Key Vault access" -ForegroundColor Green
}

# Grant current user access
$MY_OBJECT_ID = & $AZ ad signed-in-user show --query id -o tsv
$myExistingRole = & $AZ role assignment list --assignee $MY_OBJECT_ID --scope $KV_ID --query "[?roleDefinitionName=='Key Vault Secrets Officer']" -o tsv

if (-not $myExistingRole) {
    Write-Host "Granting you access to Key Vault..." -ForegroundColor Yellow
    & $AZ role assignment create --assignee $MY_OBJECT_ID --role "Key Vault Secrets Officer" --scope $KV_ID
    Start-Sleep -Seconds 30
} else {
    Write-Host "You already have Key Vault access" -ForegroundColor Green
}

# Check/Create PostgreSQL
$dbExists = & $AZ postgres flexible-server show --name weaver-db-prod --resource-group $RESOURCE_GROUP 2>$null
if ($dbExists) {
    Write-Host "PostgreSQL server exists" -ForegroundColor Green
    $DB_HOST = & $AZ postgres flexible-server show --name weaver-db-prod --resource-group $RESOURCE_GROUP --query "fullyQualifiedDomainName" -o tsv
} else {
    Write-Host "Creating PostgreSQL Flexible Server - this takes 3 to 5 minutes..." -ForegroundColor Yellow
    $DB_PASSWORD = Read-Host -Prompt "Enter PostgreSQL admin password" -AsSecureString
    $DB_PASSWORD_TEXT = [Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($DB_PASSWORD))
    
    & $AZ postgres flexible-server create --name weaver-db-prod --resource-group $RESOURCE_GROUP --location $LOCATION --admin-user weaverdbadmin --admin-password $DB_PASSWORD_TEXT --sku-name Standard_B1ms --tier Burstable --storage-size 32 --version 16 --public-access All
    
    # Create database
    & $AZ postgres flexible-server db create --server-name weaver-db-prod --resource-group $RESOURCE_GROUP --database-name weaver
    
    $DB_HOST = & $AZ postgres flexible-server show --name weaver-db-prod --resource-group $RESOURCE_GROUP --query "fullyQualifiedDomainName" -o tsv
    
    # Store password in Key Vault
    $DATABASE_URL = "postgresql://weaverdbadmin:${DB_PASSWORD_TEXT}@${DB_HOST}:5432/weaver?sslmode=require"
    & $AZ keyvault secret set --vault-name weaver-kv-ijbkmp25 --name "DATABASE-URL" --value $DATABASE_URL
}

# Check/Create Blob Storage
$storageExists = & $AZ storage account show --name weaverstorageprod --resource-group $RESOURCE_GROUP 2>$null
if ($storageExists) {
    Write-Host "Blob Storage exists" -ForegroundColor Green
} else {
    Write-Host "Creating Blob Storage..." -ForegroundColor Yellow
    & $AZ storage account create --name weaverstorageprod --resource-group $RESOURCE_GROUP --location $LOCATION --sku Standard_LRS --kind StorageV2 --access-tier Hot --allow-blob-public-access false
    
    # Create containers
    $STORAGE_KEY = & $AZ storage account keys list --account-name weaverstorageprod --resource-group $RESOURCE_GROUP --query "[0].value" -o tsv
    
    & $AZ storage container create --name encrypted-payloads --account-name weaverstorageprod --account-key $STORAGE_KEY
    & $AZ storage container create --name ml-models --account-name weaverstorageprod --account-key $STORAGE_KEY
    & $AZ storage container create --name ml-datasets --account-name weaverstorageprod --account-key $STORAGE_KEY
}

# Grant blob access to managed identity
$STORAGE_ID = & $AZ storage account show --name weaverstorageprod --resource-group $RESOURCE_GROUP --query id -o tsv
$blobRole = & $AZ role assignment list --assignee $IDENTITY_PRINCIPAL_ID --scope $STORAGE_ID --query "[?roleDefinitionName=='Storage Blob Data Contributor']" -o tsv

if (-not $blobRole) {
    Write-Host "Granting blob access to managed identity..." -ForegroundColor Yellow
    & $AZ role assignment create --assignee $IDENTITY_PRINCIPAL_ID --role "Storage Blob Data Contributor" --scope $STORAGE_ID
} else {
    Write-Host "Managed identity has blob access" -ForegroundColor Green
}

# Store secrets in Key Vault
Write-Host "`nPopulating Key Vault secrets..." -ForegroundColor Yellow

# JWT Secret
$secretExists = & $AZ keyvault secret show --vault-name weaver-kv-ijbkmp25 --name "JWT-SECRET-KEY" 2>$null
if (-not $secretExists) {
    Write-Host "Generating JWT-SECRET-KEY..." -ForegroundColor Yellow
    $jwtSecret = python -c "import secrets; print(secrets.token_hex(32))"
    & $AZ keyvault secret set --vault-name weaver-kv-ijbkmp25 --name "JWT-SECRET-KEY" --value $jwtSecret
} else {
    Write-Host "JWT-SECRET-KEY already exists" -ForegroundColor Green
}

# MFA Key
$secretExists = & $AZ keyvault secret show --vault-name weaver-kv-ijbkmp25 --name "MFA-ENCRYPTION-KEY" 2>$null
if (-not $secretExists) {
    Write-Host "Generating MFA-ENCRYPTION-KEY..." -ForegroundColor Yellow
    $mfaKey = python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode('utf-8'))"
    & $AZ keyvault secret set --vault-name weaver-kv-ijbkmp25 --name "MFA-ENCRYPTION-KEY" --value $mfaKey
} else {
    Write-Host "MFA-ENCRYPTION-KEY already exists" -ForegroundColor Green
}

# Data Encryption Key
$secretExists = & $AZ keyvault secret show --vault-name weaver-kv-ijbkmp25 --name "DATA-ENCRYPTION-KEK" 2>$null
if (-not $secretExists) {
    Write-Host "Generating DATA-ENCRYPTION-KEK..." -ForegroundColor Yellow
    $dataKey = python -c "import os,base64; print(base64.b64encode(os.urandom(32)).decode('utf-8'))"
    & $AZ keyvault secret set --vault-name weaver-kv-ijbkmp25 --name "DATA-ENCRYPTION-KEK" --value $dataKey
} else {
    Write-Host "DATA-ENCRYPTION-KEK already exists" -ForegroundColor Green
}

# ==============================================================================
# Phase 3: Container Infrastructure
# ==============================================================================
Write-Host "`n[Phase 3] Setting up container infrastructure..." -ForegroundColor Yellow

# Check/Create Container Registry
$acrExists = & $AZ acr show --name weaveracr --resource-group $RESOURCE_GROUP 2>$null
if ($acrExists) {
    Write-Host "Container Registry exists" -ForegroundColor Green
} else {
    Write-Host "Creating Container Registry..." -ForegroundColor Yellow
    & $AZ acr create --name weaveracr --resource-group $RESOURCE_GROUP --sku Basic --admin-enabled true
}

# Grant managed identity pull access
$ACR_ID = & $AZ acr show --name weaveracr --resource-group $RESOURCE_GROUP --query id -o tsv
$acrRole = & $AZ role assignment list --assignee $IDENTITY_PRINCIPAL_ID --scope $ACR_ID --query "[?roleDefinitionName=='AcrPull']" -o tsv

if (-not $acrRole) {
    Write-Host "Granting ACR pull access to managed identity..." -ForegroundColor Yellow
    & $AZ role assignment create --assignee $IDENTITY_PRINCIPAL_ID --role AcrPull --scope $ACR_ID
} else {
    Write-Host "Managed identity has ACR pull access" -ForegroundColor Green
}

# Deploy using Azure Container Apps source-to-cloud (builds in Azure, no local Docker)
Write-Host "Deploying from source code using Azure Cloud Build..." -ForegroundColor Yellow
$scriptDir = if ($PSScriptRoot) { $PSScriptRoot } else { Split-Path -Parent $MyInvocation.MyCommand.Path }
if (-not $scriptDir) { $scriptDir = "E:\MTech\MTech Sem2\Cloud\Project\Weaver\infra" }
$parentPath = Split-Path -Parent $scriptDir
Write-Host "Using backend path: $parentPath\backend" -ForegroundColor Cyan

# Create Container Apps Environment first
$envExists = & $AZ containerapp env show --name weaver-env --resource-group $RESOURCE_GROUP 2>$null
if ($envExists) {
    Write-Host "Container Apps Environment exists" -ForegroundColor Green
} else {
    Write-Host "Creating Container Apps Environment..." -ForegroundColor Yellow
    & $AZ containerapp env create --name weaver-env --resource-group $RESOURCE_GROUP --location $LOCATION
}

# Deploy Container App directly from source (Azure builds it in the cloud)
$appExists = & $AZ containerapp show --name weaver-backend --resource-group $RESOURCE_GROUP 2>$null
if ($appExists) {
    Write-Host "Updating Container App from source..." -ForegroundColor Yellow
    & $AZ containerapp up --name weaver-backend --resource-group $RESOURCE_GROUP --source "$parentPath\backend"
} else {
    Write-Host "Creating Container App from source - this takes 5-10 minutes..." -ForegroundColor Yellow
    & $AZ containerapp up --name weaver-backend --resource-group $RESOURCE_GROUP --environment weaver-env --source "$parentPath\backend" --ingress external --target-port 8000
}

# Configure the app with managed identity and env vars
Write-Host "Configuring Container App settings..." -ForegroundColor Yellow
& $AZ containerapp identity assign --name weaver-backend --resource-group $RESOURCE_GROUP --user-assigned $IDENTITY_RESOURCE_ID

& $AZ containerapp update --name weaver-backend --resource-group $RESOURCE_GROUP --set-env-vars "KEY_VAULT_URL=https://weaver-kv-ijbkmp25.vault.azure.net/" "AZURE_CLIENT_ID=$IDENTITY_CLIENT_ID" "BLOB_STORAGE_ACCOUNT=weaverstorageprod" --min-replicas 1 --max-replicas 5 --cpu 1.0 --memory 2Gi

$BACKEND_URL = & $AZ containerapp show --name weaver-backend --resource-group $RESOURCE_GROUP --query "properties.configuration.ingress.fqdn" -o tsv
Write-Host "`nBackend deployed at: https://$BACKEND_URL" -ForegroundColor Green

# ==============================================================================
# Phase 4: Frontend (Static Web App)
# ==============================================================================
Write-Host "`n[Phase 4] Deploying frontend..." -ForegroundColor Yellow

Write-Host "Creating Static Web App..." -ForegroundColor Yellow
Write-Host "Note: Manual deployment required via GitHub Actions or Azure Portal" -ForegroundColor Yellow
Write-Host "  1. Go to Azure Portal > Static Web Apps" -ForegroundColor Cyan
Write-Host "  2. Create new Static Web App named 'weaver-frontend'" -ForegroundColor Cyan
Write-Host "  3. Link to your GitHub repository" -ForegroundColor Cyan
Write-Host "  4. Set build details:" -ForegroundColor Cyan
Write-Host "     - App location: /frontend" -ForegroundColor Cyan
Write-Host "     - Build location: /dist" -ForegroundColor Cyan
Write-Host "     - Environment variable: VITE_API_URL=https://$BACKEND_URL" -ForegroundColor Cyan

# ==============================================================================
# Summary
# ==============================================================================
Write-Host "`n========================================" -ForegroundColor Green
Write-Host "Deployment Complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Backend URL: https://$BACKEND_URL" -ForegroundColor Cyan
Write-Host "Health Check: https://$BACKEND_URL/health" -ForegroundColor Cyan
Write-Host ""
Write-Host "Next Steps:" -ForegroundColor Yellow
Write-Host "1. Test backend: curl https://$BACKEND_URL/health" -ForegroundColor White
Write-Host "2. Run database migration" -ForegroundColor White
Write-Host "3. Seed database" -ForegroundColor White
Write-Host "4. Deploy frontend via GitHub Actions or Azure Portal" -ForegroundColor White
Write-Host ""
Write-Host "Resources created in: $RESOURCE_GROUP" -ForegroundColor Cyan
Write-Host "View in portal: https://portal.azure.com/#resource/subscriptions/$SUBSCRIPTION_ID/resourceGroups/$RESOURCE_GROUP" -ForegroundColor Cyan
