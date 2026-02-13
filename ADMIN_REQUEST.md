# Azure Infrastructure Configuration Request
**Service:** USABC Document Upload Service  
**Date:** February 12, 2026  
**Updated:** February 13, 2026 - Completed preliminary configurations via Azure CLI  
**Requestor:** John Bouchard  
**Subscription:** e108977f-44ed-4400-9580-f7a0bc1d3630  
**Resource Group:** rg-rfpo-e108977f  

---

> **📋 UPDATE (Feb 13, 2026):** Several configurations have been completed successfully using Azure CLI. This document now focuses on **ONLY** the items that require elevated admin permissions or external DNS access. Total admin time required: ~35 minutes for critical items.  

---

## Executive Summary

This document outlines **remaining** Azure infrastructure configurations for the USABC Document Upload Service that require administrative/elevated permissions. Several configurations have already been completed successfully.

**Current Status:** ✅ Service deployed and functional at https://usabc-upload.livelyforest-d06a98a0.eastus.azurecontainerapps.io/  
**Goal:** Complete managed identity role assignment, enable malware scanning, configure custom domain, and monitoring alerts

---

## ✅ Completed Configurations (No Admin Action Needed)

The following items have been successfully configured via Azure CLI:

1. **✅ Managed Identity Enabled** - System-assigned managed identity created on container app
   - Principal ID: `6e6b4d47-c050-495e-8842-26d035424764`
   - ⚠️ Storage account key still in use (will be removed after role assignment)
   
2. **✅ Azure Communication Services** - Email service resource created
   - Resource: `usabc-email-communication` 
   - Status: Provisioned successfully
   
3. **✅ Monitoring Action Group** - Alert notification group created
   - Name: `usabc-upload-alerts`
   
4. **✅ Backup & Recovery Configured**
   - Blob soft delete: Enabled (30-day retention)
   - Container soft delete: Enabled (30-day retention)
   - Blob versioning: Enabled
   - Quarantine container: Created


---

## Request 1: Complete Managed Identity Role Assignment (REQUIRES ADMIN)

### **Status:** ⚠️ Partially Complete - Managed identity enabled, but role assignment and key removal requires elevated permissions

### **What Was Done:**
- ✅ System-assigned managed identity enabled on container app
- ✅ Principal ID: `6e6b4d47-c050-495e-8842-26d035424764`
- ⚠️ Storage account key still in environment (required until role assignment)

### **What Needs Admin Action:**

#### Step 1: Grant Storage Permissions to Managed Identity (requires User Access Administrator or Owner role)
```powershell
# Assign "Storage Blob Data Contributor" role to managed identity
az role assignment create \
  --assignee 6e6b4d47-c050-495e-8842-26d035424764 \
  --role "Storage Blob Data Contributor" \
  --scope "/subscriptions/e108977f-44ed-4400-9580-f7a0bc1d3630/resourceGroups/rg-rfpo-e108977f/providers/Microsoft.Storage/storageAccounts/strfpo5kn5bsg47vvac"

# Verify role assignment
az role assignment list \
  --assignee 6e6b4d47-c050-495e-8842-26d035424764 \
  --query "[].{Role:roleDefinitionName,Scope:scope}" -o table
```

**Authorization Required:** `Microsoft.Authorization/roleAssignments/write`

#### Step 2: Remove Storage Key from Container App (after role assignment succeeds)

⚠️ **IMPORTANT:** Only perform this step AFTER verifying the role assignment succeeded above.

```powershell
# Remove storage key from environment variables
az containerapp update \
  --name usabc-upload \
  --resource-group rg-rfpo-e108977f \
  --remove-env-vars AZURE_STORAGE_ACCOUNT_KEY

# Verify the key was removed
az containerapp show \
  --name usabc-upload \
  --resource-group rg-rfpo-e108977f \
  --query "properties.template.containers[0].env[?name=='AZURE_STORAGE_ACCOUNT_KEY']" -o table
```

**Expected Output:** Empty table (key successfully removed)

### **Verification:**
After role assignment and key removal, test file upload at: https://usabc-upload.livelyforest-d06a98a0.eastus.azurecontainerapps.io/

Files should upload successfully using managed identity. Check container app logs to confirm:
- No authentication errors
- No references to storage account keys
- Successful blob operations using managed identity

### **Expected Outcome:**
✅ Container app authenticates to storage using managed identity  
✅ Zero stored credentials (keyless authentication)  
✅ Improved security compliance

