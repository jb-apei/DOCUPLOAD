# Third-Party Integration Guide

## Overview
This guide explains how to integrate your web form with the USABC Upload Service endpoints.

**Production URL:** `https://usabc-upload.livelyforest-d06a98a0.eastus.azurecontainerapps.io`

---

## Security & Virus Scanning

All uploaded files are automatically scanned for malware using **Microsoft Defender for Storage**:
- ✅ Automated scanning on upload
- ✅ Hash reputation analysis
- ✅ Real-time threat detection
- ✅ Automatic quarantine of infected files

### Scan Responses
- **Clean files**: Return `200/201` with `scanStatus: "clean"`
- **Malicious files**: Return `403 Forbidden` with quarantine details
- **Pending scans**: Return `201` with `scanStatus: "pending"` (scan completes in background)

See [VIRUS_SCANNING.md](VIRUS_SCANNING.md) for detailed documentation.

---

## Rate Limits
- **General requests:** 100 per hour per IP address
- **Upload endpoints:** 20 per hour per IP address
- Rate limit headers included in all responses:
  - `X-RateLimit-Limit`: Maximum requests allowed
  - `X-RateLimit-Remaining`: Requests remaining
  - `X-RateLimit-Reset`: Time when limit resets (Unix timestamp)

---

## Endpoint 1: Original Upload (2-Document)

### Endpoint
```
POST /upload
```

### Content-Type
```
multipart/form-data
```

### Required Fields
- `architectureDiagram` (file): PDF file only
- `charter` (file): DOCX file only  
- `tags` (string): JSON string with required `project` tag

### Example: HTML Form
```html
<form action="https://usabc-upload.livelyforest-d06a98a0.eastus.azurecontainerapps.io/upload" 
      method="POST" 
      enctype="multipart/form-data">
  
  <!-- PDF Upload -->
  <label>Architecture Diagram (PDF):</label>
  <input type="file" name="architectureDiagram" accept=".pdf" required>
  
  <!-- DOCX Upload -->
  <label>Charter (DOCX):</label>
  <input type="file" name="charter" accept=".docx" required>
  
  <!-- Tags (Hidden Field) -->
  <input type="hidden" name="tags" value='{"project":"myproject","environment":"prod"}'>
  
  <button type="submit">Upload</button>
</form>
```

### Example: JavaScript Fetch API
```javascript
async function uploadDocuments(pdfFile, docxFile, projectName) {
  const formData = new FormData();
  formData.append('architectureDiagram', pdfFile);
  formData.append('charter', docxFile);
  formData.append('tags', JSON.stringify({
    project: projectName,
    environment: 'prod'  // Optional
  }));
  
  try {
    const response = await fetch('https://usabc-upload.livelyforest-d06a98a0.eastus.azurecontainerapps.io/upload', {
      method: 'POST',
      body: formData
    });
    
    if (!response.ok) {
      const error = await response.json();
      console.error('Upload failed:', error);
      return null;
    }
    
    const result = await response.json();
    console.log('Upload successful:', result);
    return result;
  } catch (err) {
    console.error('Network error:', err);
    return null;
  }
}
```

### Success Response (201 Created)
```json
{
  "submissionId": "uuid",
  "blobPath": "uploads/2026/02/12/<submissionId>.zip",
  "zipSha256": "hex",
  "fileHashes": {
    "architectureDiagramSha256": "hex",
    "charterSha256": "hex"
  },
  "scanStatus": "pending",
  "storageMode": "azure",
  "status": "uploaded"
}
```

### Error Response (400/429/500)
```json
{
  "error": "ValidationFailed",
  "details": [
    {
      "field": "architectureDiagram",
      "message": "Only PDF is allowed and signature must match."
    }
  ]
}
```

---

## Endpoint 2: USABC RFPI Proposal Form

### Endpoint
```
POST /rfpi-submit
```

### Content-Type
```
multipart/form-data
```

### Required Fields
**Applicant Information:**
- `proposalTitle` (string)
- `entityName` (string)
- `entityUEI` (string)
- `email` (email)
- `firstName` (string)
- `lastName` (string)
- `phone` (string)

