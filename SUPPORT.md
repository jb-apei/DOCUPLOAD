# USABC Upload Service - Support Guide

**Service Name:** USABC Document Upload Service  
**Version:** v1.4.1  
**Last Updated:** February 13, 2026  
**Support Contact:** [Your IT Support Email]

---

## 📞 Getting Help

This document covers common issues and their solutions. For issues not covered here:
1. Check the logs: `az containerapp logs show --name usabc-upload --resource-group rg-rfpo-e108977f --tail 100`
2. Review [DEPLOYMENT_BEST_PRACTICES.md](DEPLOYMENT_BEST_PRACTICES.md)
3. Check [ADMIN_REQUEST.md](ADMIN_REQUEST.md) for pending administrative tasks
4. Contact your Azure administrator if permissions are needed

---

## 🚨 Common Issues and Solutions

### Issue: Email Notifications Not Sending

**Symptom:** Users submit forms but don't receive confirmation emails.

**How to Diagnose:**
```powershell
# Check logs for email status
az containerapp logs show --name usabc-upload --resource-group rg-rfpo-e108977f --tail 50 --follow false --format text | Select-String -Pattern "EMAIL"
```

**Look for:**
- ❌ `EMAIL_DISABLED: Would have sent email to...` - Configuration missing
- ✅ `EMAIL_SENT: Successfully sent to...` - Working correctly
- ⚠️ `EMAIL_ERROR: Failed to send email...` - Azure Communication Services issue

**Solution 1: Environment Variables Missing**
```powershell
# Re-add email configuration
az containerapp update `
  --name usabc-upload `
  --resource-group rg-rfpo-e108977f `
  --set-env-vars `
    "AZURE_COMMUNICATION_CONNECTION_STRING=<your_connection_string>" `
    "AZURE_COMMUNICATION_SENDER_ADDRESS=<your_sender_address>"

# Wait for new revision to deploy (about 30 seconds)
Start-Sleep -Seconds 30

# Verify configuration
az containerapp show `
  --name usabc-upload `
  --resource-group rg-rfpo-e108977f `
  --query "properties.template.containers[0].env[?name=='AZURE_COMMUNICATION_SENDER_ADDRESS'].value" -o tsv
```

**Solution 2: Check Email is in Recipient List**
- Email will be sent to the address entered in the form's "Email" field
- Check spam/junk folders
- Verify email address was entered correctly in the form submission

**Solution 3: Azure Communication Services Issue**
```powershell
# Test communication services directly
az communication list --resource-group rg-rfpo-e108977f -o table

# Check email service status
az communication email domain list --email-service-name rfpo-email --resource-group rg-rfpo-e108977f -o table
```

---

### Issue: File Upload Fails

**Symptom:** Form submission returns error or doesn't complete.

**How to Diagnose:**
```powershell
# Check recent upload attempts
az containerapp logs show --name usabc-upload --resource-group rg-rfpo-e108977f --tail 100 --follow false --format text | Select-String -Pattern "RFPI_SUBMIT|UPLOAD_ERROR|VALIDATION"
```

**Common Causes:**

**1. File Size Too Large**
- Maximum per file: 25 MB
- Maximum total: 50 MB
- Solution: Compress files or reduce quality before upload

**2. Wrong File Type**
- Required: PDF files for documents, Excel (.xlsx or .xls) for budgets
- Solution: Convert files to correct format

**3. Storage Authentication Failed**
```powershell
# Verify storage account key is configured
az containerapp show `
  --name usabc-upload `
  --resource-group rg-rfpo-e108977f `
  --query "properties.template.containers[0].env[?name=='AZURE_STORAGE_ACCOUNT_KEY']" -o json

# If missing, re-add storage configuration
$storageKey = az storage account keys list --account-name strfpo5kn5bsg47vvac --query "[0].value" -o tsv

az containerapp update `
  --name usabc-upload `
  --resource-group rg-rfpo-e108977f `
  --set-env-vars `
    "AZURE_STORAGE_ACCOUNT_URL=https://strfpo5kn5bsg47vvac.blob.core.windows.net" `
    "AZURE_STORAGE_ACCOUNT_NAME=strfpo5kn5bsg47vvac" `
    "AZURE_STORAGE_ACCOUNT_KEY=$storageKey" `
    "AZURE_CONTAINER_NAME=usabc-uploads-stage"
```

**4. Network/Timeout Issues**
- Check Azure Container Apps status
- Verify ingress is enabled and external
- Test with smaller files first

---

### Issue: Deployment Lost Configuration

**Symptom:** After deploying a new version, features stop working (email, file upload, etc.)

**Cause:** Using `--set-env-vars` during image update overwrites ALL environment variables.

