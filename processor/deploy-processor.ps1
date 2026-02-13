#Requires -Version 5.1
<#
.SYNOPSIS
    Deploy USABC Processor Service to Azure Container Apps

.DESCRIPTION
    Builds and deploys the blob processor service as a container app

.PARAMETER Version
    Version tag for the container image (e.g., "v1.0.0")

.EXAMPLE
    .\deploy-processor.ps1 -Version "v1.0.0"
#>

param(
    [Parameter(Mandatory=$false)]
    [string]$Version = "latest"
)

$ErrorActionPreference = "Stop"

# Configuration
$RESOURCE_GROUP = "rg-rfpo-e108977f"
$LOCATION = "eastus"
$ACR_NAME = "acrrfpoe108977f"
$APP_NAME = "usabc-processor"
$CONTAINER_APP_ENV = "rfpo-env-5kn5bsg47vvac"
$IMAGE_NAME = "usabc-processor"

# Storage configuration
$STORAGE_ACCOUNT = "strfpo5kn5bsg47vvac"
$SOURCE_CONTAINER = "usabc-uploads-stage"
$PROCESSED_CONTAINER = "usabc-uploads-processed"

# Service Bus configuration
$SERVICE_BUS_NAMESPACE = "usabc-servicebus"
$QUEUE_NAME = "blob-upload-events"

Write-Host "=" -NoNewline -ForegroundColor Cyan
Write-Host ("=" * 79) -ForegroundColor Cyan
Write-Host "USABC Processor Deployment Script" -ForegroundColor Cyan
Write-Host "=" -NoNewline -ForegroundColor Cyan
Write-Host ("=" * 79) -ForegroundColor Cyan
Write-Host ""

Write-Host "Configuration:" -ForegroundColor Yellow
Write-Host "  Version: $Version" -ForegroundColor Gray
Write-Host "  Container App: $APP_NAME" -ForegroundColor Gray
Write-Host "  Image: $ACR_NAME.azurecr.io/${IMAGE_NAME}:${Version}" -ForegroundColor Gray
Write-Host ""

# Step 1: Verify Azure CLI login
Write-Host "[1/7] Verifying Azure CLI authentication..." -ForegroundColor Green
try {
    $account = az account show 2>&1 | ConvertFrom-Json
    Write-Host "  ✓ Logged in as: $($account.user.name)" -ForegroundColor Gray
    Write-Host "  ✓ Subscription: $($account.name)" -ForegroundColor Gray
} catch {
    Write-Host "  ✗ Not logged in to Azure CLI" -ForegroundColor Red
    Write-Host "  Run: az login" -ForegroundColor Yellow
    exit 1
}

# Step 2: Build Docker image
Write-Host ""
Write-Host "[2/7] Building Docker image..." -ForegroundColor Green
try {
    docker build -t "${IMAGE_NAME}:${Version}" -t "${IMAGE_NAME}:latest" .
    Write-Host "  ✓ Image built successfully" -ForegroundColor Gray
} catch {
    Write-Host "  ✗ Docker build failed" -ForegroundColor Red
    exit 1
}

# Step 3: Get ACR credentials
Write-Host ""
Write-Host "[3/7] Getting Azure Container Registry credentials..." -ForegroundColor Green
$ACR_PASSWORD = az acr credential show --name $ACR_NAME --query "passwords[0].value" -o tsv

if (-not $ACR_PASSWORD) {
    Write-Host "  ✗ Failed to get ACR credentials" -ForegroundColor Red
    exit 1
}
Write-Host "  ✓ ACR credentials retrieved" -ForegroundColor Gray

# Step 4: Login to ACR
Write-Host ""
Write-Host "[4/7] Logging in to Azure Container Registry..." -ForegroundColor Green
echo $ACR_PASSWORD | docker login "${ACR_NAME}.azurecr.io" -u $ACR_NAME --password-stdin
Write-Host "  ✓ Logged in to ACR" -ForegroundColor Gray

# Step 5: Tag and push image
Write-Host ""
Write-Host "[5/7] Pushing image to registry..." -ForegroundColor Green
docker tag "${IMAGE_NAME}:${Version}" "${ACR_NAME}.azurecr.io/${IMAGE_NAME}:${Version}"
docker tag "${IMAGE_NAME}:${Version}" "${ACR_NAME}.azurecr.io/${IMAGE_NAME}:latest"
docker push "${ACR_NAME}.azurecr.io/${IMAGE_NAME}:${Version}"
docker push "${ACR_NAME}.azurecr.io/${IMAGE_NAME}:latest"
Write-Host "  ✓ Image pushed successfully" -ForegroundColor Gray

# Step 6: Get configuration values
Write-Host ""
Write-Host "[6/7] Retrieving Azure resource configuration..." -ForegroundColor Green

# Get Service Bus connection string
$SERVICE_BUS_CONN = az servicebus namespace authorization-rule keys list `
    --namespace-name $SERVICE_BUS_NAMESPACE `
    --resource-group $RESOURCE_GROUP `
    --name RootManageSharedAccessKey `
    --query primaryConnectionString -o tsv

