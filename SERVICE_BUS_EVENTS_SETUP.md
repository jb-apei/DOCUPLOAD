# Service Bus Event Pipeline - SETUP COMPLETE ✅

**Date:** February 13, 2026  
**Status:** Operational  
**Event Source:** Azure Blob Storage (`strfpo5kn5bsg47vvac`)  
**Event Delivery:** Azure Service Bus Queue

---

## 🎉 What's Been Configured

### Infrastructure Created

| Resource | Name | Purpose | Configuration |
|----------|------|---------|---------------|
| **Service Bus Namespace** | `usabc-servicebus` | Event messaging infrastructure | Standard tier, East US, TLS 1.2 |
| **Main Queue** | `blob-upload-events` | Receives all blob upload events | 10 retries, 5-min lock, 7-day TTL |
| **Dead Letter Queue** | `blob-events-deadletter` | Failed message storage | 14-day retention |
| **Event Subscription** | `storage-to-servicebus` | Routes blob events to queue | BlobCreated events from `usabc-uploads-stage` |

### Event Flow

```
User Uploads File
    ↓
Container App (app.py)
    ↓
Blob Storage (usabc-uploads-stage container)
    ↓
Event Grid (automatic)
    ↓
Service Bus Queue (blob-upload-events)
    ↓
Your Consumer Service
    ↓
(on failure after 10 retries)
    ↓
Dead Letter Queue (blob-events-deadletter)
```

---

## 📊 Queue Configuration Details

### Main Queue: `blob-upload-events`

- **Max Delivery Count:** 10 attempts (then moves to dead letter)
- **Lock Duration:** 5 minutes (time to process before message becomes available again)
- **Message TTL:** 7 days (messages expire after 7 days)
- **Max Message Size:** 256 KB
- **Max Queue Size:** 1 GB
- **Status:** Active ✅

### Dead Letter Queue: `blob-events-deadletter`

- **Message TTL:** 14 days (failed messages retained for 2 weeks)
- **Purpose:** Manual inspection and reprocessing of failed events
- **Lock Duration:** 1 minute

### Event Subscription: `storage-to-servicebus`

- **Event Types:** `Microsoft.Storage.BlobCreated` only
- **Filter:** Container path starts with `/blobServices/default/containers/usabc-uploads-stage/`
- **Retry Policy:** 30 attempts over 24 hours (Event Grid → Service Bus)
- **Status:** Succeeded ✅

---

## 🔑 Connection Information

### Service Bus Namespace

```
Endpoint: https://usabc-servicebus.servicebus.windows.net:443/
Namespace: usabc-servicebus
Location: East US
Resource Group: rg-rfpo-e108977f
```

### Get Connection String

```powershell
# Get primary connection string (least privileged: Listen only)
az servicebus namespace authorization-rule keys list \
  --namespace-name usabc-servicebus \
  --resource-group rg-rfpo-e108977f \
  --name RootManageSharedAccessKey \
  --query primaryConnectionString -o tsv
```

**Recommended:** Create queue-specific SAS policy with only Listen permissions:

```powershell
# Create consumer-specific authorization rule (Listen only)
az servicebus queue authorization-rule create \
  --namespace-name usabc-servicebus \
  --queue-name blob-upload-events \
  --resource-group rg-rfpo-e108977f \
  --name EventConsumer \
  --rights Listen

# Get the connection string
az servicebus queue authorization-rule keys list \
  --namespace-name usabc-servicebus \
  --queue-name blob-upload-events \
  --resource-group rg-rfpo-e108977f \
  --name EventConsumer \
  --query primaryConnectionString -o tsv
```

---

## 📝 Event Payload Example

When a file is uploaded to `usabc-uploads-stage`, this event is sent to the queue:

