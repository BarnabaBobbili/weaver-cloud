#!/bin/bash
#
# Weaver Azure Cloud Deployment Script
# Complete infrastructure setup for Azure-native deployment
#
# Prerequisites:
# - Azure CLI installed (az --version)
# - Logged in (az login)
# - Subscription set (az account set --subscription <id>)
#
# Usage:
#   chmod +x deploy.sh
#   ./deploy.sh

set -e  # Exit on error

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Configuration
RESOURCE_GROUP="weaver-rg"
LOCATION="centralindia"
SUBSCRIPTION_ID=$(az account show --query id -o tsv)

info "Starting Weaver Azure deployment..."
info "Subscription: $SUBSCRIPTION_ID"
info "Resource Group: $RESOURCE_GROUP"
info "Location: $LOCATION"

# ==============================================================================
# Phase 1: Foundation & Identity
# ==============================================================================
info "Phase 1: Creating resource group and managed identity..."

# Create resource group
az group create --name $RESOURCE_GROUP --location $LOCATION

# Register providers
info "Registering Azure providers (this may take a few minutes)..."
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

# Wait for providers to register
info "Waiting for provider registration..."
sleep 30

# Create Managed Identity
az identity create --name weaver-backend-identity --resource-group $RESOURCE_GROUP

# Get identity IDs
IDENTITY_CLIENT_ID=$(az identity show --name weaver-backend-identity --resource-group $RESOURCE_GROUP --query clientId -o tsv)
IDENTITY_PRINCIPAL_ID=$(az identity show --name weaver-backend-identity --resource-group $RESOURCE_GROUP --query principalId -o tsv)
IDENTITY_RESOURCE_ID=$(az identity show --name weaver-backend-identity --resource-group $RESOURCE_GROUP --query id -o tsv)

info "Managed Identity created:"
info "  Client ID: $IDENTITY_CLIENT_ID"
info "  Principal ID: $IDENTITY_PRINCIPAL_ID"

# ==============================================================================
# Phase 2: Data Layer
# ==============================================================================
info "Phase 2: Setting up data layer (Key Vault, PostgreSQL, Blob Storage)..."

# Create Key Vault
info "Creating Key Vault..."
az keyvault create \
  --name weaver-kv \
  --resource-group $RESOURCE_GROUP \
  --location $LOCATION \
  --enable-rbac-authorization true

# Grant managed identity access to Key Vault
KV_ID=$(az keyvault show --name weaver-kv --query id -o tsv)
az role assignment create \
  --assignee $IDENTITY_PRINCIPAL_ID \
  --role "Key Vault Secrets User" \
  --scope $KV_ID

# Grant current user access to set secrets
MY_OBJECT_ID=$(az ad signed-in-user show --query id -o tsv)
az role assignment create \
  --assignee $MY_OBJECT_ID \
  --role "Key Vault Secrets Officer" \
  --scope $KV_ID

info "Generating secret values..."
JWT_SECRET=$(python3 -c "import secrets; print(secrets.token_hex(32))")
MFA_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
KEK_KEY=$(python3 -c "import os, base64; print(base64.b64encode(os.urandom(32)).decode())")

# Create PostgreSQL
info "Creating PostgreSQL Flexible Server (this takes 3-5 minutes)..."
read -sp "Enter PostgreSQL admin password: " DB_PASSWORD
echo
az postgres flexible-server create \
  --name weaver-db-prod \
  --resource-group $RESOURCE_GROUP \
  --location $LOCATION \
  --admin-user weaver_admin \
  --admin-password "$DB_PASSWORD" \
  --sku-name Standard_B1ms \
  --tier Burstable \
  --storage-size 32 \
  --version 16 \
  --yes

# Create database
az postgres flexible-server db create \
  --server-name weaver-db-prod \
  --resource-group $RESOURCE_GROUP \
  --database-name weaver

# Allow Azure services
az postgres flexible-server firewall-rule create \
  --name AllowAzureServices \
  --resource-group $RESOURCE_GROUP \
  --server-name weaver-db-prod \
  --start-ip-address 0.0.0.0 \
  --end-ip-address 0.0.0.0

# Store DATABASE_URL in Key Vault
DATABASE_URL="postgresql+asyncpg://weaver_admin:$DB_PASSWORD@weaver-db-prod.postgres.database.azure.com:5432/weaver"

