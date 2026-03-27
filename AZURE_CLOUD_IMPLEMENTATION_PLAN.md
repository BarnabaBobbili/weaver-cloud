# Weaver — Azure Cloud Implementation Plan

> **Status update (2026-03-27):** This file is retained as the original planning artifact.  
> For current implementation state and verified runtime details, use:
> - `README.md`
> - `IMPLEMENTATION_STATUS.md`
> - `AZURE_IMPLEMENTATION_COMPLETE.md`
> - `docs/PROJECT_DOCUMENTATION.md`

## Full Cloud-Only Deployment Guide (No Local Fallback)

> **Project**: AI-Driven Adaptive Cryptographic Policy Engine
> **Goal**: Deploy Weaver as a **100% cloud-native** application on Azure. This is a dedicated cloud copy — there is NO local fallback. Every service, secret, model, and data store runs exclusively on Azure.
> **Approach**: All-in cloud. The `.env` file is deleted. Config loads from Key Vault only. ML models load from Azure ML only. Files go to Blob Storage only. No dual-mode, no conditionals.

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Azure Services Mapping](#2-azure-services-mapping)
3. [Phase 1 — Foundation & Identity](#phase-1--foundation--identity-setup)
4. [Phase 2 — Data Layer](#phase-2--data-layer)
5. [Phase 3 — Backend Containerization](#phase-3--backend-containerization)
6. [Phase 4 — Frontend Deployment](#phase-4--frontend-deployment)
7. [Phase 5 — API Management & Front Door](#phase-5--api-management--front-door)
8. [Phase 6 — Async Messaging (Service Bus)](#phase-6--async-messaging-service-bus)
9. [Phase 7 — ML Pipeline (Azure ML)](#phase-7--ml-pipeline-azure-ml)
10. [Phase 8 — Analytics (Synapse)](#phase-8--analytics-azure-synapse)
11. [Phase 9 — Monitoring & Observability](#phase-9--monitoring--observability)
12. [Phase 10 — Security Hardening](#phase-10--security-hardening)
13. [File-by-File Change List](#file-by-file-change-list)
14. [New Files to Create](#new-files-to-create)
15. [Azure CLI Commands (Full Script)](#azure-cli-commands-full-script)
16. [Cost Estimation](#cost-estimation)
17. [Step-by-Step Setup Guide](#step-by-step-setup-guide--how-to-run-the-project)
18. [Verification Walkthrough](#verification-walkthrough--testing-every-feature)
19. [Troubleshooting](#troubleshooting)
20. [Teardown (Cleanup)](#teardown--cleanup)

---

## 1. Architecture Overview

### Current Local Architecture
```
Browser (localhost:5173)
  └─ Vite Dev Server (React + TypeScript)
       └─ Proxy /api → localhost:8000
            └─ FastAPI (Uvicorn)
                 ├─ SQLAlchemy async → Supabase PostgreSQL
                 ├─ ML Model (joblib file on disk)
                 ├─ AES-GCM Encryption (DEK/KEK in memory)
                 ├─ JWT Auth + MFA (TOTP)
                 └─ Secrets from .env file
```

### Target Azure Architecture
```
Internet
  └─ Azure Front Door (Global CDN + WAF + SSL)
       ├─ /api/* → Azure API Management
       │            └─ Azure Container Apps (FastAPI backend)
       │                 ├─ Entra ID Managed Identity (service-to-service auth)
       │                 ├─ Azure PostgreSQL Flexible Server
       │                 ├─ Azure Blob Storage (large encrypted files)
       │                 ├─ Azure Key Vault (secrets)
       │                 ├─ Azure ML (model registry + training)
       │                 ├─ Azure Service Bus (event side-channel)
       │                 ├─ Azure Synapse Analytics (data warehouse)
       │                 └─ App Insights (telemetry)
       └─ /* → Azure Static Web Apps (React frontend)

Note: User authentication (login, JWT, MFA, RBAC) is handled by the
existing app code — NOT by Entra ID. Entra ID provides Managed Identity
so the backend container can access Key Vault, Blob, etc. without passwords.
```

### Data Flow Diagram
```
┌──────────────┐     ┌───────────────┐     ┌──────────────────┐
│  Front Door  │────▶│ Static Web    │     │ API Management   │
│  (CDN + WAF) │     │ Apps (React)  │     │ (Rate limit,     │
└──────┬───────┘     └───────────────┘     │  Auth, Logging)  │
       │                                    └────────┬─────────┘
       │  /api/*                                     │
       └────────────────────────────────────────────▶│
                                              ┌──────▼─────────┐
                                              │ Container Apps  │
                                              │ (FastAPI)       │
                                              └──┬──┬──┬──┬────┘
                    ┌─────────────────────────────┘  │  │  │
              ┌─────▼──────┐  ┌──────▼─────┐  ┌─────▼──┐  ┌──▼──────────┐
              │ PostgreSQL │  │ Blob Store │  │Key Vault│  │ Service Bus │
              │ Flexible   │  │ (Files)    │  │(Secrets)│  │ (Async)     │
              └─────┬──────┘  └────────────┘  └────────┘  └──┬──────────┘
                    │                                         │
              ┌─────▼──────────────────┐           ┌──────────▼──────────┐
              │ Azure Synapse          │           │ Azure ML            │
              │ (Analytics Warehouse)  │           │ (Model Training)    │
              └────────────────────────┘           └─────────────────────┘
```

---

## 2. Azure Services Mapping

| Local Component | Azure Service | Purpose | SKU/Tier |
|---|---|---|---|
| Vite Dev Server | **Static Web Apps** | Host React SPA | Free/Standard |
| FastAPI (Uvicorn) | **Container Apps** | Run backend in container | Consumption |
| Supabase PostgreSQL | **PostgreSQL Flexible Server** | Main relational DB | Burstable B1ms |
| `.env` file secrets | **Key Vault** | Centralized secrets | Standard |
| JWT Auth + MFA | **Entra ID** (Managed Identity only) | Service-to-service auth (container → Key Vault, Blob, etc.) | Free tier |
| Encrypted file bytes in DB | **Blob Storage** | Store large encrypted file payloads (>1MB). Small text stays in DB. | Hot tier |
| ML `.joblib` on disk | **Azure ML** | Model registry + training | Basic |
| `dataset.csv` on disk | **Azure ML** + **Blob** | Training data storage | — |
| N/A (sync only) | **Service Bus** | Event side-channel: audit replication, analytics sync, ML retrain triggers | Basic |
| Analytics SQL queries | **Azure Synapse** | Data warehouse + analytics | Serverless |
| N/A | **Front Door** | Global load balancer + CDN + WAF | Standard |
| N/A | **API Management** | API gateway, throttling, docs | Consumption |
| N/A | **Monitor + App Insights** | Logs, metrics, alerts | Pay-as-you-go |
| N/A | **Container Registry** | Store Docker images | Basic |

---

## Phase 1 — Foundation & Identity Setup

### 1.1 Resource Group & Naming Convention

All resources use naming convention: `weaver-<service>-<env>` (e.g., `weaver-db-prod`).

```bash
# Login and set subscription
az login
az account set --subscription "<YOUR_SUBSCRIPTION_ID>"

# Create resource group (Central India for low latency)
az group create --name weaver-rg --location centralindia

# Register required providers
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
```

### 1.2 Entra ID (Managed Identity — Service-to-Service Auth)

> **Important clarification**: Entra ID does **NOT** replace your app's user login.
> Your app has two separate auth systems:
>
> | Auth System | What it does | Changes needed |
> |---|---|---|
> | **App's own JWT + MFA + RBAC** | User login, access tokens, refresh tokens, TOTP, role checks | **Zero changes** — works exactly as-is |
> | **Entra ID Managed Identity** | Backend container authenticates to Azure services (Key Vault, Blob Storage, Service Bus, Azure ML) without storing passwords | **Infrastructure only** — no app code changes |
>
> Think of Managed Identity as an "Azure ID card" for your container. When the backend needs a secret from Key Vault, it presents this identity instead of a password. This is an Azure-level mechanism — your JWT login flow is completely untouched.

```bash
# Create a User-Assigned Managed Identity for the backend container
az identity create \
  --name weaver-backend-identity \
  --resource-group weaver-rg

# Save these values — they'll be used when granting access to Key Vault, Blob, etc.
IDENTITY_CLIENT_ID=$(az identity show --name weaver-backend-identity \
  --resource-group weaver-rg --query clientId -o tsv)
IDENTITY_PRINCIPAL_ID=$(az identity show --name weaver-backend-identity \
  --resource-group weaver-rg --query principalId -o tsv)
IDENTITY_RESOURCE_ID=$(az identity show --name weaver-backend-identity \
  --resource-group weaver-rg --query id -o tsv)

# Create App Registration for the Weaver API (used by APIM for API identity)
az ad app create --display-name "Weaver API" \
  --sign-in-audience AzureADMyOrg
```

**Impact on existing code**: None. Managed Identity is attached to the Container App at deployment time. The Azure SDKs (`azure-identity`) use it automatically — your auth routers, JWT handler, MFA logic, and RBAC middleware are completely untouched.

---

## Phase 2 — Data Layer

### 2.1 Azure Key Vault (Secrets)

**Completely replaces** the `.env` file (which will be deleted). All secrets (DB connection string, JWT key, encryption keys) are stored here and loaded at startup via Azure SDK. There is no `.env` fallback.

```bash
az keyvault create \
  --name weaver-kv \
  --resource-group weaver-rg \
  --location centralindia \
  --enable-rbac-authorization true

# Grant the managed identity access to read secrets
az role assignment create \
  --assignee $IDENTITY_PRINCIPAL_ID \
  --role "Key Vault Secrets User" \
  --scope $(az keyvault show --name weaver-kv --query id -o tsv)

# Store all secrets
az keyvault secret set --vault-name weaver-kv --name "DATABASE-URL" \
  --value "postgresql+asyncpg://weaver_admin:<password>@weaver-db-prod.postgres.database.azure.com:5432/weaver"
az keyvault secret set --vault-name weaver-kv --name "JWT-SECRET-KEY" \
  --value "<your-64-char-hex>"
az keyvault secret set --vault-name weaver-kv --name "MFA-ENCRYPTION-KEY" \
  --value "<fernet-key>"
az keyvault secret set --vault-name weaver-kv --name "DATA-ENCRYPTION-KEK" \
  --value "<base64-aes-key>"
az keyvault secret set --vault-name weaver-kv --name "BLOB-CONNECTION-STRING" \
  --value "<blob-conn-string>"
az keyvault secret set --vault-name weaver-kv --name "SERVICE-BUS-CONNECTION-STRING" \
  --value "<servicebus-conn-string>"
az keyvault secret set --vault-name weaver-kv --name "APPINSIGHTS-CONNECTION-STRING" \
  --value "<appinsights-conn-string>"
```

**Code change needed**: Rewrite `app/config.py` to load ALL secrets exclusively from Key Vault using `azure-identity` + `azure-keyvault-secrets`. Remove the `.env` loading mechanism entirely. Delete the `.env` file from the project.

### 2.2 Azure PostgreSQL Flexible Server

Replaces Supabase. Same PostgreSQL, now Azure-managed.

```bash
az postgres flexible-server create \
  --name weaver-db-prod \
  --resource-group weaver-rg \
  --location centralindia \
  --admin-user weaver_admin \
  --admin-password "<STRONG_PASSWORD>" \
  --sku-name Standard_B1ms \
  --tier Burstable \
  --storage-size 32 \
  --version 16 \
  --yes

# Create the application database
az postgres flexible-server db create \
  --server-name weaver-db-prod \
  --resource-group weaver-rg \
  --database-name weaver

# Allow Azure services to connect
az postgres flexible-server firewall-rule create \
  --name AllowAzureServices \
  --resource-group weaver-rg \
  --server-name weaver-db-prod \
  --start-ip-address 0.0.0.0 \
  --end-ip-address 0.0.0.0

# Enable SSL enforcement
az postgres flexible-server update \
  --name weaver-db-prod \
  --resource-group weaver-rg \
  --ssl-enforcement Enabled
```

**Code change needed**: Modify `app/database.py` to remove Supabase-specific pooler logic; Azure PostgreSQL uses standard connections with SSL.

### 2.3 Azure Blob Storage

Stores encrypted file payloads instead of storing raw bytes in PostgreSQL `BYTEA` columns.

```bash
az storage account create \
  --name weaverstorageprod \
  --resource-group weaver-rg \
  --location centralindia \
  --sku Standard_LRS \
  --kind StorageV2 \
  --min-tls-version TLS1_2 \
  --allow-blob-public-access false

# Create containers
az storage container create --name encrypted-payloads \
  --account-name weaverstorageprod --auth-mode login
az storage container create --name ml-models \
  --account-name weaverstorageprod --auth-mode login
az storage container create --name ml-datasets \
  --account-name weaverstorageprod --auth-mode login

# Grant managed identity blob access
az role assignment create \
  --assignee $IDENTITY_PRINCIPAL_ID \
  --role "Storage Blob Data Contributor" \
  --scope $(az storage account show --name weaverstorageprod --query id -o tsv)
```

**Code change needed**: New service `app/services/blob_service.py` for upload/download. Modify `encrypt.py` router to store ciphertext in Blob and save blob URL in DB instead of raw bytes.

---

## Phase 3 — Backend Containerization

### 3.1 Container Registry

```bash
az acr create \
  --name weaveracr \
  --resource-group weaver-rg \
  --sku Basic \
  --admin-enabled true
```

### 3.2 Dockerfile (New File)

Create `backend/Dockerfile`:
```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system deps for cryptography, ML libraries
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
```

### 3.3 Build & Push

```bash
az acr build --registry weaveracr \
  --image weaver-backend:v1.0 \
  --file backend/Dockerfile \
  backend/
```

### 3.4 Container Apps Environment

```bash
# Create Container Apps environment
az containerapp env create \
  --name weaver-env \
  --resource-group weaver-rg \
  --location centralindia

# Deploy the backend container
az containerapp create \
  --name weaver-backend \
  --resource-group weaver-rg \
  --environment weaver-env \
  --image weaveracr.azurecr.io/weaver-backend:v1.0 \
  --registry-server weaveracr.azurecr.io \
  --registry-username weaveracr \
  --registry-password "$(az acr credential show --name weaveracr --query 'passwords[0].value' -o tsv)" \
  --target-port 8000 \
  --ingress external \
  --min-replicas 1 \
  --max-replicas 5 \
  --cpu 1.0 \
  --memory 2.0Gi \
  --user-assigned $IDENTITY_RESOURCE_ID \
  --env-vars \
    "AZURE_CLIENT_ID=$IDENTITY_CLIENT_ID" \
    "KEY_VAULT_URL=https://weaver-kv.vault.azure.net/" \
    "CORS_ORIGINS=https://weaver-frontend.azurestaticapps.net"

# Set up auto-scaling based on HTTP requests
az containerapp update \
  --name weaver-backend \
  --resource-group weaver-rg \
  --scale-rule-name http-rule \
  --scale-rule-type http \
  --scale-rule-http-concurrency 50
```

---

## Phase 4 — Frontend Deployment

### 4.1 Azure Static Web Apps

```bash
# Build React for production
cd frontend
npm run build   # Output: dist/

# Create Static Web App
az staticwebapp create \
  --name weaver-frontend \
  --resource-group weaver-rg \
  --location centralindia \
  --sku Standard

# Deploy using CLI
az staticwebapp deploy \
  --name weaver-frontend \
  --resource-group weaver-rg \
  --app-location "./frontend" \
  --output-location "dist" \
  --env production
```

### 4.2 Frontend Config Changes

Create `frontend/staticwebapp.config.json` (new file):
```json
{
  "navigationFallback": {
    "rewrite": "/index.html",
    "exclude": ["/assets/*", "/api/*"]
  },
  "routes": [
    {
      "route": "/api/*",
      "allowedRoles": ["anonymous"],
      "rewrite": "https://weaver-apim.azure-api.net/api/*"
    }
  ],
  "globalHeaders": {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains"
  }
}
```

**Code change needed**: Update `vite.config.ts` to add production base URL. Set `VITE_API_URL` env variable for API Management endpoint.

---

## Phase 5 — API Management & Front Door

### 5.1 API Management

```bash
az apim create \
  --name weaver-apim \
  --resource-group weaver-rg \
  --publisher-name "Weaver" \
  --publisher-email "admin@weaver.local" \
  --sku-name Consumption \
  --location centralindia

# Import the OpenAPI spec from FastAPI
BACKEND_URL=$(az containerapp show --name weaver-backend \
  --resource-group weaver-rg --query 'properties.configuration.ingress.fqdn' -o tsv)

az apim api import \
  --resource-group weaver-rg \
  --service-name weaver-apim \
  --api-id weaver-api \
  --path "api" \
  --specification-format OpenApiJson \
  --specification-url "https://$BACKEND_URL/api/openapi.json" \
  --service-url "https://$BACKEND_URL"

# Add rate limiting policy
az apim api policy set \
  --resource-group weaver-rg \
  --service-name weaver-apim \
  --api-id weaver-api \
  --xml-policy '<policies><inbound><rate-limit calls="100" renewal-period="60"/><cors allow-credentials="true"><allowed-origins><origin>https://weaver-frontend.azurestaticapps.net</origin></allowed-origins><allowed-methods><method>*</method></allowed-methods><allowed-headers><header>*</header></allowed-headers></cors></inbound></policies>'
```

### 5.2 Azure Front Door

```bash
az afd profile create \
  --profile-name weaver-cdn \
  --resource-group weaver-rg \
  --sku Standard_AzureFrontDoor

az afd endpoint create \
  --endpoint-name weaver-app \
  --profile-name weaver-cdn \
  --resource-group weaver-rg

# Origin group for frontend (Static Web Apps)
az afd origin-group create \
  --origin-group-name frontend-group \
  --profile-name weaver-cdn \
  --resource-group weaver-rg \
  --probe-request-type GET \
  --probe-protocol Https \
  --probe-path "/" \
  --probe-interval-in-seconds 30

az afd origin create \
  --origin-name frontend-origin \
  --origin-group-name frontend-group \
  --profile-name weaver-cdn \
  --resource-group weaver-rg \
  --host-name "weaver-frontend.azurestaticapps.net" \
  --origin-host-header "weaver-frontend.azurestaticapps.net" \
  --http-port 80 --https-port 443 \
  --priority 1 --weight 1000

# Origin group for API (APIM)
az afd origin-group create \
  --origin-group-name api-group \
  --profile-name weaver-cdn \
  --resource-group weaver-rg \
  --probe-request-type GET \
  --probe-protocol Https \
  --probe-path "/health" \
  --probe-interval-in-seconds 30

az afd origin create \
  --origin-name api-origin \
  --origin-group-name api-group \
  --profile-name weaver-cdn \
  --resource-group weaver-rg \
  --host-name "weaver-apim.azure-api.net" \
  --origin-host-header "weaver-apim.azure-api.net" \
  --http-port 80 --https-port 443 \
  --priority 1 --weight 1000

# Routing rules
az afd route create \
  --route-name api-route \
  --endpoint-name weaver-app \
  --profile-name weaver-cdn \
  --resource-group weaver-rg \
  --origin-group api-group \
  --patterns-to-match "/api/*" \
  --supported-protocols Https \
  --forwarding-protocol HttpsOnly

az afd route create \
  --route-name frontend-route \
  --endpoint-name weaver-app \
  --profile-name weaver-cdn \
  --resource-group weaver-rg \
  --origin-group frontend-group \
  --patterns-to-match "/*" \
  --supported-protocols Https \
  --forwarding-protocol HttpsOnly

# Enable WAF
az afd security-policy create \
  --profile-name weaver-cdn \
  --resource-group weaver-rg \
  --security-policy-name weaver-waf \
  --domains "weaver-app-<hash>.azurefd.net" \
  --waf-policy weaver-waf-policy
```

---

## Phase 6 — Event-Driven Side-Channel (Service Bus)

### 6.1 Service Bus Setup

> **Design decision**: Service Bus is used as an **event side-channel**, NOT to replace synchronous operations.
> Classification and encryption remain **synchronous** (user gets immediate results, just like locally).
> After each operation completes, an event message is published to Service Bus for:
> - **Audit trail replication** — async copy of events to Synapse
> - **Analytics aggregation** — background processing of usage stats
> - **Notification dispatch** — async email/webhook notifications
> - **ML retraining triggers** — queue training jobs when enough new data accumulates
>
> This preserves the existing user experience while demonstrating the cloud async messaging pattern.

```bash
az servicebus namespace create \
  --name weaver-sb \
  --resource-group weaver-rg \
  --location centralindia \
  --sku Basic

# Create queues for event-driven side-channel
az servicebus queue create --namespace-name weaver-sb \
  --resource-group weaver-rg --name audit-events \
  --max-size 1024 --default-message-time-to-live P1D

az servicebus queue create --namespace-name weaver-sb \
  --resource-group weaver-rg --name analytics-sync \
  --max-size 1024 --default-message-time-to-live P1D

az servicebus queue create --namespace-name weaver-sb \
  --resource-group weaver-rg --name ml-retrain-triggers \
  --max-size 1024 --default-message-time-to-live P7D

# Get connection string
az servicebus namespace authorization-rule keys list \
  --namespace-name weaver-sb \
  --resource-group weaver-rg \
  --name RootManageSharedAccessKey \
  --query primaryConnectionString -o tsv
```

**New files needed**:
- `app/services/servicebus_service.py` — publish event messages after classify/encrypt/decrypt operations
- `app/workers/analytics_worker.py` — consume events and push aggregated data to Synapse
- `app/workers/audit_worker.py` — consume events and replicate audit trail to long-term storage

---

## Phase 7 — ML Pipeline (Azure ML)

### 7.1 Azure ML Workspace

```bash
az ml workspace create \
  --name weaver-ml \
  --resource-group weaver-rg \
  --location centralindia

# Upload training dataset to ML workspace
az ml data create \
  --name sensitivity-dataset \
  --path backend/app/ml/models/dataset.csv \
  --type uri_file \
  --workspace-name weaver-ml \
  --resource-group weaver-rg

# Register the pre-trained model
az ml model create \
  --name sensitivity-classifier \
  --path backend/app/ml/models/sensitivity_classifier.joblib \
  --type custom_model \
  --workspace-name weaver-ml \
  --resource-group weaver-rg
```

### 7.2 Training Pipeline

Create an Azure ML training job YAML `infra/ml/train-job.yml`:
```yaml
$schema: https://azuremlschemas.azureedge.net/latest/commandJob.schema.json
command: python -m app.ml.train
environment:
  image: python:3.11-slim
  conda_file: environment.yml
code: ../../backend
inputs:
  dataset:
    type: uri_file
    path: azureml:sensitivity-dataset@latest
compute: azureml:cpu-cluster
experiment_name: sensitivity-training
```

**Code change needed**: Rewrite `app/ml/model.py` to load model exclusively from Azure ML model registry. Remove all local file loading. Add `app/services/ml_service.py` for Azure ML integration. The local `.joblib` file and `dataset.csv` are uploaded to Azure and then deleted from the repo.

---

## Phase 8 — Analytics (Azure Synapse)

### 8.1 Synapse Workspace

```bash
# Create ADLS Gen2 storage for Synapse
az storage account create \
  --name weaversynapsestorage \
  --resource-group weaver-rg \
  --location centralindia \
  --sku Standard_LRS \
  --kind StorageV2 \
  --hns true

az synapse workspace create \
  --name weaver-synapse \
  --resource-group weaver-rg \
  --location centralindia \
  --storage-account weaversynapsestorage \
  --file-system weaver-synapse-fs \
  --sql-admin-login-user synapse_admin \
  --sql-admin-login-password "<STRONG_PASSWORD>"

# Create a serverless SQL pool (built-in)
# Synapse serverless is available by default

# Create Spark pool for ML analytics
az synapse spark pool create \
  --name weaverspark \
  --workspace-name weaver-synapse \
  --resource-group weaver-rg \
  --spark-version 3.4 \
  --node-count 3 \
  --node-size Small \
  --enable-auto-pause true \
  --delay 15
```

### 8.2 Data Pipeline

Set up a Synapse pipeline to periodically sync analytics data from PostgreSQL:
- Classification trends, encryption statistics, audit logs → Synapse tables
- Spark notebooks for advanced analytics (encryption algorithm effectiveness, sensitivity distribution trends)
- Power BI integration for dashboards

**Code change needed**: New `app/services/synapse_service.py` to push aggregated analytics data. Modify `analytics.py` router to query from Synapse for heavy analytical reports (trend analysis, cross-user aggregations). Standard real-time queries (dashboard counts) stay on PostgreSQL.

---

## Phase 9 — Monitoring & Observability

### 9.1 Application Insights + Log Analytics

```bash
# Create Log Analytics workspace
az monitor log-analytics workspace create \
  --workspace-name weaver-logs \
  --resource-group weaver-rg \
  --location centralindia

# Create Application Insights
az monitor app-insights component create \
  --app weaver-insights \
  --resource-group weaver-rg \
  --location centralindia \
  --workspace weaver-logs \
  --application-type web

# Get instrumentation key
APPINSIGHTS_KEY=$(az monitor app-insights component show \
  --app weaver-insights --resource-group weaver-rg \
  --query instrumentationKey -o tsv)
APPINSIGHTS_CONN=$(az monitor app-insights component show \
  --app weaver-insights --resource-group weaver-rg \
  --query connectionString -o tsv)

# Enable diagnostics on Container Apps
az containerapp env update \
  --name weaver-env \
  --resource-group weaver-rg \
  --logs-workspace-id $(az monitor log-analytics workspace show \
    --workspace-name weaver-logs --resource-group weaver-rg \
    --query customerId -o tsv) \
  --logs-workspace-key $(az monitor log-analytics workspace get-shared-keys \
    --workspace-name weaver-logs --resource-group weaver-rg \
    --query primarySharedKey -o tsv)
```

### 9.2 Alerts

```bash
# Alert: High error rate (>5% of requests return 5xx)
az monitor metrics alert create \
  --name "high-error-rate" \
  --resource-group weaver-rg \
  --scopes "/subscriptions/<sub>/resourceGroups/weaver-rg/..." \
  --condition "count requests/failed > 50" \
  --window-size 5m \
  --evaluation-frequency 1m

# Alert: Database CPU > 80%
az monitor metrics alert create \
  --name "db-high-cpu" \
  --resource-group weaver-rg \
  --scopes $(az postgres flexible-server show --name weaver-db-prod \
    --resource-group weaver-rg --query id -o tsv) \
  --condition "avg cpu_percent > 80" \
  --window-size 5m
```

**Code change needed**: Add `opencensus-ext-azure` and `azure-monitor-opentelemetry` to `requirements.txt`. Add telemetry middleware in `main.py`.

---

## Phase 10 — Security Hardening

### 10.1 Network Security

```bash
# Create VNet for private connectivity
az network vnet create \
  --name weaver-vnet \
  --resource-group weaver-rg \
  --location centralindia \
  --address-prefix 10.0.0.0/16

az network vnet subnet create \
  --name container-apps-subnet \
  --vnet-name weaver-vnet \
  --resource-group weaver-rg \
  --address-prefix 10.0.1.0/24

az network vnet subnet create \
  --name db-subnet \
  --vnet-name weaver-vnet \
  --resource-group weaver-rg \
  --address-prefix 10.0.2.0/24 \
  --delegations Microsoft.DBforPostgreSQL/flexibleServers

# Enable private endpoint for PostgreSQL
az postgres flexible-server update \
  --name weaver-db-prod \
  --resource-group weaver-rg \
  --public-access Disabled

# Enable private endpoint for Key Vault
az keyvault update --name weaver-kv \
  --resource-group weaver-rg \
  --public-network-access Disabled
```

### 10.2 Key Rotation Policy

```bash
az keyvault key set-attributes \
  --vault-name weaver-kv \
  --name jwt-signing-key \
  --policy '{"lifetimeActions":[{"trigger":{"timeAfterCreate":"P90D"},"action":{"type":"Rotate"}}]}'
```

---

## File-by-File Change List

### Files to MODIFY

| # | File | Change Description |
|---|---|---|
| 1 | `backend/app/config.py` | **Rewrite entirely**: Load ALL secrets from Azure Key Vault using `azure-identity` + `azure-keyvault-secrets`. Bootstrap config (`KEY_VAULT_URL`, `AZURE_CLIENT_ID`) comes from Container Apps env vars. All other secrets (`DATABASE_URL`, `JWT_SECRET_KEY`, encryption keys, etc.) loaded from Key Vault. |
| 2 | `backend/app/database.py` | Remove Supabase pooler workarounds. Use standard asyncpg SSL connection for Azure PostgreSQL. Simplify engine creation. |
| 3 | `backend/app/main.py` | Add Azure App Insights telemetry middleware (`opencensus`). Add health check endpoint for Azure Front Door probes. Add startup event to initialize Azure services. Add Service Bus event publishing after key operations. |
| 4 | `backend/app/routers/encrypt.py` | **Hybrid storage**: Text payloads (<1MB) stay as `BYTEA` in PostgreSQL (current behavior). File payloads (>1MB) go to Blob Storage with `blob_url` reference in DB. After encrypt completes, publish event to Service Bus. |
| 5 | `backend/app/routers/decrypt.py` | Check if payload has `blob_url` → fetch from Blob Storage. Otherwise read `ciphertext` from DB as before. |
| 6 | `backend/app/routers/classify.py` | Classification stays **synchronous** (user gets immediate result). After classification completes, publish event to Service Bus for audit/analytics. Load ML model from Azure ML registry. |
| 7 | `backend/app/models/encryption.py` | Add `blob_url` column (String, nullable). Keep `ciphertext` BYTEA column (nullable) for small text payloads. One of `ciphertext` or `blob_url` is always set. |
| 8 | `backend/app/ml/model.py` | Load model from Azure ML model registry. Download `.joblib` to container's temp storage at startup for fast inference. |
| 9 | `backend/app/ml/train.py` | Upload trained model to Azure ML after training. Read dataset from Azure ML data asset. |
| 10 | `backend/app/routers/analytics.py` | Route heavy analytical queries (trends, cross-user aggregations) to Synapse. Real-time dashboard counts stay on PostgreSQL. |
| 11 | `backend/requirements.txt` | Add: `azure-identity`, `azure-keyvault-secrets`, `azure-storage-blob`, `azure-servicebus`, `azure-ai-ml`, `opencensus-ext-azure`, `azure-monitor-opentelemetry`. |
| 12 | `backend/.env` and `backend/.env.example` | **DELETE both files**. Bootstrap config (`KEY_VAULT_URL`, `AZURE_CLIENT_ID`) comes from Container Apps env vars. All secrets come from Key Vault. |
| 13 | `frontend/vite.config.ts` | Keep proxy config for structure. Set `VITE_API_URL` via environment at build time for cloud builds (points to Front Door URL). |
| 14 | `frontend/src/api/client.ts` | Ensure `VITE_API_URL` is used as base URL (already done — just needs env var set at build). |
| 15 | `backend/scripts/seed_db.py` | Remove Supabase-specific SSL args. Use standard Azure PostgreSQL connection. |

### Files to CREATE (New)

| # | File | Purpose |
|---|---|---|
| 1 | `backend/Dockerfile` | Container image for FastAPI backend |
| 2 | `backend/.dockerignore` | Exclude venv, tests, .env from image |
| 3 | `backend/app/services/blob_service.py` | Azure Blob Storage upload/download/delete |
| 4 | `backend/app/services/servicebus_service.py` | Azure Service Bus send/receive message helpers |
| 5 | `backend/app/services/keyvault_service.py` | Azure Key Vault secret loading |
| 6 | `backend/app/services/ml_service.py` | Azure ML model download + registration |
| 7 | `backend/app/services/synapse_service.py` | Azure Synapse data push for analytics |
| 8 | `backend/app/services/telemetry_service.py` | App Insights integration + custom metrics |
| 9 | `backend/app/workers/classification_worker.py` | Service Bus consumer for async classification |
| 10 | `backend/app/workers/encryption_worker.py` | Service Bus consumer for async encryption |
| 11 | `frontend/staticwebapp.config.json` | Azure Static Web Apps routing config |
| 12 | `infra/deploy.sh` | Master deployment script (all Azure CLI commands) |
| 13 | `infra/ml/train-job.yml` | Azure ML training job definition |
| 14 | `infra/ml/environment.yml` | Conda environment for ML training |
| 15 | `.github/workflows/deploy-backend.yml` | CI/CD for backend (build + push + deploy) |
| 16 | `.github/workflows/deploy-frontend.yml` | CI/CD for frontend (build + deploy to SWA) |

---

## Cost Estimation (Monthly — Student/Dev Tier)

| Service | SKU | Estimated Cost |
|---|---|---|
| PostgreSQL Flexible Server | Burstable B1ms | ~$13/mo |
| Container Apps | Consumption (1 vCPU, 2GB) | ~$0–5/mo |
| Static Web Apps | Standard | Free–$9/mo |
| Blob Storage | Hot, <1GB | ~$0.02/mo |
| Key Vault | Standard, <10k ops | ~$0.03/mo |
| Service Bus | Basic | ~$0.05/mo |
| API Management | Consumption | ~$3.50/1M calls |
| Front Door | Standard | ~$35/mo |
| App Insights | <5GB/mo | Free |
| Azure ML | Basic (No compute) | Free |
| Synapse | Serverless SQL | ~$5/TB processed |
| Container Registry | Basic | ~$5/mo |
| **Estimated Total** | | **~$60–75/mo** |

> **Tip**: Use Azure for Students ($100 free credit) or Azure Free Tier to minimize costs.

---

## Deployment Order (Step-by-Step)

```
── MILESTONE 1: Core App Running in Cloud ──────────────────────────
Step 1:  az login → Resource Group → Managed Identity (Entra ID)
Step 2:  Key Vault → Store all secrets
Step 3:  PostgreSQL → Create DB → Run seed_db.py
Step 4:  Blob Storage → Create containers
Step 5:  Modify backend code (config, database, services)
Step 6:  Container Registry → Build Docker image → Push
Step 7:  Container Apps → Deploy backend → Test /health
Step 8:  Static Web Apps → Build React → Deploy frontend
  ✅ APP IS FUNCTIONAL — login, classify, encrypt, decrypt all work

── MILESTONE 2: Production Architecture ────────────────────────────
Step 9:  API Management → Import OpenAPI → Set policies
Step 10: Front Door → Configure origins & routes → Update CORS
  ✅ PRODUCTION READY — CDN, WAF, rate limiting, single entry point

── MILESTONE 3: Cloud-Native Enhancements ──────────────────────────
Step 11: Service Bus → Create queues → Publish events from routers
Step 12: Azure ML → Upload model & dataset → Test registry loading
Step 13: Synapse → Create workspace → Set up analytics pipeline
Step 14: App Insights → Enable monitoring → Create alerts
Step 15: Security → VNet → Private endpoints → WAF
Step 16: End-to-end testing → Full verification → Go live
  ✅ FULLY CLOUD-NATIVE — all 12+ Azure services integrated
```

---

## Verification Checklist

- [ ] Frontend loads at `https://<front-door-domain>/`
- [ ] Login with `admin@weaver.local` / `Admin@1234` works
- [ ] Text classification returns sensitivity level + LIME explanation
- [ ] File upload + classification works
- [ ] Encryption (all 4 levels: Public, Internal, Confidential, Highly Sensitive) works
- [ ] MFA setup and enforcement for Highly Sensitive works
- [ ] Sharing encrypted payloads with link works
- [ ] Guest decryption via share link works
- [ ] Admin dashboard shows all analytics
- [ ] Audit logs capture all actions
- [ ] Re-encryption (upgrade/downgrade) works
- [ ] App Insights shows request telemetry
- [ ] Alerts fire on simulated error spike
- [ ] All existing `pytest` tests pass against Azure DB
- [ ] Service Bus processes async jobs
- [ ] ML model loads from Azure ML registry
- [ ] Synapse analytics queries return data

---

## Step-by-Step Setup Guide — How to Run the Project

This section is your **complete guide** to setting up and running the Weaver cloud project from scratch after all code changes are implemented. Follow every step in order.

### Prerequisites

Before you begin, ensure you have:

| Requirement | How to Get It |
|---|---|
| Azure account with active subscription | [Azure for Students](https://azure.microsoft.com/free/students/) (free $100 credit) or [Free Account](https://azure.microsoft.com/free/) |
| Azure CLI installed (v2.50+) | `winget install -e --id Microsoft.AzureCLI` |
| Docker Desktop (for local image build only) | [docker.com/products/docker-desktop](https://docker.com/products/docker-desktop) — optional, ACR can build remotely |
| Node.js 20+ | `winget install -e --id OpenJS.NodeJS.LTS` |
| Python 3.11+ | Already installed |
| Git | Already installed |

### Step 0 — Authenticate & Set Subscription

```powershell
# Login to Azure (opens browser)
az login

# List subscriptions and pick yours
az account list --output table

# Set your subscription
az account set --subscription "<YOUR_SUBSCRIPTION_ID>"

# Verify
az account show --output table
```

**Expected output**: Your subscription name and ID displayed.

### Step 1 — Create Resource Group & Register Providers

```powershell
# Create the resource group (all resources go here)
az group create --name weaver-rg --location centralindia

# Register all required Azure providers (run once, takes ~1-2 min each)
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

# Check registration status (wait until all show 'Registered')
az provider show --namespace Microsoft.App --query registrationState -o tsv
```

**Expected output**: `Registered` for each provider. If `Registering`, wait a minute and check again.

### Step 2 — Create Managed Identity

```powershell
az identity create --name weaver-backend-identity --resource-group weaver-rg

# Save these values — you'll need them for every step below
$IDENTITY_CLIENT_ID = az identity show --name weaver-backend-identity --resource-group weaver-rg --query clientId -o tsv
$IDENTITY_PRINCIPAL_ID = az identity show --name weaver-backend-identity --resource-group weaver-rg --query principalId -o tsv
$IDENTITY_RESOURCE_ID = az identity show --name weaver-backend-identity --resource-group weaver-rg --query id -o tsv

# Verify
Write-Host "Client ID: $IDENTITY_CLIENT_ID"
Write-Host "Principal ID: $IDENTITY_PRINCIPAL_ID"
```

**Expected output**: Two UUIDs printed.

### Step 3 — Create Key Vault & Store Secrets

```powershell
# Create Key Vault
az keyvault create --name weaver-kv --resource-group weaver-rg --location centralindia --enable-rbac-authorization true

# Grant managed identity permission to read secrets
$KV_ID = az keyvault show --name weaver-kv --query id -o tsv
az role assignment create --assignee $IDENTITY_PRINCIPAL_ID --role "Key Vault Secrets User" --scope $KV_ID

# Also grant YOUR user account permission to SET secrets
$MY_OBJECT_ID = az ad signed-in-user show --query id -o tsv
az role assignment create --assignee $MY_OBJECT_ID --role "Key Vault Secrets Officer" --scope $KV_ID

# Generate secret values
python -c "import secrets; print(secrets.token_hex(32))"          # → Use as JWT_SECRET_KEY
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"  # → Use as MFA_ENCRYPTION_KEY
python -c "import os,base64; print(base64.b64encode(os.urandom(32)).decode())"            # → Use as DATA_ENCRYPTION_KEK

# Store all secrets (replace <values> with generated ones)
az keyvault secret set --vault-name weaver-kv --name "JWT-SECRET-KEY" --value "<generated-hex>"
az keyvault secret set --vault-name weaver-kv --name "MFA-ENCRYPTION-KEY" --value "<generated-fernet-key>"
az keyvault secret set --vault-name weaver-kv --name "DATA-ENCRYPTION-KEK" --value "<generated-base64-key>"
```

**Expected output**: Each `az keyvault secret set` returns JSON with `"id"` containing the secret URL.

### Step 4 — Create PostgreSQL Database

```powershell
# Create the server (takes ~3-5 minutes)
az postgres flexible-server create `
  --name weaver-db-prod `
  --resource-group weaver-rg `
  --location centralindia `
  --admin-user weaver_admin `
  --admin-password "<CHOOSE_A_STRONG_PASSWORD>" `
  --sku-name Standard_B1ms `
  --tier Burstable `
  --storage-size 32 `
  --version 16 `
  --yes

# Create the database
az postgres flexible-server db create --server-name weaver-db-prod --resource-group weaver-rg --database-name weaver

# Allow Azure services to connect
az postgres flexible-server firewall-rule create --name AllowAzureServices --resource-group weaver-rg --server-name weaver-db-prod --start-ip-address 0.0.0.0 --end-ip-address 0.0.0.0

# Store the DB connection string in Key Vault
az keyvault secret set --vault-name weaver-kv --name "DATABASE-URL" `
  --value "postgresql+asyncpg://weaver_admin:<YOUR_PASSWORD>@weaver-db-prod.postgres.database.azure.com:5432/weaver"

# Verify connection (from your machine — add your IP to firewall first)
az postgres flexible-server firewall-rule create --name AllowMyIP --resource-group weaver-rg --server-name weaver-db-prod --start-ip-address <YOUR_PUBLIC_IP> --end-ip-address <YOUR_PUBLIC_IP>
```

**Expected output**: Server and database created. Firewall rules added.

### Step 5 — Create Blob Storage

```powershell
az storage account create --name weaverstorageprod --resource-group weaver-rg --location centralindia --sku Standard_LRS --kind StorageV2 --min-tls-version TLS1_2 --allow-blob-public-access false

# Create containers
az storage container create --name encrypted-payloads --account-name weaverstorageprod --auth-mode login
az storage container create --name ml-models --account-name weaverstorageprod --auth-mode login
az storage container create --name ml-datasets --account-name weaverstorageprod --auth-mode login

# Grant managed identity blob access
$STORAGE_ID = az storage account show --name weaverstorageprod --query id -o tsv
az role assignment create --assignee $IDENTITY_PRINCIPAL_ID --role "Storage Blob Data Contributor" --scope $STORAGE_ID

# Store connection string in Key Vault
$BLOB_CONN = az storage account show-connection-string --name weaverstorageprod --resource-group weaver-rg --query connectionString -o tsv
az keyvault secret set --vault-name weaver-kv --name "BLOB-CONNECTION-STRING" --value $BLOB_CONN
```

**Expected output**: Storage account + 3 containers created.

### Step 6 — Run Database Seed Script

Before containerizing, run the seed script to create tables and default data:

```powershell
# From your local machine (temporarily — the DB firewall allows your IP from Step 4)
cd "E:\MTech\MTech Sem2\Cloud\Project\Weaver\backend"

# Set the DATABASE_URL temporarily for seeding
$env:DATABASE_URL = "postgresql+asyncpg://weaver_admin:<PASSWORD>@weaver-db-prod.postgres.database.azure.com:5432/weaver"
$env:KEY_VAULT_URL = "https://weaver-kv.vault.azure.net/"

# Activate venv and run seed
venv\Scripts\activate
python scripts/seed_db.py
```

**Expected output**:
```
  [+] Policy: public
  [+] Policy: internal
  [+] Policy: confidential
  [+] Policy: highly_sensitive
  [+] Admin user: admin@weaver.local / Admin@1234

Seed complete!
```

### Step 7 — Build & Push Backend Docker Image

```powershell
# Create Container Registry
az acr create --name weaveracr --resource-group weaver-rg --sku Basic --admin-enabled true

# Build image remotely using ACR (no local Docker needed!)
az acr build --registry weaveracr --image weaver-backend:v1.0 --file backend/Dockerfile backend/
```

**Expected output**: `Run ID: xxx was successful after xxs`. Image is now in `weaveracr.azurecr.io/weaver-backend:v1.0`.

### Step 8 — Deploy Backend to Container Apps

```powershell
# Create environment
az containerapp env create --name weaver-env --resource-group weaver-rg --location centralindia

# Get ACR password
$ACR_PASSWORD = az acr credential show --name weaveracr --query 'passwords[0].value' -o tsv

# Deploy
az containerapp create `
  --name weaver-backend `
  --resource-group weaver-rg `
  --environment weaver-env `
  --image weaveracr.azurecr.io/weaver-backend:v1.0 `
  --registry-server weaveracr.azurecr.io `
  --registry-username weaveracr `
  --registry-password $ACR_PASSWORD `
  --target-port 8000 `
  --ingress external `
  --min-replicas 1 --max-replicas 5 `
  --cpu 1.0 --memory 2.0Gi `
  --user-assigned $IDENTITY_RESOURCE_ID `
  --env-vars "AZURE_CLIENT_ID=$IDENTITY_CLIENT_ID" "KEY_VAULT_URL=https://weaver-kv.vault.azure.net/" "CORS_ORIGINS=https://weaver-frontend.azurestaticapps.net"

# Get the backend URL
$BACKEND_URL = az containerapp show --name weaver-backend --resource-group weaver-rg --query 'properties.configuration.ingress.fqdn' -o tsv
Write-Host "Backend URL: https://$BACKEND_URL"
```

**Verify**: Open `https://<BACKEND_URL>/health` in your browser. You should see:
```json
{"status": "ok", "version": "1.0.0"}
```

Also check: `https://<BACKEND_URL>/api/docs` — FastAPI Swagger UI should load.

### Step 9 — Build & Deploy Frontend

```powershell
cd "E:\MTech\MTech Sem2\Cloud\Project\Weaver\frontend"

# Set the API URL to the backend (or Front Door URL later)
$env:VITE_API_URL = "https://$BACKEND_URL"

# Build
npm install
npm run build

# Create Static Web App
az staticwebapp create --name weaver-frontend --resource-group weaver-rg --location centralindia --sku Standard

# Deploy the built dist/ folder
$SWA_TOKEN = az staticwebapp secrets list --name weaver-frontend --resource-group weaver-rg --query 'properties.apiKey' -o tsv
npx @azure/static-web-apps-cli deploy ./dist --deployment-token $SWA_TOKEN --env production

# Get the frontend URL
$FRONTEND_URL = az staticwebapp show --name weaver-frontend --resource-group weaver-rg --query 'defaultHostname' -o tsv
Write-Host "Frontend URL: https://$FRONTEND_URL"
```

**Verify**: Open `https://<FRONTEND_URL>` — the Weaver landing page should load.

### Step 10 — Set Up API Management

```powershell
# Create APIM (Consumption tier — takes ~1-2 minutes)
az apim create --name weaver-apim --resource-group weaver-rg --publisher-name "Weaver" --publisher-email "admin@weaver.local" --sku-name Consumption --location centralindia

# Import OpenAPI spec from FastAPI
az apim api import --resource-group weaver-rg --service-name weaver-apim --api-id weaver-api --path "api" --specification-format OpenApiJson --specification-url "https://$BACKEND_URL/api/openapi.json" --service-url "https://$BACKEND_URL"
```

**Verify**: Go to Azure Portal → API Management → weaver-apim → APIs → weaver-api. You should see all your endpoints listed.

### Step 11 — Set Up Front Door

```powershell
# Create Front Door profile
az afd profile create --profile-name weaver-cdn --resource-group weaver-rg --sku Standard_AzureFrontDoor
az afd endpoint create --endpoint-name weaver-app --profile-name weaver-cdn --resource-group weaver-rg

# Frontend origin
az afd origin-group create --origin-group-name frontend-group --profile-name weaver-cdn --resource-group weaver-rg --probe-request-type GET --probe-protocol Https --probe-path "/" --probe-interval-in-seconds 30
az afd origin create --origin-name frontend-origin --origin-group-name frontend-group --profile-name weaver-cdn --resource-group weaver-rg --host-name $FRONTEND_URL --origin-host-header $FRONTEND_URL --http-port 80 --https-port 443 --priority 1 --weight 1000

# API origin
az afd origin-group create --origin-group-name api-group --profile-name weaver-cdn --resource-group weaver-rg --probe-request-type GET --probe-protocol Https --probe-path "/health" --probe-interval-in-seconds 30
az afd origin create --origin-name api-origin --origin-group-name api-group --profile-name weaver-cdn --resource-group weaver-rg --host-name "weaver-apim.azure-api.net" --origin-host-header "weaver-apim.azure-api.net" --http-port 80 --https-port 443 --priority 1 --weight 1000

# Routes
az afd route create --route-name api-route --endpoint-name weaver-app --profile-name weaver-cdn --resource-group weaver-rg --origin-group api-group --patterns-to-match "/api/*" --supported-protocols Https --forwarding-protocol HttpsOnly
az afd route create --route-name frontend-route --endpoint-name weaver-app --profile-name weaver-cdn --resource-group weaver-rg --origin-group frontend-group --patterns-to-match "/*" --supported-protocols Https --forwarding-protocol HttpsOnly

# Get the Front Door URL
$FD_HOSTNAME = az afd endpoint show --endpoint-name weaver-app --profile-name weaver-cdn --resource-group weaver-rg --query hostName -o tsv
Write-Host "Front Door URL: https://$FD_HOSTNAME"
```

**Verify**: Open `https://<FD_HOSTNAME>/` — should show the Weaver frontend. Open `https://<FD_HOSTNAME>/api/docs` — should show Swagger docs.

### Step 12 — Set Up Service Bus

```powershell
az servicebus namespace create --name weaver-sb --resource-group weaver-rg --location centralindia --sku Basic
az servicebus queue create --namespace-name weaver-sb --resource-group weaver-rg --name classification-jobs --max-size 1024 --default-message-time-to-live P1D
az servicebus queue create --namespace-name weaver-sb --resource-group weaver-rg --name encryption-jobs --max-size 1024 --default-message-time-to-live P1D
az servicebus queue create --namespace-name weaver-sb --resource-group weaver-rg --name analytics-sync-jobs --max-size 1024 --default-message-time-to-live P1D

# Store connection string in Key Vault
$SB_CONN = az servicebus namespace authorization-rule keys list --namespace-name weaver-sb --resource-group weaver-rg --name RootManageSharedAccessKey --query primaryConnectionString -o tsv
az keyvault secret set --vault-name weaver-kv --name "SERVICE-BUS-CONNECTION-STRING" --value $SB_CONN
```

### Step 13 — Set Up Azure ML

```powershell
# Create ML workspace
az ml workspace create --name weaver-ml --resource-group weaver-rg --location centralindia

# Upload dataset
az ml data create --name sensitivity-dataset --path backend/app/ml/models/dataset.csv --type uri_file --workspace-name weaver-ml --resource-group weaver-rg

# Register pre-trained model
az ml model create --name sensitivity-classifier --path backend/app/ml/models/sensitivity_classifier.joblib --type custom_model --workspace-name weaver-ml --resource-group weaver-rg

# Verify
az ml model list --workspace-name weaver-ml --resource-group weaver-rg --output table
```

**Expected output**: Table showing `sensitivity-classifier` model with version 1.

### Step 14 — Set Up Synapse Analytics

```powershell
# Create ADLS Gen2 storage
az storage account create --name weaversynapsestorage --resource-group weaver-rg --location centralindia --sku Standard_LRS --kind StorageV2 --hns true

# Create Synapse workspace
az synapse workspace create --name weaver-synapse --resource-group weaver-rg --location centralindia --storage-account weaversynapsestorage --file-system weaver-synapse-fs --sql-admin-login-user synapse_admin --sql-admin-login-password "<STRONG_PASSWORD>"

# Create Spark pool
az synapse spark pool create --name weaverspark --workspace-name weaver-synapse --resource-group weaver-rg --spark-version 3.4 --node-count 3 --node-size Small --enable-auto-pause true --delay 15
```

### Step 15 — Set Up Monitoring

```powershell
# Log Analytics workspace
az monitor log-analytics workspace create --workspace-name weaver-logs --resource-group weaver-rg --location centralindia

# App Insights
az monitor app-insights component create --app weaver-insights --resource-group weaver-rg --location centralindia --workspace weaver-logs --application-type web

# Store connection string in Key Vault
$AI_CONN = az monitor app-insights component show --app weaver-insights --resource-group weaver-rg --query connectionString -o tsv
az keyvault secret set --vault-name weaver-kv --name "APPINSIGHTS-CONNECTION-STRING" --value $AI_CONN

# Update Container Apps to use Log Analytics
$LOG_ID = az monitor log-analytics workspace show --workspace-name weaver-logs --resource-group weaver-rg --query customerId -o tsv
$LOG_KEY = az monitor log-analytics workspace get-shared-keys --workspace-name weaver-logs --resource-group weaver-rg --query primarySharedKey -o tsv
az containerapp env update --name weaver-env --resource-group weaver-rg --logs-workspace-id $LOG_ID --logs-workspace-key $LOG_KEY
```

### Step 16 — Update CORS & Redeploy Backend

After Front Door is set up, update the backend CORS to use the Front Door hostname:

```powershell
az containerapp update --name weaver-backend --resource-group weaver-rg `
  --set-env-vars "CORS_ORIGINS=https://$FD_HOSTNAME"
```

Also rebuild the frontend with the Front Door URL as the API base:

```powershell
cd "E:\MTech\MTech Sem2\Cloud\Project\Weaver\frontend"
$env:VITE_API_URL = "https://$FD_HOSTNAME"
npm run build
npx @azure/static-web-apps-cli deploy ./dist --deployment-token $SWA_TOKEN --env production
```

---

## Verification Walkthrough — Testing Every Feature

After all services are deployed, run through this checklist to verify everything works:

### Test 1: Frontend Loads
1. Open `https://<FRONT_DOOR_HOSTNAME>/` in your browser
2. ✅ The Weaver landing page should load with full styling
3. ✅ No console errors in browser dev tools

### Test 2: Login
1. Click "Login" → enter `admin@weaver.local` / `Admin@1234`
2. ✅ Login succeeds, redirected to dashboard
3. ✅ JWT token stored in localStorage

### Test 3: Text Classification
1. Go to Classify page
2. Enter text: `My SSN is 123-45-6789 and credit card is 4111-1111-1111-1111`
3. ✅ Returns `highly_sensitive` classification
4. ✅ LIME explanation shows top features (SSN pattern, credit card pattern)
5. ✅ Confidence score displayed

### Test 4: File Classification
1. Upload a `.txt` or `.pdf` file containing sensitive data
2. ✅ File is classified with correct sensitivity level
3. ✅ File name and type displayed

### Test 5: Encryption (All 4 Levels)
1. Classify a text → Encrypt at **Public** level → ✅ Base64 encoded (no encryption)
2. Classify → Encrypt at **Internal** → ✅ AES-128-GCM encrypted
3. Classify → Encrypt at **Confidential** → ✅ AES-256-GCM + ECDSA signature
4. Classify → Encrypt at **Highly Sensitive** → ✅ Requires MFA, AES-256-GCM + RSA-PSS

### Test 6: MFA Setup & Enforcement
1. Go to Profile → Enable MFA
2. ✅ QR code displayed, scan with authenticator app
3. ✅ Enter TOTP code → MFA enabled
4. Encrypt something at Highly Sensitive level
5. ✅ MFA challenge modal appears, enter TOTP code → Encryption succeeds

### Test 7: Share Links
1. Encrypt a payload → Create share link
2. ✅ Share link URL generated with token prefix
3. Copy link → Open in incognito/different browser
4. ✅ Guest can access and decrypt the shared data

### Test 8: Admin Dashboard
1. Login as admin → Go to Admin Dashboard
2. ✅ Analytics overview loads (total classifications, encryptions, users)
3. ✅ Charts render (sensitivity distribution, algorithm usage)
4. ✅ Audit logs table populated with recent actions
5. ✅ User management page lists all users

### Test 9: Re-encryption
1. Go to History → Select an encrypted payload
2. Re-encrypt at a different level
3. ✅ New payload created with updated encryption

### Test 10: Azure Services Verification
```powershell
# Check Container Apps logs
az containerapp logs show --name weaver-backend --resource-group weaver-rg --type system

# Check App Insights for requests
az monitor app-insights query --app weaver-insights --resource-group weaver-rg --analytics-query "requests | take 10"

# Check Blob Storage has encrypted payloads
az storage blob list --container-name encrypted-payloads --account-name weaverstorageprod --auth-mode login --output table

# Check Service Bus messages processed
az servicebus queue show --namespace-name weaver-sb --resource-group weaver-rg --name classification-jobs --query 'countDetails' -o json

# Check ML model is registered
az ml model show --name sensitivity-classifier --workspace-name weaver-ml --resource-group weaver-rg
```

---

## Troubleshooting

| Problem | Likely Cause | Fix |
|---|---|---|
| Backend returns 500 | Key Vault secrets not loading | Check managed identity has `Key Vault Secrets User` role. Check `KEY_VAULT_URL` env var. |
| Can't connect to database | Firewall blocking | Add Container Apps outbound IPs to PostgreSQL firewall, or use `0.0.0.0` for Azure services. |
| Frontend shows blank page | Build failed or wrong API URL | Re-run `npm run build` with correct `VITE_API_URL`. Check browser console for errors. |
| CORS errors in browser | Wrong `CORS_ORIGINS` | Update Container Apps env var to match your Front Door domain. |
| Login returns 401 | JWT secret mismatch | Verify `JWT-SECRET-KEY` in Key Vault matches what `config.py` loads. |
| ML classification fails | Model not loaded from Azure ML | Check `az ml model list`. Verify `ml_service.py` downloads the model on startup. |
| Blob upload fails | Permission denied | Verify managed identity has `Storage Blob Data Contributor` on the storage account. |
| Front Door returns 503 | Backend not healthy | Check `https://<BACKEND_URL>/health` directly. Check Container Apps logs. |
| Service Bus not processing | Worker not running | Ensure the worker container app is deployed and scaled to ≥1 replica. |
| Static Web App 404 on routes | Missing SPA fallback | Check `staticwebapp.config.json` has `navigationFallback` configured. |

### Useful Debug Commands

```powershell
# View backend container logs (live)
az containerapp logs show --name weaver-backend --resource-group weaver-rg --follow

# Restart backend container
az containerapp revision restart --name weaver-backend --resource-group weaver-rg --revision <revision-name>

# List all resources in the resource group
az resource list --resource-group weaver-rg --output table

# Check all Key Vault secrets (names only)
az keyvault secret list --vault-name weaver-kv --output table

# Test database connectivity
az postgres flexible-server connect --name weaver-db-prod --admin-user weaver_admin --admin-password "<PASSWORD>" --database-name weaver
```

---

## Teardown — Cleanup

If you need to delete everything and start over (or shut down to stop billing):

```powershell
# ⚠️ THIS DELETES EVERYTHING — all data, all services, irreversible!
az group delete --name weaver-rg --yes --no-wait

# Also delete the app registration
az ad app delete --id $(az ad app list --display-name "Weaver API" --query '[0].appId' -o tsv)
```

This removes all ~12 Azure services in one command. Your code is safe locally — only cloud resources are deleted.

---

> **Key Principle**: This is a **100% cloud-only** deployment. There is NO local fallback, NO `.env` file, NO local model files. Every secret comes from Key Vault, every file goes to Blob Storage, every model loads from Azure ML. The app runs exclusively on Azure — just like a real production cloud project. 🚀
