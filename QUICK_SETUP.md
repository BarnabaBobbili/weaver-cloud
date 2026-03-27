# Quick Setup Commands for Weaver CI/CD

**YOUR AZURE SUBSCRIPTION ID:** `7e28e79f-6729-47d7-accc-38b7c1cefdf1`

## Step-by-Step Setup

### 1️⃣ Create Azure Service Principal

Run this command in your terminal:

```bash
az ad sp create-for-rbac \
  --name "weaver-github-actions" \
  --role contributor \
  --scopes /subscriptions/7e28e79f-6729-47d7-accc-38b7c1cefdf1/resourceGroups/weaver-rg \
  --sdk-auth
```

**📋 Copy the ENTIRE JSON output** - you'll need it for GitHub Secrets.

It will look like this:
```json
{
  "clientId": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "clientSecret": "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
  "subscriptionId": "7e28e79f-6729-47d7-accc-38b7c1cefdf1",
  "tenantId": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  ...
}
```

---

### 2️⃣ Get Azure Container Registry Credentials

**Already retrieved for you:**

- **ACR_USERNAME:** `weaveracr`
- **ACR_PASSWORD:** `1e1SDwOUXuM3bByFVTpMMVrEUA3yB1I0jFcBYylibqFPRnCa74s0JQQJ99CCACGhslBEqg7NAAACAZCRoPOY`

---

### 3️⃣ Get Static Web App Deployment Token

Run this command to get the full token:

```bash
az staticwebapp secrets list \
  --name weaver-frontend \
  --resource-group weaver-rg \
  --query "properties.apiKey" -o tsv
```

**📋 Copy the output** - you'll need it for GitHub Secrets.

---

### 4️⃣ Add Secrets to GitHub

Go to: **https://github.com/BarnabaBobbili/weaver-cloud/settings/secrets/actions**

Click **"New repository secret"** for each of these:

#### Secret 1: AZURE_CREDENTIALS
- **Name:** `AZURE_CREDENTIALS`
- **Value:** Paste the ENTIRE JSON from Step 1 (including `{` and `}`)

#### Secret 2: ACR_USERNAME
- **Name:** `ACR_USERNAME`
- **Value:** `weaveracr`

#### Secret 3: ACR_PASSWORD
- **Name:** `ACR_PASSWORD`
- **Value:** `1e1SDwOUXuM3bByFVTpMMVrEUA3yB1I0jFcBYylibqFPRnCa74s0JQQJ99CCACGhslBEqg7NAAACAZCRoPOY`

#### Secret 4: AZURE_STATIC_WEB_APPS_API_TOKEN
- **Name:** `AZURE_STATIC_WEB_APPS_API_TOKEN`
- **Value:** Paste the token from Step 3

---

### 5️⃣ Test the CI/CD Pipeline

Once secrets are added, test the deployment:

#### Option A: Trigger Manually
1. Go to **https://github.com/BarnabaBobbili/weaver-cloud/actions**
2. Click on **"Deploy Backend to Azure Container Apps"**
3. Click **"Run workflow"** → Select `main` → Click **"Run workflow"**

#### Option B: Make a Test Commit
```bash
cd "E:\MTech\MTech Sem2\Cloud\Project\Weaver"

# Make a small change
echo "# CI/CD test" >> backend/README.md

# Commit and push
git add backend/README.md
git commit -m "test: verify CI/CD pipeline"
git push origin main
```

Then go to **https://github.com/BarnabaBobbili/weaver-cloud/actions** to watch it deploy!

---

## ✅ Verification Checklist

After setup, verify:

- [ ] All 4 secrets are added in GitHub
- [ ] Service principal was created successfully
- [ ] You can manually trigger workflows
- [ ] Test deployment completes successfully
- [ ] Backend health check passes: https://weaver-backend.whitehill-eea76820.centralindia.azurecontainerapps.io/health
- [ ] Frontend loads: https://salmon-meadow-04fa55300.1.azurestaticapps.net
- [ ] ML Service health check passes: https://weaver-ml.whitehill-eea76820.centralindia.azurecontainerapps.io/health

---

## 🔧 Troubleshooting

### "Login failed" Error
- Make sure `AZURE_CREDENTIALS` contains the **complete JSON** from Step 1
- No extra spaces or formatting

### "Unauthorized" ACR Error
- Verify `ACR_USERNAME` is exactly: `weaveracr`
- Verify `ACR_PASSWORD` is the full string (no spaces)

### Workflow Doesn't Trigger
- Make sure you pushed changes to the `main` branch
- Check that files changed are in `backend/**`, `frontend/**`, or `ml-service/**`

### Need Help?
Check the full guide: `CICD_SETUP_GUIDE.md`

---

## 📊 What Happens When You Push Code?

### Changes in `backend/**`
→ Builds Docker image → Pushes to ACR → Deploys to Container Apps → Runs health check

### Changes in `frontend/**`
→ Installs dependencies → Builds React app → Deploys to Static Web Apps → Updates CORS

### Changes in `ml-service/**`
→ Builds Docker image → Pushes to ACR → Deploys to Container Apps → Updates backend endpoint

---

## 🚀 You're All Set!

Once secrets are configured, every push to `main` will automatically deploy to Azure.

**Repository:** https://github.com/BarnabaBobbili/weaver-cloud
**Actions:** https://github.com/BarnabaBobbili/weaver-cloud/actions
