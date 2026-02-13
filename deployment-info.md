# USABC-UPLOAD Deployment Details

## 🎉 Successfully Deployed!

**Service Name:** USABC-UPLOAD  
**Public URL:** https://usabc-upload.livelyforest-d06a98a0.eastus.azurecontainerapps.io/  
**Current Version:** v1.4.1  
**Status:** Running  
**Resource Group:** rg-rfpo-e108977f  
**Environment:** rfpo-env-5kn5bsg47vvac  
**Container Registry:** acrrfpoe108977f.azurecr.io  
**Image:** usabc-upload:v1.4.1

---

## 🚀 Deploying New Versions

### **CRITICAL: Always Use the Deployment Script**

```powershell
# Deploy a new version (builds and deploys)
.\deploy.ps1 -Version "v1.5"

# Deploy without rebuilding (use existing image)
.\deploy.ps1 -Version "v1.5" -SkipBuild
```

**Why use the script?**
- ✅ **Preserves environment variables** (email config, storage keys, etc.)
- ✅ Verifies configuration before and after deployment
- ✅ Shows deployment summary and status
- ✅ Prevents common deployment mistakes

### **⚠️ NEVER Do This:**
```powershell
# ❌ WRONG - This OVERWRITES all environment variables!
az containerapp update \
  --name usabc-upload \
  --resource-group rg-rfpo-e108977f \
  --image acrrfpoe108977f.azurecr.io/usabc-upload:v1.5 \
  --set-env-vars "VAR1=value1"  # This removes ALL other env vars!
```

### **Manual Deployment (If Script Not Available)**
```powershell
# Step 1: Build image
az acr build --registry acrrfpoe108977f --image usabc-upload:v1.5 --file Dockerfile .

# Step 2: Update image ONLY (preserves existing env vars)
az containerapp update \
  --name usabc-upload \
  --resource-group rg-rfpo-e108977f \
  --image acrrfpoe108977f.azurecr.io/usabc-upload:v1.5
  # Do NOT use --set-env-vars here!

# Step 3: Verify environment variables are intact
az containerapp show \
  --name usabc-upload \
  --resource-group rg-rfpo-e108977f \
  --query "properties.template.containers[0].env[].name" -o table
```

### **Required Environment Variables**
The following must be configured (preserved across deployments):
- `AZURE_STORAGE_ACCOUNT_URL`
- `AZURE_STORAGE_ACCOUNT_NAME`
- `AZURE_STORAGE_ACCOUNT_KEY`
- `AZURE_CONTAINER_NAME`
- `AZURE_COMMUNICATION_CONNECTION_STRING` (for email notifications)
- `AZURE_COMMUNICATION_SENDER_ADDRESS` (for email notifications)

---

## 📋 How Developers Use Your Service

### Option 1: Direct Web Form
Share this URL with developers:
```
https://usabc-upload.livelyforest-d06a98a0.eastus.azurecontainerapps.io/
```
They can open it in a browser and upload files directly.

### Option 2: Embed the Widget
Developers can embed your upload form in their applications:

```html
<!DOCTYPE html>
<html>
<head>
    <title>My Application</title>
</head>
<body>
    <h1>Upload Project Documents</h1>
    
    <!-- Embedded upload widget -->
    <div id="docupload-widget"></div>
    <script src="https://usabc-upload.livelyforest-d06a98a0.eastus.azurecontainerapps.io/widget.js"></script>
</body>
</html>
```

### Option 3: API Integration
Developers can call your API programmatically:

```bash
curl -X POST https://usabc-upload.livelyforest-d06a98a0.eastus.azurecontainerapps.io/upload \
  -F "architectureDiagram=@diagram.pdf" \
  -F "charter=@charter.docx" \
  -F 'tags={"project":"myproject","environment":"dev"}'
```

```python
import requests

url = "https://usabc-upload.livelyforest-d06a98a0.eastus.azurecontainerapps.io/upload"

files = {
    'architectureDiagram': open('diagram.pdf', 'rb'),
    'charter': open('charter.docx', 'rb'),
    'tags': (None, '{"project":"myproject","environment":"dev"}')
}

response = requests.post(url, files=files)
print(response.json())
```

