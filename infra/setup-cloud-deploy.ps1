# Complete Cloud Deployment Setup - No Local Builds
# All builds happen in GitHub Actions (cloud), deploy to Azure

$AZ = "C:\Program Files\Microsoft SDKs\Azure\CLI2\wbin\az.cmd"
$RESOURCE_GROUP = "weaver-rg"

Write-Host "========================================" -ForegroundColor Green
Write-Host "Cloud Deployment Setup" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green

# Step 1: Create Service Principal for GitHub Actions
Write-Host "`n[Step 1] Creating Service Principal for GitHub Actions..." -ForegroundColor Yellow
$subscriptionId = & $AZ account show --query id -o tsv
$spOutput = & $AZ ad sp create-for-rbac --name "weaver-github-actions" --role contributor --scopes "/subscriptions/$subscriptionId/resourceGroups/$RESOURCE_GROUP" --sdk-auth 2>&1

Write-Host "`nCopy this JSON and add as GitHub secret 'AZURE_CREDENTIALS':" -ForegroundColor Cyan
Write-Host "========================================"
$spOutput
Write-Host "========================================"

# Step 2: Get ACR credentials
Write-Host "`n[Step 2] Getting Container Registry credentials..." -ForegroundColor Yellow
$acrCreds = & $AZ acr credential show --name weaveracr --query "{username:username, password:passwords[0].value}" -o json | ConvertFrom-Json

Write-Host "`nAdd these as GitHub secrets:" -ForegroundColor Cyan
Write-Host "ACR_USERNAME: $($acrCreds.username)"
Write-Host "ACR_PASSWORD: $($acrCreds.password)"

# Step 3: Get Static Web Apps deployment token
Write-Host "`n[Step 3] Getting Static Web App deployment token..." -ForegroundColor Yellow
$swaToken = & $AZ staticwebapp secrets list --name weaver-frontend --resource-group $RESOURCE_GROUP --query "properties.apiKey" -o tsv 2>&1

if ($swaToken -notlike "*ERROR*") {
    Write-Host "`nAdd this as GitHub secret 'SWA_DEPLOYMENT_TOKEN':" -ForegroundColor Cyan
    Write-Host $swaToken
} else {
    Write-Host "Static Web App not found - will be created by GitHub Actions" -ForegroundColor Yellow
}

# Step 4: Instructions
Write-Host "`n========================================" -ForegroundColor Green
Write-Host "Next Steps - Setup GitHub Actions" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "1. Push your code to GitHub:" -ForegroundColor Yellow
Write-Host "   cd E:\MTech\MTech Sem2\Cloud\Project\Weaver"
Write-Host "   git init"
Write-Host "   git add ."
Write-Host '   git commit -m "Initial commit"'
Write-Host "   git remote add origin https://github.com/YOUR_USERNAME/Weaver.git"
Write-Host "   git push -u origin main"
Write-Host ""
Write-Host "2. Add GitHub Secrets (Settings > Secrets and variables > Actions):" -ForegroundColor Yellow
Write-Host "   - AZURE_CREDENTIALS (JSON from Step 1 above)"
Write-Host "   - ACR_USERNAME (from Step 2 above)"
Write-Host "   - ACR_PASSWORD (from Step 2 above)"
Write-Host ""
Write-Host "3. Trigger deployment:" -ForegroundColor Yellow
Write-Host "   - Push to main branch, or"
Write-Host "   - Go to Actions tab > Deploy Backend > Run workflow"
Write-Host ""
Write-Host "GitHub Actions will build in the cloud and deploy to Azure" -ForegroundColor Green
Write-Host ""