**Prevention:**
Always use the deployment script:
```powershell
.\deploy.ps1 -Version "v1.X"
```

**Recovery:**
```powershell
# 1. Get storage key
$storageKey = az storage account keys list --account-name strfpo5kn5bsg47vvac --query "[0].value" -o tsv

# 2. Restore ALL environment variables
az containerapp update `
  --name usabc-upload `
  --resource-group rg-rfpo-e108977f `
  --set-env-vars `
    "AZURE_STORAGE_ACCOUNT_URL=https://strfpo5kn5bsg47vvac.blob.core.windows.net" `
    "AZURE_STORAGE_ACCOUNT_NAME=strfpo5kn5bsg47vvac" `
    "AZURE_STORAGE_ACCOUNT_KEY=$storageKey" `
    "AZURE_CONTAINER_NAME=usabc-uploads-stage" `
    "AZURE_COMMUNICATION_CONNECTION_STRING=<your_connection_string>" `
    "AZURE_COMMUNICATION_SENDER_ADDRESS=<your_sender_address>"

# 3. Wait for deployment
Start-Sleep -Seconds 30

# 4. Test the service
# Visit: https://usabc-upload.livelyforest-d06a98a0.eastus.azurecontainerapps.io/
```

---

### Issue: Malware Scanning Not Working

**Symptom:** Files show `scanStatus: pending` indefinitely, not `clean`.

**Cause:** Microsoft Defender for Storage not enabled on storage account.

**Solution:** 
Requires administrator with Security Admin or Owner role. See [ADMIN_REQUEST.md](ADMIN_REQUEST.md) Request #2.

**Workaround:**
Files are still uploaded and accessible. Scanning will automatically complete once Defender is enabled.

---

### Issue: Service Not Responding / 502 Error

**How to Diagnose:**
```powershell
# Check container app status
az containerapp show --name usabc-upload --resource-group rg-rfpo-e108977f --query "properties.runningStatus" -o tsv

# Check recent revisions
az containerapp revision list --name usabc-upload --resource-group rg-rfpo-e108977f --query "[].{Name:name, Active:properties.active, Status:properties.runningStatus, Traffic:properties.trafficWeight}" -o table
```

**Solutions:**

**1. Restart the app:**
```powershell
az containerapp revision restart --name usabc-upload --resource-group rg-rfpo-e108977f
```

**2. Check replica count:**
```powershell
az containerapp show --name usabc-upload --resource-group rg-rfpo-e108977f --query "properties.template.scale" -o json

# Should show minReplicas: 1, maxReplicas: 10
```

**3. Review error logs:**
```powershell
az containerapp logs show --name usabc-upload --resource-group rg-rfpo-e108977f --tail 200 --follow false --format text | Select-String -Pattern "ERROR|Exception|Failed"
```

---

### Issue: Rate Limiting (429 Errors)

**Symptom:** User receives "Too many requests" error.

**Cause:** 
- Upload limit: 20 uploads per hour per IP
- General limit: 100 requests per hour per IP

**Solution:**
- Wait for rate limit to reset (up to 1 hour)
- Contact administrator if limits need to be increased

**Check Rate Limit Status:**
Response headers include:
```
X-RateLimit-Limit: 20
X-RateLimit-Remaining: 5
X-RateLimit-Reset: 1644742800
```

---

## 🔧 Maintenance Tasks

### Check Service Health

```powershell
# Health endpoint
curl https://usabc-upload.livelyforest-d06a98a0.eastus.azurecontainerapps.io/health

# Expected response:
# {
#   "status": "healthy",
#   "service": "usabc-upload",
#   "version": "v1.4.1",
#   "timestamp": "2026-02-13T03:00:00Z"
# }
```

### View Recent Submissions

```powershell
# List recent uploads in storage
az storage blob list `
  --account-name strfpo5kn5bsg47vvac `
  --container-name usabc-uploads-stage `
  --prefix "rfpi-submissions/2026/02/" `
  --auth-mode key `
  --query "[].{Name:name, Size:properties.contentLength, Uploaded:properties.creationTime}" `
  --output table
```

### Check Quarantined Files

```powershell
# List quarantined files (if any exist)
az storage blob list `
  --account-name strfpo5kn5bsg47vvac `
  --container-name quarantine `
  --auth-mode key `
  --query "[].{Name:name, QuarantineTime:properties.creationTime, Reason:metadata.scanDetails}" `
  --output table
```

### Monitor Application Performance

```powershell
# View request duration and status codes
az containerapp logs show `
  --name usabc-upload `
  --resource-group rg-rfpo-e108977f `
  --tail 100 `
  --follow false `
  --format text | Select-String -Pattern "RESPONSE|Duration"
