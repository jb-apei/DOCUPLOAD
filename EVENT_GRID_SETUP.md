# Azure Event Grid Setup for Blob Storage Events

**Purpose:** Enable event-driven architecture to react to file uploads in real-time  
**Approach:** Azure Event Grid (native blob storage event integration)  
**Date:** February 13, 2026

---

## Overview

Azure Event Grid is the recommended solution for blob storage events because it:
- ✅ Natively integrates with Azure Storage (no code changes needed)
- ✅ Delivers events reliably with built-in retry logic
- ✅ Supports filtering (by container, blob prefix, file extensions, etc.)
- ✅ Can route to multiple subscribers (Azure Functions, Logic Apps, webhooks, Event Hubs, Service Bus, etc.)
- ✅ Low latency (typically within seconds)
- ✅ Pay-per-event pricing ($0.60 per million operations - essentially free for most workloads)

---

## Event Types Available

| Event Type | Description | Use Case |
|------------|-------------|----------|
| `Microsoft.Storage.BlobCreated` | Blob created or replaced | Process new uploads |
| `Microsoft.Storage.BlobDeleted` | Blob deleted | Cleanup or audit |
| `Microsoft.Storage.BlobRenamed` | Blob renamed (Data Lake Gen2) | Track file moves |
| `Microsoft.Storage.DirectoryCreated` | Directory created (Data Lake Gen2) | Folder monitoring |
| `Microsoft.Storage.DirectoryRenamed` | Directory renamed (Data Lake Gen2) | Track folder moves |
| `Microsoft.Storage.DirectoryDeleted` | Directory deleted (Data Lake Gen2) | Cleanup tracking |
| `Microsoft.Storage.BlobTierChanged` | Blob tier changed (Hot/Cool/Archive) | Cost optimization tracking |
| `Microsoft.Storage.AsyncOperationInitiated` | Async operation started | Long-running operations |
| `Microsoft.Storage.BlobInventoryPolicyCompleted` | Inventory policy completed | Inventory reports |

**Most Common:** `Microsoft.Storage.BlobCreated` for upload notifications

---

## Architecture Options

### Option 1: Direct Event Subscription (Simplest)
Storage Account → Event Grid → Azure Function / Logic App / Webhook

**Best For:** Simple event handling, single consumer

### Option 2: Event Grid Custom Topic (Most Flexible)
Storage Account → Event Grid → Custom Topic → Multiple Subscribers

**Best For:** Multiple consumers, complex routing, mixing storage + custom events

### Option 3: Event Grid → Service Bus/Event Hubs (Enterprise)
Storage Account → Event Grid → Service Bus/Event Hubs → Multiple Consumers

**Best For:** Guaranteed ordering, dead letter queues, high-throughput scenarios

---

## Option 1: Direct Event Subscription (RECOMMENDED START)

This is the simplest approach - storage events go directly to your endpoint.

### Example: Route to Azure Function

```powershell
# Create event subscription for blob uploads
az eventgrid event-subscription create \
  --source-resource-id "/subscriptions/e108977f-44ed-4400-9580-f7a0bc1d3630/resourceGroups/rg-rfpo-e108977f/providers/Microsoft.Storage/storageAccounts/strfpo5kn5bsg47vvac" \
  --name blob-upload-events \
  --endpoint-type azurefunction \
  --endpoint "/subscriptions/e108977f-44ed-4400-9580-f7a0bc1d3630/resourceGroups/<function-rg>/providers/Microsoft.Web/sites/<function-app>/functions/<function-name>" \
  --included-event-types Microsoft.Storage.BlobCreated \
  --subject-begins-with "/blobServices/default/containers/usabc-uploads-stage/" \
  --advanced-filter data.api stringin CopyBlob PutBlob PutBlockList FlushWithClose
```

**Event Filtering:**
- `--subject-begins-with`: Only events from specific container
- `--subject-ends-with`: Filter by file extension (e.g., `.pdf`, `.zip`)
- `--advanced-filter`: Filter by API operation, blob size, etc.

### Example: Route to Webhook

```powershell
# Create event subscription to webhook endpoint
az eventgrid event-subscription create \
  --source-resource-id "/subscriptions/e108977f-44ed-4400-9580-f7a0bc1d3630/resourceGroups/rg-rfpo-e108977f/providers/Microsoft.Storage/storageAccounts/strfpo5kn5bsg47vvac" \
  --name blob-upload-webhook \
  --endpoint-type webhook \
  --endpoint "https://your-service.com/api/blob-events" \
  --included-event-types Microsoft.Storage.BlobCreated \
  --subject-begins-with "/blobServices/default/containers/usabc-uploads-stage/"
```