```json
{
  "topic": "/subscriptions/e108977f-44ed-4400-9580-f7a0bc1d3630/resourceGroups/rg-rfpo-e108977f/providers/Microsoft.Storage/storageAccounts/strfpo5kn5bsg47vvac",
  "subject": "/blobServices/default/containers/usabc-uploads-stage/blobs/uploads/2026/02/13/submission-abc123/document.zip",
  "eventType": "Microsoft.Storage.BlobCreated",
  "id": "9b87886d-21a9-4af3-8ecd-a79f56f96960",
  "data": {
    "api": "PutBlob",
    "clientRequestId": "6643116f-97e3-4620-a8a3-6e4f95f847e6",
    "requestId": "0b16231f-001e-00bd-79c8-2771e2000000",
    "eTag": "0x8D4BCC2E4835CD0",
    "contentType": "application/zip",
    "contentLength": 524288,
    "blobType": "BlockBlob",
    "url": "https://strfpo5kn5bsg47vvac.blob.core.windows.net/usabc-uploads-stage/uploads/2026/02/13/submission-abc123/document.zip",
    "sequencer": "0000000000000000000000000002896300000000000001bc",
    "storageDiagnostics": {
      "batchId": "6643116f-97e3-4620-a8a3-6e4f95f847e6"
    }
  },
  "dataVersion": "",
  "metadataVersion": "1",
  "eventTime": "2026-02-13T15:42:00.000Z"
}
```

**Key Fields:**
- `data.url` - Full blob URL to download
- `data.contentType` - MIME type
- `data.contentLength` - File size in bytes
- `subject` - Full blob path (parse for container and filename)
- `eventTime` - When the upload occurred

---

## 🛠️ Consumer Implementation Examples

### Option 1: Python Consumer (Recommended)

```python
import os
import json
from azure.servicebus import ServiceBusClient
from azure.identity import DefaultAzureCredential

# Connection string from above command
CONNECTION_STRING = os.getenv("SERVICE_BUS_CONNECTION_STRING")
QUEUE_NAME = "blob-upload-events"

def process_blob_event(event_data):
    """Process a single blob upload event"""
    data = event_data['data']
    
    print(f"New file uploaded: {data['url']}")
    print(f"Size: {data['contentLength']} bytes")
    print(f"Content-Type: {data['contentType']}")
    
    # Extract filename from subject
    subject = event_data['subject']
    filename = subject.split('/')[-1]
    
    # Your processing logic here
    # - Download blob
    # - Process file
    # - Update database
    # - Send notifications
    # etc.
    
    return True  # Return True if processed successfully

def main():
    # Create Service Bus client
    with ServiceBusClient.from_connection_string(CONNECTION_STRING) as client:
        with client.get_queue_receiver(QUEUE_NAME) as receiver:
            print(f"Listening for events on queue: {QUEUE_NAME}")
            
            for message in receiver:
                try:
                    # Parse the Event Grid event
                    event = json.loads(str(message))
                    
                    print(f"Received event: {event['eventType']}")
                    
                    # Process the event
                    success = process_blob_event(event)
                    
                    if success:
                        # Complete the message (removes from queue)
                        receiver.complete_message(message)
                        print("✅ Message processed and completed")
                    else:
                        # Abandon to retry
                        receiver.abandon_message(message)
                        print("⚠️  Processing failed, message abandoned for retry")
                        
                except Exception as e:
                    print(f"❌ Error processing message: {e}")
                    # Abandon message to retry (up to 10 times)
                    receiver.abandon_message(message)

if __name__ == "__main__":
    main()
```

**Install dependencies:**
```bash
pip install azure-servicebus azure-identity
```

**Run:**
```bash
export SERVICE_BUS_CONNECTION_STRING="<connection-string>"
python blob_event_consumer.py
```

---

### Option 2: Azure Function Consumer (Serverless)

**function.json:**
```json
{
  "bindings": [
    {
      "name": "message",
      "type": "serviceBusTrigger",
      "direction": "in",
      "queueName": "blob-upload-events",
      "connection": "ServiceBusConnection"
    }
  ]
}
```

**__init__.py:**
```python
import json
import logging
import azure.functions as func

def main(message: func.ServiceBusMessage):
    logging.info('Blob event received from Service Bus')
    
    # Parse Event Grid event
    event = json.loads(message.get_body().decode('utf-8'))
    
    event_type = event['eventType']
    data = event['data']
    
    logging.info(f'Event Type: {event_type}')
    logging.info(f'Blob URL: {data["url"]}')
    logging.info(f'Content Length: {data["contentLength"]}')
    
    # Your processing logic
    try:
        process_uploaded_file(data['url'])
        logging.info('✅ File processed successfully')
    except Exception as e:
        logging.error(f'❌ Error processing file: {e}')
        raise  # Re-raise to trigger retry

def process_uploaded_file(blob_url):
    # Download and process the file
    # Add your business logic here
    pass
```

