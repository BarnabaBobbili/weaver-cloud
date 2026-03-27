# GitHub Actions Deployment Guide (Secure)

This guide configures Weaver CI/CD without embedding raw credentials in the repository.

## 1. Required GitHub Secrets

Add these in: `Settings -> Secrets and variables -> Actions`

- `AZURE_CREDENTIALS` (service principal JSON)
- `ACR_USERNAME`
- `ACR_PASSWORD`

## 2. Create Service Principal for `AZURE_CREDENTIALS`

```powershell
az ad sp create-for-rbac `
  --name "weaver-github-actions" `
  --role contributor `
  --scopes /subscriptions/<SUBSCRIPTION_ID>/resourceGroups/weaver-rg `
  --sdk-auth
```

Copy the JSON output and store it as `AZURE_CREDENTIALS`.

## 3. Get ACR Credentials

```powershell
az acr credential show --name weaveracr --query username -o tsv
az acr credential show --name weaveracr --query "passwords[0].value" -o tsv
```

Set outputs as:

- `ACR_USERNAME`
- `ACR_PASSWORD`

## 4. Workflows in This Repo

- Backend deploy: `.github/workflows/deploy-backend.yml`
- Frontend deploy: `.github/workflows/deploy-frontend.yml`

Both can run on `push` to `main` or via `workflow_dispatch`.

## 5. Verification

After workflow success:

- Backend health: `https://weaver-backend.whitehill-eea76820.centralindia.azurecontainerapps.io/health`
- Frontend: `https://salmon-meadow-04fa55300.1.azurestaticapps.net`

## 6. Security Checklist

- Rotate service principal secret periodically.
- Rotate ACR passwords periodically.
- Never commit connection strings, PATs, or cloud secrets into Markdown/docs.
