"""
Virus scanning module supporting Azure Defender for Storage and ClamAV fallback.

Azure Defender for Storage provides automated malware scanning with hash reputation
analysis. For local development, ClamAV can be used as a fallback.
"""
import os
import time
import logging
from typing import Dict, Tuple, Optional
from azure.storage.blob import BlobServiceClient, BlobClient
from azure.core.exceptions import ResourceNotFoundError

logger = logging.getLogger(__name__)

# Configuration
SCAN_TIMEOUT_SECONDS = int(os.environ.get("SCAN_TIMEOUT_SECONDS", "30"))
SCAN_POLL_INTERVAL = int(os.environ.get("SCAN_POLL_INTERVAL", "2"))
QUARANTINE_CONTAINER = os.environ.get("QUARANTINE_CONTAINER", "quarantine")

class ScanResult:
    """Represents a virus scan result"""
    CLEAN = "clean"
    MALICIOUS = "malicious"
    PENDING = "pending"
    ERROR = "error"
    NO_SCAN = "no_scan_result"

def check_azure_defender_scan_result(blob_client: BlobClient) -> Tuple[str, Optional[Dict]]:
    """
    Check Azure Defender for Storage scan results from blob tags.

    Azure Defender adds a 'Malware Scanning scan result' tag with values:
    - 'Malicious': Threat detected
    - 'No threats found': Clean
    - 'No scan result': Scan not completed or not enabled

    Returns:
        Tuple of (scan_status, scan_details)
        scan_status: "clean", "malicious", "pending", "error", "no_scan_result"
        scan_details: Dict with scan metadata
    """
    try:
        # Get blob tags
        tags = blob_client.get_blob_tags()

        # Check for Azure Defender scan result tag
        defender_result = tags.get("Malware Scanning scan result", "").lower()

        scan_details = {
            "scanner": "azure_defender",
            "raw_result": tags.get("Malware Scanning scan result", ""),
            "scan_time": tags.get("Malware Scanning scan time UTC", "unknown")
        }

        if "malicious" in defender_result:
            logger.warning(f"Azure Defender detected malware in blob: {blob_client.blob_name}")
            return ScanResult.MALICIOUS, scan_details

        elif "no threats found" in defender_result:
            logger.info(f"Azure Defender scan clean: {blob_client.blob_name}")
            return ScanResult.CLEAN, scan_details

        elif "no scan result" in defender_result or not defender_result:
            # Scan not completed yet or Defender not enabled
            return ScanResult.NO_SCAN, scan_details

        else:
            logger.warning(f"Unknown Azure Defender scan result: {defender_result}")
            return ScanResult.NO_SCAN, scan_details

    except Exception as e:
        logger.error(f"Error checking Azure Defender scan result: {str(e)}")
        return ScanResult.ERROR, {"error": str(e)}


def wait_for_scan_result(blob_client: BlobClient, timeout: int = SCAN_TIMEOUT_SECONDS) -> Tuple[str, Optional[Dict]]:
    """
    Wait for Azure Defender to complete scanning and return result.

    Polls blob tags periodically until scan completes or timeout.

    Args:
        blob_client: Azure BlobClient instance
        timeout: Maximum seconds to wait for scan completion

    Returns:
        Tuple of (scan_status, scan_details)
    """
    start_time = time.time()
    attempts = 0

    logger.info(f"Waiting for Azure Defender scan result: {blob_client.blob_name}")

    while (time.time() - start_time) < timeout:
        attempts += 1
        status, details = check_azure_defender_scan_result(blob_client)

        # If we have a definitive result, return it
        if status in [ScanResult.CLEAN, ScanResult.MALICIOUS]:
            logger.info(f"Scan completed after {attempts} attempts ({time.time() - start_time:.1f}s): {status}")
            return status, details

        # If error or still pending, wait and retry
        if attempts >= (timeout / SCAN_POLL_INTERVAL):
            logger.warning(f"Scan timeout after {attempts} attempts ({time.time() - start_time:.1f}s)")
            return ScanResult.PENDING, {"timeout": True, "attempts": attempts}

        time.sleep(SCAN_POLL_INTERVAL)

    return ScanResult.PENDING, {"timeout": True, "attempts": attempts}


