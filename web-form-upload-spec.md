# Web Form Spec: Secure Document Upload Service

**Version:** 1.2  
**Last Updated:** February 12, 2026  
**Status:** Production - Deployed to Azure Container Apps

## Overview
This service provides secure web forms for document upload with validation, hashing, and Azure Blob Storage integration.

**Deployed Services:**
- **Original Form:** 2-document upload (Architectural Diagram PDF + Charter DOCX)
- **USABC RFPI Form:** Multi-document proposal submission (3 PDFs + Excel files)

Each submission:

- Validates file types by **signature**, not just MIME/extension
- Validates user tags (original form) or applicant metadata (RFPI form)
- Computes **SHA-256 hashes for each file AND the final zip**
- Packages files + `manifest.json` into a zip
- Uploads to **Azure Blob Storage** with proper metadata and tags
- Uses **Eastern Time (America/New_York)** for directory structure and timestamps
- Supports **asynchronous malware scanning** (scanStatus=pending until confirmed clean)

**Production URL:** https://usabc-upload.livelyforest-d06a98a0.eastus.azurecontainerapps.io/

---

## Form Types

### Form 1: Original 2-Document Upload
**Endpoint:** `/upload`  
**Web UI:** `/` (index.html)

Accepts exactly two uploads:
1) **Architectural Diagram** (**PDF only**)  
2) **Charter** (**DOCX only**)

### Form 2: USABC RFPI Proposal Form
**Endpoint:** `/rfpi-submit`  
**Web UI:** `/rfpi-form`

Accepts multiple uploads:
- **Required:**
  - RFPI Proposal (PDF)
  - Financial Documents (PDF)
  - Additional Required Proposal Documents (PDF)
  - Budget Justification (Excel: .xls or .xlsx)
- **Optional:**
  - Budget Justification: Optional 2nd Tier Subrecipient (1) (Excel)
  - Budget Justification: Optional 2nd Tier Subrecipient (2) (Excel)

---

## Implementation Status

### ✅ Completed Features
- ✅ Original 2-document upload form (PDF + DOCX)
- ✅ USABC RFPI proposal form (multi-file support)
- ✅ File type validation by signature (PDF, DOCX, Excel)
- ✅ SHA-256 hashing for individual files and zip packages
- ✅ Manifest.json generation with submission details
- ✅ Azure Blob Storage integration with metadata and index tags
- ✅ Eastern Time (EST/EDT) for directory structure and timestamps
- ✅ Reserved tag collision handling (user.* prefix)
- ✅ File size tracking in manifest
- ✅ Normalized blob index tags (lowercase, underscore)
- ✅ Docker containerization
- ✅ Deployed to Azure Container Apps (v1.2)
- ✅ Embeddable widget (static/widget.js)

### ⚠️ Implemented with Temporary Configuration
- ⚠️ Storage Account Key authentication (should migrate to Managed Identity)
- ⚠️ No authentication on web forms (anonymous access allowed)
- ⚠️ CORS allows all origins

### ❌ Not Yet Implemented
- ❌ Microsoft Entra ID (Azure AD) authentication
- ❌ Authorization rules and role-based access
- ❌ Malware scanning integration (scanStatus remains "pending")
- ❌ Rate limiting
- ❌ Application Insights monitoring
- ❌ Custom domain configuration
- ❌ Quarantine handling for infected files
- ❌ Scanner worker service

---

## Scope

### In Scope (Implemented)
- Two web forms with different upload requirements
- Submission-level metadata (tags for original form, applicant info for RFPI)
- Strict validation (extension + signature)
- Dual hashing: per-file SHA-256 and zip SHA-256
- Zip creation with safe internal paths
- Upload to Azure Blob Storage
- Blob Metadata + Blob Index Tags
- Timezone-aware timestamps (Eastern Time)
- Multi-file upload support (RFPI form)

### Out of Scope (Current Version)
- Resumable/chunked uploads
- Direct-to-blob browser upload via SAS
- Auto-tagging via ML/LLM
- Automatic document parsing / OCR
- UI progress bars
- Real-time malware scanning
- Authentication and authorization

---

## High-Level Architecture
**Browser UI** → **Upload API (server)** → **Zip builder** → **Azure Blob Storage**  
                                                     ↘ **Scan request event** → **Scanner Worker** → updates blob tags/metadata

