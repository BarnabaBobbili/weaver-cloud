# Weaver Azure Cloud Deployment Script (PowerShell)
# Complete infrastructure setup for Azure-native deployment
#
# Prerequisites:
# - Azure CLI installed (az --version)
# - Logged in (az login)
# - Subscription set (az account set --subscription <id>)
#
# Usage: .\deploy.ps1

$ErrorActionPreference = "Stop"

# Configuration
$RESOURCE_GROUP = "weaver-rg"
$LOCATION = "centralindia"
$SUBSCRIPTION_ID = (az account show --query id -o tsv)

Write-Host "========================================" -ForegroundColor Green
Write-Host "Weaver Azure Deployment" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host "Subscription: $SUBSCRIPTION_ID" -ForegroundColor Cyan
Write-Host "Resource Group: $RESOURCE_GROUP" -ForegroundColor Cyan
Write-Host "Location: $LOCATION" -ForegroundColor Cyan
Write-Host ""

# ==============================================================================
# Phase 1: Foundation & Identity
# ==============================================================================
Write-Host "[Phase 1] Creating resource group and managed identity..." -ForegroundColor Yellow

# Create resource group
az group create --name $RESOURCE_GROUP --location $LOCATION

# Register providers
Write-Host "Registering Azure providers (this may take a few minutes)..." -ForegroundColor Yellow
az provider register --namespace Microsoft.App
az provider register --namespace Microsoft.ContainerRegistry
az provider register --namespace Microsoft.DBforPostgreSQL
az provider register --namespace Microsoft.KeyVault
az provider register --namespace Microsoft.ServiceBus
az provider register --namespace Microsoft.MachineLearningServices
az provider register --namespace Microsoft.Synapse
az provider register --namespace Microsoft.Cdn
az provider register --namespace Microsoft.ApiManagement
az provider register --namespace Microsoft.Insights

Start-Sleep -Seconds 30

# Create Managed Identity
az identity create --name weaver-backend-identity --resource-group $RESOURCE_GROUP

# Get identity IDs
$IDENTITY_CLIENT_ID = az identity show --name weaver-backend-identity --resource-group $RESOURCE_GROUP --query clientId -o tsv
$IDENTITY_PRINCIPAL_ID = az identity show --name weaver-backend-identity --resource-group $RESOURCE_GROUP --query principalId -o tsv
$IDENTITY_RESOURCE_ID = az identity show --name weaver-backend-identity --resource-group $RESOURCE_GROUP --query id -o tsv

Write-Host "Managed Identity created:" -ForegroundColor Green
Write-Host "  Client ID: $IDENTITY_CLIENT_ID" -ForegroundColor Cyan
Write-Host "  Principal ID: $IDENTITY_PRINCIPAL_ID" -ForegroundColor Cyan

# ==============================================================================
# Phase 2: Data Layer
# ==============================================================================
Write-Host "`n[Phase 2] Setting up data layer..." -ForegroundColor Yellow

# Create Key Vault
Write-Host "Creating Key Vault..." -ForegroundColor Yellow
az keyvault create `
  --name weaver-kv `
  --resource-group $RESOURCE_GROUP `
  --location $LOCATION `
  --enable-rbac-authorization true

# Grant managed identity access
$KV_ID = az keyvault show --name weaver-kv --query id -o tsv
az role assignment create `
  --assignee $IDENTITY_PRINCIPAL_ID `
  --role "Key Vault Secrets User" `
  --scope $KV_ID

# Grant current user access
$MY_OBJECT_ID = az ad signed-in-user show --query id -o tsv
az role assignment create `
  --assignee $MY_OBJECT_ID `
  --role "Key Vault Secrets Officer" `
  --scope $KV_ID

# Generate secrets
Write-Host "Generating secret values..." -ForegroundColor Yellow
$JWT_SECRET = python -c "import secrets; print(secrets.token_hex(32))"
$MFA_KEY = python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
$KEK_KEY = python -c "import os, base64; print(base64.b64encode(os.urandom(32)).decode())"

# Create PostgreSQL
Write-Host "Creating PostgreSQL Flexible Server (3-5 minutes)..." -ForegroundColor Yellow
$DB_PASSWORD = Read-Host -Prompt "Enter PostgreSQL admin password" -AsSecureString
$DB_PASSWORD_TEXT = [Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($DB_PASSWORD))

