# CI/CD Setup Guide for Weaver

This guide will help you set up GitHub Actions CI/CD pipelines for automatic deployment to Azure.

## Overview

The repository contains 3 GitHub Actions workflows:
1. **Backend CI/CD** (`.github/workflows/deploy-backend.yml`) - Deploys to Azure Container Apps
2. **Frontend CI/CD** (`.github/workflows/deploy-frontend.yml`) - Deploys to Azure Static Web Apps
3. **ML Service CI/CD** (`.github/workflows/deploy-ml-service.yml`) - Deploys to Azure Container Apps

## Prerequisites

Before setting up CI/CD, ensure you have:
- GitHub repository: `https://github.com/BarnabaBobbili/weaver-cloud`
- Azure subscription with the following resources deployed:
  - Resource Group: `weaver-rg`
  - Azure Container Registry: `weaveracr.azurecr.io`
  - Container Apps: `weaver-backend`, `weaver-ml`
  - Static Web App: `weaver-frontend`
  - Container Apps Environment: `weaver-env`

## Step 1: Create Azure Service Principal

The workflows need an Azure Service Principal to authenticate and deploy resources.

### 1.1 Create Service Principal

Open your terminal and run:

```bash
az ad sp create-for-rbac \
  --name "weaver-github-actions" \
  --role contributor \
  --scopes /subscriptions/YOUR_SUBSCRIPTION_ID/resourceGroups/weaver-rg \
  --sdk-auth
```

**Replace `YOUR_SUBSCRIPTION_ID`** with your actual Azure subscription ID. You can get it with:
```bash
az account show --query id -o tsv
```

### 1.2 Save the Output

The command will output JSON like this:
```json
{
  "clientId": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "clientSecret": "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
  "subscriptionId": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "tenantId": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "activeDirectoryEndpointUrl": "https://login.microsoftonline.com",
  "resourceManagerEndpointUrl": "https://management.azure.com/",
  "activeDirectoryGraphResourceId": "https://graph.windows.net/",
  "sqlManagementEndpointUrl": "https://management.core.windows.net:8443/",
  "galleryEndpointUrl": "https://gallery.azure.com/",
  "managementEndpointUrl": "https://management.core.windows.net/"
}
```

**IMPORTANT:** Save this entire JSON output - you'll need it for GitHub Secrets.

## Step 2: Get Azure Container Registry Credentials

### 2.1 Enable Admin Access on ACR

```bash
az acr update --name weaveracr --admin-enabled true
```

### 2.2 Get ACR Credentials

```bash
az acr credential show --name weaveracr
```

Output will look like:
```json
{
  "passwords": [
    {
      "name": "password",
      "value": "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
    },
    {
      "name": "password2",
      "value": "yyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyy"
    }
  ],
  "username": "weaveracr"
}
```

**Save:**
- Username: `weaveracr`
- Password: Copy one of the password values

## Step 3: Get Static Web App Deployment Token

```bash
az staticwebapp secrets list \
  --name weaver-frontend \
  --resource-group weaver-rg \
  --query "properties.apiKey" -o tsv
```

**Save** the output token - you'll need it for GitHub Secrets.

## Step 4: Add GitHub Secrets

Go to your GitHub repository: `https://github.com/BarnabaBobbili/weaver-cloud`

1. Click **Settings** → **Secrets and variables** → **Actions**
2. Click **New repository secret** for each of the following:

### Required Secrets

| Secret Name | Value | Where to Get It |
|-------------|-------|-----------------|
| `AZURE_CREDENTIALS` | The entire JSON output from Step 1.2 | Service Principal creation command |
| `ACR_USERNAME` | `weaveracr` | From Step 2.2 |
| `ACR_PASSWORD` | The password from Step 2.2 | ACR credentials command |
| `AZURE_STATIC_WEB_APPS_API_TOKEN` | The token from Step 3 | Static Web App secrets command |

### How to Add Each Secret

For each secret:
1. Click **New repository secret**
2. Enter the **Name** (exactly as shown above)
3. Paste the **Value**
4. Click **Add secret**

**IMPORTANT:** 
- For `AZURE_CREDENTIALS`, paste the **ENTIRE JSON** from Step 1.2 (including the curly braces)
- Make sure there are no extra spaces or line breaks

## Step 5: Verify Workflows

Once secrets are added, the workflows are ready to use.

### Automatic Triggers

The workflows automatically run when:
- **Backend workflow**: Changes pushed to `main` branch in `backend/**` folder
- **Frontend workflow**: Changes pushed to `main` branch in `frontend/**` folder
- **ML Service workflow**: Changes pushed to `main` branch in `ml-service/**` folder

### Manual Trigger

You can also manually trigger any workflow:
1. Go to **Actions** tab in GitHub
2. Select the workflow (e.g., "Deploy Backend to Azure Container Apps")
3. Click **Run workflow** → Select `main` branch → Click **Run workflow**

## Step 6: Test the CI/CD Pipeline

Let's test the backend workflow:

### 6.1 Make a Small Change

Edit `backend/app/main.py` and change the version or add a comment:

```python
# Test CI/CD pipeline - updated at 2026-03-27
```

### 6.2 Commit and Push

```bash
git add backend/app/main.py
git commit -m "test: verify CI/CD pipeline"
git push origin main
```

### 6.3 Monitor Deployment

1. Go to **Actions** tab: `https://github.com/BarnabaBobbili/weaver-cloud/actions`
2. You should see the "Deploy Backend to Azure Container Apps" workflow running
3. Click on it to see the live logs
4. Wait for it to complete (usually 3-5 minutes)

### 6.4 Verify Deployment