### Design Principle
The browser is an untrusted client. The API is the security boundary.

---

## Authentication & Authorization

### Current Status (v1.2)
**⚠️ No Authentication Currently Implemented**
- Both forms accept anonymous uploads
- No user identity captured
- Should be secured before wider deployment

### Recommended (Future Implementation)
#### Authentication
- Use **Microsoft Entra ID (Azure AD)** for the web app and API
- API should reject anonymous requests
- Capture authenticated user identity in manifest

#### Authorization
- Enforce authorization rules:
  - User must be in allowed tenant
  - User must be in a specific group (optional)
  - User must have an application role claim (recommended)

---

## Timezone Handling

### Implementation (v1.2)
- **Timezone:** America/New_York (handles EST/EDT automatically)
- **Directory Structure:** Uses Eastern Time for blob paths
  - Example: `/uploads/2026/02/12/{submissionId}.zip`
  - Example: `/rfpi-submissions/2026/02/13/{submissionId}.zip`
- **Timestamps:** ISO 8601 format with timezone offset
  - Example: `2026-02-12T19:36:15.734836-05:00`
- **Configuration:**
  - Dockerfile sets `TZ=America/New_York`
  - Python uses `ZoneInfo("America/New_York")`
  - Package: `tzdata` (included in requirements.txt)

---

## UX Requirements

### Form 1: Original Upload (Upload Project Artifacts)

#### Form Layout
Title: **Upload Project Artifacts**

##### Section A: Architectural Diagram (Required)
- Label: **Architectural Diagram (PDF)**
- Input name: `architectureDiagram`
- Accept: `.pdf` only
- Help text: "Upload a PDF architecture diagram."

##### Section B: Charter (Required)
- Label: **Charter (DOCX)**
- Input name: `charter`
- Accept: `.docx` only
- Help text: "Upload a DOCX charter document."

### Form 2: USABC RFPI Proposal Form

#### Form Layout
Title: **USABC RFPI Proposal Form**

##### Section A: Applicant Submission (Required Fields)
- Proposal Title (text, required)
- Entity Name (text, required)
- Entity UEI or in-progress (text, required)
- Email (email, required)
- Name: First and Last (text, required)
- Phone (tel, required)

##### Section B: Required Documents
- **RFPI Proposal** (PDF, required)
  - Input name: `rfpiProposal`
  - Help: "1 PDF, maximum of 25 pages - see sections 3.1-3.6 of the RFPI"
- **Financial Documents** (PDF, required)
  - Input name: `financialDocuments`
  - Help: "1 PDF - see section 4.1 of the RFPI"
- **Additional Required Proposal Documents** (PDF, required)
  - Input name: `additionalDocuments`
  - Help: "1 PDF - see sections 4.2-4.9 of the RFPI"
- **Budget Justification** (Excel, required)
  - Input name: `budgetJustification`
  - Accept: `.xls, .xlsx`
  - Help: "1 Excel file - see section 4.10 of the RFPI"

##### Section C: Optional Documents
- **Budget Justification: Optional 2nd Tier Subrecipient (1)** (Excel, optional)
  - Input name: `optionalBudget1`
  - Accept: `.xls, .xlsx`
- **Budget Justification: Optional 2nd Tier Subrecipient (2)** (Excel, optional)
  - Input name: `optionalBudget2`
  - Accept: `.xls, .xlsx`

##### Section D: Acknowledgments (Required)
- Checkbox: "I understand that all information submitted in response to this USABC RFPI shall be treated on a non-confidential basis."
- Checkbox: "The content of this application is complete"

---

## Metadata Tagging (Submission-Level)

### Tag Picker UI
- Multi-select tags from an allowlist (config or API)
- Optional: Add custom tags (key/value)
- All tags apply to the submission and are inherited by both files.

### Required Tags (MVP)
- `project` is required.

### Tag Validation (Required)
- Key:
  - lowercase, 1–32 chars
  - regex: `^[a-z0-9-]{1,32}$`
- Value:
  - 1–64 chars
  - regex: `^[A-Za-z0-9 _.-]{1,64}$`
- Max tags: 25 (configurable)

### Reserved/System Keys (Cannot be overridden)
System-owned keys include:
- `documentType`
- `sourceForm`
- `submittedAt`
- `submittedBy`
- `submissionId`
- `scanStatus`
- `scanProvider`
- `scanRequestedAt`
- `scanCompletedAt`

