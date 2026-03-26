# Weaver Azure Cloud Deployment Guide

## ✅ Completed: All Code Changes (60%)

**Status:** 24/40 tasks complete

All application code changes have been implemented:
- ✅ Azure service modules (Blob, Service Bus, ML, Synapse, Telemetry)
- ✅ Main application updates (health checks, telemetry, startup events)
- ✅ Hybrid storage implementation (Blob for >1MB, DB for <1MB)
- ✅ Database model updates (blob_url column)
- ✅ ML model loading from Azure ML registry
- ✅ Analytics routing (PostgreSQL for realtime, Synapse for heavy queries)
- ✅ Frontend configuration (production API URL)
- ✅ Docker containerization files
- ✅ CI/CD pipelines
- ✅ Infrastructure deployment scripts

---

## 🚀 Next Steps: Azure Infrastructure Deployment (40%)

The remaining 16 tasks require Azure CLI and an active Azure subscription. Follow the steps below to complete the deployment.

### Prerequisites

Before starting, ensure you have:

1. **Azure Account**
   - Active subscription ([Azure for Students](https://azure.microsoft.com/free/students/) gives $100 credit)
   - Or [Azure Free Account](https://azure.microsoft.com/free/)

2. **Azure CLI** (v2.50+)
   ```powershell
   # Install Azure CLI
   winget install -e --id Microsoft.AzureCLI
   
   # Verify installation
   az --version
   ```

3. **Login to Azure**
   ```powershell
   # Opens browser for authentication
   az login
   
   # List subscriptions
   az account list --output table
   
   # Set active subscription
   az account set --subscription "<YOUR_SUBSCRIPTION_ID>"
   
   # Verify
   az account show
   ```

---

## Deployment Option 1: Automated Script (Recommended)

### Windows (PowerShell)

```powershell
cd "E:\MTech\MTech Sem2\Cloud\Project\Weaver\infra"
.\deploy.ps1
```

### Linux/Mac (Bash)

```bash
cd /path/to/Weaver/infra
chmod +x deploy.sh
./deploy.sh
```

The script will:
1. Create all Azure resources (takes 15-30 minutes)
2. Configure networking and security
3. Build and deploy containers
4. Set up monitoring and alerts
5. Provide URLs for backend and frontend

### What the Script Does

| Phase | Resources Created | Duration |
|-------|-------------------|----------|
| Phase 1 | Resource Group, Managed Identity | 2 min |
| Phase 2 | Key Vault, PostgreSQL, Blob Storage, Service Bus, App Insights | 8-10 min |
| Phase 3 | Container Registry, Backend Container App | 5-7 min |
| Phase 4 | Static Web App (Frontend) | 3-5 min |
| **Total** | **12+ Azure Resources** | **18-27 min** |

---

## Deployment Option 2: Manual Step-by-Step

If you prefer manual control or the script fails, follow these steps:

### Step 1: Foundation & Identity (Phase 1)

```powershell
# Create resource group
$RESOURCE_GROUP = "weaver-rg"
$LOCATION = "centralindia"

az group create --name $RESOURCE_GROUP --location $LOCATION

# Register providers (only needs to be done once per subscription)
az provider register --namespace Microsoft.App
az provider register --namespace Microsoft.ContainerRegistry
az provider register --namespace Microsoft.DBforPostgreSQL
az provider register --namespace Microsoft.KeyVault
az provider register --namespace Microsoft.ServiceBus
az provider register --namespace Microsoft.MachineLearningServices
az provider register --namespace Microsoft.Insights

# Wait for providers to register (check status)
az provider show --namespace Microsoft.App --query registrationState -o tsv

# Create Managed Identity
az identity create --name weaver-backend-identity --resource-group $RESOURCE_GROUP

# Save these values - you'll need them
$IDENTITY_CLIENT_ID = az identity show --name weaver-backend-identity --resource-group $RESOURCE_GROUP --query clientId -o tsv
$IDENTITY_PRINCIPAL_ID = az identity show --name weaver-backend-identity --resource-group $RESOURCE_GROUP --query principalId -o tsv
$IDENTITY_RESOURCE_ID = az identity show --name weaver-backend-identity --resource-group $RESOURCE_GROUP --query id -o tsv

Write-Host "Identity Client ID: $IDENTITY_CLIENT_ID"
Write-Host "Identity Principal ID: $IDENTITY_PRINCIPAL_ID"
```

### Step 2: Key Vault & Secrets (Phase 2.1)

```powershell
# Create Key Vault
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

# Grant yourself access to set secrets
$MY_OBJECT_ID = az ad signed-in-user show --query id -o tsv
az role assignment create `
  --assignee $MY_OBJECT_ID `
  --role "Key Vault Secrets Officer" `
  --scope $KV_ID

# Generate secrets
$JWT_SECRET = python -c "import secrets; print(secrets.token_hex(32))"
$MFA_KEY = python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
$KEK_KEY = python -c "import os, base64; print(base64.b64encode(os.urandom(32)).decode())"

Write-Host "Generated secrets - save these securely!"
Write-Host "JWT_SECRET: $JWT_SECRET"
Write-Host "MFA_KEY: $MFA_KEY"
Write-Host "KEK_KEY: $KEK_KEY"

# Store secrets in Key Vault (we'll add DATABASE-URL after creating PostgreSQL)
az keyvault secret set --vault-name weaver-kv --name "JWT-SECRET-KEY" --value $JWT_SECRET
az keyvault secret set --vault-name weaver-kv --name "MFA-ENCRYPTION-KEY" --value $MFA_KEY
az keyvault secret set --vault-name weaver-kv --name "DATA-ENCRYPTION-KEK" --value $KEK_KEY
```

### Step 3: PostgreSQL Database (Phase 2.2)

```powershell
# Create PostgreSQL server (takes 3-5 minutes)
$DB_PASSWORD = Read-Host -Prompt "Enter PostgreSQL admin password (min 8 chars, mixed case + numbers)" -AsSecureString
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

# Create database
az postgres flexible-server db create `
  --server-name weaver-db-prod `
  --resource-group $RESOURCE_GROUP `
  --database-name weaver

# Allow Azure services
az postgres flexible-server firewall-rule create `
  --name AllowAzureServices `
  --resource-group $RESOURCE_GROUP `
  --server-name weaver-db-prod `
  --start-ip-address 0.0.0.0 `
  --end-ip-address 0.0.0.0

# Store DATABASE-URL in Key Vault
$DATABASE_URL = "postgresql+asyncpg://weaver_admin:$DB_PASSWORD_TEXT@weaver-db-prod.postgres.database.azure.com:5432/weaver"
az keyvault secret set --vault-name weaver-kv --name "DATABASE-URL" --value $DATABASE_URL
```

### Step 4: Blob Storage (Phase 2.3)

```powershell
# Create storage account
az storage account create `
  --name weaverstorageprod `
  --resource-group $RESOURCE_GROUP `
  --location $LOCATION `
  --sku Standard_LRS `
  --kind StorageV2 `
  --min-tls-version TLS1_2 `
  --allow-blob-public-access false

# Create containers
az storage container create --name encrypted-payloads --account-name weaverstorageprod --auth-mode login
az storage container create --name ml-models --account-name weaverstorageprod --auth-mode login
az storage container create --name ml-datasets --account-name weaverstorageprod --auth-mode login

# Grant managed identity access
$STORAGE_ID = az storage account show --name weaverstorageprod --query id -o tsv
az role assignment create `
  --assignee $IDENTITY_PRINCIPAL_ID `
  --role "Storage Blob Data Contributor" `
  --scope $STORAGE_ID

# Get connection string and store in Key Vault
$BLOB_CONN = az storage account show-connection-string --name weaverstorageprod --resource-group $RESOURCE_GROUP --query connectionString -o tsv
az keyvault secret set --vault-name weaver-kv --name "BLOB-CONNECTION-STRING" --value $BLOB_CONN
```

### Step 5: Service Bus (Phase 6)

```powershell
# Create Service Bus namespace
az servicebus namespace create `
  --name weaver-sb `
  --resource-group $RESOURCE_GROUP `
  --location $LOCATION `
  --sku Basic

# Create queues
az servicebus queue create --namespace-name weaver-sb --resource-group $RESOURCE_GROUP --name audit-events --max-size 1024
az servicebus queue create --namespace-name weaver-sb --resource-group $RESOURCE_GROUP --name analytics-sync --max-size 1024
az servicebus queue create --namespace-name weaver-sb --resource-group $RESOURCE_GROUP --name ml-retrain --max-size 1024
az servicebus queue create --namespace-name weaver-sb --resource-group $RESOURCE_GROUP --name classification-jobs --max-size 1024
az servicebus queue create --namespace-name weaver-sb --resource-group $RESOURCE_GROUP --name encryption-jobs --max-size 1024

# Get connection string
$SB_CONN = az servicebus namespace authorization-rule keys list `
  --namespace-name weaver-sb `
  --resource-group $RESOURCE_GROUP `
  --name RootManageSharedAccessKey `
  --query primaryConnectionString -o tsv

az keyvault secret set --vault-name weaver-kv --name "SERVICE-BUS-CONNECTION-STRING" --value $SB_CONN
```

### Step 6: Application Insights (Phase 9)

```powershell
# Create Log Analytics workspace
az monitor log-analytics workspace create `
  --workspace-name weaver-logs `
  --resource-group $RESOURCE_GROUP `
  --location $LOCATION

# Create Application Insights
az monitor app-insights component create `
  --app weaver-insights `
  --resource-group $RESOURCE_GROUP `
  --location $LOCATION `
  --workspace weaver-logs `
  --application-type web

# Get connection string
$APPINSIGHTS_CONN = az monitor app-insights component show `
  --app weaver-insights `
  --resource-group $RESOURCE_GROUP `
  --query connectionString -o tsv

az keyvault secret set --vault-name weaver-kv --name "APPINSIGHTS-CONNECTION-STRING" --value $APPINSIGHTS_CONN
```

### Step 7: Container Registry & Backend (Phase 3)

```powershell
# Create Container Registry
az acr create `
  --name weaveracr `
  --resource-group $RESOURCE_GROUP `
  --sku Basic `
  --admin-enabled true

# Build and push backend image (takes 5-10 minutes)
cd "E:\MTech\MTech Sem2\Cloud\Project\Weaver"
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

# Get ACR credentials
$ACR_PASSWORD = az acr credential show --name weaveracr --query 'passwords[0].value' -o tsv

# Deploy backend container
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
    "AZURE_SUBSCRIPTION_ID=$(az account show --query id -o tsv)" `
    "AZURE_RESOURCE_GROUP=$RESOURCE_GROUP"

# Get backend URL
$BACKEND_URL = az containerapp show --name weaver-backend --resource-group $RESOURCE_GROUP --query 'properties.configuration.ingress.fqdn' -o tsv
Write-Host "Backend URL: https://$BACKEND_URL"

# Test health endpoint
curl "https://$BACKEND_URL/health"
```

### Step 8: Seed the Database

```powershell
# Temporarily allow your IP to connect
$MY_IP = (Invoke-WebRequest -Uri "https://api.ipify.org").Content
az postgres flexible-server firewall-rule create `
  --name AllowMyIP `
  --resource-group $RESOURCE_GROUP `
  --server-name weaver-db-prod `
  --start-ip-address $MY_IP `
  --end-ip-address $MY_IP

# Set environment variables for seeding
cd "E:\MTech\MTech Sem2\Cloud\Project\Weaver\backend"
$env:DATABASE_URL = $DATABASE_URL
$env:KEY_VAULT_URL = "https://weaver-kv.vault.azure.net/"

# Run seed script
python scripts/seed_db.py

# Run database migration for blob_url column
python migrations/add_blob_url_column.py
```

### Step 9: Deploy Frontend (Phase 4)

```powershell
# Build frontend
cd "E:\MTech\MTech Sem2\Cloud\Project\Weaver\frontend"
npm install
$env:VITE_API_URL = "https://$BACKEND_URL"
npm run build

# Create Static Web App
cd ..
az staticwebapp create `
  --name weaver-frontend `
  --resource-group $RESOURCE_GROUP `
  --location $LOCATION `
  --sku Standard

# Get deployment token
$SWA_TOKEN = az staticwebapp secrets list --name weaver-frontend --resource-group $RESOURCE_GROUP --query properties.apiKey -o tsv

# Deploy (requires Azure Static Web Apps CLI)
npm install -g @azure/static-web-apps-cli
swa deploy --app-location ./frontend --output-location dist --deployment-token $SWA_TOKEN
```

---

## Post-Deployment Tasks

### 1. Verify All Services

```powershell
# Check backend health
$BACKEND_URL = az containerapp show --name weaver-backend --resource-group $RESOURCE_GROUP --query 'properties.configuration.ingress.fqdn' -o tsv
curl "https://$BACKEND_URL/health"

# Check frontend
$FRONTEND_URL = az staticwebapp show --name weaver-frontend --resource-group $RESOURCE_GROUP --query 'defaultHostname' -o tsv
curl "https://$FRONTEND_URL"

# Test login
# Open: https://$FRONTEND_URL
# Login: admin@weaver.local / Admin@1234
```

### 2. Set Up CI/CD (GitHub Actions)

Add these secrets to your GitHub repository:

```bash
# Get Azure credentials for GitHub Actions
az ad sp create-for-rbac --name "weaver-github-actions" --role contributor --scopes /subscriptions/<SUBSCRIPTION_ID>/resourceGroups/weaver-rg --sdk-auth

# Copy the JSON output and add as GitHub secret: AZURE_CREDENTIALS
```

**GitHub Secrets to Add:**
- `AZURE_CREDENTIALS` - Service principal JSON from above
- `ACR_USERNAME` - `weaveracr`
- `ACR_PASSWORD` - Get from: `az acr credential show --name weaveracr --query 'passwords[0].value' -o tsv`

### 3. Update CORS Origins

```powershell
# Add frontend URL to backend CORS
$FRONTEND_URL = az staticwebapp show --name weaver-frontend --resource-group $RESOURCE_GROUP --query 'defaultHostname' -o tsv

az containerapp update `
  --name weaver-backend `
  --resource-group $RESOURCE_GROUP `
  --set-env-vars "CORS_ORIGINS=https://$FRONTEND_URL"
```

### 4. Configure Custom Domain (Optional)

```powershell
# For frontend
az staticwebapp hostname set --name weaver-frontend --resource-group $RESOURCE_GROUP --hostname "weaver.yourdomain.com"

# For backend (requires Azure Front Door or Application Gateway)
```

---

## Cost Management

### Monitor Costs

```powershell
# View current month costs
az consumption usage list --start-date (Get-Date).AddDays(-30).ToString("yyyy-MM-dd") --end-date (Get-Date).ToString("yyyy-MM-dd")

# Set budget alert
az consumption budget create --amount 100 --category Cost --time-grain Monthly --resource-group weaver-rg --name weaver-monthly-budget
```

### Estimated Monthly Cost (Dev/Student Tier)

| Service | Monthly Cost |
|---------|--------------|
| PostgreSQL (B1ms) | ~$13 |
| Container Apps | ~$0-5 |
| Blob Storage (<1GB) | ~$0.02 |
| Key Vault | ~$0.03 |
| Service Bus (Basic) | ~$0.05 |
| Application Insights | Free (<5GB) |
| Container Registry | ~$5 |
| Static Web Apps | ~$9 |
| **Total** | **~$27-32/month** |

> **Tip:** Use [Azure Cost Calculator](https://azure.microsoft.com/pricing/calculator/) for precise estimates.

---

## Troubleshooting

### Issue: Container App not starting

```powershell
# View logs
az containerapp logs show --name weaver-backend --resource-group weaver-rg --tail 100

# Check environment variables
az containerapp show --name weaver-backend --resource-group weaver-rg --query 'properties.template.containers[0].env'

# Restart container
az containerapp restart --name weaver-backend --resource-group weaver-rg
```

### Issue: Database connection fails

```powershell
# Check firewall rules
az postgres flexible-server firewall-rule list --server-name weaver-db-prod --resource-group weaver-rg

# Test connection from container
az containerapp exec --name weaver-backend --resource-group weaver-rg --command /bin/bash
# Inside container:
psql "$DATABASE_URL"
```

### Issue: Key Vault access denied

```powershell
# Verify role assignments
az role assignment list --assignee $IDENTITY_PRINCIPAL_ID --all

# Re-grant access
az role assignment create --assignee $IDENTITY_PRINCIPAL_ID --role "Key Vault Secrets User" --scope $KV_ID
```

### Issue: Blob upload fails

```powershell
# Check managed identity has blob access
az role assignment list --assignee $IDENTITY_PRINCIPAL_ID --scope $STORAGE_ID

# Verify containers exist
az storage container list --account-name weaverstorageprod --auth-mode login
```

---

## Cleanup / Teardown

To delete all resources and stop billing:

```powershell
# Delete everything
az group delete --name weaver-rg --yes --no-wait

# This deletes:
# - All compute (Container Apps, Static Web Apps)
# - All storage (PostgreSQL, Blob Storage)
# - All secrets (Key Vault)
# - All networking (VNet, if configured)
# - All monitoring (Application Insights)
```

**⚠️ Warning:** This is irreversible. Export any data you need first!

---

## Next Steps

1. **Complete Infrastructure Deployment** - Follow steps above
2. **Test All Features** - Use the testing checklist in `IMPLEMENTATION_STATUS.md`
3. **Set Up Monitoring** - Configure alerts in Application Insights
4. **Enable CI/CD** - Push to GitHub to trigger automated deployments
5. **Security Hardening** - Add VNet, private endpoints (Phase 10)
6. **Custom Domain** - Configure DNS for production domain

---

## Support & Resources

- **Full Implementation Plan:** `AZURE_CLOUD_IMPLEMENTATION_PLAN.md`
- **Status Tracking:** `IMPLEMENTATION_STATUS.md`
- **Azure Documentation:** https://docs.microsoft.com/azure
- **GitHub Actions:** https://docs.github.com/actions

For issues or questions, refer to the troubleshooting section or check Azure Portal diagnostics.
