param(
    [string]$Version = "latest"
)

$ErrorActionPreference = "Stop"

$RESOURCE_GROUP = "rg-rfpo-e108977f"
$ACR_NAME = "acrrfpoe108977f"
$APP_NAME = "usabc-processor"
$CONTAINER_APP_ENV = "rfpo-env-5kn5bsg47vvac"
$IMAGE_NAME = "usabc-processor"
$STORAGE_ACCOUNT = "strfpo5kn5bsg47vvac"
$SOURCE_CONTAINER = "usabc-uploads-stage"
$PROCESSED_CONTAINER = "usabc-uploads-processed"
$SERVICE_BUS_NAMESPACE = "usabc-servicebus"
$QUEUE_NAME = "blob-upload-events"

Write-Host "Building Docker image..." -ForegroundColor Green
docker build -t "${IMAGE_NAME}:${Version}" .

Write-Host "Getting ACR credentials..." -ForegroundColor Green
$ACR_PASSWORD = az acr credential show --name $ACR_NAME --query "passwords[0].value" -o tsv

Write-Host "Logging in to ACR..." -ForegroundColor Green
echo $ACR_PASSWORD | docker login "${ACR_NAME}.azurecr.io" -u $ACR_NAME --password-stdin

Write-Host "Tagging and pushing image..." -ForegroundColor Green
docker tag "${IMAGE_NAME}:${Version}" "${ACR_NAME}.azurecr.io/${IMAGE_NAME}:${Version}"
docker push "${ACR_NAME}.azurecr.io/${IMAGE_NAME}:${Version}"

Write-Host "Getting configuration..." -ForegroundColor Green
$SERVICE_BUS_CONN = az servicebus namespace authorization-rule keys list --namespace-name $SERVICE_BUS_NAMESPACE --resource-group $RESOURCE_GROUP --name RootManageSharedAccessKey --query primaryConnectionString -o tsv
$STORAGE_KEY = az storage account keys list --account-name $STORAGE_ACCOUNT --resource-group $RESOURCE_GROUP --query "[0].value" -o tsv
$STORAGE_URL = "https://${STORAGE_ACCOUNT}.blob.core.windows.net"

Write-Host "Checking if app exists..." -ForegroundColor Green
$appExists = az containerapp show --name $APP_NAME --resource-group $RESOURCE_GROUP 2>$null

if ($appExists) {
    Write-Host "Updating existing container app..." -ForegroundColor Yellow
    az containerapp update --name $APP_NAME --resource-group $RESOURCE_GROUP --image "${ACR_NAME}.azurecr.io/${IMAGE_NAME}:${Version}"
    az containerapp secret set --name $APP_NAME --resource-group $RESOURCE_GROUP --secrets "service-bus-connection=$SERVICE_BUS_CONN" "storage-key=$STORAGE_KEY"
    az containerapp update --name $APP_NAME --resource-group $RESOURCE_GROUP --set-env-vars "SERVICE_BUS_CONNECTION_STRING=secretref:service-bus-connection" "SERVICE_BUS_QUEUE_NAME=$QUEUE_NAME" "AZURE_STORAGE_ACCOUNT_NAME=$STORAGE_ACCOUNT" "AZURE_STORAGE_ACCOUNT_URL=$STORAGE_URL" "AZURE_STORAGE_ACCOUNT_KEY=secretref:storage-key" "SOURCE_CONTAINER_NAME=$SOURCE_CONTAINER" "PROCESSED_CONTAINER_NAME=$PROCESSED_CONTAINER"
    Write-Host "Container app updated successfully!" -ForegroundColor Green
} else {
    Write-Host "Creating new container app..." -ForegroundColor Yellow
    az containerapp create --name $APP_NAME --resource-group $RESOURCE_GROUP --environment $CONTAINER_APP_ENV --image "${ACR_NAME}.azurecr.io/${IMAGE_NAME}:${Version}" --registry-server "${ACR_NAME}.azurecr.io" --registry-username $ACR_NAME --registry-password $ACR_PASSWORD --ingress internal --min-replicas 1 --max-replicas 3 --cpu 0.5 --memory 1.0Gi --env-vars "SERVICE_BUS_CONNECTION_STRING=secretref:service-bus-connection" "SERVICE_BUS_QUEUE_NAME=$QUEUE_NAME" "AZURE_STORAGE_ACCOUNT_NAME=$STORAGE_ACCOUNT" "AZURE_STORAGE_ACCOUNT_URL=$STORAGE_URL" "AZURE_STORAGE_ACCOUNT_KEY=secretref:storage-key" "SOURCE_CONTAINER_NAME=$SOURCE_CONTAINER" "PROCESSED_CONTAINER_NAME=$PROCESSED_CONTAINER" --secrets "service-bus-connection=$SERVICE_BUS_CONN" "storage-key=$STORAGE_KEY"
    Write-Host "Container app created successfully!" -ForegroundColor Green
}

Write-Host ""
Write-Host "Deployment Complete!" -ForegroundColor Green
Write-Host "Monitor logs: az containerapp logs show --name $APP_NAME --resource-group $RESOURCE_GROUP --follow" -ForegroundColor Cyan