Collision handling rule:
- If the user submits a reserved key, store it as `user.<key>`.

---

## Strict File Type Rules

### Allowed Types
#### Original Form
| Field | Allowed Extension | Verified Content Type |
|------|-------------------|-----------------------|
| `architectureDiagram` | `.pdf` | `application/pdf` |
| `charter` | `.docx` | `application/vnd.openxmlformats-officedocument.wordprocessingml.document` |

#### RFPI Form
| Field | Allowed Extension | Verified Content Type |
|------|-------------------|-----------------------|
| `rfpiProposal` | `.pdf` | `application/pdf` |
| `financialDocuments` | `.pdf` | `application/pdf` |
| `additionalDocuments` | `.pdf` | `application/pdf` |
| `budgetJustification` | `.xls, .xlsx` | Excel (XLS or XLSX) |
| `optionalBudget1` | `.xls, .xlsx` | Excel (XLS or XLSX) |
| `optionalBudget2` | `.xls, .xlsx` | Excel (XLS or XLSX) |

### Signature Verification (Required)
Do **not** trust the browser-provided MIME type.

The server must verify:

#### PDF Signature
- Must begin with: `%PDF-`

#### DOCX Signature & Structure
- DOCX is a ZIP container:
  - Must begin with: `PK`
- Must contain:
  - `word/document.xml`

#### Excel Signature
- **XLSX (modern format):**
  - Must begin with: `PK` (ZIP container)
- **XLS (legacy format):**
  - Must begin with: `D0CF11E0A1B11AE1` (OLE2 compound document)

If any mismatch occurs, reject with `400 ValidationFailed`.

---

## Size Limits (Required)
Configurable limits (recommended defaults):

- Per file max: `25 MB`
- Total submission max: `50 MB`

Enforce at:
- reverse proxy / gateway (max request body)
- API (authoritative)

---

## Filename Handling (Required)
- Never trust user filenames for paths.
- Zip entry names must be fixed and safe:
  - `files/architecture-diagram.pdf`
  - `files/charter.docx`

Store original filenames only as escaped strings in `manifest.json`.

---

## Hashing Requirements (Both Required)

### Hash Algorithm
- SHA-256

### 1) Per-File Hashing (Required)
The API must compute SHA-256 for:
- the Architectural Diagram PDF
- the Charter DOCX

Store each hash in the file entry of `manifest.json`.

### 2) Zip Hashing (Required)
After building the zip (including the manifest), compute:
- `zipSha256`

Store in:
- `manifest.json`
- blob metadata (`zipSha256`)
- API response

---

## Zip Output

### Zip Naming Convention
`upload_{yyyy-MM-ddTHH-mm-ssZ}_{submissionId}.zip`

### Zip Contents (Required)
The zip must contain:

- `files/architecture-diagram.pdf`
- `files/charter.docx`
- `manifest.json`

### Zip Slip Protection (Required)
- Do not include any user-controlled path segments.
- Do not include original filenames as zip entry names.

---

## manifest.json (Required)

### Goals
- Provide traceability and auditability
- Capture hashes, sizes, verified types, and effective tags
- Provide a safe, machine-readable contract for downstream services

### Example: Original Form Manifest
```json
{
  "submissionId": "uuid",
  "submittedAt": "2026-02-12T19:32:10.734836-05:00",
  "submittedBy": "user@example.com",
  "tags": {
    "project": "SIS",
    "domain": "student",
    "environment": "dev"
  },
  "scan": {
    "scanStatus": "pending"
  },
  "files": [
    {
      "field": "architectureDiagram",
      "documentType": "architecture-diagram",
      "originalFileName": "Target Architecture.pdf",
      "storedPathInZip": "files/architecture-diagram.pdf",
      "contentTypeVerified": "application/pdf",
      "sizeBytes": 1234567,
      "sha256": "hex",
      "effectiveTags": {
        "documentType": "architecture-diagram",
        "sourceForm": "upload-project-artifacts",
        "project": "SIS",
        "domain": "student",
        "environment": "dev"
      }
    },
    {
      "field": "charter",
      "documentType": "charter",
      "originalFileName": "SIS Charter.docx",
      "storedPathInZip": "files/charter.docx",
      "contentTypeVerified": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
      "sizeBytes": 234567,
      "sha256": "hex",
      "effectiveTags": {
        "documentType": "charter",
        "sourceForm": "upload-project-artifacts",
        "project": "SIS",
        "domain": "student",
        "environment": "dev"
      }
    }
  ],
  "zip": {
    "zipSha256": "hex",
    "zipSizeBytes": 1500000
  }
}
```

