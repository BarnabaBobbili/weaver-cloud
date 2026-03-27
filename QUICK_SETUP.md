# Quick Setup for GitHub Actions (OIDC)

Use this if `az ad sp create-for-rbac` fails with insufficient directory privileges.

## Values for this project

- Subscription ID: `7e28e79f-6729-47d7-accc-38b7c1cefdf1`
- Tenant ID: `00f9cda3-075e-44e5-aa0b-aba3add6539f`
- Resource group: `weaver-rg`
- Repo: `BarnabaBobbili/weaver-cloud`

## What was set up

An Azure user-assigned managed identity was created and linked to GitHub OIDC:

- Identity name: `weaver-github-oidc`
- Client ID: `bdc12812-af72-4a7f-9a8b-0aa6fa96755c`
- Principal ID: `d4b8a35a-e61f-49c6-83f5-2518f1ccf8c1`
- Federated credential subject: `repo:BarnabaBobbili/weaver-cloud:ref:refs/heads/main`

## Add these GitHub secrets

Go to `https://github.com/BarnabaBobbili/weaver-cloud/settings/secrets/actions` and add:

1. `AZURE_CLIENT_ID`
   - Value: `bdc12812-af72-4a7f-9a8b-0aa6fa96755c`

2. `AZURE_TENANT_ID`
   - Value: `00f9cda3-075e-44e5-aa0b-aba3add6539f`

3. `AZURE_SUBSCRIPTION_ID`
   - Value: `7e28e79f-6729-47d7-accc-38b7c1cefdf1`

4. `ACR_USERNAME`
   - Get from:
   ```bash
   az acr credential show --name weaveracr --query username -o tsv
   ```

5. `ACR_PASSWORD`
   - Get from:
   ```bash
   az acr credential show --name weaveracr --query "passwords[0].value" -o tsv
   ```

6. `AZURE_STATIC_WEB_APPS_API_TOKEN`
   - Get from:
   ```bash
   az staticwebapp secrets list --name weaver-frontend --resource-group weaver-rg --query "properties.apiKey" -o tsv
   ```

## Workflows already updated

These workflows now use OIDC (`azure/login@v2` with client/tenant/subscription secrets):

- `.github/workflows/deploy-backend.yml`
- `.github/workflows/deploy-frontend.yml`
- `.github/workflows/deploy-ml-service.yml`

## Run and verify

1. Open `https://github.com/BarnabaBobbili/weaver-cloud/actions`
2. Run in this order:
   - `Deploy ML Service to Azure Container Apps`
   - `Deploy Backend to Azure Container Apps`
   - `Deploy Frontend to Azure Static Web Apps`
3. Verify URLs:
   - Backend health: `https://weaver-backend.whitehill-eea76820.centralindia.azurecontainerapps.io/health`
   - ML health: `https://weaver-ml.whitehill-eea76820.centralindia.azurecontainerapps.io/health`
   - Frontend: `https://salmon-meadow-04fa55300.1.azurestaticapps.net`

## If you need to recreate OIDC setup manually

```bash
az identity create --resource-group weaver-rg --name weaver-github-oidc --location centralindia

MSYS_NO_PATHCONV=1 az role assignment create \
  --assignee-object-id <principal-id> \
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

Note: In Git Bash on Windows, use `MSYS_NO_PATHCONV=1` for commands that include `/subscriptions/...`.