**Required Files:**
- `rfpiProposal` (file): PDF
- `financialDocuments` (file): PDF
- `additionalDocuments` (file): PDF
- `budgetJustification` (file): Excel (.xls or .xlsx)

**Optional Files:**
- `optionalBudget1` (file): Excel (.xls or .xlsx)
- `optionalBudget2` (file): Excel (.xls or .xlsx)

### Example: HTML Form
```html
<form action="https://usabc-upload.livelyforest-d06a98a0.eastus.azurecontainerapps.io/rfpi-submit" 
      method="POST" 
      enctype="multipart/form-data">
  
  <!-- Applicant Info -->
  <label>Proposal Title:</label>
  <input type="text" name="proposalTitle" required>
  
  <label>Entity Name:</label>
  <input type="text" name="entityName" required>
  
  <label>Entity UEI:</label>
  <input type="text" name="entityUEI" required>
  
  <label>Email:</label>
  <input type="email" name="email" required>
  
  <label>First Name:</label>
  <input type="text" name="firstName" required>
  
  <label>Last Name:</label>
  <input type="text" name="lastName" required>
  
  <label>Phone:</label>
  <input type="tel" name="phone" required>
  
  <!-- Required Files -->
  <label>RFPI Proposal (PDF):</label>
  <input type="file" name="rfpiProposal" accept=".pdf" required>
  
  <label>Financial Documents (PDF):</label>
  <input type="file" name="financialDocuments" accept=".pdf" required>
  
  <label>Additional Documents (PDF):</label>
  <input type="file" name="additionalDocuments" accept=".pdf" required>
  
  <label>Budget Justification (Excel):</label>
  <input type="file" name="budgetJustification" accept=".xls,.xlsx" required>
  
  <!-- Optional Files -->
  <label>Optional Budget 1 (Excel):</label>
  <input type="file" name="optionalBudget1" accept=".xls,.xlsx">
  
  <label>Optional Budget 2 (Excel):</label>
  <input type="file" name="optionalBudget2" accept=".xls,.xlsx">
  
  <button type="submit">Submit Proposal</button>
</form>
```

### Success Response (201 Created)
```json
{
  "submissionId": "uuid",
  "blobPath": "rfpi-submissions/2026/02/12/<submissionId>.zip",
  "zipSha256": "hex",
  "fileCount": 4,
  "scanStatus": "pending",
  "storageMode": "azure",
  "status": "uploaded"
}
```

---

## File Validation Rules

### PDF Files
- **Extension:** `.pdf`
- **Signature Check:** Must start with `%PDF-`
- **Max Size:** 25 MB per file
- **Used For:** Architecture diagrams, RFPI proposals, financial documents, additional documents

### DOCX Files
- **Extension:** `.docx`
- **Signature Check:** Must be valid ZIP container (starts with `PK`) and contain `word/document.xml`
- **Max Size:** 25 MB per file
- **Used For:** Charter documents

### Excel Files
- **Extensions:** `.xls` or `.xlsx`
- **Signature Check:** 
  - XLSX: Must be valid ZIP container (starts with `PK`)
  - XLS: Must be OLE2 compound document (starts with `D0CF11E0A1B11AE1`)
- **Max Size:** 25 MB per file
- **Used For:** Budget justifications

---

## Error Codes

| Code | Error | Description |
|------|-------|-------------|
| 400 | `ValidationFailed` | Missing required fields, invalid file types, or invalid tags |
| 403 | `MalwareDetected` | File failed virus scan and has been quarantined |
| 413 | `PayloadTooLarge` | Total upload size exceeds 50 MB |
| 429 | `RateLimitExceeded` | Too many requests from your IP address |
| 500 | `UploadFailed` | Server error during processing or storage |

### Malware Detection Response (403)
```json
{
  "error": "MalwareDetected",
  "submissionId": "abc-123",
  "scanStatus": "malicious",
  "quarantined": true,
  "message": "File failed security scan and has been quarantined",
  "scanDetails": {
    "scanner": "azure_defender",
    "threat": "Win32/Malware"
  }
}
```

---

## Best Practices

