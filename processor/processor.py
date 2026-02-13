import os
import json
import zipfile
import tempfile
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from io import BytesIO

from azure.servicebus import ServiceBusClient, ServiceBusMessage
from azure.storage.blob import BlobServiceClient, BlobClient, ContainerClient
from azure.identity import DefaultAzureCredential
from azure.eventgrid import EventGridPublisherClient
from azure.core.credentials import AzureKeyCredential
from pythonjsonlogger import jsonlogger

# Configure structured logging
logger = logging.getLogger(__name__)
logHandler = logging.StreamHandler()
formatter = jsonlogger.JsonFormatter()
logHandler.setFormatter(formatter)
logger.addHandler(logHandler)
logger.setLevel(logging.INFO)


class BlobEventProcessor:
    """Processes blob upload events: downloads, extracts, and reprocesses files"""
    
    def __init__(self):
        # Service Bus configuration
        self.service_bus_connection = os.getenv("SERVICE_BUS_CONNECTION_STRING")
        self.queue_name = os.getenv("SERVICE_BUS_QUEUE_NAME", "blob-upload-events")
        
        # Blob Storage configuration
        self.storage_account_url = os.getenv("AZURE_STORAGE_ACCOUNT_URL")
        self.storage_account_name = os.getenv("AZURE_STORAGE_ACCOUNT_NAME")
        self.storage_account_key = os.getenv("AZURE_STORAGE_ACCOUNT_KEY")
        self.source_container = os.getenv("SOURCE_CONTAINER_NAME", "usabc-uploads-stage")
        self.processed_container = os.getenv("PROCESSED_CONTAINER_NAME", "usabc-uploads-processed")
        
        # Event Grid configuration (for emitting processed events)
        self.eventgrid_endpoint = os.getenv("EVENT_GRID_TOPIC_ENDPOINT")
        self.eventgrid_key = os.getenv("EVENT_GRID_TOPIC_KEY")
        
        # Initialize clients
        self._init_clients()
        
        logger.info("BlobEventProcessor initialized", extra={
            "queue_name": self.queue_name,
            "source_container": self.source_container,
            "processed_container": self.processed_container
        })
    
    def _init_clients(self):
        """Initialize Azure service clients"""
        # Service Bus client
        self.service_bus_client = ServiceBusClient.from_connection_string(
            self.service_bus_connection
        )
        
        # Blob Storage client
        if self.storage_account_key:
            # Use account key authentication
            connection_string = f"DefaultEndpointsProtocol=https;AccountName={self.storage_account_name};AccountKey={self.storage_account_key};EndpointSuffix=core.windows.net"
            self.blob_service_client = BlobServiceClient.from_connection_string(connection_string)
        else:
            # Use managed identity
            credential = DefaultAzureCredential()
            self.blob_service_client = BlobServiceClient(
                account_url=self.storage_account_url,
                credential=credential
            )
        
        # Event Grid client (optional)
        if self.eventgrid_endpoint and self.eventgrid_key:
            self.eventgrid_client = EventGridPublisherClient(
                self.eventgrid_endpoint,
                AzureKeyCredential(self.eventgrid_key)
            )
        else:
            self.eventgrid_client = None
            logger.warning("Event Grid not configured - processed events will not be published")
    
    def download_blob(self, blob_url: str) -> bytes:
        """Download blob content from Azure Storage"""
        logger.info("Downloading blob", extra={"blob_url": blob_url})
        
        # Parse blob URL to get container and blob name
        # URL format: https://{account}.blob.core.windows.net/{container}/{blob}
        url_parts = blob_url.replace(f"https://{self.storage_account_name}.blob.core.windows.net/", "").split("/", 1)
        container_name = url_parts[0]
        blob_name = url_parts[1] if len(url_parts) > 1 else ""
        
        blob_client = self.blob_service_client.get_blob_client(
            container=container_name,
            blob=blob_name
        )
        
        blob_data = blob_client.download_blob()
        content = blob_data.readall()
        
        logger.info("Blob downloaded successfully", extra={
            "size_bytes": len(content),
            "blob_name": blob_name
        })
        
        return content
    
    def extract_zip(self, zip_content: bytes) -> Dict[str, bytes]:
        """Extract zip file and return all files as dict"""
        logger.info("Extracting zip file", extra={"size_bytes": len(zip_content)})
        
        files = {}
        
        try:
            with zipfile.ZipFile(BytesIO(zip_content)) as zip_ref:
                for file_info in zip_ref.filelist:
                    if not file_info.is_dir():
                        file_content = zip_ref.read(file_info.filename)
                        files[file_info.filename] = file_content
                        logger.debug("Extracted file", extra={
                            "filename": file_info.filename,
                            "size_bytes": len(file_content)
                        })
        except zipfile.BadZipFile as e:
            logger.error("Invalid zip file", extra={"error": str(e)})
            raise
        
        logger.info("Zip extraction complete", extra={"file_count": len(files)})
        return files
    
    def read_manifest(self, files: Dict[str, bytes]) -> Optional[Dict]:
        """Read and parse manifest.json from extracted files"""
        manifest_filename = None
        
        # Look for manifest.json (case-insensitive)
        for filename in files.keys():
            if filename.lower().endswith('manifest.json') or filename.lower() == 'manifest.json':
                manifest_filename = filename
                break
        
        if not manifest_filename:
            logger.warning("manifest.json not found in zip file")
            return None
        
        try:
            manifest_content = files[manifest_filename].decode('utf-8')
            manifest = json.loads(manifest_content)
            logger.info("Manifest loaded successfully", extra={
                "submission_id": manifest.get("submissionId", "unknown")
            })
            return manifest
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            logger.error("Failed to parse manifest.json", extra={"error": str(e)})
            return None
    
    def upload_processed_files(self, files: Dict[str, bytes], submission_id: str, 
                              original_metadata: Dict) -> List[str]:
        """Upload extracted files to processed container"""
        logger.info("Uploading processed files", extra={
            "submission_id": submission_id,
            "file_count": len(files)
        })
        
        # Ensure processed container exists
        try:
            container_client = self.blob_service_client.get_container_client(self.processed_container)
            if not container_client.exists():
                container_client.create_container()
                logger.info("Created processed container", extra={"container": self.processed_container})
        except Exception as e:
            logger.warning("Could not verify/create container", extra={"error": str(e)})
        
        uploaded_urls = []
        
        # Upload each file to processed/{submission_id}/
        for filename, content in files.items():
            # Clean filename (remove any directory paths from zip)
            clean_filename = Path(filename).name
            blob_path = f"processed/{submission_id}/{clean_filename}"
            
            blob_client = self.blob_service_client.get_blob_client(
                container=self.processed_container,
                blob=blob_path
            )
            
            # Add metadata from original upload
            metadata = {
                "original_blob_url": original_metadata.get("url", ""),
                "original_submission_id": submission_id,
                "processed_timestamp": datetime.utcnow().isoformat(),
                "processor_version": "1.0.0"
            }
            
            blob_client.upload_blob(
                content,
                overwrite=True,
                metadata=metadata
            )
            
            blob_url = blob_client.url
            uploaded_urls.append(blob_url)
            
            logger.info("File uploaded", extra={
                "file_name": clean_filename,
                "blob_path": blob_path,
                "size_bytes": len(content)
            })
        
        logger.info("All files uploaded successfully", extra={
            "submission_id": submission_id,
            "uploaded_count": len(uploaded_urls)
        })
        
        return uploaded_urls
    
    def move_to_sharepoint(self, files: Dict[str, bytes], submission_id: str, 
                          manifest: Dict) -> bool:
        """
        PLACEHOLDER: Move files to SharePoint
        
        TODO: Implement SharePoint integration
        - Authenticate to SharePoint (using app registration or managed identity)
        - Create folder structure
        - Upload files
        - Set metadata
        """
        logger.info("SharePoint integration placeholder called", extra={
            "submission_id": submission_id,
            "file_count": len(files)
        })
        
        # Placeholder implementation
        logger.warning("⚠️  SharePoint upload not implemented - files remain in blob storage only")
        
        # Future implementation example:
        # from office365.sharepoint.client_context import ClientContext
        # from office365.runtime.auth.client_credential import ClientCredential
        # 
        # site_url = os.getenv("SHAREPOINT_SITE_URL")
        # client_id = os.getenv("SHAREPOINT_CLIENT_ID")
        # client_secret = os.getenv("SHAREPOINT_CLIENT_SECRET")
        # 
        # credentials = ClientCredential(client_id, client_secret)
        # ctx = ClientContext(site_url).with_credentials(credentials)
        # 
        # target_folder = ctx.web.ensure_folder_path(f"Documents/{submission_id}")
        # 
        # for filename, content in files.items():
        #     target_folder.upload_file(filename, content).execute_query()
        
        return True  # Placeholder success
    
    def emit_processed_event(self, submission_id: str, manifest: Dict, 
                            uploaded_files: List[str], event_metadata: Dict):
        """Emit event to Event Grid topic when processing is complete"""
        if not self.eventgrid_client:
            logger.warning("Event Grid not configured - cannot emit processed event")
            return
        
        event = {
            "id": f"{submission_id}-processed-{datetime.utcnow().timestamp()}",
            "subject": f"processing/{submission_id}",
            "dataVersion": "1.0",
            "eventType": "USABC.Upload.ProcessingCompleted",
            "data": {
                "submissionId": submission_id,
                "manifestData": manifest,
                "processedFiles": uploaded_files,
                "fileCount": len(uploaded_files),
                "originalBlobUrl": event_metadata.get("url", ""),
                "processedTimestamp": datetime.utcnow().isoformat(),
                "status": "completed"
            },
            "eventTime": datetime.utcnow().isoformat()
        }
        
        try:
            self.eventgrid_client.send([event])
            logger.info("Processed event emitted to Event Grid", extra={
                "submission_id": submission_id,
                "event_type": event["eventType"]
            })
        except Exception as e:
            logger.error("Failed to emit processed event", extra={
                "submission_id": submission_id,
                "error": str(e)
            })
    
    def process_blob_event(self, event_data: Dict) -> bool:
        """Main processing logic for a blob upload event"""
        try:
            data = event_data['data']
            blob_url = data['url']
            content_type = data.get('contentType', '')
            
            logger.info("Processing blob event", extra={
                "event_type": event_data['eventType'],
                "blob_url": blob_url,
                "content_type": content_type
            })
            
            # Only process zip files
            if not blob_url.endswith('.zip') and content_type != 'application/zip':
                logger.warning("Skipping non-zip file", extra={"blob_url": blob_url})
                return True  # Complete message (not an error, just not applicable)
            
            # Step 1: Download the zip file
            zip_content = self.download_blob(blob_url)
            
            # Step 2: Extract files
            extracted_files = self.extract_zip(zip_content)
            
            if not extracted_files:
                logger.error("No files extracted from zip")
                return False
            
            # Step 3: Read manifest
            manifest = self.read_manifest(extracted_files)
            
            if not manifest:
                logger.error("Could not read manifest.json - cannot determine submission ID")
                return False
            
            submission_id = manifest.get("submissionId")
            if not submission_id:
                logger.error("No submissionId found in manifest")
                return False
            
            logger.info("Processing submission", extra={
                "submission_id": submission_id,
                "file_count": len(extracted_files)
            })
            
            # Step 4: Upload to processed container
            uploaded_files = self.upload_processed_files(
                extracted_files,
                submission_id,
                data
            )
            
            # Step 5: Move to SharePoint (placeholder)
            sharepoint_success = self.move_to_sharepoint(
                extracted_files,
                submission_id,
                manifest
            )
            
            # Step 6: Emit processed event
            self.emit_processed_event(
                submission_id,
                manifest,
                uploaded_files,
                data
            )
            
            logger.info("✅ Processing completed successfully", extra={
                "submission_id": submission_id,
                "processed_files": len(uploaded_files),
                "sharepoint_uploaded": sharepoint_success
            })
            
            return True
            
        except Exception as e:
            logger.error("❌ Processing failed", extra={
                "error": str(e),
                "error_type": type(e).__name__
            }, exc_info=True)
            return False
    
    def start(self):
        """Start consuming messages from Service Bus queue"""
        logger.info("🚀 Starting blob event processor", extra={
            "queue_name": self.queue_name
        })
        
        with self.service_bus_client.get_queue_receiver(self.queue_name) as receiver:
            logger.info("👂 Listening for blob upload events...")
            
            for message in receiver:
                try:
                    # Parse the Event Grid event
                    event = json.loads(str(message))
                    
                    logger.info("📨 Event received", extra={
                        "event_id": event.get('id'),
                        "event_type": event.get('eventType')
                    })
                    
                    # Process the event
                    success = self.process_blob_event(event)
                    
                    if success:
                        # Complete the message (removes from queue)
                        receiver.complete_message(message)
                        logger.info("✅ Message completed")
                    else:
                        # Abandon to retry (up to 10 times per queue config)
                        receiver.abandon_message(message)
                        logger.warning("⚠️  Processing failed - message abandoned for retry")
                        
                except json.JSONDecodeError as e:
                    logger.error("Failed to parse message JSON", extra={"error": str(e)})
                    # Dead letter invalid messages
                    receiver.dead_letter_message(
                        message,
                        reason="InvalidMessageFormat",
                        error_description=str(e)
                    )
                    
                except Exception as e:
                    logger.error("Unexpected error processing message", extra={
                        "error": str(e),
                        "error_type": type(e).__name__
                    }, exc_info=True)
                    # Abandon to retry
                    receiver.abandon_message(message)


def main():
    """Entry point for the processor service"""
    logger.info("=" * 80)
    logger.info("USABC Upload Processor Service Starting")
    logger.info("=" * 80)
    
    # Validate required environment variables
    required_vars = [
        "SERVICE_BUS_CONNECTION_STRING",
        "AZURE_STORAGE_ACCOUNT_NAME",
        "AZURE_STORAGE_ACCOUNT_URL"
    ]
    
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    if missing_vars:
        logger.error("Missing required environment variables", extra={
            "missing_vars": missing_vars
        })
        return
    
    # Optional but recommended
    optional_vars = [
        "EVENT_GRID_TOPIC_ENDPOINT",
        "EVENT_GRID_TOPIC_KEY"
    ]
    
    missing_optional = [var for var in optional_vars if not os.getenv(var)]
    if missing_optional:
        logger.warning("Optional configuration missing", extra={
            "missing_vars": missing_optional
        })
    
    try:
        processor = BlobEventProcessor()
        processor.start()
    except KeyboardInterrupt:
        logger.info("🛑 Processor stopped by user")
    except Exception as e:
        logger.error("❌ Fatal error", extra={
            "error": str(e),
            "error_type": type(e).__name__
        }, exc_info=True)
        raise


if __name__ == "__main__":
    main()
