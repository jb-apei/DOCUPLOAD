# Admin Request - USABC Document Upload Service

**To:** Azure Administrator  
**From:** John Bouchard (johnbouchard@icloud.com)  
**Date:** February 13, 2026  
**Subject:** Action Required - Elevated Permissions for Production Security Configuration  

---

## Summary

The USABC Document Upload Service requires the following administrative actions to complete production security configuration. Total estimated time: **40 minutes**.

**Subscription:** `e108977f-44ed-4400-9580-f7a0bc1d3630`  
**Resource Group:** `rg-rfpo-e108977f`  
**Container App:** `usabc-upload`  
**Storage Account:** `strfpo5kn5bsg47vvac`  

---

## Request 1: Grant Storage Role to Managed Identity & Remove Storage Key

**Priority:** HIGH  
**Time:** 10 minutes  
**Reason:** Enable keyless authentication

### Commands:

```powershell
# Step 1: Assign Storage Blob Data Contributor role
az role assignment create \
  --assignee 6e6b4d47-c050-495e-8842-26d035424764 \
  --role "Storage Blob Data Contributor" \
  --scope "/subscriptions/e108977f-44ed-4400-9580-f7a0bc1d3630/resourceGroups/rg-rfpo-e108977f/providers/Microsoft.Storage/storageAccounts/strfpo5kn5bsg47vvac"

# Step 2: Verify role assignment succeeded
az role assignment list \
  --assignee 6e6b4d47-c050-495e-8842-26d035424764 \
  --query "[].{Role:roleDefinitionName,Scope:scope}" -o table

# Step 3: Remove storage key (ONLY after Step 2 confirms success)
az containerapp update \
  --name usabc-upload \
  --resource-group rg-rfpo-e108977f \
  --remove-env-vars AZURE_STORAGE_ACCOUNT_KEY
```

**Required Permission:** `Microsoft.Authorization/roleAssignments/write`

---

## Request 2: Enable Malware Scanning on Storage Account

**Priority:** HIGH  
**Time:** 10 minutes  
**Reason:** Activate automated malware detection

### Command:

```powershell
az rest --method PUT \
  --url "https://management.azure.com/subscriptions/e108977f-44ed-4400-9580-f7a0bc1d3630/resourceGroups/rg-rfpo-e108977f/providers/Microsoft.Storage/storageAccounts/strfpo5kn5bsg47vvac/providers/Microsoft.Security/defenderForStorageSettings/current?api-version=2022-12-01-preview" \
  --body '{
    "properties": {
      "isEnabled": true,
      "malwareScanning": {
        "onUpload": {
          "isEnabled": true,
          "capGBPerMonth": 5000
        }
      },
      "sensitiveDataDiscovery": {
        "isEnabled": false
      },
      "overrideSubscriptionLevelSettings": true
    }
  }'
```

**Required Permission:** `Microsoft.Authorization/roleAssignments/write`  
**Note:** Defender for Storage is already enabled (Standard tier, DefenderForStorageV2)

---

## Request 3: Register Microsoft.Insights Provider & Create Alerts

**Priority:** HIGH  
**Time:** 20 minutes  
**Reason:** Enable monitoring and alerting

### Commands:

```powershell
# Check provider registration
az provider show --namespace Microsoft.Insights --query "registrationState"

# Register if needed
az provider register --namespace Microsoft.Insights

# Create container health alert
az monitor metrics alert create \
  --name usabc-upload-down \
  --resource-group rg-rfpo-e108977f \
  --scopes "/subscriptions/e108977f-44ed-4400-9580-f7a0bc1d3630/resourceGroups/rg-rfpo-e108977f/providers/Microsoft.App/containerapps/usabc-upload" \
  --condition "count Replicas < 1" \
  --window-size 5m \
  --evaluation-frequency 1m \
  --action usabc-upload-alerts \
  --description "Container app has no running replicas"

# Create error rate alert
az monitor metrics alert create \
  --name usabc-upload-errors \
  --resource-group rg-rfpo-e108977f \
  --scopes "/subscriptions/e108977f-44ed-4400-9580-f7a0bc1d3630/resourceGroups/rg-rfpo-e108977f/providers/Microsoft.App/containerapps/usabc-upload" \
  --condition "total Requests count > 10 where ResultType includes '5'" \
  --window-size 15m \
  --evaluation-frequency 5m \
  --action usabc-upload-alerts \
  --description "High rate of server errors (5xx)"

# Create storage capacity alert
az monitor metrics alert create \
  --name usabc-storage-capacity \
  --resource-group rg-rfpo-e108977f \
  --scopes "/subscriptions/e108977f-44ed-4400-9580-f7a0bc1d3630/resourceGroups/rg-rfpo-e108977f/providers/Microsoft.Storage/storageAccounts/strfpo5kn5bsg47vvac" \
  --condition "total UsedCapacity > 80000000000" \
  --window-size 1h \
  --evaluation-frequency 15m \
  --action usabc-upload-alerts \
  --description "Storage usage exceeds 80GB"
```

**Required Permission:** Contributor role or higher  
**Note:** Action group `usabc-upload-alerts` already created

---

## Resources Summary

| Resource Type | Name | Location | Purpose |
|---------------|------|----------|---------|
| Container App | usabc-upload | East US | Application runtime |
| Storage Account | strfpo5kn5bsg47vvac | East US | File storage |
| Managed Identity | 6e6b4d47-c050-495e-8842-26d035424764 | System-assigned | Authentication |
| Action Group | usabc-upload-alerts | East US | Alert notifications |

---

## Verification

After completion, please verify:

1. **Managed Identity:** Upload test file at https://usabc-upload.livelyforest-d06a98a0.eastus.azurecontainerapps.io/ - should work without storage key
2. **Malware Scanning:** Check blob tags after upload for `Malware Scanning scan result`
3. **Alerts:** Confirm alerts are listed in Azure Portal under resource group monitoring

---

## Questions?

Please contact John Bouchard at johnbouchard@icloud.com if any issues arise.

**Service Status Page:** https://usabc-upload.livelyforest-d06a98a0.eastus.azurecontainerapps.io/health
