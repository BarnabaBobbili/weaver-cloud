# Weaver

Weaver is an AI-driven adaptive cryptographic policy engine that classifies content sensitivity, applies policy-based encryption/signing, enforces MFA for high-risk operations, and provides secure sharing plus analytics.

## Current Deployment Snapshot (Verified: 2026-03-27)

| Component | Value |
|---|---|
| Frontend | `https://salmon-meadow-04fa55300.1.azurestaticapps.net` |
| Backend | `https://weaver-backend.whitehill-eea76820.centralindia.azurecontainerapps.io` |
| API Gateway | `https://weaver-apim.azure-api.net` |
| PostgreSQL | `weaver-db-prod.postgres.database.azure.com` (Azure PostgreSQL Flexible Server v16) |
| Synapse SQL (serverless) | `weaver-synapse-ws-ondemand.sql.azuresynapse.net` |
| Synapse workspace SQL endpoint | `weaver-synapse-ws.sql.azuresynapse.net` |
| Service Bus namespace | `weaver-servicebus-prod.servicebus.windows.net` |

## Core Modules

- **Authentication and Security**: JWT, RBAC, MFA (TOTP), session timeout, rate limiting, security headers.
- **Classification Pipeline**: Text/file sensitivity analysis with ML-assisted policy selection.
- **Cryptography Engine**: AES-GCM encryption, signing policies, key hierarchy support, audit logging.
- **Sharing and Guest Access**: Time-bounded secure links and share-access tracking.
- **Admin and Compliance**: User/policy management, MFA reset controls, audit/compliance dashboards.
- **Analytics**: Operational analytics endpoints and Synapse export pipeline.
- **Cloud Integrations**: Key Vault, Blob Storage, Service Bus, Application Insights, Azure ML, Synapse.

## Repository Layout

- `backend/` FastAPI application, models, services, workers, tests.
- `frontend/` React + Vite application.
- `infra/` deployment scripts, Synapse SQL artifacts, Azure Function ETL.
- `docs/` consolidated project documentation and submission report (`.tex`).

## Documentation Index

- `SETUP.md` local/cloud setup.
- `DEPLOYMENT_GUIDE.md` Azure deployment and execution flow.
- `IMPLEMENTATION_STATUS.md` current implementation and verification status.
- `AZURE_IMPLEMENTATION_COMPLETE.md` cloud architecture completion summary.
- `GITHUB_DEPLOY_GUIDE.md` secure CI/CD setup notes.
- `docs/PROJECT_DOCUMENTATION.md` detailed technical documentation.
- `docs/Weaver_Project_Report.tex` structured submission report in LaTeX.