### Example: RFPI Form Manifest
```json
{
  "submissionId": "uuid",
  "submittedAt": "2026-02-12T19:36:15.734836-05:00",
  "formType": "usabc-rfpi-proposal",
  "applicantInfo": {
    "proposalTitle": "Advanced Battery Technology Research",
    "entityName": "Example University",
    "entityUEI": "ABC123456789",
    "email": "researcher@example.edu",
    "firstName": "Jane",
    "lastName": "Doe",
    "phone": "555-1234"
  },
  "rfpiInfo": {
    "title": "",
    "category": ""
  },
  "scan": {
    "scanStatus": "pending"
  },
  "files": [
    {
      "field": "rfpiProposal",
      "documentType": "rfpi-proposal",
      "originalFileName": "RFPI_Proposal.pdf",
      "storedPathInZip": "files/rfpi-proposal.pdf",
      "sizeBytes": 2345678,
      "sha256": "hex"
    },
    {
      "field": "financialDocuments",
      "documentType": "financial-documents",
      "originalFileName": "Financials.pdf",
      "storedPathInZip": "files/financial-documents.pdf",
      "sizeBytes": 1234567,
      "sha256": "hex"
    },
    {
      "field": "additionalDocuments",
      "documentType": "additional-documents",
      "originalFileName": "Additional.pdf",
      "storedPathInZip": "files/additional-documents.pdf",
      "sizeBytes": 987654,
      "sha256": "hex"
    },
    {
      "field": "budgetJustification",
      "documentType": "budget-justification",
      "originalFileName": "Budget.xlsx",
      "storedPathInZip": "files/budget-justification.xlsx",
      "sizeBytes": 456789,
      "sha256": "hex"
    }
  ],
  "zip": {
    "zipSha256": "hex",
    "zipSizeBytes": 5500000
  }
}
```

---

## Azure Blob Storage Requirements

### Storage Targets
- **Container:** `usabc-uploads-stage` (configured via environment variable)
- **Blob path conventions:**
  - Original form: `uploads/{yyyy}/{MM}/{dd}/{submissionId}.zip`
  - RFPI form: `rfpi-submissions/{yyyy}/{MM}/{dd}/{submissionId}.zip`

**Timezone:** Dates use Eastern Time (America/New_York)

Examples:
- `uploads/2026/02/12/2f3a9c2b-4a9f-4d1a-a9c0-0f0b7a6f1c1b.zip`
- `rfpi-submissions/2026/02/12/8e4b2c1d-9f3a-4e2a-b7c1-3d5e8f9a2b4c.zip`

---

## Storage Authentication

### Current Implementation (v1.2)
**⚠️ Using Storage Account Keys (Temporary)**
- Environment variable: `AZURE_STORAGE_ACCOUNT_KEY`
- Easier for initial deployment but not recommended for production
- Should migrate to Managed Identity

### Recommended (Future)
- Upload API uses **Managed Identity**
- Role assignment:
  - `Storage Blob Data Contributor` scoped to the container
- Remove storage account keys from app settings
- More secure, no credential rotation needed

---

## Encryption (Required)
- Storage Service Encryption enabled (default)
- Optional: Customer Managed Keys (CMK) via Key Vault (policy-driven)

---

## Blob Metadata vs Blob Index Tags

### Blob Metadata (Required)
Store stable submission attributes:

- `submissionId`
- `sourceForm`
- `submittedAt`
- `submittedBy`
- `docTypes` = `architecture-diagram,charter`
- `zipSha256`
- `scanStatus` = `pending|clean|infected|error`

### Blob Index Tags (Recommended)
Store queryable tags:

- `project`
- `domain`
- `environment`
- `sourceForm`
- `submittedBy` (normalized)
- `scanStatus`

Normalization:
- lowercase
- spaces → `_`
- enforce Azure tag constraints

---

## Malware Scanning Hook (Not Yet Implemented)

### Design Goal
Uploads are stored quickly, but **nothing downstream may trust the content** until scan completion.