```

---

## 📋 Configuration Checklist

Use this checklist to verify the service is properly configured:

### Environment Variables
```powershell
# Run this command to check all required variables
az containerapp show `
  --name usabc-upload `
  --resource-group rg-rfpo-e108977f `
  --query "properties.template.containers[0].env[].name" -o table
```

**Required variables (must all be present):**
- [ ] `AZURE_STORAGE_ACCOUNT_URL`
- [ ] `AZURE_STORAGE_ACCOUNT_NAME`
- [ ] `AZURE_STORAGE_ACCOUNT_KEY`
- [ ] `AZURE_CONTAINER_NAME`
- [ ] `AZURE_COMMUNICATION_CONNECTION_STRING`
- [ ] `AZURE_COMMUNICATION_SENDER_ADDRESS`

### Service Status
- [ ] Service URL accessible: https://usabc-upload.livelyforest-d06a98a0.eastus.azurecontainerapps.io/
- [ ] Health endpoint returns `"status": "healthy"`
- [ ] Form loads without errors
- [ ] File upload completes successfully
- [ ] Email confirmation received
- [ ] Files appear in Azure Blob Storage

### Pending Administrative Tasks
Check [ADMIN_REQUEST.md](ADMIN_REQUEST.md) for items requiring admin permissions:
- [ ] Managed Identity configured
- [ ] Microsoft Defender for Storage enabled
- [ ] Custom domain (uploads.uscar.org) DNS configured
- [ ] Email domain (uscar.org) verified
- [ ] Azure Monitor alerts configured
- [ ] Backup and disaster recovery enabled

---

## 📚 Related Documentation

- **[DEPLOYMENT_QUICKREF.md](DEPLOYMENT_QUICKREF.md)** - Quick deployment commands
- **[DEPLOYMENT_BEST_PRACTICES.md](DEPLOYMENT_BEST_PRACTICES.md)** - Detailed deployment guide
- **[deployment-info.md](deployment-info.md)** - Current deployment information
- **[ADMIN_REQUEST.md](ADMIN_REQUEST.md)** - Tasks requiring administrator access
- **[VIRUS_SCANNING.md](VIRUS_SCANNING.md)** - Malware scanning documentation
- **[THIRD_PARTY_INTEGRATION.md](THIRD_PARTY_INTEGRATION.md)** - API integration guide

---

## 🐛 Reporting Bugs or Issues

When reporting an issue, include:

1. **What happened:** Describe the problem
2. **Expected behavior:** What should have happened
3. **Steps to reproduce:** How to recreate the issue
4. **Logs:** Relevant log entries (see commands below)
5. **Environment:** Browser version, file types, file sizes

**Collect diagnostic information:**
```powershell
# 1. Service status
az containerapp show --name usabc-upload --resource-group rg-rfpo-e108977f --query "{Status:properties.runningStatus, Version:properties.template.containers[0].image, Replicas:properties.template.scale}" -o json

# 2. Recent errors
az containerapp logs show --name usabc-upload --resource-group rg-rfpo-e108977f --tail 100 --follow false --format text | Select-String -Pattern "ERROR|Exception|Failed" | Select-Object -First 20

# 3. Environment variables (names only, not values)
az containerapp show --name usabc-upload --resource-group rg-rfpo-e108977f --query "properties.template.containers[0].env[].name" -o table

# 4. Active revision
az containerapp revision list --name usabc-upload --resource-group rg-rfpo-e108977f --query "[?properties.active].{Name:name, Created:properties.createdTime, Traffic:properties.trafficWeight}" -o table
```

---

## 🔐 Security Concerns

**Do not share in logs or reports:**
- Storage account keys
- Azure Communication Services connection strings
- User email addresses
- Uploaded file contents

**If you suspect a security issue:**
1. Do not post details publicly
2. Contact your security team immediately
3. Preserve logs for investigation
4. Consider disabling the service temporarily

---

## 📊 Service Level Information

**Availability:** 99.5% (Azure Container Apps SLA)  
**Maintenance Window:** Deployments can occur anytime with zero downtime  
**Backup Frequency:** Depends on storage account configuration (see ADMIN_REQUEST.md)  
**Data Retention:** Uploaded files retained indefinitely unless lifecycle policy configured  

**Current Capacity:**
- Concurrent uploads: 8 per replica × 10 replicas = 80 concurrent
- File size limit: 25 MB per file, 50 MB total per submission
- Rate limits: 20 uploads/hour per IP, 100 requests/hour per IP

---

## 📞 Escalation Path

1. **Level 1:** Check this support guide
2. **Level 2:** Review logs and recent changes
3. **Level 3:** Contact Azure administrator for permission-related issues
4. **Level 4:** Azure Support for platform-level issues

---

**Last Reviewed:** February 13, 2026  
**Next Review Due:** March 13, 2026