Once complete, verify the backend is updated:
```bash
curl https://weaver-backend.whitehill-eea76820.centralindia.azurecontainerapps.io/health
```

## Workflow Details

### Backend Workflow (deploy-backend.yml)

**Triggers:** Changes in `backend/**`

**Steps:**
1. Build Docker image
2. Push to Azure Container Registry
3. Deploy to Azure Container Apps
4. Run health check

**Image Tags:**
- `weaveracr.azurecr.io/weaver-backend:${{ github.sha }}`
- `weaveracr.azurecr.io/weaver-backend:latest`

### Frontend Workflow (deploy-frontend.yml)

**Triggers:** Changes in `frontend/**`

**Steps:**
1. Install dependencies
2. Get backend URL from Azure
3. Build with `VITE_API_URL` environment variable
4. Deploy to Azure Static Web Apps
5. Update backend CORS settings

### ML Service Workflow (deploy-ml-service.yml)

**Triggers:** Changes in `ml-service/**`

**Steps:**
1. Build Docker image
2. Push to Azure Container Registry
3. Deploy to Azure Container Apps
4. Run health check
5. Update backend's `AZURE_ML_ENDPOINT_URL` environment variable

**Image Tags:**
- `weaveracr.azurecr.io/weaver-ml:${{ github.sha }}`
- `weaveracr.azurecr.io/weaver-ml:latest`

## Troubleshooting

### Workflow Fails with "Login failed"

**Issue:** `AZURE_CREDENTIALS` secret is incorrect or missing.

**Solution:**
1. Verify the secret contains the complete JSON from Step 1.2
2. Re-create the service principal if needed
3. Update the secret in GitHub

### ACR Push Fails with "unauthorized"

**Issue:** `ACR_USERNAME` or `ACR_PASSWORD` is incorrect.

**Solution:**
1. Run the command from Step 2.2 again
2. Update both `ACR_USERNAME` and `ACR_PASSWORD` secrets

### Static Web App Deployment Fails

**Issue:** `AZURE_STATIC_WEB_APPS_API_TOKEN` is incorrect or expired.

**Solution:**
1. Run the command from Step 3 again to get a fresh token
2. Update the secret in GitHub

### Container App Update Fails

**Issue:** Service principal doesn't have permission.

**Solution:**
Add Contributor role to the service principal:
```bash
az role assignment create \
  --assignee YOUR_SERVICE_PRINCIPAL_CLIENT_ID \
  --role Contributor \
  --scope /subscriptions/YOUR_SUBSCRIPTION_ID/resourceGroups/weaver-rg
```

### Build Succeeds but Deployment Doesn't Update

**Issue:** Container Apps may take time to pull new image.

**Solution:**
1. Wait 1-2 minutes after workflow completes
2. Check Container App revision in Azure Portal
3. Manually restart if needed:
```bash
az containerapp revision restart \
  --name weaver-backend \
  --resource-group weaver-rg \
  --revision REVISION_NAME
```

## Security Best Practices

1. **Never commit secrets** to the repository
2. **Rotate credentials** regularly (every 90 days)
3. **Use least privilege** - service principal should only have access to `weaver-rg`
4. **Enable branch protection** on `main` branch to require PR reviews
5. **Review workflow logs** regularly for suspicious activity

## Advanced Configuration

### Environment-Specific Deployments

To deploy to different environments (dev, staging, prod):

1. Create separate resource groups for each environment
2. Create separate service principals with scoped access
3. Add environment-specific secrets (e.g., `AZURE_CREDENTIALS_DEV`, `AZURE_CREDENTIALS_PROD`)
4. Modify workflows to use different secrets based on branch

### Deployment Approvals

Add manual approval gates for production deployments:

```yaml
# Add to workflow
environment:
  name: production
  url: https://weaver-backend.whitehill-eea76820.centralindia.azurecontainerapps.io
```

Then configure environment protection rules in GitHub Settings → Environments.

## Current Deployment Status

After completing this setup, your deployments will be:

| Service | URL | Container/App |
|---------|-----|---------------|
| Backend | https://weaver-backend.whitehill-eea76820.centralindia.azurecontainerapps.io | `weaver-backend` |
| ML Service | https://weaver-ml.whitehill-eea76820.centralindia.azurecontainerapps.io | `weaver-ml` |
| Frontend | https://salmon-meadow-04fa55300.1.azurestaticapps.net | `weaver-frontend` |

## Quick Reference Commands

```bash
# Get subscription ID
az account show --query id -o tsv

# Create service principal (run once)
az ad sp create-for-rbac --name "weaver-github-actions" \
  --role contributor \
  --scopes /subscriptions/SUBSCRIPTION_ID/resourceGroups/weaver-rg \
  --sdk-auth

# Get ACR credentials
az acr credential show --name weaveracr

# Get Static Web App token
az staticwebapp secrets list --name weaver-frontend \
  --resource-group weaver-rg --query "properties.apiKey" -o tsv

# Check Container App status
az containerapp show --name weaver-backend \
  --resource-group weaver-rg \
  --query "properties.latestRevisionName" -o tsv

# View workflow runs
# Go to: https://github.com/BarnabaBobbili/weaver-cloud/actions
```

## Next Steps

After CI/CD is set up:
1. ✅ Make a test commit to verify workflows work
2. ✅ Set up branch protection rules
3. ✅ Configure deployment notifications (Slack/Teams/Email)
4. ✅ Set up monitoring alerts for failed deployments
5. ✅ Document your team's deployment process

---

**Need Help?**
- GitHub Actions Docs: https://docs.github.com/en/actions
- Azure Container Apps: https://learn.microsoft.com/en-us/azure/container-apps/
- Azure Static Web Apps: https://learn.microsoft.com/en-us/azure/static-web-apps/