az postgres flexible-server create `
  --name weaver-db-prod `
  --resource-group $RESOURCE_GROUP `
  --location $LOCATION `
  --admin-user weaver_admin `
  --admin-password $DB_PASSWORD_TEXT `
  --sku-name Standard_B1ms `
  --tier Burstable `
  --storage-size 32 `
  --version 16 `
  --yes

az postgres flexible-server db create `
  --server-name weaver-db-prod `
  --resource-group $RESOURCE_GROUP `
  --database-name weaver

az postgres flexible-server firewall-rule create `
  --name AllowAzureServices `
  --resource-group $RESOURCE_GROUP `
  --server-name weaver-db-prod `
  --start-ip-address 0.0.0.0 `
  --end-ip-address 0.0.0.0

$DATABASE_URL = "postgresql+asyncpg://weaver_admin:$DB_PASSWORD_TEXT@weaver-db-prod.postgres.database.azure.com:5432/weaver"

# Create Blob Storage
Write-Host "Creating Blob Storage..." -ForegroundColor Yellow
az storage account create `
  --name weaverstorageprod `
  --resource-group $RESOURCE_GROUP `
  --location $LOCATION `
  --sku Standard_LRS `
  --kind StorageV2 `
  --min-tls-version TLS1_2 `
  --allow-blob-public-access false

az storage container create --name encrypted-payloads --account-name weaverstorageprod --auth-mode login
az storage container create --name ml-models --account-name weaverstorageprod --auth-mode login
az storage container create --name ml-datasets --account-name weaverstorageprod --auth-mode login

$STORAGE_ID = az storage account show --name weaverstorageprod --query id -o tsv
az role assignment create `
  --assignee $IDENTITY_PRINCIPAL_ID `
  --role "Storage Blob Data Contributor" `
  --scope $STORAGE_ID

$BLOB_CONN = az storage account show-connection-string --name weaverstorageprod --resource-group $RESOURCE_GROUP --query connectionString -o tsv

# Create Service Bus
Write-Host "Creating Service Bus..." -ForegroundColor Yellow
az servicebus namespace create `
  --name weaver-sb `
  --resource-group $RESOURCE_GROUP `
  --location $LOCATION `
  --sku Basic

az servicebus queue create --namespace-name weaver-sb --resource-group $RESOURCE_GROUP --name audit-events --max-size 1024
az servicebus queue create --namespace-name weaver-sb --resource-group $RESOURCE_GROUP --name analytics-sync --max-size 1024
az servicebus queue create --namespace-name weaver-sb --resource-group $RESOURCE_GROUP --name ml-retrain --max-size 1024
az servicebus queue create --namespace-name weaver-sb --resource-group $RESOURCE_GROUP --name classification-jobs --max-size 1024
az servicebus queue create --namespace-name weaver-sb --resource-group $RESOURCE_GROUP --name encryption-jobs --max-size 1024

$SB_CONN = az servicebus namespace authorization-rule keys list `
  --namespace-name weaver-sb `
  --resource-group $RESOURCE_GROUP `
  --name RootManageSharedAccessKey `
  --query primaryConnectionString -o tsv

# Create Application Insights
Write-Host "Creating Application Insights..." -ForegroundColor Yellow
az monitor log-analytics workspace create `
  --workspace-name weaver-logs `
  --resource-group $RESOURCE_GROUP `
  --location $LOCATION

az monitor app-insights component create `
  --app weaver-insights `
  --resource-group $RESOURCE_GROUP `
  --location $LOCATION `
  --workspace weaver-logs `
  --application-type web

$APPINSIGHTS_CONN = az monitor app-insights component show `
  --app weaver-insights `
  --resource-group $RESOURCE_GROUP `
  --query connectionString -o tsv

# Store secrets in Key Vault
Write-Host "Storing secrets in Key Vault..." -ForegroundColor Yellow
az keyvault secret set --vault-name weaver-kv --name "DATABASE-URL" --value $DATABASE_URL
az keyvault secret set --vault-name weaver-kv --name "JWT-SECRET-KEY" --value $JWT_SECRET
az keyvault secret set --vault-name weaver-kv --name "MFA-ENCRYPTION-KEY" --value $MFA_KEY
az keyvault secret set --vault-name weaver-kv --name "DATA-ENCRYPTION-KEK" --value $KEK_KEY
az keyvault secret set --vault-name weaver-kv --name "BLOB-CONNECTION-STRING" --value $BLOB_CONN
az keyvault secret set --vault-name weaver-kv --name "SERVICE-BUS-CONNECTION-STRING" --value $SB_CONN
az keyvault secret set --vault-name weaver-kv --name "APPINSIGHTS-CONNECTION-STRING" --value $APPINSIGHTS_CONN

# ==============================================================================
# Phase 3: Backend Containerization
# ==============================================================================
Write-Host "`n[Phase 3] Building and deploying backend..." -ForegroundColor Yellow

