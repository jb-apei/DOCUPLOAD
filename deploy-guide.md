# Deployment Guide

## How Developers Will Use Your Service

### Option 1: Direct Link to Hosted Form
Give developers this URL after deployment:
```
https://your-service.azurewebsites.net/
```
They open it in a browser and upload files directly.

### Option 2: Embed the Widget
Developers can embed your upload form in their own applications:

```html
<!DOCTYPE html>
<html>
<head>
    <title>My App</title>
</head>
<body>
    <h1>Upload Project Documents</h1>
    
    <!-- Embedded upload widget -->
    <div id="docupload-widget"></div>
    <script src="https://your-service.azurewebsites.net/widget.js"></script>
</body>
</html>
```

### Option 3: API Integration
Developers can call your API directly:

```bash
curl -X POST https://your-service.azurewebsites.net/upload \
  -F "architectureDiagram=@diagram.pdf" \
  -F "charter=@charter.docx" \
  -F 'tags={"project":"myproject","environment":"dev"}'
```

---

## Deployment Options

### Option A: Azure Container Apps (Recommended)
Easiest, fully managed, scales automatically.

```powershell
# Build and push image
az acr create --resource-group rg-rfpo-e108977f --name <registry-name> --sku Basic
az acr build --registry <registry-name> --image docupload:latest .

# Deploy to Container Apps
az containerapp create \
  --name docupload-service \
  --resource-group rg-rfpo-e108977f \
  --image <registry-name>.azurecr.io/docupload:latest \
  --target-port 5000 \
  --ingress external \
  --environment-variables \
    AZURE_STORAGE_ACCOUNT_URL=https://strfpo5kn5bsg47vvac.blob.core.windows.net \
    AZURE_STORAGE_ACCOUNT_NAME=strfpo5kn5bsg47vvac \
    AZURE_STORAGE_ACCOUNT_KEY=<your-key> \
    AZURE_CONTAINER_NAME=usabc-uploads-stage
```

### Option B: Azure App Service (Container)
Good balance of features and control.

```powershell
# Create App Service Plan
az appservice plan create --name docupload-plan --resource-group rg-rfpo-e108977f --is-linux --sku B1

# Create Web App
az webapp create --resource-group rg-rfpo-e108977f --plan docupload-plan --name docupload-app --deployment-container-image <registry-name>.azurecr.io/docupload:latest

# Configure environment variables
az webapp config appsettings set --resource-group rg-rfpo-e108977f --name docupload-app --settings \
  AZURE_STORAGE_ACCOUNT_URL=https://strfpo5kn5bsg47vvac.blob.core.windows.net \
  AZURE_STORAGE_ACCOUNT_NAME=strfpo5kn5bsg47vvac \
  AZURE_STORAGE_ACCOUNT_KEY=<your-key> \
  AZURE_CONTAINER_NAME=usabc-uploads-stage
```

### Option C: Azure Kubernetes Service (AKS)
Most flexible, for production-scale deployments.

---

## Local Testing with Docker

```powershell
# Build the image
docker build -t docupload:local .

# Run locally
docker run -p 5000:5000 \
  -e AZURE_STORAGE_ACCOUNT_URL=https://strfpo5kn5bsg47vvac.blob.core.windows.net \
  -e AZURE_STORAGE_ACCOUNT_NAME=strfpo5kn5bsg47vvac \
  -e AZURE_STORAGE_ACCOUNT_KEY=<your-key> \
  -e AZURE_CONTAINER_NAME=usabc-uploads-stage \
  docupload:local
```

Then open: http://localhost:5000

---

## What Happens When Files Are Uploaded

1. **Validation**: Files are checked for correct type (PDF/DOCX signatures)
2. **Hashing**: SHA-256 computed for each file
3. **Packaging**: Files + manifest.json → zip file
4. **Storage**: Uploaded to Azure Blob Storage at:
   - Container: `usabc-uploads-stage`
   - Path: `uploads/YYYY/MM/DD/{submissionId}.zip`
5. **Metadata Applied**:
   - Blob metadata: `submissionId`, `scanStatus`, `zipSha256`, `submittedAt`
   - Blob index tags: `project`, `scanStatus` (queryable)
6. **Response**: Returns submission ID, blob path, and hashes

---

## Production Readiness Checklist

Before giving the link to developers:

- [ ] Deploy to Azure Container Apps/App Service
- [ ] Configure custom domain (optional)
- [ ] Enable HTTPS (automatic with Azure)
- [ ] Set up Application Insights for monitoring
- [ ] Configure CORS to allow specific domains
- [ ] Add rate limiting
- [ ] Switch from storage account key to Managed Identity
- [ ] Add authentication (if needed)
- [ ] Set up malware scanning (if required)
- [ ] Create API documentation for developers

---

## Next Steps

1. Test the Docker image locally
2. Choose deployment option
3. Deploy to Azure
4. Get the public URL
5. Share with developers!
