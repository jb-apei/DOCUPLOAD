# Enable Microsoft Defender for Storage on the Azure Storage Account
# This enables automated malware scanning for uploaded blobs

$STORAGE_ACCOUNT = "strfpo5kn5bsg47vvac"
$RESOURCE_GROUP = "rg-rfpo-e108977f"

Write-Host "Enabling Microsoft Defender for Storage..." -ForegroundColor Cyan

# Enable Defender for Storage at the storage account level
# This requires Microsoft.Security provider to be registered
az provider register --namespace Microsoft.Security

# Wait for provider registration
Write-Host "Waiting for Microsoft.Security provider registration..."
Start-Sleep -Seconds 10

# Get subscription ID
$SUBSCRIPTION_ID = az account show --query id -o tsv

# Enable Defender for Storage with malware scanning
az security pricing create `
    --name StorageAccounts `
    --tier Standard `
    --subplan DefenderForStorageV2

Write-Host "Defender for Storage enabled at subscription level" -ForegroundColor Green

# Configure per-storage account settings for malware scanning
# Note: Malware scanning must be enabled via Azure Portal or ARM template
# as it's not fully supported via CLI yet

Write-Host "`nIMPORTANT: Complete the following steps in Azure Portal:" -ForegroundColor Yellow
Write-Host "1. Navigate to: https://portal.azure.com/#@/resource/subscriptions/$SUBSCRIPTION_ID/resourceGroups/$RESOURCE_GROUP/providers/Microsoft.Storage/storageAccounts/$STORAGE_ACCOUNT/overview"
Write-Host "2. Click 'Microsoft Defender for Cloud' in the left sidebar"
Write-Host "3. Under 'Malware Scanning', toggle it to 'Enabled'"
Write-Host "4. Set 'Capping (GB per month)' to appropriate limit (default 5000)"
Write-Host "5. Click 'Save'"

Write-Host "`nAlternatively, you can enable it via Azure Resource Manager template or REST API" -ForegroundColor Yellow
Write-Host "See: https://learn.microsoft.com/en-us/azure/defender-for-cloud/defender-for-storage-malware-scan"

# Create quarantine container if it doesn't exist
Write-Host "`nCreating quarantine container..." -ForegroundColor Cyan
az storage container create `
    --name quarantine `
    --account-name $STORAGE_ACCOUNT `
    --auth-mode login

Write-Host "`nSetup complete!" -ForegroundColor Green
Write-Host "After enabling malware scanning in the portal, uploads will be automatically scanned."
Write-Host "Scan results will appear in blob tags: 'Malware Scanning scan result'"
