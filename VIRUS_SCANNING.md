# Virus Scanning Integration - Azure Defender for Storage

## Overview

The document upload service now includes automated malware scanning using **Microsoft Defender for Storage**. This provides enterprise-grade protection against malicious files with minimal configuration.

## Architecture

### Azure Defender for Storage
- **Automated Scanning**: All uploaded blobs are automatically scanned
- **Hash Reputation Analysis**: Uses Microsoft threat intelligence
- **Real-time Protection**: Scans typically complete within 10-30 seconds
- **Quarantine**: Infected files are automatically moved to a quarantine container

### Scan Flow

1. **Upload** → File uploaded to Azure Blob Storage
2. **Scan** → Azure Defender automatically scans the blob
3. **Result** → Scan result stored in blob tags:
   - `Malware Scanning scan result`: "No threats found" or "Malicious"
   - `Malware Scanning scan time UTC`: Timestamp of scan
4. **Action**:
   - **Clean**: Update blob metadata, return success to client
   - **Malicious**: Move to quarantine container, return 403 error
   - **Pending**: Mark as pending, allow upload (async scan continues)

## Implementation Details

### Scan Results

The scanner module (`scanner.py`) checks blob tags for Azure Defender results:

```python
# Scan statuses
ScanResult.CLEAN      # File is safe
ScanResult.MALICIOUS  # Malware detected
ScanResult.PENDING    # Scan in progress
ScanResult.NO_SCAN    # Defender not enabled
ScanResult.ERROR      # Scan failed
```

### Quarantine Process

When malware is detected:
1. Copy infected blob to `quarantine` container with date prefix
2. Add quarantine metadata:
   - `quarantinedAt`: Timestamp
   - `quarantinedReason`: "malicious"
   - `originalContainer`: Source container
   - `originalPath`: Original blob path
   - `scanDetails`: Scan result details
3. Delete original blob
4. Return 403 error to client with quarantine details

### API Response

**Clean file:**
```json
{
  "submissionId": "uuid",
  "blobPath": "uploads/2026/02/12/uuid.zip",
  "scanStatus": "clean",
  "scanDetails": {
    "scanner": "azure_defender",
    "raw_result": "No threats found",
    "scan_time": "2026-02-12T20:30:45Z"
  },
  "status": "uploaded"
}
```

**Malicious file (403 Forbidden):**
```json
{
  "error": "MalwareDetected",
  "submissionId": "uuid",
  "scanStatus": "malicious",
  "quarantined": true,
  "message": "File failed security scan and has been quarantined",
  "scanDetails": {
    "scanner": "azure_defender",
    "raw_result": "Malicious",
    "threat": "Win32/TrojanDropper"
  }
}
```

## Configuration

### Environment Variables

```bash
# Scan timeout (default: 30 seconds)
SCAN_TIMEOUT_SECONDS=30

# Poll interval for scan results (default: 2 seconds)
SCAN_POLL_INTERVAL=2

# Quarantine container name (default: "quarantine")
QUARANTINE_CONTAINER=quarantine
```

### Enable Azure Defender

1. **Run the setup script:**
   ```powershell
   .\enable-defender.ps1
   ```

2. **Complete manual steps in Azure Portal:**
   - Navigate to Storage Account → Microsoft Defender for Cloud
   - Enable "Malware Scanning"
   - Set monthly GB cap (default: 5000 GB)
   - Save configuration

3. **Verify:**
   ```powershell
   # Check Defender status
   az security pricing show --name StorageAccounts
   
   # Test upload and check blob tags
   az storage blob tag list \
     --account-name strfpo5kn5bsg47vvac \
     --container-name usabc-uploads-stage \
     --name "uploads/2026/02/12/test.zip" \
     --auth-mode login
   ```

## Blob Metadata & Tags

### Metadata
```
scanStatus: "clean" | "malicious" | "pending"
scanTime: ISO 8601 timestamp
scanDetails: JSON string (max 256 chars)
```

### Tags (Azure Blob Index)
```
scanStatus: "clean" | "malicious" | "pending"
Malware Scanning scan result: "No threats found" | "Malicious"
Malware Scanning scan time UTC: Timestamp
```

## Monitoring & Alerts

