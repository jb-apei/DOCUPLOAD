# Deployment Best Practices

## Environment Variable Management

### Critical Rule: Never Overwrite Environment Variables During Deployment

When updating a container app image, Azure CLI commands have different behaviors:

**✅ CORRECT - Preserves environment variables:**
```powershell
az containerapp update \
  --name usabc-upload \
  --resource-group rg-rfpo-e108977f \
  --image acrrfpoe108977f.azurecr.io/usabc-upload:v1.5
```

**❌ WRONG - Overwrites ALL environment variables:**
```powershell
az containerapp update \
  --name usabc-upload \
  --resource-group rg-rfpo-e108977f \
  --image acrrfpoe108977f.azurecr.io/usabc-upload:v1.5 \
  --set-env-vars "NEW_VAR=value"  # This REMOVES all other env vars!
```

### Why This Matters

The USABC Upload Service depends on several environment variables:
- **Storage Configuration:** `AZURE_STORAGE_ACCOUNT_URL`, `AZURE_STORAGE_ACCOUNT_KEY`, etc.
- **Email Configuration:** `AZURE_COMMUNICATION_CONNECTION_STRING`, `AZURE_COMMUNICATION_SENDER_ADDRESS`
- **Container Name:** `AZURE_CONTAINER_NAME`

If these are lost during deployment, the service will fail with:
- ❌ Unable to upload files (storage authentication fails)
- ❌ Email notifications disabled (connection string missing)
- ❌ Application errors and crashes

### Best Practice: Use the Deployment Script

Always use `deploy.ps1` which:
1. ✅ Reads current environment variables before deployment
2. ✅ Updates only the container image
3. ✅ Verifies environment variables after deployment
4. ✅ Shows before/after comparison
5. ✅ Alerts if configuration changes

```powershell
# Standard deployment
.\deploy.ps1 -Version "v1.5"

# Deploy existing image without rebuilding
.\deploy.ps1 -Version "v1.5" -SkipBuild
```

### Adding New Environment Variables

When you need to ADD a new environment variable without affecting existing ones:

```powershell
# Get all current env vars
$currentEnvVars = az containerapp show `
  --name usabc-upload `
  --resource-group rg-rfpo-e108977f `
  --query "properties.template.containers[0].env" -o json | ConvertFrom-Json

# Build the --set-env-vars parameter including all existing vars plus new ones
# Example: Add NEW_FEATURE=enabled while keeping all existing vars
az containerapp update `
  --name usabc-upload `
  --resource-group rg-rfpo-e108977f `
  --set-env-vars `
    AZURE_STORAGE_ACCOUNT_URL="$($currentEnvVars[0].value)" `
    AZURE_STORAGE_ACCOUNT_KEY="$($currentEnvVars[1].value)" `
    ... (all existing vars) ... `
    NEW_FEATURE="enabled"
```

**Better approach:** Use `replace-env-vars` with just the new variable:
```powershell
az containerapp update `
  --name usabc-upload `
  --resource-group rg-rfpo-e108977f `
  --replace-env-vars "NEW_FEATURE=enabled"
```

### Troubleshooting Lost Configuration

If environment variables were accidentally removed during deployment:

1. **Check what's missing:**
```powershell
az containerapp show `
  --name usabc-upload `
  --resource-group rg-rfpo-e108977f `
  --query "properties.template.containers[0].env[].name" -o table
```

2. **Re-add missing variables:**
```powershell
az containerapp update `
  --name usabc-upload `
  --resource-group rg-rfpo-e108977f `
  --set-env-vars `
    "AZURE_COMMUNICATION_CONNECTION_STRING=endpoint=https://...;accesskey=..." `
    "AZURE_COMMUNICATION_SENDER_ADDRESS=donotreply@...azurecomm.net"
```

3. **Verify in logs:**
```powershell
az containerapp logs show `
  --name usabc-upload `
  --resource-group rg-rfpo-e108977f `
  --tail 50 --follow false --format text | Select-String -Pattern "EMAIL"
```

Look for:
- ✅ `EMAIL_SENT: Successfully sent to...` (working)
- ❌ `EMAIL_DISABLED: Would have sent...` (configuration missing)

### Version History

| Version | Date | Changes | Env Vars Status |
|---------|------|---------|-----------------|
| v1.4.1 | 2026-02-13 | Added RFPI title to email subject | ⚠️ Lost during image update |
| v1.4.1 (rev2) | 2026-02-13 | Re-added email configuration | ✅ Restored |
| v1.4 | 2026-02-13 | Initial email notifications | ✅ Configured |

### Checklist Before Each Deployment

- [ ] Run `deploy.ps1` script (or follow manual steps exactly)
- [ ] Do NOT use `--set-env-vars` when updating images
- [ ] Verify environment variable count before/after
- [ ] Check logs for EMAIL_SENT (not EMAIL_DISABLED)
- [ ] Test file upload with email notification
- [ ] Update version number in deployment-info.md