**local.settings.json:**
```json
{
  "IsEncrypted": false,
  "Values": {
    "AzureWebJobsStorage": "UseDevelopmentStorage=true",
    "FUNCTIONS_WORKER_RUNTIME": "python",
    "ServiceBusConnection": "<your-connection-string>"
  }
}
```

---

### Option 3: .NET Consumer

```csharp
using Azure.Messaging.ServiceBus;
using System.Text.Json;

var connectionString = Environment.GetEnvironmentVariable("SERVICE_BUS_CONNECTION_STRING");
var queueName = "blob-upload-events";

await using var client = new ServiceBusClient(connectionString);
await using var processor = client.CreateProcessor(queueName, new ServiceBusProcessorOptions());

processor.ProcessMessageAsync += async args =>
{
    var body = args.Message.Body.ToString();
    var eventData = JsonSerializer.Deserialize<BlobEvent>(body);
    
    Console.WriteLine($"Processing: {eventData.Data.Url}");
    
    try
    {
        // Your processing logic
        await ProcessBlobAsync(eventData.Data.Url);
        
        // Complete the message
        await args.CompleteMessageAsync(args.Message);
        Console.WriteLine("✅ Message completed");
    }
    catch (Exception ex)
    {
        Console.WriteLine($"❌ Error: {ex.Message}");
        // Abandon to retry
        await args.AbandonMessageAsync(args.Message);
    }
};

processor.ProcessErrorAsync += args =>
{
    Console.WriteLine($"Error: {args.Exception}");
    return Task.CompletedTask;
};

await processor.StartProcessingAsync();
Console.WriteLine("Listening for events... Press any key to exit.");
Console.ReadKey();
await processor.StopProcessingAsync();
```

---

## 🧪 Testing Your Setup

### Test 1: Upload a File

Upload a test file through your web app or directly to blob storage:

```powershell
# Upload test file to trigger event
az storage blob upload \
  --account-name strfpo5kn5bsg47vvac \
  --container-name usabc-uploads-stage \
  --name "test/test-file.txt" \
  --file "test-file.txt" \
  --auth-mode login
```

### Test 2: Check Queue Messages

```powershell
# Peek at messages in queue (doesn't remove them)
az servicebus queue show \
  --namespace-name usabc-servicebus \
  --queue-name blob-upload-events \
  --resource-group rg-rfpo-e108977f \
  --query "countDetails" -o json
```

**Expected output:**
```json
{
  "activeMessageCount": 1,
  "deadLetterMessageCount": 0,
  "scheduledMessageCount": 0
}
```

### Test 3: Monitor Event Delivery

```powershell
# Check Event Grid metrics
az monitor metrics list \
  --resource "/subscriptions/e108977f-44ed-4400-9580-f7a0bc1d3630/resourceGroups/rg-rfpo-e108977f/providers/Microsoft.EventGrid/eventSubscriptions/storage-to-servicebus" \
  --metric DeliverySuccessCount DeliveryFailCount \
  --start-time 2026-02-13T00:00:00Z
```

---

## 📈 Monitoring and Operations

### View Queue Metrics in Azure Portal

1. Navigate to: https://portal.azure.com
2. Search: `usabc-servicebus`
3. Select: **blob-upload-events** queue
4. View: **Metrics** tab

**Key Metrics:**
- Active Messages
- Incoming Messages
- Outgoing Messages
- Dead Letter Messages
- Server Errors

### Set Up Alerts

```powershell
# Alert when dead letter queue has messages
az monitor metrics alert create \
  --name deadletter-messages-alert \
  --resource-group rg-rfpo-e108977f \
  --scopes "/subscriptions/e108977f-44ed-4400-9580-f7a0bc1d3630/resourceGroups/rg-rfpo-e108977f/providers/Microsoft.ServiceBus/namespaces/usabc-servicebus/queues/blob-events-deadletter" \
  --condition "avg DeadletteredMessages > 0" \
  --window-size 5m \
  --evaluation-frequency 1m \
  --action usabc-upload-alerts \
  --description "Dead letter queue has failed messages"
```

### Dead Letter Queue Management

**View dead letter messages:**
```powershell
# List dead lettered messages (requires Service Bus Explorer or code)
# Manual approach: Use Azure Portal → Service Bus → Queue → Dead letter
```

