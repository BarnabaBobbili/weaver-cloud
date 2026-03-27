# Azure Functions: Synapse Incremental ETL

This function app triggers frequent incremental ETL calls to Weaver backend for Synapse export.

## Purpose

- Schedule-driven incremental export
- Calls backend endpoint:
  - `POST /api/analytics/synapse/export/internal`
- Auth via sync key header `X-Synapse-Sync-Key`

## Files

- `function_app.py` timer trigger implementation
- `host.json` function host settings
- `requirements.txt` runtime dependencies

## Runtime Configuration

Set these app settings in the Function App:

- `BACKEND_URL` (default points to deployed Weaver backend)
- `SYNAPSE_SYNC_API_KEY` (required, must match backend setting)

## Schedule

Cron: `0 */5 * * * *`  
Execution: every 5 minutes

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