# Get Storage Account key
$STORAGE_KEY = az storage account keys list `
    --account-name $STORAGE_ACCOUNT `
    --resource-group $RESOURCE_GROUP `
    --query "[0].value" -o tsv

# Get Storage Account URL
$STORAGE_URL = "https://${STORAGE_ACCOUNT}.blob.core.windows.net"

Write-Host "  ✓ Configuration retrieved" -ForegroundColor Gray

# Step 7: Deploy or update Container App
Write-Host ""
Write-Host "[7/7] Deploying to Azure Container Apps..." -ForegroundColor Green

# Check if container app exists
$appExists = az containerapp show --name $APP_NAME --resource-group $RESOURCE_GROUP 2>$null

if ($appExists) {
    Write-Host "  Updating existing container app..." -ForegroundColor Yellow
    
    az containerapp update `
        --name $APP_NAME `
        --resource-group $RESOURCE_GROUP `
        --image "${ACR_NAME}.azurecr.io/${IMAGE_NAME}:${Version}" `
        --set-env-vars `
            "SERVICE_BUS_CONNECTION_STRING=secretref:service-bus-connection" `
            "SERVICE_BUS_QUEUE_NAME=$QUEUE_NAME" `
            "AZURE_STORAGE_ACCOUNT_NAME=$STORAGE_ACCOUNT" `
            "AZURE_STORAGE_ACCOUNT_URL=$STORAGE_URL" `
            "AZURE_STORAGE_ACCOUNT_KEY=secretref:storage-key" `
            "SOURCE_CONTAINER_NAME=$SOURCE_CONTAINER" `
            "PROCESSED_CONTAINER_NAME=$PROCESSED_CONTAINER" `
        --secrets `
            "service-bus-connection=$SERVICE_BUS_CONN" `
            "storage-key=$STORAGE_KEY"
            
    Write-Host "  ✓ Container app updated" -ForegroundColor Gray
} else {
    Write-Host "  Creating new container app..." -ForegroundColor Yellow
    
    az containerapp create `
        --name $APP_NAME `
        --resource-group $RESOURCE_GROUP `
        --environment $CONTAINER_APP_ENV `
        --image "${ACR_NAME}.azurecr.io/${IMAGE_NAME}:${Version}" `
        --registry-server "${ACR_NAME}.azurecr.io" `
        --registry-username $ACR_NAME `
        --registry-password $ACR_PASSWORD `
        --target-port 8080 `
        --ingress external `
        --min-replicas 1 `
        --max-replicas 5 `
        --cpu 0.5 `
        --memory 1Gi `
        --env-vars `
            "SERVICE_BUS_CONNECTION_STRING=secretref:service-bus-connection" `
            "SERVICE_BUS_QUEUE_NAME=$QUEUE_NAME" `
            "AZURE_STORAGE_ACCOUNT_NAME=$STORAGE_ACCOUNT" `
            "AZURE_STORAGE_ACCOUNT_URL=$STORAGE_URL" `
            "AZURE_STORAGE_ACCOUNT_KEY=secretref:storage-key" `
            "SOURCE_CONTAINER_NAME=$SOURCE_CONTAINER" `
            "PROCESSED_CONTAINER_NAME=$PROCESSED_CONTAINER" `
        --secrets `
            "service-bus-connection=$SERVICE_BUS_CONN" `
            "storage-key=$STORAGE_KEY"
            
    Write-Host "  ✓ Container app created" -ForegroundColor Gray
}

# Get the app URL
$APP_URL = az containerapp show `
    --name $APP_NAME `
    --resource-group $RESOURCE_GROUP `
    --query "properties.configuration.ingress.fqdn" -o tsv

Write-Host ""
Write-Host "=" -NoNewline -ForegroundColor Green
Write-Host ("=" * 79) -ForegroundColor Green
Write-Host "Deployment Complete!" -ForegroundColor Green
Write-Host "=" -NoNewline -ForegroundColor Green
Write-Host ("=" * 79) -ForegroundColor Green
Write-Host ""
Write-Host "Container App: $APP_NAME" -ForegroundColor Cyan
Write-Host "Version: $Version" -ForegroundColor Cyan
Write-Host "URL: https://$APP_URL" -ForegroundColor Cyan
Write-Host ""
Write-Host "Monitor logs with:" -ForegroundColor Yellow
Write-Host "  az containerapp logs show --name $APP_NAME --resource-group $RESOURCE_GROUP --follow" -ForegroundColor Gray
Write-Host ""
Write-Host "View in Azure Portal:" -ForegroundColor Yellow
$portalUrl = "https://portal.azure.com/#@/resource/subscriptions/e108977f-44ed-4400-9580-f7a0bc1d3630/resourceGroups/$RESOURCE_GROUP/providers/Microsoft.App/containerApps/$APP_NAME"
Write-Host "  $portalUrl" -ForegroundColor Gray
Write-Host ""