def quarantine_blob(blob_client: BlobClient, blob_service_client: BlobServiceClient,
                   scan_result: str, scan_details: Dict) -> Dict:
    """
    Move malicious blob to quarantine container and update metadata.

    Args:
        blob_client: Source blob to quarantine
        blob_service_client: Service client for container operations
        scan_result: Scan result status
        scan_details: Scan metadata

    Returns:
        Dict with quarantine operation results
    """
    try:
        source_blob_name = blob_client.blob_name
        source_container = blob_client.container_name

        # Get quarantine container client
        quarantine_container_client = blob_service_client.get_container_client(QUARANTINE_CONTAINER)

        # Create quarantine container if it doesn't exist
        try:
            if not quarantine_container_client.exists():
                quarantine_container_client.create_container()
                logger.info(f"Created quarantine container: {QUARANTINE_CONTAINER}")
        except Exception as e:
            logger.warning(f"Error checking/creating quarantine container: {e}")

        # Generate quarantine blob name with timestamp
        quarantine_blob_name = f"{time.strftime('%Y/%m/%d')}/quarantined_{source_blob_name.split('/')[-1]}"
        quarantine_blob_client = quarantine_container_client.get_blob_client(quarantine_blob_name)

        # Copy blob to quarantine
        source_url = blob_client.url
        quarantine_blob_client.start_copy_from_url(source_url)

        # Wait for copy to complete
        copy_status_timeout = 30
        copy_start = time.time()
        while (time.time() - copy_start) < copy_status_timeout:
            props = quarantine_blob_client.get_blob_properties()
            if props.copy.status == "success":
                break
            elif props.copy.status in ["failed", "aborted"]:
                raise Exception(f"Copy to quarantine failed: {props.copy.status}")
            time.sleep(1)

        # Update quarantine blob metadata
        quarantine_metadata = {
            "quarantinedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "quarantinedReason": scan_result,
            "originalContainer": source_container,
            "originalPath": source_blob_name,
            "scanDetails": str(scan_details)[:256]  # Azure metadata limit
        }
        quarantine_blob_client.set_blob_metadata(quarantine_metadata)

        # Update quarantine blob tags
        quarantine_tags = {
            "quarantined": "true",
            "scanStatus": "malicious",
            "originalContainer": source_container[:256]  # Tag value limit
        }
        quarantine_blob_client.set_blob_tags(quarantine_tags)

        # Delete original blob
        blob_client.delete_blob()

        logger.info(f"Quarantined blob {source_blob_name} -> {quarantine_blob_name}")

        return {
            "quarantined": True,
            "quarantinePath": quarantine_blob_name,
            "originalPath": source_blob_name
        }

    except Exception as e:
        logger.error(f"Error quarantining blob: {str(e)}", exc_info=True)
        return {
            "quarantined": False,
            "error": str(e)
        }


def scan_clamav_fallback(file_content: bytes, filename: str) -> Tuple[str, Optional[Dict]]:
    """
    Fallback ClamAV scanning for local development.

    Connects to ClamAV daemon (clamd) if available.

    Args:
        file_content: Binary file content to scan
        filename: Original filename for logging

    Returns:
        Tuple of (scan_status, scan_details)
    """
    try:
        import clamd

        # Try to connect to ClamAV daemon
        cd = clamd.ClamdUnixSocket()

        # Scan the content
        scan_result = cd.instream(file_content)

        if scan_result['stream'][0] == 'OK':
            return ScanResult.CLEAN, {
                "scanner": "clamav",
                "filename": filename,
                "result": "clean"
            }
        elif scan_result['stream'][0] == 'FOUND':
            return ScanResult.MALICIOUS, {
                "scanner": "clamav",
                "filename": filename,
                "threat": scan_result['stream'][1]
            }
        else:
            return ScanResult.ERROR, {
                "scanner": "clamav",
                "error": "Unknown scan result"
            }

    except ImportError:
        logger.debug("ClamAV not available (clamd package not installed)")
        return ScanResult.NO_SCAN, {"error": "ClamAV not available"}
    except Exception as e:
        logger.warning(f"ClamAV scan failed: {str(e)}")
        return ScanResult.NO_SCAN, {"error": str(e)}


def update_blob_scan_status(blob_client: BlobClient, scan_status: str, scan_details: Optional[Dict] = None):
    """
    Update blob metadata and tags with scan results.

    Args:
        blob_client: Blob to update
        scan_status: Scan result status
        scan_details: Optional scan metadata
    """
    try:
        # Get current properties
        props = blob_client.get_blob_properties()
        metadata = props.metadata or {}

        # Update metadata
        metadata["scanStatus"] = scan_status
        metadata["scanTime"] = time.strftime("%Y-%m-%dT%H:%M:%SZ")
        if scan_details:
            metadata["scanDetails"] = str(scan_details)[:256]

        blob_client.set_blob_metadata(metadata)

        # Update tags
        tags = blob_client.get_blob_tags()
        tags["scanStatus"] = scan_status
        blob_client.set_blob_tags(tags)

        logger.info(f"Updated scan status for {blob_client.blob_name}: {scan_status}")

    except Exception as e:
        logger.error(f"Error updating blob scan status: {str(e)}")
