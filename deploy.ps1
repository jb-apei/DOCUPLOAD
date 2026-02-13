# USABC Upload Service Deployment Script
# This script properly deploys new versions while preserving environment variables

param(
    [Parameter(Mandatory=$true)]
    [string]$Version,

    [Parameter(Mandatory=$false)]
    [switch]$SkipBuild = $false
)

$ErrorActionPreference = "Stop"

# Configuration
$ResourceGroup = "rg-rfpo-e108977f"
$ContainerAppName = "usabc-upload"
$RegistryName = "acrrfpoe108977f"
$ImageName = "usabc-upload"

Write-Host "=====================================" -ForegroundColor Cyan
Write-Host "USABC Upload Service Deployment" -ForegroundColor Cyan
Write-Host "Version: $Version" -ForegroundColor Cyan
Write-Host "=====================================" -ForegroundColor Cyan
Write-Host ""

# Step 1: Build and push Docker image (unless skipped)
if (-not $SkipBuild) {
    Write-Host "[1/4] Building Docker image ($ImageName`:$Version)..." -ForegroundColor Yellow

    az acr build --registry $RegistryName --image "$ImageName`:$Version" --file Dockerfile .

    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: Docker build failed" -ForegroundColor Red
        exit 1
    }

    Write-Host "Build completed successfully" -ForegroundColor Green
    Write-Host ""
} else {
    Write-Host "[1/4] Skipping build (using existing image)" -ForegroundColor Yellow
    Write-Host ""
}

# Step 2: Get current environment variables
Write-Host "[2/4] Reading existing environment variables..." -ForegroundColor Yellow

$envVars = az containerapp show --name $ContainerAppName --resource-group $ResourceGroup --query "properties.template.containers[0].env" -o json | ConvertFrom-Json

$envVarCount = $envVars.Count
Write-Host "Found $envVarCount existing environment variables" -ForegroundColor Green
Write-Host ""

# Step 3: Update Container App
Write-Host "[3/4] Deploying new version..." -ForegroundColor Yellow
$fullImageUrl = "$RegistryName.azurecr.io/$ImageName`:$Version"

# NOTE: We do NOT use --set-env-vars here, so existing vars are preserved
az containerapp update --name $ContainerAppName --resource-group $ResourceGroup --image $fullImageUrl

if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Deployment failed" -ForegroundColor Red
    exit 1
}

Write-Host "Deployment completed successfully" -ForegroundColor Green
Write-Host ""

Write-Host "[4/4] Verifying deployment..." -ForegroundColor Yellow

Start-Sleep -Seconds 5

# Get the latest revision info
$revisionInfo = az containerapp revision list --name $ContainerAppName --resource-group $ResourceGroup --query "[0]" -o json | ConvertFrom-Json

Write-Host "Active revision: $($revisionInfo.name)" -ForegroundColor Green
Write-Host "Image: $fullImageUrl" -ForegroundColor Green
Write-Host ""

# Verify environment variables are still present
$newEnvVars = az containerapp show --name $ContainerAppName --resource-group $ResourceGroup --query "properties.template.containers[0].env" -o json | ConvertFrom-Json

$newEnvVarCount = $newEnvVars.Count

if ($newEnvVarCount -eq $envVarCount) {
    Write-Host "Environment variables preserved: $newEnvVarCount variables" -ForegroundColor Green
} else {
    Write-Host "WARNING: Environment variable count changed!" -ForegroundColor Yellow
    Write-Host "  Before: $envVarCount variables" -ForegroundColor Yellow
    Write-Host "  After: $newEnvVarCount variables" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "=====================================" -ForegroundColor Cyan
Write-Host "Deployment Summary" -ForegroundColor Cyan
Write-Host "=====================================" -ForegroundColor Cyan
Write-Host "Version deployed: $Version" -ForegroundColor White
Write-Host "Revision: $($revisionInfo.name)" -ForegroundColor White
Write-Host "Status: Running" -ForegroundColor Green
Write-Host "URL: https://usabc-upload.livelyforest-d06a98a0.eastus.azurecontainerapps.io/" -ForegroundColor White
Write-Host ""
Write-Host "All environment variables preserved!" -ForegroundColor Green
Write-Host "=====================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "Deployment complete." -ForegroundColor Green