### 1. Validate Before Upload
```javascript
function validateFile(file, type) {
  const maxSize = 25 * 1024 * 1024; // 25 MB
  
  if (file.size > maxSize) {
    alert('File too large. Maximum size is 25 MB.');
    return false;
  }
  
  if (type === 'pdf' && !file.name.endsWith('.pdf')) {
    alert('Please select a PDF file.');
    return false;
  }
  
  if (type === 'docx' && !file.name.endsWith('.docx')) {
    alert('Please select a DOCX file.');
    return false;
  }
  
  if (type === 'excel' && !file.name.match(/\.(xls|xlsx)$/)) {
    alert('Please select an Excel file (.xls or .xlsx).');
    return false;
  }
  
  return true;
}
```

### 2. Handle Rate Limits
```javascript
async function uploadWithRetry(formData, maxRetries = 3) {
  for (let attempt = 1; attempt <= maxRetries; attempt++) {
    try {
      const response = await fetch('https://usabc-upload.livelyforest-d06a98a0.eastus.azurecontainerapps.io/upload', {
        method: 'POST',
        body: formData
      });
      
      if (response.status === 429) {
        const retryAfter = response.headers.get('X-RateLimit-Reset');
        console.log(`Rate limited. Retry after: ${retryAfter}`);
        
        if (attempt < maxRetries) {
          // Wait before retrying
          await new Promise(resolve => setTimeout(resolve, 60000)); // Wait 1 minute
          continue;
        }
      }
      
      return await response.json();
    } catch (err) {
      console.error(`Attempt ${attempt} failed:`, err);
      if (attempt === maxRetries) throw err;
    }
  }
}
```

### 3. Show Upload Progress
```javascript
function showProgress(file) {
  const formData = new FormData();
  formData.append('architectureDiagram', file);
  // ... add other files
  
  const xhr = new XMLHttpRequest();
  
  xhr.upload.addEventListener('progress', (e) => {
    if (e.lengthComputable) {
      const percentComplete = (e.loaded / e.total) * 100;
      console.log(`Upload progress: ${percentComplete.toFixed(2)}%`);
      // Update your UI here
    }
  });
  
  xhr.addEventListener('load', () => {
    if (xhr.status === 201) {
      const result = JSON.parse(xhr.responseText);
      console.log('Upload successful:', result);
    }
  });
  
  xhr.open('POST', 'https://usabc-upload.livelyforest-d06a98a0.eastus.azurecontainerapps.io/upload');
  xhr.send(formData);
}
```

### 4. Store Submission IDs
After successful upload, store the `submissionId` to track submissions:

```javascript
function saveSubmissionRecord(result) {
  const submission = {
    id: result.submissionId,
    timestamp: new Date().toISOString(),
    status: result.scanStatus,
    blobPath: result.blobPath
  };
  
  // Save to your database or local storage
  localStorage.setItem(`submission_${result.submissionId}`, JSON.stringify(submission));
}
```

---

## Testing

### Test with cURL

**Original Form:**
```bash
curl -X POST \
  https://usabc-upload.livelyforest-d06a98a0.eastus.azurecontainerapps.io/upload \
  -F "architectureDiagram=@diagram.pdf" \
  -F "charter=@charter.docx" \
  -F 'tags={"project":"test","environment":"dev"}'
```

**RFPI Form:**
```bash
curl -X POST \
  https://usabc-upload.livelyforest-d06a98a0.eastus.azurecontainerapps.io/rfpi-submit \
  -F "proposalTitle=Test Proposal" \
  -F "entityName=Test Entity" \
  -F "entityUEI=ABC123" \
  -F "email=test@example.com" \
  -F "firstName=John" \
  -F "lastName=Doe" \
  -F "phone=555-1234" \
  -F "rfpiProposal=@proposal.pdf" \
  -F "financialDocuments=@financial.pdf" \
  -F "additionalDocuments=@additional.pdf" \
  -F "budgetJustification=@budget.xlsx"
```

---

## Support

For questions or issues:
- Review logs in Azure Container Apps
- Check rate limit headers in responses
- Ensure files meet validation requirements
- Contact: johnbouchard@icloud.com (service administrator)

**Service Version:** 1.2  
**Last Updated:** February 12, 2026
