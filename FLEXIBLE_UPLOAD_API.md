# Flexible Upload Endpoint Documentation

## Overview

The `/submit` endpoint provides a flexible, generic file upload service that can be embedded in any form requiring file uploads. Unlike the original form-specific endpoints, this endpoint accepts **any number of files** with **any field names** and supports **multiple file types**.

## Key Features

✅ **Flexible File Handling** - Accept 1 to many files with any field names
✅ **Multiple File Types** - PDF, DOCX, XLSX, XLS, PPTX, PNG, JPG, TXT, CSV
✅ **File Signature Validation** - Validates actual file content, not just extensions
✅ **Virus Scanning** - Automatic malware scanning via Azure Defender
✅ **Organized Storage** - Files packaged as ZIP with manifest
✅ **Custom Tags** - Add metadata for organization and searchability
✅ **Backward Compatible** - Original endpoints remain unchanged

## Supported File Types

| File Type | Extension(s) | MIME Type | Validation Method |
|-----------|--------------|-----------|-------------------|
| PDF | `.pdf` | `application/pdf` | Magic bytes: `%PDF-` |
| Word | `.docx` | `application/vnd.openxmlformats-officedocument.wordprocessingml.document` | ZIP container with `word/document.xml` |
| Excel | `.xlsx`, `.xls` | `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet` | ZIP or OLE2 container |
| PowerPoint | `.pptx` | `application/vnd.openxmlformats-officedocument.presentationml.presentation` | ZIP container with `ppt/` folder |
| Image | `.png`, `.jpg`, `.jpeg` | `image/png`, `image/jpeg` | PNG or JPEG magic bytes |
| Text | `.txt` | `text/plain` | UTF-8 decodable text |
| CSV | `.csv` | `text/csv` | UTF-8 decodable text |

## File Size Limits

- **Per File:** 25 MB
- **Total Upload:** 50 MB

## Endpoint Details

### URL
```
POST /submit
```

### Request Format
- **Content-Type:** `multipart/form-data`
- **Rate Limit:** 20 requests per hour per IP

### Form Fields

#### Required Fields
- At least **one file** must be uploaded (any field name is accepted)

#### Optional Fields
- `formId` (string) - Identifier for your form (default: `"generic-form"`)
- `email` (string) - Email address to receive confirmation (triggers email notification)
- `submittedBy` (string) - Name or identifier of submitter (default: `"anonymous"`)
- `tags` (JSON string) - Custom metadata tags as key-value pairs

**Email Notifications:**  
If you provide an `email` field (or `submittedBy` with an email format), the system will automatically send a confirmation email with:
- Submission ID and timestamp
- List of all uploaded files
- Virus scan status
- Custom tags (if provided)

### Tags Format

Tags must be provided as a JSON string:

```json
{
  "project": "ProjectName",
  "department": "Engineering",
  "environment": "production"
}
```

**Tag Validation Rules:**
- **Keys:** Lowercase letters, numbers, hyphens only. Max 32 characters. Pattern: `^[a-z0-9-]{1,32}$`
- **Values:** Letters, numbers, spaces, underscores, dots, hyphens. Max 64 characters. Pattern: `^[A-Za-z0-9 _.-]{1,64}$`

**Reserved Tag Keys:**
These keys are automatically set by the system. If you use them, they'll be prefixed with `user.`:
- `documentType`, `sourceForm`, `submittedAt`, `submittedBy`
- `submissionId`, `scanStatus`, `scanProvider`, `scanRequestedAt`, `scanCompletedAt`

## Example Usage

### Example 1: Single Document Upload

