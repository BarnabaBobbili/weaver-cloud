# CI/CD Setup Guide (OIDC + GitHub Actions)

This project deploys three services from GitHub Actions:

- Backend -> Azure Container Apps (`weaver-backend`)
- ML service -> Azure Container Apps (`weaver-ml`)
- Frontend -> Azure Static Web Apps (`weaver-frontend`)

## Why OIDC

`az ad sp create-for-rbac` can fail in student/locked tenants due to app registration permissions.

This repo now uses GitHub OIDC with a user-assigned managed identity, which avoids storing Azure client secrets in GitHub.

## Azure resources and IDs

- Subscription ID: `7e28e79f-6729-47d7-accc-38b7c1cefdf1`
- Tenant ID: `00f9cda3-075e-44e5-aa0b-aba3add6539f`
- Resource group: `weaver-rg`
- ACR: `weaveracr.azurecr.io`
- Managed identity: `weaver-github-oidc`
- Managed identity client ID: `bdc12812-af72-4a7f-9a8b-0aa6fa96755c`

## One-time Azure setup

If not already done, run:

```bash
az identity create --resource-group weaver-rg --name weaver-github-oidc --location centralindia

IDENTITY_PRINCIPAL_ID=$(az identity show --resource-group weaver-rg --name weaver-github-oidc --query principalId -o tsv)

MSYS_NO_PATHCONV=1 az role assignment create \
  --assignee-object-id "$IDENTITY_PRINCIPAL_ID" \
  --assignee-principal-type ServicePrincipal \
  --role Contributor \
  --scope /subscriptions/7e28e79f-6729-47d7-accc-38b7c1cefdf1/resourceGroups/weaver-rg

az identity federated-credential create \
  --name github-main \
  --identity-name weaver-github-oidc \
  --resource-group weaver-rg \
  --issuer https://token.actions.githubusercontent.com \
  --subject repo:BarnabaBobbili/weaver-cloud:ref:refs/heads/main \
  --audiences api://AzureADTokenExchange
```

Notes:

- `MSYS_NO_PATHCONV=1` is needed in Git Bash on Windows for `/subscriptions/...` scope paths.
- If role assignment already exists, Azure returns a conflict; this is safe to ignore.

## Required GitHub secrets

Go to `Settings -> Secrets and variables -> Actions` in:

`https://github.com/BarnabaBobbili/weaver-cloud`

Add these repository secrets:

1. `AZURE_CLIENT_ID`
   - `bdc12812-af72-4a7f-9a8b-0aa6fa96755c`

2. `AZURE_TENANT_ID`
   - `00f9cda3-075e-44e5-aa0b-aba3add6539f`

3. `AZURE_SUBSCRIPTION_ID`
   - `7e28e79f-6729-47d7-accc-38b7c1cefdf1`

4. `ACR_USERNAME`
   - Command:
   ```bash
   az acr credential show --name weaveracr --query username -o tsv
   ```

5. `ACR_PASSWORD`
   - Command:
   ```bash
   az acr credential show --name weaveracr --query "passwords[0].value" -o tsv
   ```

6. `AZURE_STATIC_WEB_APPS_API_TOKEN`
   - Command:
   ```bash
   az staticwebapp secrets list --name weaver-frontend --resource-group weaver-rg --query "properties.apiKey" -o tsv
   ```

## Workflow files

- `.github/workflows/deploy-backend.yml`
- `.github/workflows/deploy-frontend.yml`
- `.github/workflows/deploy-ml-service.yml`

Each workflow now includes:

- `permissions: id-token: write`
- `azure/login@v2` using `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID`

## Trigger behavior

- Backend deploy runs on changes in `backend/**`
- Frontend deploy runs on changes in `frontend/**`
- ML deploy runs on changes in `ml-service/**`
- All also support manual `workflow_dispatch`

## First run checklist

1. Add all secrets.
2. Open `https://github.com/BarnabaBobbili/weaver-cloud/actions`.
3. Manually run these workflows in order:
   - `Deploy ML Service to Azure Container Apps`
   - `Deploy Backend to Azure Container Apps`
   - `Deploy Frontend to Azure Static Web Apps`
4. Verify:
   - Backend health: `https://weaver-backend.whitehill-eea76820.centralindia.azurecontainerapps.io/health`
   - ML health: `https://weaver-ml.whitehill-eea76820.centralindia.azurecontainerapps.io/health`
   - Frontend: `https://salmon-meadow-04fa55300.1.azurestaticapps.net`

## Troubleshooting

### `Login failed with OIDC`

- Confirm secret values are exact and not quoted.
- Confirm federated subject matches exactly:
  `repo:BarnabaBobbili/weaver-cloud:ref:refs/heads/main`
- Ensure workflow file has:
  - `permissions: id-token: write`
  - `azure/login@v2`

### `Insufficient privileges` during setup

- This usually appears with `az ad sp create-for-rbac` in restricted tenants.
- Use the managed identity OIDC path in this guide instead.

### `ACR unauthorized`

- Rotate and re-save ACR password:
  ```bash
  az acr credential renew --name weaveracr --password-name password
  az acr credential show --name weaveracr --query "passwords[0].value" -o tsv
  ```

### Git Bash role assignment shows `MissingSubscription`

- You likely hit path conversion (`/subscriptions/...` became `C:/Program Files/Git/...`).
- Prefix command with `MSYS_NO_PATHCONV=1`.

## Security notes

- Prefer OIDC over long-lived Azure client secrets.
- Rotate ACR password periodically.
- Keep branch protection enabled on `main`.
