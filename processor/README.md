# USABC Upload Processor Service

A containerized Python service that processes blob upload events from Azure Service Bus, extracts zip files, and prepares them for SharePoint integration.

## 🎯 Purpose

This service automatically processes uploaded files by:
1. ✅ Receiving blob upload events from Service Bus queue
2. ✅ Downloading zip files from Azure Blob Storage
3. ✅ Extracting all files from the zip
4. ✅ Reading `manifest.json` to get submission details
5. ✅ Uploading extracted files to `processed/{submissionId}/` folder
6. ✅ Emitting "processing completed" events (optional)
7. 🔄 Moving files to SharePoint (placeholder - not implemented yet)

## 📋 Prerequisites

- Azure subscription with appropriate permissions
- Service Bus namespace with queue created
- Azure Storage account with containers
- Azure Container Registry
- Docker installed (for local development)
- Azure CLI installed

## 🏗️ Architecture

```
Blob Upload Event
      ↓
Service Bus Queue
      ↓
Processor Container App
      ↓
├── Download .zip from blob storage
├── Extract files
├── Read manifest.json
├── Upload to processed/{submissionId}/
├── [Placeholder] Move to SharePoint
└── Emit processed event
```

## 📁 Project Structure

```
processor/
├── processor.py              # Main processing logic
├── requirements.txt          # Python dependencies
├── Dockerfile               # Container image definition
├── docker-compose.yml       # Local development with Docker Compose
├── deploy-processor.ps1     # Azure deployment script
├── .env.example            # Environment variables template
└── README.md               # This file
```

## 🚀 Quick Start

### Local Development

1. **Copy environment template:**
   ```bash
   cp .env.example .env
   ```

2. **Edit `.env` with your Azure credentials:**
   ```bash
   # Get Service Bus connection string
   az servicebus namespace authorization-rule keys list \
     --namespace-name usabc-servicebus \
     --resource-group rg-rfpo-e108977f \
     --name RootManageSharedAccessKey \
     --query primaryConnectionString -o tsv

   # Get Storage account key
   az storage account keys list \
     --account-name strfpo5kn5bsg47vvac \
     --resource-group rg-rfpo-e108977f \
     --query "[0].value" -o tsv
   ```

3. **Run with Docker Compose:**
   ```bash
   docker-compose up
   ```

4. **Watch logs:**
   ```bash
   docker-compose logs -f
   ```

### Run Locally with Python

```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variables
export SERVICE_BUS_CONNECTION_STRING="your-connection-string"
export AZURE_STORAGE_ACCOUNT_NAME="strfpo5kn5bsg47vvac"
export AZURE_STORAGE_ACCOUNT_URL="https://strfpo5kn5bsg47vvac.blob.core.windows.net"
export AZURE_STORAGE_ACCOUNT_KEY="your-storage-key"

# Run processor
python processor.py
```

## ☁️ Azure Deployment

### Deploy to Azure Container Apps

```powershell
# Deploy with version tag
./deploy-processor.ps1 -Version "v1.0.0"

# Deploy as latest
./deploy-processor.ps1
```

The deployment script will:
1. Build Docker image
2. Push to Azure Container Registry
3. Retrieve configuration from Azure resources
4. Create/update Container App with environment variables

### Monitor Deployment

```powershell
# View live logs
az containerapp logs show \
  --name usabc-processor \
  --resource-group rg-rfpo-e108977f \
  --follow

# Check app status
az containerapp show \
  --name usabc-processor \
  --resource-group rg-rfpo-e108977f \
  --query "properties.runningStatus"
```

## 🔧 Configuration

### Required Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `SERVICE_BUS_CONNECTION_STRING` | Service Bus connection string | `Endpoint=sb://...` |
| `SERVICE_BUS_QUEUE_NAME` | Queue name to consume from | `blob-upload-events` |
| `AZURE_STORAGE_ACCOUNT_NAME` | Storage account name | `strfpo5kn5bsg47vvac` |
| `AZURE_STORAGE_ACCOUNT_URL` | Storage account URL | `https://...blob.core.windows.net` |
| `AZURE_STORAGE_ACCOUNT_KEY` | Storage account key | (use managed identity in production) |

### Optional Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `SOURCE_CONTAINER_NAME` | Source blob container | `usabc-uploads-stage` |
| `PROCESSED_CONTAINER_NAME` | Destination for processed files | `usabc-uploads-processed` |
| `EVENT_GRID_TOPIC_ENDPOINT` | Event Grid topic URL | (none) |
| `EVENT_GRID_TOPIC_KEY` | Event Grid access key | (none) |

### Future SharePoint Configuration

These will be used when SharePoint integration is implemented:

| Variable | Description |
|----------|-------------|
| `SHAREPOINT_SITE_URL` | SharePoint site URL |
| `SHAREPOINT_CLIENT_ID` | App registration client ID |
| `SHAREPOINT_CLIENT_SECRET` | App registration secret |
| `SHAREPOINT_TENANT_ID` | Azure AD tenant ID |

## 📝 Event Processing Flow

### 1. Input Event (from Service Bus)

```json
{
  "topic": "/subscriptions/.../storageAccounts/strfpo5kn5bsg47vvac",
  "subject": "/blobServices/default/containers/usabc-uploads-stage/blobs/uploads/2026/02/13/submission-123.zip",
  "eventType": "Microsoft.Storage.BlobCreated",
  "data": {
    "api": "PutBlob",
    "contentType": "application/zip",
    "contentLength": 524288,
    "url": "https://strfpo5kn5bsg47vvac.blob.core.windows.net/usabc-uploads-stage/uploads/2026/02/13/submission-123.zip"
  }
}
```

### 2. Manifest.json Format

```json
{
  "submissionId": "abc123-2026-02-13",
  "submitterEmail": "user@example.com",
  "uploadTimestamp": "2026-02-13T15:30:00Z",
  "fileCount": 5
}
```

### 3. Output Event (to Event Grid - Optional)

```json
{
  "id": "abc123-2026-02-13-processed-1234567890",
  "subject": "processing/abc123-2026-02-13",
  "eventType": "USABC.Upload.ProcessingCompleted",
  "data": {
    "submissionId": "abc123-2026-02-13",
    "manifestData": { ... },
    "processedFiles": [
      "https://.../usabc-uploads-processed/processed/abc123-2026-02-13/file1.pdf",
      "https://.../usabc-uploads-processed/processed/abc123-2026-02-13/file2.docx"
    ],
    "fileCount": 5,
    "status": "completed"
  }
}
```

## 🧪 Testing

### Test the Complete Flow

1. **Upload a test zip file:**
   ```powershell
   # Create test files
   echo "Test content" > test.txt
   echo '{"submissionId":"test-123","fileCount":1}' > manifest.json
   
   # Create zip
   Compress-Archive -Path test.txt,manifest.json -DestinationPath test-upload.zip
   
   # Upload to blob storage (this triggers the event)
   az storage blob upload \
     --account-name strfpo5kn5bsg47vvac \
     --container-name usabc-uploads-stage \
     --name "test/test-upload.zip" \
     --file test-upload.zip \
     --auth-mode login
   ```

2. **Check Service Bus queue:**
   ```powershell
   az servicebus queue show \
     --namespace-name usabc-servicebus \
     --queue-name blob-upload-events \
     --resource-group rg-rfpo-e108977f \
     --query "countDetails.activeMessageCount"
   ```

3. **Watch processor logs:**
   ```powershell
   # If running locally
   docker-compose logs -f
   
   # If running in Azure
   az containerapp logs show \
     --name usabc-processor \
     --resource-group rg-rfpo-e108977f \
     --follow
   ```

4. **Verify processed files:**
   ```powershell
   az storage blob list \
     --account-name strfpo5kn5bsg47vvac \
     --container-name usabc-uploads-processed \
     --prefix "processed/test-123/" \
     --auth-mode login \
     -o table
   ```

## 🔍 Monitoring

### Structured Logging

The service uses JSON structured logging for easy parsing and monitoring:

```json
{
  "message": "Processing blob event",
  "level": "INFO",
  "timestamp": "2026-02-13T15:30:00Z",
  "submission_id": "abc123",
  "blob_url": "https://...",
  "event_type": "Microsoft.Storage.BlobCreated"
}
```

### Key Log Messages

| Message | Level | Meaning |
|---------|-------|---------|
| `📨 Event received` | INFO | New event from queue |
| `✅ Processing completed successfully` | INFO | File processed successfully |
| `⚠️ Processing failed - message abandoned for retry` | WARNING | Temporary failure, will retry |
| `❌ Processing failed` | ERROR | Fatal error details |

### Azure Monitor Queries

```kusto
// Count processing by submission ID
ContainerAppConsoleLogs_CL
| where ContainerAppName_s == "usabc-processor"
| where Log_s contains "Processing completed"
| summarize count() by submission_id_s

// Find failed processing
ContainerAppConsoleLogs_CL
| where ContainerAppName_s == "usabc-processor"
| where Log_s contains "Processing failed"
| project TimeGenerated, submission_id_s, error_s
```

## 🛠️ Troubleshooting

### Processor Not Receiving Messages