```html
<form id="myForm">
  <input type="file" name="contract" required>
  <input type="text" name="department" value="Legal">
  <button type="submit">Upload</button>
</form>

<script>
document.getElementById('myForm').addEventListener('submit', async (e) => {
  e.preventDefault();
  
  const formData = new FormData();
  formData.append('contract', document.querySelector('input[name="contract"]').files[0]);
  formData.append('formId', 'legal-contract-form');
  formData.append('submittedBy', 'user@example.com');
  formData.append('tags', JSON.stringify({
    'department': 'Legal',
    'document-class': 'contract'
  }));

  const response = await fetch('/submit', {
    method: 'POST',
    body: formData
  });

  const result = await response.json();
  console.log('Submission ID:', result.submissionId);
});
</script>
```

### Example 2: Multiple Documents

```html
<form id="multiForm">
  <input type="file" name="proposal" required>
  <input type="file" name="budget">
  <input type="file" name="timeline">
  <button type="submit">Upload All</button>
</form>

<script>
document.getElementById('multiForm').addEventListener('submit', async (e) => {
  e.preventDefault();
  
  const formData = new FormData();
  
  // Add all files
  const proposal = document.querySelector('input[name="proposal"]').files[0];
  const budget = document.querySelector('input[name="budget"]').files[0];
  const timeline = document.querySelector('input[name="timeline"]').files[0];
  
  if (proposal) formData.append('proposal', proposal);
  if (budget) formData.append('budget', budget);
  if (timeline) formData.append('timeline', timeline);
  
  formData.append('formId', 'project-submission');
  formData.append('tags', JSON.stringify({
    'project': 'Project-Alpha',
    'fiscal-year': '2026'
  }));

  const response = await fetch('/submit', {
    method: 'POST',
    body: formData
  });

  const result = await response.json();
  if (response.ok) {
    alert(`Success! Submission ID: ${result.submissionId}`);
  } else {
    alert(`Error: ${result.error}`);
  }
});
</script>
```

### Example 3: Using cURL

```bash
curl -X POST http://localhost:5000/submit \
  -F "document=@/path/to/file.pdf" \
  -F "formId=api-test" \
  -F "submittedBy=api-user@example.com" \
  -F 'tags={"project":"TestProject","environment":"dev"}'
```

## Response Format

### Success Response (201 Created)

```json
{
  "submissionId": "123e4567-e89b-12d3-a456-426614174000",
  "blobPath": "submissions/2026/02/13/123e4567-e89b-12d3-a456-426614174000.zip",
  "zipSha256": "a1b2c3d4...",
  "fileCount": 3,
  "files": [
    {
      "field": "contract",
      "originalFileName": "contract.pdf",
      "fileType": "pdf",
      "sizeBytes": 245678,
      "sha256": "e4f5a6b7..."
    }
  ],
  "scanStatus": "clean",
  "scanDetails": {
    "scanResult": "No threats found",
    "completedAt": "2026-02-13T10:30:45-05:00"
  },
  "storageMode": "azure",
  "status": "uploaded",
  "emailSent": true,
  "emailRecipient": "user@example.com"
}
```

**Response Fields:**
- `emailSent` - Only present if email was successfully sent
- `emailRecipient` - Email address where confirmation was sent (only if `emailSent` is true)

### Error Response (400 Bad Request)

```json
{
  "error": "ValidationFailed",
  "details": [
    {
      "field": "document1",
      "filename": "malformed.pdf",
      "message": "Unsupported file type or invalid file signature"
    }
  ]
}
```

### Malware Detected (403 Forbidden)

```json
{
  "error": "MalwareDetected",
  "submissionId": "123e4567-e89b-12d3-a456-426614174000",
  "scanStatus": "malicious",
  "scanDetails": {
    "malwareName": "EICAR-Test-File",
    "scanResult": "Malware detected"
  },
  "quarantined": true,
  "message": "File failed security scan and has been quarantined"
}
```

## Storage Structure

All submissions are packaged as ZIP files with the following structure:

```
submission_2026-02-13T10-30-45_<uuid>.zip
├── files/
│   ├── contract_agreement.pdf
│   ├── budget_spreadsheet.xlsx
│   └── timeline_schedule.docx
└── manifest.json
```