### Current Status (v1.2)
**❌ Scanner Not Implemented**
- All uploads marked `scanStatus=pending`
- No scanner worker service deployed
- No scan status updates occur
- Downstream consumers should check scanStatus but currently no enforcement

### Planned Flow
1) API uploads zip to Blob Storage.
2) API sets:
   - blob metadata: `scanStatus=pending`
   - blob index tag: `scanStatus=pending`
3) API emits a scan request message/event containing:
   - `submissionId`
   - `container`
   - `blobPath`
   - `zipSha256`
   - `submittedBy`
   - `submittedAt`
4) Scanner worker downloads the zip (streaming) and scans.
5) Scanner updates:
   - `scanStatus=clean|infected|error`
   - `scanCompletedAt=<timestamp>`
   - `scanProvider=<provider-name>`

### Enforcement Rule (Critical)
Any downstream consumer (unzipping, parsing, indexing) must enforce:

- Only proceed if `scanStatus=clean`
- If `pending` → retry later
- If `infected` → quarantine and deny access
- If `error` → treat as unsafe until resolved

### Quarantine Handling (Recommended)
If infected:
- move blob to a quarantine container OR
- apply a `quarantine=true` tag and enforce access controls

---

## API Contract

### Endpoint 1: Original Form Upload
**Route:** `POST /upload`

**Auth:** Currently none (⚠️ should add Entra ID Bearer Token)

**Content type:** `multipart/form-data`

**Parts:**
- `architectureDiagram` (file, required)
- `charter` (file, required)
- `tags` (stringified JSON, required because `project` required)

**Example `tags`:**
```json
{
  "project": "SIS",
  "domain": "student",
  "environment": "dev"
}
```