**Reprocess dead letter messages (Python):**
```python
from azure.servicebus import ServiceBusClient

CONNECTION_STRING = "<connection-string>"
QUEUE_NAME = "blob-upload-events"

with ServiceBusClient.from_connection_string(CONNECTION_STRING) as client:
    # Receive from dead letter sub-queue
    with client.get_queue_receiver(QUEUE_NAME, sub_queue="deadletter") as receiver:
        for message in receiver:
            print(f"Dead letter reason: {message.dead_letter_reason}")
            print(f"Dead letter description: {message.dead_letter_error_description}")
            
            # Optionally resubmit to main queue
            # ... your reprocessing logic ...
            
            receiver.complete_message(message)
```

---

## 💰 Cost Estimate

**Service Bus Standard Tier:**
- Base cost: ~$10/month
- Operations: $0.05 per million operations
- Storage: First 1 GB included

**Event Grid:**
- First 100,000 operations: Free
- Additional: $0.60 per million operations

**Estimated Monthly Cost:**
- 10,000 uploads/month: ~$10 (base Service Bus only)
- 100,000 uploads/month: ~$11 (base + minimal operations)
- 1,000,000 uploads/month: ~$16 (base + $6 operations)

---

## 🔧 Management Commands

### View all resources

```powershell
# List queues
az servicebus queue list \
  --namespace-name usabc-servicebus \
  --resource-group rg-rfpo-e108977f \
  -o table

# List event subscriptions
az eventgrid event-subscription list \
  --source-resource-id "/subscriptions/e108977f-44ed-4400-9580-f7a0bc1d3630/resourceGroups/rg-rfpo-e108977f/providers/Microsoft.Storage/storageAccounts/strfpo5kn5bsg47vvac" \
  -o table
```

### Update queue configuration

```powershell
# Increase max delivery count
az servicebus queue update \
  --namespace-name usabc-servicebus \
  --queue-name blob-upload-events \
  --resource-group rg-rfpo-e108977f \
  --max-delivery-count 20

# Increase message TTL
az servicebus queue update \
  --namespace-name usabc-servicebus \
  --queue-name blob-upload-events \
  --resource-group rg-rfpo-e108977f \
  --default-message-time-to-live P14D
```

### Add additional event subscriptions

```powershell
# Subscribe to final container uploads too
az eventgrid event-subscription create \
  --source-resource-id "/subscriptions/e108977f-44ed-4400-9580-f7a0bc1d3630/resourceGroups/rg-rfpo-e108977f/providers/Microsoft.Storage/storageAccounts/strfpo5kn5bsg47vvac" \
  --name final-uploads-to-servicebus \
  --endpoint-type servicebusqueue \
  --endpoint "/subscriptions/e108977f-44ed-4400-9580-f7a0bc1d3630/resourceGroups/rg-rfpo-e108977f/providers/Microsoft.ServiceBus/namespaces/usabc-servicebus/queues/blob-upload-events" \
  --included-event-types Microsoft.Storage.BlobCreated \
  --subject-begins-with "/blobServices/default/containers/usabc-uploads-final/"
```

---

## 🚀 Next Steps

1. **Create Consumer Service**
   - Build Azure Function or standalone service
   - Use one of the code examples above
   - Deploy to Azure or run locally

2. **Set Up Monitoring**
   - Configure alerts for dead letter messages
   - Monitor queue depth
   - Track processing latency

3. **Test End-to-End**
   - Upload test files
   - Verify events arrive in queue
   - Confirm consumer processes them

4. **Scale as Needed**
   - Add multiple consumers (competing consumers pattern)
   - Consider Premium tier for dedicated capacity
   - Enable partitioning for higher throughput

---

## 📚 Additional Resources

- [Service Bus Documentation](https://docs.microsoft.com/azure/service-bus-messaging/)
- [Event Grid Documentation](https://docs.microsoft.com/azure/event-grid/)
- [Azure Storage Events Schema](https://docs.microsoft.com/azure/event-grid/event-schema-blob-storage)
- [Service Bus Python SDK](https://github.com/Azure/azure-sdk-for-python/tree/main/sdk/servicebus)

---

## ✅ Setup Summary

**Status:** OPERATIONAL ✅  
**Created:** February 13, 2026  
**By:** John Bouchard

| Component | Status |
|-----------|--------|
| Service Bus Namespace | ✅ Active |
| Blob Upload Events Queue | ✅ Active |
| Dead Letter Queue | ✅ Active |
| Event Grid Subscription | ✅ Succeeded |
| Event Flow | ✅ Configured |

**You're ready to start consuming blob upload events!** 🎉