### Manifest.json Structure

```json
{
  "submissionId": "123e4567-e89b-12d3-a456-426614174000",
  "submittedAt": "2026-02-13T10:30:45-05:00",
  "sourceForm": "contract-submission",
  "submittedBy": "user@example.com",
  "tags": {
    "project": "ProjectName",
    "department": "Legal"
  },
  "scan": {
    "scanStatus": "clean",
    "scanDetails": {
      "scanResult": "No threats found"
    }
  },
  "files": [
    {
      "field": "contract",
      "documentType": "contract",
      "originalFileName": "agreement.pdf",
      "storedPathInZip": "files/contract_agreement.pdf",
      "contentTypeVerified": "application/pdf",
      "fileType": "pdf",
      "sizeBytes": 245678,
      "sha256": "e4f5a6b7c8d9...",
      "effectiveTags": {
        "documentType": "contract",
        "sourceForm": "contract-submission",
        "project": "ProjectName",
        "department": "Legal"
      }
    }
  ],
  "zip": {
    "zipSha256": "a1b2c3d4e5f6...",
    "zipSizeBytes": 246789
  }
}
```

## Security Features

1. **File Signature Validation** - Files are validated by content, not just extension
2. **Size Limits** - Per-file and total upload size restrictions
3. **Virus Scanning** - Automatic scanning with Azure Defender for Storage
4. **Quarantine** - Malicious files are automatically quarantined
5. **Rate Limiting** - 20 uploads per hour per IP
6. **Secure Filenames** - All filenames are sanitized
7. **SHA-256 Hashing** - Every file is hashed for integrity verification

## Azure Blob Storage

Files are stored in Azure Blob Storage with the following metadata:

- **Blob Path:** `submissions/YYYY/MM/DD/<submissionId>.zip`
- **Container:** Configured via `AZURE_CONTAINER_NAME` environment variable
- **Metadata:** Includes submission ID, form ID, scan status, file count, and custom tags
- **Index Tags:** Up to 10 tags for efficient querying and filtering

## Migration from Original Endpoints

The original endpoints (`/upload` and `/rfpi-submit`) remain **fully functional** for backward compatibility. You can migrate to the flexible endpoint at your own pace:

| Original Endpoint | Flexible Equivalent |
|-------------------|---------------------|
| `/upload` (architectureDiagram + charter) | `/submit` with any file fields |
| `/rfpi-submit` (multiple required PDFs + Excel) | `/submit` with any file fields |

## Testing

A complete example form is provided in [`example-flexible-form.html`](example-flexible-form.html). To test:

1. Start the Flask application
2. Open `http://localhost:5000/example-flexible-form.html` in your browser
3. Upload one or more files
4. View the detailed response

## Error Handling

The endpoint validates files individually and returns detailed error messages:

- **No files uploaded** - "At least one file is required"
- **Invalid file type** - "Unsupported file type or invalid file signature"
- **File too large** - "File size exceeds maximum"
- **Total size exceeded** - "Total file size exceeds maximum"
- **Invalid tags** - "Invalid tag format"
- **Malware detected** - File quarantined, 403 response

## Integration Best Practices

1. **Always validate file types on the frontend** - Provide clear guidance to users
2. **Show file size limits** - Help users avoid upload failures
3. **Handle all error responses** - Display user-friendly error messages
4. **Use meaningful field names** - They become document types in the manifest
5. **Add relevant tags** - Makes searching and organizing easier
6. **Show upload progress** - Improve user experience for large files
7. **Store the submissionId** - Reference for tracking and retrieval

## Questions?

Refer to the following documentation files:
- [`GETTING_STARTED.md`](GETTING_STARTED.md) - General setup guide
- [`DEPLOYMENT_QUICKREF.md`](DEPLOYMENT_QUICKREF.md) - Deployment reference
- [`VIRUS_SCANNING.md`](VIRUS_SCANNING.md) - Virus scanning details