# Create Container Registry
az acr create `
  --name weaveracr `
  --resource-group $RESOURCE_GROUP `
  --sku Basic `
  --admin-enabled true

# Build image
Write-Host "Building Docker image (this may take several minutes)..." -ForegroundColor Yellow
az acr build `
  --registry weaveracr `
  --image weaver-backend:v1.0 `
  --file backend/Dockerfile `
  backend/

# Create Container Apps environment
az containerapp env create `
  --name weaver-env `
  --resource-group $RESOURCE_GROUP `
  --location $LOCATION

# Get ACR password
$ACR_PASSWORD = az acr credential show --name weaveracr --query 'passwords[0].value' -o tsv

# Deploy container
az containerapp create `
  --name weaver-backend `
  --resource-group $RESOURCE_GROUP `
  --environment weaver-env `
  --image weaveracr.azurecr.io/weaver-backend:v1.0 `
  --registry-server weaveracr.azurecr.io `
  --registry-username weaveracr `
  --registry-password $ACR_PASSWORD `
  --target-port 8000 `
  --ingress external `
  --min-replicas 1 `
  --max-replicas 5 `
  --cpu 1.0 `
  --memory 2.0Gi `
  --user-assigned $IDENTITY_RESOURCE_ID `
  --env-vars `
    "AZURE_CLIENT_ID=$IDENTITY_CLIENT_ID" `
    "KEY_VAULT_URL=https://weaver-kv.vault.azure.net/" `
    "BLOB_STORAGE_ACCOUNT=weaverstorageprod" `
    "SERVICE_BUS_NAMESPACE=weaver-sb" `
    "AZURE_SUBSCRIPTION_ID=$SUBSCRIPTION_ID" `
    "AZURE_RESOURCE_GROUP=$RESOURCE_GROUP" `
    "AZURE_ML_WORKSPACE=weaver-ml"

$BACKEND_URL = az containerapp show --name weaver-backend --resource-group $RESOURCE_GROUP --query 'properties.configuration.ingress.fqdn' -o tsv

Write-Host "`nBackend deployed at: https://$BACKEND_URL" -ForegroundColor Green

# ==============================================================================
# Phase 4: Frontend Deployment
# ==============================================================================
Write-Host "`n[Phase 4] Deploying frontend..." -ForegroundColor Yellow

# Build React frontend
Write-Host "Building React frontend..." -ForegroundColor Yellow
Push-Location frontend
npm install
$env:VITE_API_URL = "https://$BACKEND_URL"
npm run build
Pop-Location

# Create Static Web App
az staticwebapp create `
  --name weaver-frontend `
  --resource-group $RESOURCE_GROUP `
  --location $LOCATION `
  --sku Standard

$FRONTEND_URL = az staticwebapp show --name weaver-frontend --resource-group $RESOURCE_GROUP --query 'defaultHostname' -o tsv

# ==============================================================================
# Summary
# ==============================================================================
Write-Host "`n========================================" -ForegroundColor Green
Write-Host "Deployment Complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Resources created:" -ForegroundColor Cyan
Write-Host "  - Backend URL: https://$BACKEND_URL" -ForegroundColor White
Write-Host "  - Frontend URL: https://$FRONTEND_URL" -ForegroundColor White
Write-Host "  - Key Vault: https://weaver-kv.vault.azure.net/" -ForegroundColor White
Write-Host "  - PostgreSQL: weaver-db-prod.postgres.database.azure.com" -ForegroundColor White
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "  1. Test backend: curl https://$BACKEND_URL/health" -ForegroundColor White
Write-Host "  2. Seed database: cd backend && python scripts/seed_db.py" -ForegroundColor White
Write-Host "  3. Deploy frontend: az staticwebapp deploy --name weaver-frontend ..." -ForegroundColor White
Write-Host ""
Write-Host "To tear down: az group delete --name $RESOURCE_GROUP --yes --no-wait" -ForegroundColor Red