### Check Quarantined Files
```powershell
# List quarantined blobs
az storage blob list \
  --account-name strfpo5kn5bsg47vvac \
  --container-name quarantine \
  --auth-mode login \
  --output table

# Get quarantine details
az storage blob metadata show \
  --account-name strfpo5kn5bsg47vvac \
  --container-name quarantine \
  --name "2026/02/12/quarantined_uuid.zip" \
  --auth-mode login
```

### Application Logs

The service logs all scan events:
- `SCAN_START`: Scan initiated
- `SCAN_CLEAN`: File passed scan
- `SCAN_MALICIOUS`: Malware detected
- `SCAN_PENDING`: Scan timeout/pending
- `RFPI_SCAN_START/CLEAN/MALICIOUS`: RFPI-specific events

Example:
```
2026-02-12 15:30:45 - SCAN_START: Initiating virus scan for abc-123
2026-02-12 15:30:55 - SCAN_CLEAN: File abc-123 passed virus scan
```

### Azure Monitor Alerts

Set up alerts in Azure Portal:
1. Navigate to Storage Account → Alerts
2. Create alert rule:
   - Signal: "Malware Scanning scan result"
   - Condition: Tag value equals "Malicious"
   - Action: Email security team

## Cost

Microsoft Defender for Storage pricing (as of 2026):
- **Per-storage account**: $10/month
- **Malware scanning**: $0.15 per GB scanned
- **Cap**: Configurable monthly GB limit

Typical costs for this service:
- Base: $10/month
- Scanning: ~$0.15 per GB of uploads
- Example: 100 GB/month = $10 + $15 = $25/month

## Fallback: ClamAV (Local Development)

For local testing without Azure Defender:

1. **Install ClamAV:**
   ```powershell
   # Windows (using Chocolatey)
   choco install clamav
   
   # Start clamd service
   clamd
   ```

2. **Install Python client:**
   ```bash
   pip install clamd
   ```

3. **Test:**
   ```python
   from scanner import scan_clamav_fallback
   
   with open("test.pdf", "rb") as f:
       status, details = scan_clamav_fallback(f.read(), "test.pdf")
   ```

## Security Best Practices

1. ✅ **Enable Defender**: Always enable in production
2. ✅ **Monitor Quarantine**: Regularly review quarantined files
3. ✅ **Set Caps**: Configure monthly GB limits to control costs
4. ✅ **Alert on Malware**: Set up Azure Monitor alerts
5. ✅ **Log Review**: Monitor scan logs for patterns
6. ✅ **Access Control**: Restrict quarantine container access
7. ✅ **Retention Policy**: Set lifecycle rules for quarantine container

## Troubleshooting

### Scan Always Returns "pending"

**Cause**: Azure Defender not enabled or not fully provisioned

**Solution**:
1. Verify Defender is enabled: `az security pricing show --name StorageAccounts`
2. Check malware scanning is enabled in portal
3. Wait 15-30 minutes after enabling for provisioning
4. Test with EICAR test file

### Scan Results Not in Tags

**Cause**: Scanning not enabled at storage account level

**Solution**:
1. Go to Storage Account → Microsoft Defender for Cloud
2. Enable "Malware Scanning"
3. Save and wait 5-10 minutes

### Test with EICAR

Download EICAR test file (safe test virus):
```bash
# This is a standard antivirus test file
curl -o eicar.txt https://secure.eicar.org/eicar.com.txt
```

Upload via API - should be quarantined with scanStatus="malicious"

## API Integration

Third-party integrators should handle scan responses:

```javascript
const response = await fetch('/upload', {
  method: 'POST',
  body: formData
});

if (response.status === 403) {
  const error = await response.json();
  if (error.error === 'MalwareDetected') {
    alert('File failed security scan. Please check the file and try again.');
    console.error('Scan details:', error.scanDetails);
  }
} else if (response.ok) {
  const result = await response.json();
  console.log('Scan status:', result.scanStatus);
  if (result.scanStatus === 'pending') {
    // Scan still in progress - file was uploaded
    console.log('File uploaded, scan completing in background');
  }
}
```

## References

- [Microsoft Defender for Storage](https://learn.microsoft.com/en-us/azure/defender-for-cloud/defender-for-storage-introduction)
- [Malware Scanning in Azure](https://learn.microsoft.com/en-us/azure/defender-for-cloud/defender-for-storage-malware-scan)
- [Azure Blob Tags](https://learn.microsoft.com/en-us/azure/storage/blobs/storage-blob-tags)