# Create Blob Storage
info "Creating Blob Storage..."
az storage account create \
  --name weaverstorageprod \
  --resource-group $RESOURCE_GROUP \
  --location $LOCATION \
  --sku Standard_LRS \
  --kind StorageV2 \
  --min-tls-version TLS1_2 \
  --allow-blob-public-access false

# Create containers
az storage container create --name encrypted-payloads --account-name weaverstorageprod --auth-mode login
az storage container create --name ml-models --account-name weaverstorageprod --auth-mode login
az storage container create --name ml-datasets --account-name weaverstorageprod --auth-mode login

# Grant managed identity blob access
STORAGE_ID=$(az storage account show --name weaverstorageprod --query id -o tsv)
az role assignment create \
  --assignee $IDENTITY_PRINCIPAL_ID \
  --role "Storage Blob Data Contributor" \
  --scope $STORAGE_ID

# Get blob connection string
BLOB_CONN=$(az storage account show-connection-string --name weaverstorageprod --resource-group $RESOURCE_GROUP --query connectionString -o tsv)

# Create Service Bus
info "Creating Service Bus..."
az servicebus namespace create \
  --name weaver-sb \
  --resource-group $RESOURCE_GROUP \
  --location $LOCATION \
  --sku Basic

# Create queues
az servicebus queue create --namespace-name weaver-sb --resource-group $RESOURCE_GROUP --name audit-events --max-size 1024
az servicebus queue create --namespace-name weaver-sb --resource-group $RESOURCE_GROUP --name analytics-sync --max-size 1024
az servicebus queue create --namespace-name weaver-sb --resource-group $RESOURCE_GROUP --name ml-retrain --max-size 1024
az servicebus queue create --namespace-name weaver-sb --resource-group $RESOURCE_GROUP --name classification-jobs --max-size 1024
az servicebus queue create --namespace-name weaver-sb --resource-group $RESOURCE_GROUP --name encryption-jobs --max-size 1024

# Get Service Bus connection string
SB_CONN=$(az servicebus namespace authorization-rule keys list \
  --namespace-name weaver-sb \
  --resource-group $RESOURCE_GROUP \
  --name RootManageSharedAccessKey \
  --query primaryConnectionString -o tsv)

# Create Application Insights
info "Creating Application Insights..."
az monitor log-analytics workspace create \
  --workspace-name weaver-logs \
  --resource-group $RESOURCE_GROUP \
  --location $LOCATION

az monitor app-insights component create \
  --app weaver-insights \
  --resource-group $RESOURCE_GROUP \
  --location $LOCATION \
  --workspace weaver-logs \
  --application-type web

# Get App Insights connection string
APPINSIGHTS_CONN=$(az monitor app-insights component show \
  --app weaver-insights \
  --resource-group $RESOURCE_GROUP \
  --query connectionString -o tsv)

# Store all secrets in Key Vault
info "Storing secrets in Key Vault..."
az keyvault secret set --vault-name weaver-kv --name "DATABASE-URL" --value "$DATABASE_URL"
az keyvault secret set --vault-name weaver-kv --name "JWT-SECRET-KEY" --value "$JWT_SECRET"
az keyvault secret set --vault-name weaver-kv --name "MFA-ENCRYPTION-KEY" --value "$MFA_KEY"
az keyvault secret set --vault-name weaver-kv --name "DATA-ENCRYPTION-KEK" --value "$KEK_KEY"
az keyvault secret set --vault-name weaver-kv --name "BLOB-CONNECTION-STRING" --value "$BLOB_CONN"
az keyvault secret set --vault-name weaver-kv --name "SERVICE-BUS-CONNECTION-STRING" --value "$SB_CONN"
az keyvault secret set --vault-name weaver-kv --name "APPINSIGHTS-CONNECTION-STRING" --value "$APPINSIGHTS_CONN"

# ==============================================================================
# Phase 3: Backend Containerization
# ==============================================================================
info "Phase 3: Building and deploying backend container..."

# Create Container Registry
info "Creating Container Registry..."
az acr create \
  --name weaveracr \
  --resource-group $RESOURCE_GROUP \
  --sku Basic \
  --admin-enabled true

# Build and push backend image
info "Building backend Docker image (this may take a few minutes)..."
az acr build \
  --registry weaveracr \
  --image weaver-backend:v1.0 \
  --file backend/Dockerfile \
  backend/

# Create Container Apps environment
info "Creating Container Apps environment..."
az containerapp env create \
  --name weaver-env \
  --resource-group $RESOURCE_GROUP \
  --location $LOCATION