**Note:** Service continues to work during this transition using the storage key until Step 2 is completed.

---

## Request 2: Enable Malware Scanning (REQUIRES ADMIN)

### **Status:** ⚠️ Defender for Storage enabled at subscription level, but malware scanning requires role assignment permissions

### **What Was Done:**
- ✅ Verified Defender for Storage is enabled (Standard tier with DefenderForStorageV2)
- ✅ Quarantine container already exists
- ✅ Free trial period: 29 days remaining

### **What Needs Admin Action:****

#### Enable Malware Scanning on Storage Account (requires role assignment write permissions)

```powershell
# Enable malware scanning via REST API
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

**Authorization Required:** `Microsoft.Authorization/roleAssignments/write`

#### Alternative: Enable via Azure Portal (if CLI fails)

If the REST API command fails due to permissions, use the Azure Portal:

1. Navigate to: https://portal.azure.com
2. Search for storage account: **strfpo5kn5bsg47vvac**
3. In the left sidebar under **Security + networking** section
4. Click **Microsoft Defender for Cloud**
5. Locate **Malware Scanning** section
6. Toggle **Malware Scanning** to **ON**
7. Set **Capping (GB per month)**: 5000
8. Click **Save**
9. Wait 5-10 minutes for provisioning

### **Verification:**
```powershell
# Test with a file upload
# Upload a file via the web form
# Then check blob tags for scan results:

az storage blob tag list \
  --account-name strfpo5kn5bsg47vvac \
  --container-name usabc-uploads-stage \
  --name "uploads/2026/02/13/<submission-id>.zip" \
  --auth-mode login
```

**Look for tags:**
- `Malware Scanning scan result`: "No threats found" or "Malicious"
- `Malware Scanning scan time UTC`: Timestamp

### **Expected Outcome:**
✅ Malware scanning enabled on storage account  
✅ Uploaded files automatically scanned within 30 seconds  
✅ Malicious files quarantined to quarantine container  
✅ Application returns 403 error for infected files

### **Cost Impact:**
- Base: $10/month
- Scanning: $0.15 per GB scanned
- Monthly cap: 5000 GB
- Estimated: $10-30/month depending on upload volume

---

## Request 3: Configure Custom Domain uploads.uscar.org (REQUIRES DNS ACCESS + ADMIN)

### **Status:** ⏳ Requires DNS provider access and Azure permissions

### **Current Domain:** usabc-upload.livelyforest-d06a98a0.eastus.azurecontainerapps.io  
### **Target Domain:** uploads.uscar.org  
### **Verification Token:** 92AD77A30DEAB51492DBE7D424BC6B8026AA51D21C1856F7498C4D009F697494

### **Step-by-Step Instructions:**

#### Step 1: Add TXT Record for Domain Verification
```
Name:  asuid.uploads.uscar.org
Type:  TXT
Value: 92AD77A30DEAB51492DBE7D424BC6B8026AA51D21C1856F7498C4D009F697494
TTL:   3600 seconds (1 hour)
```

**Why:** Azure requires this TXT record to verify ownership of the domain before allowing custom domain binding.

#### Step 2: Add CNAME Record for Traffic Routing
```
Name:  uploads.uscar.org
Type:  CNAME
Value: usabc-upload.livelyforest-d06a98a0.eastus.azurecontainerapps.io
TTL:   3600 seconds (1 hour)
```

**Alternative if CNAME not supported:**
```
Name:  uploads.uscar.org
Type:  A
Value: 172.212.19.84
TTL:   3600 seconds (1 hour)
```

**Note:** CNAME is preferred as it follows Azure infrastructure changes automatically. Use A record only if DNS provider doesn't support CNAME for subdomains.

#### Step 3: Wait for DNS Propagation
Wait 5-15 minutes, then verify:
```powershell
# Verify TXT record
nslookup -type=TXT asuid.uploads.uscar.org

# Verify CNAME or A record
nslookup uploads.uscar.org
```

#### Step 4: Bind Custom Domain to Container App
```powershell
# Add custom domain
az containerapp hostname add \
  --hostname uploads.uscar.org \
  --name usabc-upload \
  --resource-group rg-rfpo-e108977f

# Enable managed TLS certificate (automatic HTTPS)
az containerapp hostname bind \
  --hostname uploads.uscar.org \
  --name usabc-upload \
  --resource-group rg-rfpo-e108977f \
  --environment-certificate-issuer "Managed" \
  --validation-method CNAME