---

## 🎯 What Happens When Files Are Uploaded

1. **Validation**: Files are checked for correct types (PDF/DOCX signatures)
2. **Hashing**: SHA-256 computed for each file and the final zip
3. **Packaging**: Files + manifest.json are packaged into a zip
4. **Storage**: Uploaded to Azure Blob Storage:
   - **Container**: `usabc-uploads-stage`
   - **Path**: `uploads/YYYY/MM/DD/{submissionId}.zip`
5. **Metadata**: Applied to blob:
   - `submissionId`, `scanStatus`, `zipSha256`, `submittedAt`
   - Index tags: `project`, `scanStatus` (queryable)
6. **Response**: JSON with submission ID, blob path, and hashes

---

## 📊 Management Commands

### View uploaded files in storage:
```powershell
az storage blob list \
  --account-name strfpo5kn5bsg47vvac \
  --container-name usabc-uploads-stage \
  --auth-mode key \
  --output table
```

### View app logs:
```powershell
az containerapp logs show \
  --name usabc-upload \
  --resource-group rg-rfpo-e108977f \
  --follow
```

### Scale the app:
```powershell
az containerapp update \
  --name usabc-upload \
  --resource-group rg-rfpo-e108977f \
  --min-replicas 1 \
  --max-replicas 5
```

### Update the app with a new version:
```powershell
# Build new image
az acr build --registry acrrfpoe108977f --image usabc-upload:v1.1 .

# Update container app
az containerapp update \
  --name usabc-upload \
  --resource-group rg-rfpo-e108977f \
  --image acrrfpoe108977f.azurecr.io/usabc-upload:v1.1
```

### Stop the app:
```powershell
az containerapp revision deactivate \
  --name usabc-upload \
  --resource-group rg-rfpo-e108977f \
  --revision latest
```

### Delete the app:
```powershell
az containerapp delete \
  --name usabc-upload \
  --resource-group rg-rfpo-e108977f \
  --yes
```

---

## 🔒 Security Configuration

Currently configured with:
- ✅ HTTPS enabled (automatic with Azure Container Apps)
- ✅ External ingress (publicly accessible)
- ✅ Storage account key authentication
- ⚠️ No authentication required (anonymous access)
- ⚠️ CORS allows all origins

### To add authentication (recommended for production):
```powershell
az containerapp auth update \
  --name usabc-upload \
  --resource-group rg-rfpo-e108977f \
  --enable true \
  --aad-client-id <your-app-registration-id> \
  --aad-tenant-id <your-tenant-id>
```

---

## 📈 Monitoring

View in Azure Portal:
1. Go to: https://portal.azure.com
2. Navigate to: Container Apps > usabc-upload
3. View metrics, logs, and revisions

Enable Application Insights (recommended):
```powershell
# Create Application Insights
az monitor app-insights component create \
  --app usabc-upload-insights \
  --location eastus \
  --resource-group rg-rfpo-e108977f

# Get instrumentation key
$key = az monitor app-insights component show \
  --app usabc-upload-insights \
  --resource-group rg-rfpo-e108977f \
  --query instrumentationKey -o tsv

# Add to container app
az containerapp update \
  --name usabc-upload \
  --resource-group rg-rfpo-e108977f \
  --set-env-vars APPLICATIONINSIGHTS_CONNECTION_STRING="InstrumentationKey=$key"
```

---

## ✅ Deployment Summary

- Container image built and pushed to ACR
- Deployed to Azure Container Apps
- Public endpoint is live and accessible
- Connected to Azure Blob Storage (usabc-uploads-stage)
- All environment variables configured
- Ready for developers to use!

---

## 📝 Next Steps

1. ✅ Test the upload form at the public URL
2. Share the URL with developers
3. Consider adding:
   - Authentication (Azure AD)
   - Rate limiting
   - Custom domain
   - Application Insights monitoring
   - Malware scanning integration
