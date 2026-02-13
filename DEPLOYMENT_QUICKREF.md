# 🚨 DEPLOYMENT QUICK REFERENCE 🚨

## ✅ CORRECT Way to Deploy

```powershell
# Use the deployment script
.\deploy.ps1 -Version "v1.5"
```

**What this does:**
- ✅ Builds Docker image with version tag
- ✅ Preserves ALL environment variables
- ✅ Verifies configuration before/after
- ✅ Shows deployment summary

---

## ❌ NEVER DO THIS

```powershell
# This DESTROYS all environment variables!
az containerapp update --name usabc-upload --resource-group rg-rfpo-e108977f --image acrrfpoe108977f.azurecr.io/usabc-upload:v1.5 --set-env-vars "NEW_VAR=value"
```

**Using `--set-env-vars` REPLACES ALL env vars, not adds to them!**

---

## 📋 Manual Deployment Steps (Script Not Available)

```powershell
# 1. Build the image
az acr build --registry acrrfpoe108977f --image usabc-upload:v1.5 --file Dockerfile .

# 2. Update ONLY the image (env vars preserved automatically)
az containerapp update --name usabc-upload --resource-group rg-rfpo-e108977f --image acrrfpoe108977f.azurecr.io/usabc-upload:v1.5

# 3. Verify env vars still exist
az containerapp show --name usabc-upload --resource-group rg-rfpo-e108977f --query "properties.template.containers[0].env[].name" -o table
```

**Rule: NO `--set-env-vars` when updating images!**

---

## 🔍 Post-Deployment Verification

```powershell
# Check if email is working (should see EMAIL_SENT, not EMAIL_DISABLED)
az containerapp logs show --name usabc-upload --resource-group rg-rfpo-e108977f --tail 50 --follow false --format text | Select-String -Pattern "EMAIL"
```

**Expected:** `EMAIL_SENT: Successfully sent to...`  
**Problem:** `EMAIL_DISABLED: Would have sent...` ← Environment variables missing!

---

## 🆘 Emergency: Lost Environment Variables

```powershell
# Re-add email configuration
az containerapp update --name usabc-upload --resource-group rg-rfpo-e108977f --set-env-vars "AZURE_COMMUNICATION_CONNECTION_STRING=<your-connection-string>" "AZURE_COMMUNICATION_SENDER_ADDRESS=<your-sender-address>"
```

---

## 📦 Required Environment Variables

These must ALWAYS be configured:
- ✅ `AZURE_STORAGE_ACCOUNT_URL`
- ✅ `AZURE_STORAGE_ACCOUNT_NAME`
- ✅ `AZURE_STORAGE_ACCOUNT_KEY`
- ✅ `AZURE_CONTAINER_NAME`
- ✅ `AZURE_COMMUNICATION_CONNECTION_STRING`
- ✅ `AZURE_COMMUNICATION_SENDER_ADDRESS`

---

## 📚 Full Documentation

- [DEPLOYMENT_BEST_PRACTICES.md](DEPLOYMENT_BEST_PRACTICES.md) - Complete guide
- [deployment-info.md](deployment-info.md) - Current deployment status

---

**Remember: When in doubt, use `.\deploy.ps1`**