```

#### Step 5: Verify SSL Certificate
```powershell
# Check certificate status
az containerapp hostname list \
  --name usabc-upload \
  --resource-group rg-rfpo-e108977f \
  -o table
```

### **Verification:**
- Open browser and navigate to: https://uploads.uscar.org
- Verify HTTPS padlock icon (valid TLS certificate)
- Test file upload functionality

### **Expected Outcome:**
✅ Service accessible at https://uploads.uscar.org  
✅ Automatic HTTPS with managed certificate  
✅ Certificate auto-renews before expiration  
✅ Old URL still works for backward compatibility

---

## Request 4: Complete Email Configuration for uploads@uscar.org (REQUIRES DNS ACCESS)

### **Status:** ⚠️ Email service created, requires DNS verification and sender configuration

### **What Was Done:**
- ✅ Azure Communication Services Email resource created (`usabc-email-communication`)
- ✅ Resource provisioned successfully in US data location

### **Part A: Configure Custom Domain and Sender Address (REQUIRES DNS ACCESS):**
#### Step 1: Add Custom Domain (uscar.org) to Email Service
```powershell
# Get email service resource ID
$emailServiceId="/subscriptions/e108977f-44ed-4400-9580-f7a0bc1d3630/resourceGroups/rg-rfpo-e108977f/providers/Microsoft.Communication/emailServices/usabc-email-communication"

# Add custom domain
az communication email domain create \
  --name uscar-org-domain \
  --email-service-name usabc-email-communication \
  --resource-group rg-rfpo-e108977f \
  --domain-management-type CustomerManaged \
  --custom-domain uscar.org

# Get DNS verification records
az communication email domain show \
  --name uscar-org-domain \
  --email-service-name usabc-email-communication \
  --resource-group rg-rfpo-e108977f \
  --query verificationRecords -o json
```

#### Step 2: Add Required DNS Records (Requires DNS Provider Access)
Add the following records to uscar.org DNS (records will be provided by previous command):
- **TXT record** for domain verification: `_azuremail-validation.uscar.org`
- **TXT record** for SPF: `v=spf1 include:spf.protection.outlook.com -all`
- **CNAME record** for DKIM: `selector1._domainkey.uscar.org`
- **CNAME record** for DKIM: `selector2._domainkey.uscar.org`

#### Step 3: Verify Domain and Configure Sender
```powershell
# After DNS records are added and propagated, verify domain
az communication email domain initiate-verification \
  --name uscar-org-domain \
  --email-service-name usabc-email-communication \
  --resource-group rg-rfpo-e108977f \
  --verification-type Domain

# Check verification status
az communication email domain show \
  --name uscar-org-domain \
  --email-service-name usabc-email-communication \
  --resource-group rg-rfpo-e108977f \
  --query domainVerificationStatus

# Once verified, add sender username (uploads@uscar.org)
az communication email domain sender-username create \
  --domain-name uscar-org-domain \
  --email-service-name usabc-email-communication \
  --resource-group rg-rfpo-e108977f \
  --sender-username uploads \
  --username uploads \
  --display-name "USABC Document Uploads"
```

#### Step 4: Create Communication Services Resource and Configure Container App
```powershell
# Create Communication Services resource to get connection string
az communication create \
  --name usabc-communication \
  --resource-group rg-rfpo-e108977f \
  --data-location "United States"

# Link email service
az communication email domain association create \
  --connection-string "$(az communication list-key --name usabc-communication --resource-group rg-rfpo-e108977f --query primaryConnectionString -o tsv)" \
  --email-service-resource-id $emailServiceId

# Get connection string (needed for app config)
az communication list-key \
  --name usabc-communication \
  --resource-group rg-rfpo-e108977f \
  --query primaryConnectionString -o tsv
```

#### Step 6: Configure Container App with Connection String
```powershell
# Add environment variables for email functionality
az containerapp update \
  --name usabc-upload \
  --resource-group rg-rfpo-e108977f \
  --set-env-vars \
    AZURE_COMMUNICATION_CONNECTION_STRING="<connection-string-from-step-5>" \
    AZURE_COMMUNICATION_SENDER_ADDRESS="uploads@uscar.org"