1. **Check Service Bus queue has messages:**
   ```powershell
   az servicebus queue show \
     --namespace-name usabc-servicebus \
     --queue-name blob-upload-events \
     --resource-group rg-rfpo-e108977f
   ```

2. **Verify connection string:**
   ```powershell
   # Test connection
   az servicebus namespace show \
     --name usabc-servicebus \
     --resource-group rg-rfpo-e108977f
   ```

3. **Check container app is running:**
   ```powershell
   az containerapp show \
     --name usabc-processor \
     --resource-group rg-rfpo-e108977f \
     --query "properties.runningStatus"
   ```

### Files Not Extracting

- Ensure uploaded files are valid zip files
- Check blob storage has read permissions
- Verify manifest.json exists in the zip
- Check manifest.json has `submissionId` field

### Dead Letter Queue Messages

```powershell
# View dead letter queue count
az servicebus queue show \
  --namespace-name usabc-servicebus \
  --queue-name blob-upload-events \
  --resource-group rg-rfpo-e108977f \
  --query "countDetails.deadLetterMessageCount"
```

Messages go to dead letter after 10 failed attempts. Common causes:
- Invalid zip file format
- Missing or malformed manifest.json
- Missing submissionId in manifest
- Storage permission issues

## 🔐 Security Best Practices

### Production Recommendations

1. **Use Managed Identity instead of storage keys:**
   ```powershell
   # Enable managed identity on container app
   az containerapp identity assign \
     --name usabc-processor \
     --resource-group rg-rfpo-e108977f \
     --system-assigned
   
   # Grant Storage Blob Data Contributor role
   $principalId = $(az containerapp identity show \
     --name usabc-processor \
     --resource-group rg-rfpo-e108977f \
     --query principalId -o tsv)
   
   az role assignment create \
     --assignee $principalId \
     --role "Storage Blob Data Contributor" \
     --scope "/subscriptions/.../storageAccounts/strfpo5kn5bsg47vvac"
   
   # Remove AZURE_STORAGE_ACCOUNT_KEY from environment
   ```

2. **Use least-privilege Service Bus access:**
   ```powershell
   # Create listen-only SAS policy
   az servicebus queue authorization-rule create \
     --namespace-name usabc-servicebus \
     --queue-name blob-upload-events \
     --resource-group rg-rfpo-e108977f \
     --name ProcessorListener \
     --rights Listen
   ```

3. **Store secrets in Azure Key Vault** (recommended for production)

## 📊 Performance

### Scaling Configuration

The container app auto-scales based on:
- **Min replicas:** 1 (always running)
- **Max replicas:** 5 (scale up under load)
- **Scale rule:** Service Bus queue length

### Resource Allocation

- **CPU:** 0.5 cores per instance
- **Memory:** 1 GB per instance
- **Throughput:** ~10-20 messages/second per instance

### Optimization Tips

- Increase replicas for high-volume processing
- Use Premium Service Bus for dedicated capacity
- Enable blob storage CDN for faster downloads
- Batch process multiple files if latency allows

## 📚 Dependencies

### Python Packages

```
azure-servicebus==7.12.1      # Service Bus client
azure-storage-blob==12.19.1   # Blob Storage client
azure-identity==1.15.0        # Managed identity support
azure-eventgrid==4.18.0       # Event Grid publishing
python-dotenv==1.0.1          # Environment management
python-json-logger==2.0.7     # Structured logging
```

## 🔄 SharePoint Integration (Future)

### Planned Implementation

```python
def move_to_sharepoint(files, submission_id, manifest):
    """Upload extracted files to SharePoint"""
    from office365.sharepoint.client_context import ClientContext
    from office365.runtime.auth.client_credential import ClientCredential
    
    # Authenticate
    credentials = ClientCredential(client_id, client_secret)
    ctx = ClientContext(site_url).with_credentials(credentials)
    
    # Create folder
    target_folder = ctx.web.ensure_folder_path(f"Documents/{submission_id}")
    
    # Upload files
    for filename, content in files.items():
        target_folder.upload_file(filename, content).execute_query()
    
    return True
```

### Required Setup

1. Register Azure AD app for SharePoint access
2. Grant SharePoint API permissions
3. Configure site and library paths
4. Add SharePoint SDK: `pip install Office365-REST-Python-Client`

## 🤝 Contributing

To modify or extend the processor:

1. Update `processor.py` with your changes
2. Test locally with `docker-compose up`
3. Deploy with `./deploy-processor.ps1 -Version "v1.1.0"`

## 📞 Support

**Created by:** John Bouchard  
**Date:** February 13, 2026  
**Contact:** johnbouchard@icloud.com

For issues or questions:
- Check Azure Container App logs
- Review Service Bus dead letter queue
- Verify Event Grid event delivery metrics
