#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Submit ML training job to Azure ML workspace.

.DESCRIPTION
    Uploads training scripts and submits a training job for the
    DistilBERT sensitivity classifier to Azure ML.

.PARAMETER WorkspaceName
    Azure ML workspace name.

.PARAMETER ResourceGroup
    Azure resource group name.

.PARAMETER ComputeCluster
    Compute cluster name for training.
#>

param(
    [string]$WorkspaceName = "weaver-ml-workspace",
    [string]$ResourceGroup = "weaver-rg",
    [string]$ComputeCluster = "weaver-cpu-cluster"
)

$ErrorActionPreference = "Stop"

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "   AZURE ML TRAINING JOB SUBMISSION" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# Check Azure CLI and ML extension
Write-Host "`n[1/5] Checking prerequisites..." -ForegroundColor Green
$mlExtension = az extension list --query "[?name=='ml'].name" -o tsv
if (-not $mlExtension) {
    Write-Host "Installing Azure ML extension..." -ForegroundColor Yellow
    az extension add --name ml --upgrade
}
Write-Host "✓ Azure ML extension ready" -ForegroundColor White

# Verify workspace exists
Write-Host "`n[2/5] Verifying ML workspace..." -ForegroundColor Green
$workspace = az ml workspace show `
    --name $WorkspaceName `
    --resource-group $ResourceGroup `
    --query "name" -o tsv 2>$null

if (-not $workspace) {
    Write-Host "Error: Workspace '$WorkspaceName' not found!" -ForegroundColor Red
    exit 1
}
Write-Host "✓ Workspace verified: $WorkspaceName" -ForegroundColor White

# Upload training code
Write-Host "`n[3/5] Preparing training code..." -ForegroundColor Green

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$mlTrainingDir = Join-Path $scriptDir ".." "ml_training"
$srcDir = Join-Path $mlTrainingDir "src"

# Create src directory and copy files
if (-not (Test-Path $srcDir)) {
    New-Item -ItemType Directory -Path $srcDir -Force | Out-Null
}

# Copy training scripts to src
Copy-Item (Join-Path $mlTrainingDir "train_bert_classifier.py") $srcDir -Force
Copy-Item (Join-Path $mlTrainingDir "xai_explainer.py") $srcDir -Force

Write-Host "✓ Training code prepared" -ForegroundColor White

# Create job YAML
Write-Host "`n[4/5] Creating job configuration..." -ForegroundColor Green

$jobYaml = @"
`$schema: https://azuremlschemas.azureedge.net/latest/commandJob.schema.json
type: command
display_name: weaver_bert_training_$(Get-Date -Format 'yyyyMMdd_HHmmss')
experiment_name: weaver-sensitivity-classification
description: Train DistilBERT model for sensitivity classification

compute: azureml:$ComputeCluster

environment:
  image: mcr.microsoft.com/azureml/openmpi4.1.0-ubuntu20.04
  conda_file:
    name: weaver-training-env
    channels:
      - pytorch
      - conda-forge
    dependencies:
      - python=3.11
      - pip
      - pip:
        - torch>=2.0.0
        - transformers>=4.35.0
        - scikit-learn>=1.3.0
        - pandas>=2.0.0
        - numpy>=1.24.0
        - mlflow>=2.9.0
        - azureml-mlflow>=1.53.0

code: $srcDir

command: >-
  python train_bert_classifier.py
  --output-dir outputs
  --batch-size 16
  --learning-rate 2e-5
  --num-epochs 5
  --samples-per-class 500

resources:
  instance_count: 1
"@

$jobYamlPath = Join-Path $mlTrainingDir "training_job.yml"
$jobYaml | Out-File -FilePath $jobYamlPath -Encoding utf8

Write-Host "✓ Job configuration created" -ForegroundColor White

# Submit job
Write-Host "`n[5/5] Submitting training job..." -ForegroundColor Green
Write-Host "Note: This may take 15-30 minutes to complete" -ForegroundColor Yellow

$jobResult = az ml job create `
    --file $jobYamlPath `
    --workspace-name $WorkspaceName `
    --resource-group $ResourceGroup `
    --query "{name:name,status:status,studioUrl:services.Studio.endpoint}" `
    -o json | ConvertFrom-Json

if ($jobResult) {
    Write-Host "`n========================================" -ForegroundColor Green
    Write-Host "   TRAINING JOB SUBMITTED!" -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Green
    
    Write-Host "`nJob Details:" -ForegroundColor Cyan
    Write-Host "  Name: $($jobResult.name)" -ForegroundColor White
    Write-Host "  Status: $($jobResult.status)" -ForegroundColor White
    Write-Host "`nAzure ML Studio URL:" -ForegroundColor Yellow
    Write-Host "  $($jobResult.studioUrl)" -ForegroundColor White
    
    Write-Host "`nTo monitor the job:" -ForegroundColor Cyan
    Write-Host "  az ml job show --name $($jobResult.name) -w $WorkspaceName -g $ResourceGroup" -ForegroundColor White
    
    Write-Host "`nTo stream logs:" -ForegroundColor Cyan
    Write-Host "  az ml job stream --name $($jobResult.name) -w $WorkspaceName -g $ResourceGroup" -ForegroundColor White
    
} else {
    Write-Host "Error: Failed to submit training job" -ForegroundColor Red
    exit 1
}

# Clean up temp files
Remove-Item $jobYamlPath -Force -ErrorAction SilentlyContinue

Write-Host "`n✅ Done!" -ForegroundColor Green
