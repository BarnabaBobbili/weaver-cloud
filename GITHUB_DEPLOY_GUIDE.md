# GitHub Actions Cloud Deployment Setup

## What You Have
- ACR_USERNAME: weaveracr
- ACR_PASSWORD: 1e1SDwOUXuM3bByFVTpMMVrEUA3yB1I0jFcBYylibqFPRnCa74s0JQQJ99CCACGhslBEqg7NAAACAZCRoPOY
- AZURE_SUBSCRIPTION_ID: 7e28e79f-6729-47d7-accc-38b7c1cefdf1

## Steps to Deploy

### 1. Push Code to GitHub
```powershell
cd E:\MTech\MTech Sem2\Cloud\Project\Weaver
git init
git add .
git commit -m "Initial deployment"
git remote add origin https://github.com/YOUR_USERNAME/Weaver.git
git push -u origin main
```

### 2. Add GitHub Secrets
Go to: `https://github.com/YOUR_USERNAME/Weaver/settings/secrets/actions`

Click "New repository secret" and add:

**Secret 1:**
- Name: `ACR_USERNAME`
- Value: `weaveracr`

**Secret 2:**
- Name: `ACR_PASSWORD`
- Value: `1e1SDwOUXuM3bByFVTpMMVrEUA3yB1I0jFcBYylibqFPRnCa74s0JQQJ99CCACGhslBEqg7NAAACAZCRoPOY`

**Secret 3:**
- Name: `AZURE_SUBSCRIPTION_ID`
- Value: `7e28e79f-6729-47d7-accc-38b7c1cefdf1`

### 3. Trigger Deployment
- Go to Actions tab in GitHub
- Click "Deploy Backend to Azure Container Apps"
- Click "Run workflow"

GitHub will build Docker image in the cloud and push to your ACR, then deploy to Container Apps.

### 4. Deploy Frontend (After Backend Works)
Run: `.\deploy-frontend.ps1`

## Result
- Backend: Container Apps with auto-scaling
- Frontend: Static Web App
- 100% Cloud-based (no local Docker needed)