# Get ACR credentials
ACR_PASSWORD=$(az acr credential show --name weaveracr --query 'passwords[0].value' -o tsv)

# Deploy backend container
info "Deploying backend container..."
az containerapp create \
  --name weaver-backend \
  --resource-group $RESOURCE_GROUP \
  --environment weaver-env \
  --image weaveracr.azurecr.io/weaver-backend:v1.0 \
  --registry-server weaveracr.azurecr.io \
  --registry-username weaveracr \
  --registry-password "$ACR_PASSWORD" \
  --target-port 8000 \
  --ingress external \
  --min-replicas 1 \
  --max-replicas 5 \
  --cpu 1.0 \
  --memory 2.0Gi \
  --user-assigned "$IDENTITY_RESOURCE_ID" \
  --env-vars \
    "AZURE_CLIENT_ID=$IDENTITY_CLIENT_ID" \
    "KEY_VAULT_URL=https://weaver-kv.vault.azure.net/" \
    "BLOB_STORAGE_ACCOUNT=weaverstorageprod" \
    "SERVICE_BUS_NAMESPACE=weaver-sb" \
    "AZURE_SUBSCRIPTION_ID=$SUBSCRIPTION_ID" \
    "AZURE_RESOURCE_GROUP=$RESOURCE_GROUP" \
    "AZURE_ML_WORKSPACE=weaver-ml"

# Get backend URL
BACKEND_URL=$(az containerapp show --name weaver-backend --resource-group $RESOURCE_GROUP --query 'properties.configuration.ingress.fqdn' -o tsv)
info "Backend deployed at: https://$BACKEND_URL"

# ==============================================================================
# Phase 4: Frontend Deployment
# ==============================================================================
info "Phase 4: Deploying frontend..."

# Build React frontend
info "Building React frontend..."
cd frontend
npm install
VITE_API_URL="https://$BACKEND_URL" npm run build
cd ..

# Create and deploy Static Web App
info "Creating Static Web App..."
az staticwebapp create \
  --name weaver-frontend \
  --resource-group $RESOURCE_GROUP \
  --location $LOCATION \
  --sku Standard

# Note: Actual deployment requires GitHub integration or manual upload
# For manual upload, use: az staticwebapp deploy

FRONTEND_URL=$(az staticwebapp show --name weaver-frontend --resource-group $RESOURCE_GROUP --query 'defaultHostname' -o tsv)
info "Frontend will be available at: https://$FRONTEND_URL"

# ==============================================================================
# Phase 5: API Management & Front Door
# ==============================================================================
info "Phase 5: Setting up API Management and Front Door..."

# Create API Management (Consumption tier)
info "Creating API Management (this can take 5-10 minutes)..."
az apim create \
  --name weaver-apim \
  --resource-group $RESOURCE_GROUP \
  --publisher-name "Weaver" \
  --publisher-email "admin@weaver.local" \
  --sku-name Consumption \
  --location $LOCATION

# Import OpenAPI spec
az apim api import \
  --resource-group $RESOURCE_GROUP \
  --service-name weaver-apim \
  --api-id weaver-api \
  --path "api" \
  --specification-format OpenApi \
  --specification-url "https://$BACKEND_URL/api/openapi.json" \
  --service-url "https://$BACKEND_URL"

# ==============================================================================
# Summary
# ==============================================================================
info "=========================================="
info "Deployment Complete!"
info "=========================================="
info ""
info "Resources created:"
info "  - Resource Group: $RESOURCE_GROUP"
info "  - Backend URL: https://$BACKEND_URL"
info "  - Frontend URL: https://$FRONTEND_URL"
info "  - Key Vault: https://weaver-kv.vault.azure.net/"
info "  - PostgreSQL: weaver-db-prod.postgres.database.azure.com"
info "  - Blob Storage: weaverstorageprod.blob.core.windows.net"
info ""
info "Next steps:"
info "  1. Test backend health: curl https://$BACKEND_URL/health"
info "  2. Run database seed: cd backend && python scripts/seed_db.py"
info "  3. Deploy frontend: az staticwebapp deploy --name weaver-frontend --app-location ./frontend --output-location dist"
info "  4. Set up CI/CD with GitHub Actions"
info ""
warn "Important: Save these credentials securely!"
info "  - PostgreSQL password: [entered during setup]"
info "  - ACR password: $ACR_PASSWORD"
info ""
info "To tear down all resources:"
info "  az group delete --name $RESOURCE_GROUP --yes --no-wait"