```

### **Part B: Email Monitoring Mailbox (OPTIONAL)**

While not required for automated confirmations, a monitored mailbox allows support for user inquiries.

#### **Option B1: Microsoft 365 Shared Mailbox**
```powershell
# Create shared mailbox (no license needed, up to 50GB)
New-Mailbox -Shared -Name "USABC Document Uploads" -PrimarySmtpAddress uploads@uscar.org

# Grant permissions to team members
Add-MailboxPermission -Identity uploads@uscar.org -User "admin@uscar.org" -AccessRights FullAccess
```

#### **Option B2: Email Alias/Forwarding**
```powershell
# Create alias on existing mailbox to receive replies
Set-Mailbox -Identity "support@uscar.org" -EmailAddresses @{add="uploads@uscar.org"}
```

### **Verification:**
1. Upload a file through the web form with a valid email address
2. Check that confirmation email is received
3. Verify email shows correct sender (uploads@uscar.org)
4. Check container app logs for `EMAIL_SENT` messages

### **Expected Outcome:**
✅ Azure Communication Services configured and verified  
✅ uploads@uscar.org can send automated confirmation emails  
✅ Submitters receive professional email confirmations with file details  
✅ Email delivery tracked in application logs  

### **Cost Impact:**
- Azure Communication Services Email: $0.0000625 per email (negligible for expected volume)
- Shared mailbox (if created): Free with Exchange Online

---

## Request 5: Configure Monitoring Alerts (MAY REQUIRE ADMIN)

### **Status:** ⚠️ Action group created, metric alerts require microsoft.insights provider registration

### **What Was Done:**
- ✅ Action group created (`usabc-upload-alerts`) for email notifications

### **What Needs Admin Action:**

#### Register microsoft.insights Provider (if needed)
```powershell
# Check if provider is registered
az provider show --namespace Microsoft.Insights --query "registrationState"

# If not registered, register it (requires contributor or higher)
az provider register --namespace Microsoft.Insights
```

#### Create Monitoring Alerts
```powershell
# Alert when container app is not running
az monitor metrics alert create \
  --name usabc-upload-down \
  --resource-group rg-rfpo-e108977f \
  --scopes "/subscriptions/e108977f-44ed-4400-9580-f7a0bc1d3630/resourceGroups/rg-rfpo-e108977f/providers/Microsoft.App/containerapps/usabc-upload" \
  --condition "count Replicas < 1" \
  --window-size 5m \
  --evaluation-frequency 1m \
  --action usabc-upload-alerts \
  --description "Container app has no running replicas"
```

#### Step 3: Create High Error Rate Alert
```powershell
# Alert when HTTP 5xx errors exceed threshold
az monitor metrics alert create \
  --name usabc-upload-errors \
  --resource-group rg-rfpo-e108977f \
  --scopes "/subscriptions/e108977f-44ed-4400-9580-f7a0bc1d3630/resourceGroups/rg-rfpo-e108977f/providers/Microsoft.App/containerapps/usabc-upload" \
  --condition "total Requests count > 10 where ResultType includes '5'" \
  --window-size 15m \
  --evaluation-frequency 5m \
  --action usabc-upload-alerts \
  --description "High rate of server errors (5xx)"
```

#### Step 4: Create Malware Detection Alert
```powershell
# Alert when malware is detected in uploaded files
# Note: This monitors blob tags via Log Analytics
# Requires storage account diagnostic settings to be enabled first

# Enable diagnostic logging
az monitor diagnostic-settings create \
  --name storage-logs \
  --resource "/subscriptions/e108977f-44ed-4400-9580-f7a0bc1d3630/resourceGroups/rg-rfpo-e108977f/providers/Microsoft.Storage/storageAccounts/strfpo5kn5bsg47vvac" \
  --logs '[{"category": "StorageRead", "enabled": true}, {"category": "StorageWrite", "enabled": true}]' \
  --workspace "/subscriptions/e108977f-44ed-4400-9580-f7a0bc1d3630/resourceGroups/rg-rfpo-e108977f/providers/Microsoft.OperationalInsights/workspaces/<workspace-name>"
```

*Note: Replace `<workspace-name>` with your Log Analytics workspace name, or create one if it doesn't exist.*

#### Step 5: Create Storage Capacity Alert
```powershell
# Alert when storage usage exceeds 80%
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

### **Expected Outcome:**
✅ Email notifications for service health issues  
✅ Alerts for malware detections  
✅ Proactive capacity management  
✅ Reduced mean time to detection (MTTD)

---