**Response (201 Created):**
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
  "status": "uploaded"
}
```

### Endpoint 2: RFPI Form Submission
**Route:** `POST /rfpi-submit`

**Auth:** Currently none (⚠️ should add Entra ID Bearer Token)

**Content type:** `multipart/form-data`

**Parts:**
- `proposalTitle` (text, required)
- `entityName` (text, required)
- `entityUEI` (text, required)
- `email` (email, required)
- `firstName` (text, required)
- `lastName` (text, required)
- `phone` (tel, required)
- `rfpiProposal` (PDF file, required)
- `financialDocuments` (PDF file, required)
- `additionalDocuments` (PDF file, required)
- `budgetJustification` (Excel file, required)
- `optionalBudget1` (Excel file, optional)
- `optionalBudget2` (Excel file, optional)

**Response (201 Created):**
```json
{
  "submissionId": "uuid",
  "blobPath": "rfpi-submissions/2026/02/12/<submissionId>.zip",
  "zipSha256": "hex",
  "fileCount": 4,
  "scanStatus": "pending",
  "status": "uploaded",
  "storageMode": "azure"
}
```

---

## Error Handling

### Common HTTP Codes
- `400 ValidationFailed`
- `401 Unauthorized`
- `403 Forbidden`
- `413 PayloadTooLarge`
- `429 TooManyRequests`
- `500 UploadFailed`

### Error Schema
```json
{
  "error": "ValidationFailed",
  "details": [
    { "field": "architectureDiagram", "message": "Only PDF is allowed and signature must match." }
  ]
}
```

---

## Security Requirements

### Current Implementation (v1.2)
#### ✅ Implemented
- ✅ Server-side input validation
- ✅ File signature verification (PDF, DOCX, Excel)
- ✅ Safe zip entry paths (no user-controlled segments)
- ✅ SHA-256 hashing for auditability
- ✅ Structured logging (submissionId, sizes, types, blob paths)
- ✅ File contents not logged

#### ⚠️ Uses Temporary/Weak Configuration
- ⚠️ No authentication (anonymous access allowed)
- ⚠️ No rate limiting
- ⚠️ CORS allows all origins
- ⚠️ Storage account key authentication (not Managed Identity)

#### ❌ Not Yet Implemented
- ❌ Microsoft Entra ID authentication
- ❌ Authorization rules
- ❌ Per-user rate limits
- ❌ CSRF protection (if using cookie-based auth)
- ❌ Restricted CORS to trusted origins
- ❌ Least privilege with Managed Identity

### Recommended Security Enhancements
1. **Add Authentication:** Implement Entra ID Bearer Token validation
2. **Rate Limiting:** Per-user and per-IP limits
3. **CORS:** Restrict to specific trusted origins
4. **Managed Identity:** Remove storage account keys
5. **Authorization:** Role-based access control
6. **Request Limits:** Already enforced at gateway and API

---

## Acceptance Criteria

### ✅ Completed (v1.2)
- ✅ Two forms deployed and functional:
  - Original: Exactly two files (PDF + DOCX) with signature validation
  - RFPI: Multiple files (3 PDFs + Excel) with signature validation
- ✅ Excel file validation (XLSX and XLS formats)
- ✅ Tag validation with reserved key collision handling (original form)
- ✅ Applicant metadata captured (RFPI form)
- ✅ Zip contains files with fixed internal names + manifest.json
- ✅ SHA-256 computed for all files and the zip
- ✅ Zip uploaded to Blob Storage with Eastern Time timestamps
- ✅ Blob metadata and index tags are set
- ✅ All blobs marked `scanStatus=pending`
- ✅ Deployed to Azure Container Apps
- ✅ Embeddable widget available

### ⚠️ Partial Implementation
- ⚠️ No authentication (should require Entra ID)
- ⚠️ Using storage account keys (should use Managed Identity)
- ⚠️ Scanner not implemented (scanStatus never updates from "pending")

### ❌ Not Yet Met
- ❌ Authentication required; currently accepts anonymous uploads
- ❌ Authorization rules not enforced
- ❌ Scanner worker not deployed
- ❌ Downstream consumers don't enforce scanStatus checks
- ❌ Rate limiting not implemented
- ❌ Application Insights monitoring not configured

---

## Deployment Information

### Production Environment
- **Platform:** Azure Container Apps
- **Region:** East US
- **Resource Group:** rg-rfpo-e108977f
- **Container Registry:** acrrfpoe108977f.azurecr.io
- **Storage Account:** strfpo5kn5bsg47vvac
- **Container:** usabc-uploads-stage
- **Public URL:** https://usabc-upload.livelyforest-d06a98a0.eastus.azurecontainerapps.io/

### Current Version
- **Version:** v1.2
- **Image:** acrrfpoe108977f.azurecr.io/usabc-upload:v1.2
- **Revision:** usabc-upload--0000003
- **Status:** Active (100% traffic)

### Environment Variables
- `AZURE_STORAGE_ACCOUNT_URL`
- `AZURE_STORAGE_ACCOUNT_NAME`
- `AZURE_STORAGE_ACCOUNT_KEY` (⚠️ should migrate to Managed Identity)
- `AZURE_CONTAINER_NAME`

---

## Future Enhancements

### High Priority (Security & Production Readiness)
1. **Authentication & Authorization**
   - Implement Microsoft Entra ID authentication
   - Add role-based access control
   - Capture authenticated user identity
2. **Managed Identity Migration**
   - Remove storage account keys
   - Configure Container App with Managed Identity
   - Assign Storage Blob Data Contributor role
3. **Malware Scanning Integration**
   - Deploy scanner worker service
   - Implement scan event queue (Azure Service Bus or Event Grid)
   - Update scanStatus based on scan results
   - Add quarantine handling
4. **Rate Limiting**
   - Implement per-user and per-IP limits
   - Configure Azure API Management or Azure Front Door
5. **Monitoring & Alerting**
   - Configure Application Insights
   - Set up alerts for failures and anomalies
   - Dashboard for submission tracking

### Medium Priority (Features & UX)
1. **Additional Forms**
   - Create templates for other document submission types
   - Dynamic form configuration
2. **UI Enhancements**
   - Progress bars during upload
   - Drag-and-drop for all file inputs
   - File preview capabilities
3. **Resumable Uploads**
   - Support for large files (>25MB)
   - Chunked upload with resume capability
4. **Custom Domain**
   - Configure custom domain with SSL
   - Branded URLs

### Low Priority (Advanced Features)
1. **Auto-tagging via ML/LLM**
   - Document classification
   - Automatic metadata extraction
2. **Document Parsing/OCR**
   - Extract text from PDFs
   - Parse structured data
3. **Search & Discovery**
   - Full-text search across submissions
   - Advanced filtering by tags/metadata
4. **Direct-to-Blob Upload**
   - Generate SAS tokens for browser-direct upload
   - Reduce server load