**Event Payload Example:**
```json
{
  "topic": "/subscriptions/{subscription-id}/resourceGroups/rg-rfpo-e108977f/providers/Microsoft.Storage/storageAccounts/strfpo5kn5bsg47vvac",
  "subject": "/blobServices/default/containers/usabc-uploads-stage/blobs/uploads/2026/02/13/abc123.zip",
  "eventType": "Microsoft.Storage.BlobCreated",
  "id": "uuid-here",
  "data": {
    "api": "PutBlob",
    "clientRequestId": "uuid-here",
    "requestId": "uuid-here",
    "eTag": "0x8D4BCC2E4835CD0",
    "contentType": "application/zip",
    "contentLength": 524288,
    "blobType": "BlockBlob",
    "url": "https://strfpo5kn5bsg47vvac.blob.core.windows.net/usabc-uploads-stage/uploads/2026/02/13/abc123.zip",
    "sequencer": "00000000000004420000000000028963",
    "storageDiagnostics": {
      "batchId": "uuid-here"
    }
  },
  "dataVersion": "",
  "metadataVersion": "1",
  "eventTime": "2026-02-13T15:30:00.000Z"
}
```

---

## Option 2: Custom Event Grid Topic (For Multiple Consumers)

Create a custom topic that multiple services can subscribe to.

### Step 1: Create Event Grid Topic

```powershell
# Create custom topic
az eventgrid topic create \
  --name usabc-upload-events \
  --resource-group rg-rfpo-e108977f \
  --location eastus

# Get topic endpoint and key
$topicEndpoint = az eventgrid topic show \
  --name usabc-upload-events \
  --resource-group rg-rfpo-e108977f \
  --query "endpoint" -o tsv

$topicKey = az eventgrid topic key list \
  --name usabc-upload-events \
  --resource-group rg-rfpo-e108977f \
  --query "key1" -o tsv
```

### Step 2: Route Storage Events to Custom Topic

```powershell
# Subscribe storage events to custom topic
az eventgrid event-subscription create \
  --source-resource-id "/subscriptions/e108977f-44ed-4400-9580-f7a0bc1d3630/resourceGroups/rg-rfpo-e108977f/providers/Microsoft.Storage/storageAccounts/strfpo5kn5bsg47vvac" \
  --name storage-to-topic \
  --endpoint-type eventhub \
  --endpoint "/subscriptions/e108977f-44ed-4400-9580-f7a0bc1d3630/resourceGroups/rg-rfpo-e108977f/providers/Microsoft.EventGrid/topics/usabc-upload-events" \
  --included-event-types Microsoft.Storage.BlobCreated
```

**Note:** Direct routing from storage to custom topic isn't supported. Use Azure Function as a bridge.

### Step 3: Create Subscriptions to Custom Topic

```powershell
# Subscriber 1: Azure Function for processing
az eventgrid event-subscription create \
  --source-resource-id "/subscriptions/e108977f-44ed-4400-9580-f7a0bc1d3630/resourceGroups/rg-rfpo-e108977f/providers/Microsoft.EventGrid/topics/usabc-upload-events" \
  --name processor-function \
  --endpoint-type azurefunction \
  --endpoint "/subscriptions/e108977f-44ed-4400-9580-f7a0bc1d3630/resourceGroups/<rg>/providers/Microsoft.Web/sites/<app>/functions/<func>"

# Subscriber 2: Webhook for notifications
az eventgrid event-subscription create \
  --source-resource-id "/subscriptions/e108977f-44ed-4400-9580-f7a0bc1d3630/resourceGroups/rg-rfpo-e108977f/providers/Microsoft.EventGrid/topics/usabc-upload-events" \
  --name notification-webhook \
  --endpoint-type webhook \
  --endpoint "https://notification-service.com/webhook"

# Subscriber 3: Service Bus Queue for reliable processing
az eventgrid event-subscription create \
  --source-resource-id "/subscriptions/e108977f-44ed-4400-9580-f7a0bc1d3630/resourceGroups/rg-rfpo-e108977f/providers/Microsoft.EventGrid/topics/usabc-upload-events" \
  --name servicebus-queue \
  --endpoint-type servicebusqueue \
  --endpoint "/subscriptions/e108977f-44ed-4400-9580-f7a0bc1d3630/resourceGroups/<rg>/providers/Microsoft.ServiceBus/namespaces/<namespace>/queues/<queue>"
```

