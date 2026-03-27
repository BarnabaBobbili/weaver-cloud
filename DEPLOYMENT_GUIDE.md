# Weaver Azure Deployment Guide

## Scope

This guide documents execution of Weaver on Azure using the resources currently deployed in `weaver-rg`.

## Deployed Runtime (Verified: 2026-03-27)

- Backend Container App: `weaver-backend`
- Frontend Static Web App: `weaver-frontend`
- PostgreSQL Flexible Server: `weaver-db-prod` (v16)
- Key Vault: `weaver-kv-ijbkmp25`
- Service Bus: `weaver-servicebus-prod`
- Synapse Workspace: `weaver-synapse-ws`
- Azure ML Workspace: `weaver-ml-workspace`
- API Management: `weaver-apim`

## Option A: Scripted Deployment

```powershell
cd "E:\MTech\MTech Sem2\Cloud\Project\Weaver\infra"
.\deploy.ps1
```

What the script handles:

1. Foundation setup (resource group + managed identity).
2. Data layer (Key Vault, PostgreSQL, Storage, Service Bus, Insights).
3. Backend container build and deployment.
4. Frontend deployment.
5. Optional advanced integrations (ML/Synapse/APIM depending on variant script).

## Option B: CI/CD Deployment

- Backend workflow: `.github/workflows/deploy-backend.yml`
- Frontend workflow: `.github/workflows/deploy-frontend.yml`

Required secrets:

- `AZURE_CREDENTIALS`
- `ACR_USERNAME`
- `ACR_PASSWORD`

## Post-Deployment Verification

### Endpoint Checks

```powershell
# Backend health
Invoke-WebRequest -Uri "https://weaver-backend.whitehill-eea76820.centralindia.azurecontainerapps.io/health" -UseBasicParsing

# Frontend
Invoke-WebRequest -Uri "https://salmon-meadow-04fa55300.1.azurestaticapps.net" -UseBasicParsing
```

### Azure Resource Verification

```powershell
az resource list --resource-group weaver-rg --output table
```

### Database Connectivity Check

```powershell
psql "postgresql://<user>:<password>@weaver-db-prod.postgres.database.azure.com:5432/weaver?sslmode=require" -c "SELECT NOW();"
```

## Data Migration Workflow (Supabase to Azure PostgreSQL)

Use direct connections and SSL:

```powershell
pg_dump --dbname "postgresql://<supabase-user>:<supabase-pass>@<supabase-host>:5432/postgres?sslmode=require" `
  --format=plain --clean --if-exists --no-owner --no-privileges --schema=public `
  --file "supabase_public.sql"

# If needed, remove unsupported server settings from dump before restore.
psql "postgresql://<azure-user>:<azure-pass>@weaver-db-prod.postgres.database.azure.com:5432/weaver?sslmode=require" `
  -v ON_ERROR_STOP=1 -f "supabase_public.sql"
```

## Operational Notes

- Keep `CORS_ORIGINS` aligned with frontend hostname.
- Run seed scripts only in controlled environments.
- Use Azure Key Vault for secret rotation and runtime retrieval.
- For Power BI through Synapse serverless, use server:
  - `weaver-synapse-ws-ondemand.sql.azuresynapse.net`
