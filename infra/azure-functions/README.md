# Azure Functions: Synapse Daily ETL

This function app triggers a daily ETL call to Weaver backend for Synapse export.

## Purpose

- Schedule-driven analytics export
- Calls backend endpoint:
  - `POST /api/analytics/synapse/export`
- Supports optional bearer token via `ADMIN_API_KEY`

## Files

- `function_app.py` timer trigger implementation
- `host.json` function host settings
- `requirements.txt` runtime dependencies

## Runtime Configuration

Set these app settings in the Function App:

- `BACKEND_URL` (default points to deployed Weaver backend)
- `ADMIN_API_KEY` (optional, if endpoint is protected)

## Schedule

Cron: `0 0 0 * * *`  
Execution: daily at 00:00:00 UTC

## Deployment (CLI)

```powershell
az functionapp create `
  --name weaver-synapse-etl `
  --resource-group weaver-rg `
  --storage-account weaverstorageprod `
  --consumption-plan-location centralindia `
  --runtime python `
  --runtime-version 3.11 `
  --functions-version 4 `
  --os-type Linux

func azure functionapp publish weaver-synapse-etl
```

## Monitoring

- Azure Portal -> Function App -> Monitor
- Application Insights telemetry (if linked)