---

## Option 3: Storage → Event Grid → Service Bus (Enterprise Pattern)

Best for guaranteed message delivery, dead letter queues, and ordered processing.

### Step 1: Create Service Bus Namespace and Queue

```powershell
# Create Service Bus namespace (if doesn't exist)
az servicebus namespace create \
  --name usabc-servicebus \
  --resource-group rg-rfpo-e108977f \
  --location eastus \
  --sku Standard

# Create queue for blob events
az servicebus queue create \
  --name blob-upload-events \
  --namespace-name usabc-servicebus \
  --resource-group rg-rfpo-e108977f \
  --max-delivery-count 10 \
  --lock-duration PT5M
```

### Step 2: Subscribe Storage Events to Service Bus Queue

```powershell
# Get Service Bus queue resource ID
$queueId = az servicebus queue show \
  --name blob-upload-events \
  --namespace-name usabc-servicebus \
  --resource-group rg-rfpo-e108977f \
  --query id -o tsv

# Create event subscription
az eventgrid event-subscription create \
  --source-resource-id "/subscriptions/e108977f-44ed-4400-9580-f7a0bc1d3630/resourceGroups/rg-rfpo-e108977f/providers/Microsoft.Storage/storageAccounts/strfpo5kn5bsg47vvac" \
  --name storage-to-servicebus \
  --endpoint-type servicebusqueue \
  --endpoint $queueId \
  --included-event-types Microsoft.Storage.BlobCreated \
  --subject-begins-with "/blobServices/default/containers/usabc-uploads-stage/"
```

### Step 3: Configure Dead Letter Queue (Optional)

```powershell
# Create dead letter queue
az servicebus queue create \
  --name blob-events-deadletter \
  --namespace-name usabc-servicebus \
  --resource-group rg-rfpo-e108977f

# Enable dead letter on event subscription
az eventgrid event-subscription create \
  --source-resource-id "/subscriptions/e108977f-44ed-4400-9580-f7a0bc1d3630/resourceGroups/rg-rfpo-e108977f/providers/Microsoft.Storage/storageAccounts/strfpo5kn5bsg47vvac" \
  --name storage-to-servicebus-with-dl \
  --endpoint-type servicebusqueue \
  --endpoint $queueId \
  --included-event-types Microsoft.Storage.BlobCreated \
  --deadletter-endpoint "/subscriptions/e108977f-44ed-4400-9580-f7a0bc1d3630/resourceGroups/rg-rfpo-e108977f/providers/Microsoft.Storage/storageAccounts/<deadletter-storage>/blobServices/default/containers/<container>"
```

---

## Advanced Filtering Examples

### Filter by File Extension (Only .zip and .pdf files)

```powershell
az eventgrid event-subscription create \
  --source-resource-id "/subscriptions/e108977f-44ed-4400-9580-f7a0bc1d3630/resourceGroups/rg-rfpo-e108977f/providers/Microsoft.Storage/storageAccounts/strfpo5kn5bsg47vvac" \
  --name zip-pdf-only \
  --endpoint "https://your-endpoint.com/webhook" \
  --included-event-types Microsoft.Storage.BlobCreated \
  --subject-ends-with ".zip" --subject-ends-with ".pdf"
```

### Filter by Container and Folder

```powershell
az eventgrid event-subscription create \
  --source-resource-id "/subscriptions/e108977f-44ed-4400-9580-f7a0bc1d3630/resourceGroups/rg-rfpo-e108977f/providers/Microsoft.Storage/storageAccounts/strfpo5kn5bsg47vvac" \
  --name final-uploads-only \
  --endpoint "https://your-endpoint.com/webhook" \
  --included-event-types Microsoft.Storage.BlobCreated \
  --subject-begins-with "/blobServices/default/containers/usabc-uploads-final/blobs/uploads/"
```

### Filter by Blob Size (Files > 1MB)

```powershell
az eventgrid event-subscription create \
  --source-resource-id "/subscriptions/e108977f-44ed-4400-9580-f7a0bc1d3630/resourceGroups/rg-rfpo-e108977f/providers/Microsoft.Storage/storageAccounts/strfpo5kn5bsg47vvac" \
  --name large-files-only \
  --endpoint "https://your-endpoint.com/webhook" \
  --included-event-types Microsoft.Storage.BlobCreated \
  --advanced-filter data.contentLength NumberGreaterThan 1048576
```

