# Weaver Frontend - Azure Static Web Apps Deployment
# Builds and deploys in Azure cloud - no local build needed

$ErrorActionPreference = "Continue"
$AZ = "C:\Program Files\Microsoft SDKs\Azure\CLI2\wbin\az.cmd"

$RESOURCE_GROUP = "weaver-rg"
$LOCATION = "eastasia"  # Static Web Apps has limited regions
$SWA_NAME = "weaver-frontend"
$BACKEND_URL = "https://weaver-backend-app.azurewebsites.net"

Write-Host "========================================" -ForegroundColor Green
Write-Host "Weaver Frontend - Static Web App" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green

# Get paths
$scriptDir = if ($PSScriptRoot) { $PSScriptRoot } else { Split-Path -Parent $MyInvocation.MyCommand.Path }
if (-not $scriptDir) { $scriptDir = "E:\MTech\MTech Sem2\Cloud\Project\Weaver\infra" }
$parentPath = Split-Path -Parent $scriptDir
$frontendPath = "$parentPath\frontend"

Write-Host "Frontend path: $frontendPath" -ForegroundColor Cyan

# Check if Static Web App exists
$swaExists = & $AZ staticwebapp show --name $SWA_NAME --resource-group $RESOURCE_GROUP 2>$null

if (-not $swaExists) {
    Write-Host "Creating Static Web App..." -ForegroundColor Yellow
    & $AZ staticwebapp create --name $SWA_NAME --resource-group $RESOURCE_GROUP --location $LOCATION --sku Free
} else {
    Write-Host "Static Web App exists" -ForegroundColor Green
}

# Set environment variable for the API URL
Write-Host "Configuring API URL..." -ForegroundColor Yellow
& $AZ staticwebapp appsettings set --name $SWA_NAME --resource-group $RESOURCE_GROUP --setting-names "VITE_API_URL=$BACKEND_URL"

# Get deployment token
Write-Host "Getting deployment token..." -ForegroundColor Yellow
$DEPLOYMENT_TOKEN = & $AZ staticwebapp secrets list --name $SWA_NAME --resource-group $RESOURCE_GROUP --query "properties.apiKey" -o tsv

# Create zip of frontend source
Write-Host "Creating deployment package..." -ForegroundColor Yellow
$zipPath = "$env:TEMP\frontend-deploy.zip"
if (Test-Path $zipPath) { Remove-Item $zipPath -Force }

Set-Location $frontendPath
Compress-Archive -Path "src", "public", "package.json", "package-lock.json", "index.html", "vite.config.ts", "tsconfig.json", "tsconfig.app.json", "tsconfig.node.json" -DestinationPath $zipPath -Force

# Deploy using SWA CLI (builds in Azure)
Write-Host "Deploying to Azure Static Web Apps (builds in cloud)..." -ForegroundColor Yellow

# Install SWA CLI if not installed
$swaPath = npm root -g
$swaInstalled = Test-Path "$swaPath\@azure\static-web-apps-cli"
if (-not $swaInstalled) {
    Write-Host "Installing SWA CLI globally..." -ForegroundColor Yellow
    npm install -g @azure/static-web-apps-cli
}

# Deploy with corrected arguments
npx swa deploy --deployment-token $DEPLOYMENT_TOKEN --app-location $frontendPath --output-location "dist" --env production

# Cleanup
Remove-Item $zipPath -Force 2>$null

# Get the URL
$FRONTEND_URL = & $AZ staticwebapp show --name $SWA_NAME --resource-group $RESOURCE_GROUP --query "defaultHostname" -o tsv

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "Frontend Deployed Successfully!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Frontend URL: https://$FRONTEND_URL" -ForegroundColor Cyan
Write-Host "Backend URL: $BACKEND_URL" -ForegroundColor Cyan
Write-Host ""

Set-Location $scriptDir
