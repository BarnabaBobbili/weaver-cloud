# Weaver Project Documentation

**Project:** Weaver - AI-Driven Adaptive Cryptographic Policy Engine  
**Last Updated:** 2026-03-27  
**Environment Baseline:** Azure deployment in resource group `weaver-rg`

## 1. Problem Statement

Organizations process mixed-sensitivity data (public, internal, confidential, highly sensitive) but often rely on static encryption policies and fragmented controls. This creates two operational failures:

1. Inconsistent cryptographic protection across data classes.
2. Weak linkage between user risk posture (for example, MFA state) and cryptographic enforcement.

Weaver addresses this by combining ML-assisted sensitivity classification with adaptive policy enforcement, so each payload is protected using a policy suitable to its risk profile.

## 2. Project Objectives

1. Build a secure API platform for classification, encryption/decryption, sharing, and governance.
2. Enforce role-based controls and MFA-aware operations for high-risk workflows.
3. Implement adaptive cryptographic policy mapping from content sensitivity.
4. Deploy as an Azure-native architecture with managed services.
5. Provide observability, auditability, and analytics export for governance.

## 3. Project Modules

### 3.1 Backend (FastAPI)

- Authentication and token lifecycle (access + refresh).
- MFA setup/verify/disable and recovery-code flow.
- Sensitivity classification endpoints (text/file).
- Encryption/decryption APIs with policy checks.
- Share-link generation and guest access flow.
- Admin APIs for users, policies, shares, compliance, audit views.
- Analytics APIs and Synapse export orchestration.

### 3.2 Frontend (React + TypeScript)

- Public pages (landing, login, registration, decrypt by token).
- Authenticated dashboard and workflow pages.
- Role-gated analyst/admin screens.
- Profile, help, MFA setup, and security-facing UX.

### 3.3 Security and Governance

- RBAC (`admin`, `analyst`, `viewer`).
- MFA enforcement points for sensitive actions.
- Security headers, session timeout, and rate limiting.
- Audit event capture and access logs.

### 3.4 Data and Analytics

- PostgreSQL transactional storage.
- Blob storage for large encrypted payloads.
- Service Bus events for asynchronous processing.
- Synapse-oriented export path for analytical workloads and BI.

## 4. Azure Services Used

The following services are active in `weaver-rg` (verified via Azure CLI):

| Service Category | Azure Service | Deployed Resource(s) | Purpose in Weaver |
|---|---|---|---|
| Compute | Azure Container Apps | `weaver-env`, `weaver-backend` | Backend API runtime with autoscaling |
| Frontend Hosting | Azure Static Web Apps | `weaver-frontend` | React frontend hosting |
| Database | Azure PostgreSQL Flexible Server | `weaver-db-prod` | Primary OLTP database |
| Secrets | Azure Key Vault | `weaver-kv-ijbkmp25` | Runtime secret storage |
| Identity | Managed Identity | `weaver-backend-identity` | Secretless service-to-service auth |
| Object Storage | Azure Storage | `weaverstorageprod` | Encrypted payload and model/data object storage |
| Messaging | Azure Service Bus | `weaver-servicebus-prod` | Async events/jobs (`analytics-events`, `classification-jobs`, `encryption-jobs`) |
| Monitoring | Application Insights | `weaver-appinsights` | Application telemetry and diagnostics |
| API Layer | API Management | `weaver-apim` | Gateway and API governance layer |
| ML Platform | Azure Machine Learning | `weaver-ml-workspace` (+ endpoints) | Model lifecycle and online ML endpoints |
| Analytics Warehouse | Azure Synapse | `weaver-synapse-ws` | Analytical querying and BI integration |
| BI Capacity | Power BI Dedicated | `weaveranalytics` | Dedicated capacity for analytics workloads |

## 5. Verified Runtime Endpoints

- Frontend: `https://salmon-meadow-04fa55300.1.azurestaticapps.net`
- Backend: `https://weaver-backend.whitehill-eea76820.centralindia.azurecontainerapps.io`
- APIM Gateway: `https://weaver-apim.azure-api.net`
- PostgreSQL server: `weaver-db-prod.postgres.database.azure.com`
- Synapse serverless SQL (Power BI server value): `weaver-synapse-ws-ondemand.sql.azuresynapse.net`

## 6. Project Execution Steps

### Phase 1: Foundation

1. Create Azure resource group and register required providers.
2. Create user-assigned managed identity.
3. Set subscription-scoped and resource-scoped access roles.

### Phase 2: Data and Security Baseline

1. Provision Key Vault and configure secret access.
2. Provision PostgreSQL Flexible Server + database.
3. Configure firewall/network access and SSL-required DB connections.
4. Provision storage account and required containers.

### Phase 3: Backend Deployment

1. Build backend container image and push to ACR.
2. Deploy Container App and inject required environment values.
3. Wire runtime to Key Vault and managed identity.
4. Run seed/migration tasks and verify `/health`.

### Phase 4: Frontend Deployment

1. Build frontend with production API URL.
2. Deploy to Azure Static Web Apps.
3. Update backend CORS origins for deployed domain.

### Phase 5: Integration Services

1. Configure Service Bus namespace/queues.
2. Configure Application Insights telemetry.
3. Configure API Management gateway.
4. Configure Azure ML workspace and endpoints.
5. Configure Synapse workspace and ETL/export path.

### Phase 6: Data Migration and Validation

1. Export source database (`pg_dump`) from Supabase direct connection.
2. Restore to Azure PostgreSQL (`psql`/`pg_restore`) with compatibility handling.
3. Validate schema/table parity and key row counts.
4. Execute critical business-flow smoke tests.

## 7. Operational Validation Checklist

- Backend health endpoints return healthy status.
- Auth/MFA flows execute successfully.
- Encryption/decryption workflows complete for text and file payloads.
- Admin role operations (user/policy/share management) are functional.
- Analytics export endpoint triggers successfully.
- Synapse endpoint is reachable for BI integrations.

## 8. Risks and Recommendations

- Standardize Service Bus namespace naming across scripts and runtime config.
- Add CI integration tests that run against cloud-like ephemeral environment.
- Add runbooks for rollback and incident response.
- Keep credentials only in Key Vault/secret stores; avoid embedding in docs/scripts.