---

## Integration with Your Current App

Since your Python app already handles uploads, you have two options:

### Option A: External Event Subscription (Recommended)
Keep your app unchanged, let Event Grid notify other services:

```
User Upload → Container App → Blob Storage → Event Grid → Other Services
                                    ↓
                                Email Confirmation (current)
```

**Pros:** No code changes, separation of concerns  
**Cons:** Can't enrich event data from app context

### Option B: App Publishes to Custom Topic
Your app publishes to Event Grid topic after successful upload:

```python
# In your app.py after successful blob upload
from azure.eventgrid import EventGridPublisherClient
from azure.core.credentials import AzureKeyCredential

# Initialize Event Grid client
topic_endpoint = os.getenv("EVENT_GRID_TOPIC_ENDPOINT")
topic_key = os.getenv("EVENT_GRID_TOPIC_KEY")
client = EventGridPublisherClient(topic_endpoint, AzureKeyCredential(topic_key))

# Publish custom event with enriched data
event = {
    "id": submission_id,
    "subject": f"upload/{submission_id}",
    "dataVersion": "1.0",
    "eventType": "USABC.Upload.FileReceived",
    "data": {
        "submissionId": submission_id,
        "fileName": filename,
        "fileSize": file_size,
        "uploaderEmail": uploader_email,
        "blobUrl": blob_url,
        "timestamp": datetime.utcnow().isoformat(),
        "malwareScanStatus": "Pending"
    },
    "eventTime": datetime.utcnow().isoformat()
}
client.send([event])
```

**Pros:** Full control, enriched event data, custom event types  
**Cons:** Code changes required, app dependency

---

## Monitoring and Testing

### List Event Subscriptions

```powershell
# List all event subscriptions for storage account
az eventgrid event-subscription list \
  --source-resource-id "/subscriptions/e108977f-44ed-4400-9580-f7a0bc1d3630/resourceGroups/rg-rfpo-e108977f/providers/Microsoft.Storage/storageAccounts/strfpo5kn5bsg47vvac" \
  -o table
```

### View Event Delivery Metrics

```powershell
# Check event delivery success rate
az monitor metrics list \
  --resource "/subscriptions/e108977f-44ed-4400-9580-f7a0bc1d3630/resourceGroups/rg-rfpo-e108977f/providers/Microsoft.Storage/storageAccounts/strfpo5kn5bsg47vvac" \
  --metric PublishSuccessCount PublishFailCount DeliverySuccessCount \
  --start-time 2026-02-13T00:00:00Z
```

### Test Event Subscription (Using Event Grid Viewer)

Deploy a test endpoint: https://github.com/Azure-Samples/azure-event-grid-viewer

```powershell
# Deploy Event Grid Viewer (simple web app to see events)
az deployment group create \
  --resource-group rg-rfpo-e108977f \
  --template-uri "https://raw.githubusercontent.com/Azure-Samples/azure-event-grid-viewer/master/azuredeploy.json" \
  --parameters siteName=usabc-event-viewer
```

---

## Cost Estimate

**Event Grid Pricing:**
- First 100,000 operations/month: Free
- After that: $0.60 per million operations
- Storage events: Each blob upload = 1 operation

**Example:** 10,000 uploads/month = FREE  
**Example:** 1 million uploads/month = $0.54

**Service Bus (if used):**
- Standard tier: ~$10/month base + $0.05 per million operations
- Premium tier: ~$677/month for dedicated capacity

---

## Recommended Next Steps

1. **Start Simple:** Create a webhook event subscription to test
2. **Test locally:** Use ngrok or Azure Event Grid Viewer
3. **Choose pattern:** Direct subscription vs Custom Topic vs Service Bus
4. **Implement consumer:** Azure Function, Logic App, or custom service
5. **Add monitoring:** Set up alerts for failed deliveries

---

## Example Use Cases

| Use Case | Recommended Approach |
|----------|---------------------|
| Send notification when file uploaded | Direct subscription → Azure Function |
| Trigger OCR/analysis pipeline | Direct subscription → Azure Function → Durable Functions |
| Multiple downstream systems | Custom Topic → Multiple subscribers |
| Guaranteed processing with retry | Service Bus Queue subscription |
| Real-time dashboard updates | Direct subscription → SignalR |
| Audit logging | Direct subscription → Azure Functions → Cosmos DB |
| Integration with external system | Webhook subscription |

---

## Questions?

Contact: johnbouchard@icloud.com