## Request 6: Enable Continuous Deployment (OPTIONAL - LOW PRIORITY)

### **Status:** ⏳ Optional enhancement for automated deployments

### **Step-by-Step Instructions:**

#### Enable Continuous Deployment from Container Registry
```powershell
# Configure container app to poll registry for updates
az containerapp registry set \
  --name usabc-upload \
  --resource-group rg-rfpo-e108977f \
  --server acrrfpoe108977f.azurecr.io \
  --username acrrfpoe108977f \
  --password "<registry-password>"

# Note: Password can be retrieved with:
# az acr credential show --name acrrfpoe108977f --query "passwords[0].value" -o tsv
```

### **Expected Outcome:**
✅ New container versions automatically deployed  
✅ Zero-downtime rolling updates  
✅ Simplified deployment process

---

---

## Summary of Required Admin Actions

| # | Task | Status | Estimated Time | Priority |
|---|------|--------|----------------|----------|
| 1 | Grant Managed Identity Storage Role + Remove Key | ❌ Requires Admin | 10 minutes | **HIGH** |
| 2 | Enable Malware Scanning | ❌ Requires Admin | 10 minutes | **HIGH** |
| 3 | Configure Custom Domain DNS | 🔄 Requires DNS Access | 30 minutes | Medium |
| 4 | Configure uploads@uscar.org Email | 🔄 Requires DNS Access | 20 minutes | Medium |
| 5 | Register Insights Provider & Create Alerts | ❌ May Require Admin | 20 minutes | **HIGH** |
| 6 | Enable Continuous Deployment | ⏸️ Optional | 10 minutes | Low |

**Completed:** Managed identity enabled, email service created, action group created, backup/DR configured ✅

**Total Admin Time Required:** ~40 minutes for critical items (HIGH priority only)

---

## Testing and Validation Checklist

After completing admin requests, verify:

- [ ] **Request 1:** File uploads work with managed identity (verify in container logs)
- [ ] **Request 2:** Malware scan results appear in blob tags after upload
- [ ] **Request 3:** Custom domain https://uploads.uscar.org redirects correctly with valid TLS
- [ ] **Request 4:** Automated emails sent from uploads@uscar.org to submitters
- [ ] **Request 5:** Test alert triggers when container app is stopped
- [ ] **Backup:** Verify soft-deleted blob can be recovered in Azure Portal
- [ ] **Health:** Endpoint returns 200: https://usabc-upload.livelyforest-d06a98a0.eastus.azurecontainerapps.io/health

---

## Support Contacts

**Requestor:** John Bouchard (johnbouchard@icloud.com)  
**Service Documentation:** See repository /docs folder  
**Container App Logs:** Azure Portal → rg-rfpo-e108977f → usabc-upload → Log stream

---

## Additional Notes

**What Was Successfully Configured:**
- ✅ Managed Identity: Enabled (no additional cost)
- ⚠️ Storage Key: Still in place (will be removed after admin grants role)
- ✅ Email Service: Azure Communication Services resource created
- ✅ Action Group: Alert notifications configured
- ✅ Backup/DR: Soft delete (30 days) and versioning enabled (~$0.01/GB/month)
- ✅ Quarantine Container: Created and ready for malware quarantine

**Anticipated Cost Impact (after admin completes requests):**
- Defender for Storage Malware Scanning: +$10-30/month
- Backup/Versioning Storage: ~$0.01/GB/month for versioning
- Custom Domain & TLS: No additional cost (included)
- Monitoring Alerts: Included in Container Apps pricing
- Email Sending: $0.0000625 per email (negligible)

**Total Additional Monthly Cost:** ~$10-35/month (primarily Defender malware scanning)

**Security Compliance Achieved:**
- 🔄 Zero stored credentials (managed identity enabled, key removal pending admin action)
- ⏳ Automated malware protection (pending admin enable)
- ✅ 30-day backup retention with versioning
- ⏳ TLS 1.2+ encrypted traffic on custom domain (pending DNS)
- ⏳ Operational monitoring and alerting (pending insights registration)
- ⏳ Professional branding and communication (pending DNS)

---

## Questions or Issues?

If any of these steps fail or require clarification, please contact the requestor or refer to the service repository documentation at:
- Virus Scanning: `VIRUS_SCANNING.md`
- Third-Party Integration: `THIRD_PARTY_INTEGRATION.md`
- Deployment Guide: `deploy-guide.md`
