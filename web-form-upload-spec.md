# Web Form Spec (MVP): Secure 2-Document Upload + Tagging + Dual Hashing + Zip + Azure Blob Storage + Async Malware Scan (Option A)

## Purpose
Provide a secure web form that accepts **exactly two uploads**:

1) **Architectural Diagram** (**PDF only**)  
2) **Charter** (**DOCX only**)

Each submission:

- Validates file types by **signature**, not just MIME/extension
- Validates user tags and applies system tags
- Computes **SHA-256 hashes for each file AND the final zip**
- Packages files + `manifest.json` into a zip
- Uploads to **Azure Blob Storage** using **Managed Identity**
- Triggers **asynchronous malware scanning (Option A)** and marks the blob `scanStatus=pending` until confirmed clean

This MVP is intentionally limited to **two file types total** (PDF + DOCX), but is otherwise designed to be **production-grade** in security, validation, auditability, and downstream safety.

---

## Scope (MVP)
### In Scope
- Web form with exactly 2 upload sections
- Submission-level metadata tags (applies to both files)
- Strict validation (extension + signature)
- Dual hashing:
  - Per-file SHA-256
  - Zip SHA-256
- Zip creation with safe internal paths
- Upload to Azure Blob Storage
- Apply Blob Metadata + Blob Index Tags
- Async malware scanning hook (Option A)
- Scan status enforcement contract for downstream consumers

### Out of Scope (for MVP)
- Multiple files per section
- Resumable/chunked uploads
- Direct-to-blob browser upload via SAS
- Auto-tagging via ML/LLM
- Automatic document parsing / OCR
- UI progress bars (nice-to-have)

---

## High-Level Architecture
**Browser UI** → **Upload API (server)** → **Zip builder** → **Azure Blob Storage**  
                                                     ↘ **Scan request event** → **Scanner Worker** → updates blob tags/metadata

### Design Principle
The browser is an untrusted client. The API is the security boundary.

---

## Authentication & Authorization (Required)
### Authentication
- Use **Microsoft Entra ID (Azure AD)** for the web app and API.
- API must reject anonymous requests.

### Authorization
- API must enforce authorization rules (examples):
  - user must be in allowed tenant
  - user must be in a specific group (optional)
  - user must have an application role claim (recommended)

---

## UX Requirements

### Form Layout
Title: **Upload Project Artifacts**

#### Section A: Architectural Diagram (Required)
- Label: **Architectural Diagram (PDF)**
- Input name: `architectureDiagram`
- Accept: `.pdf` only
- Help text: “Upload a PDF architecture diagram.”

#### Section B: Charter (Required)
- Label: **Charter (DOCX)**
- Input name: `charter`
- Accept: `.docx` only
- Help text: “Upload a DOCX charter document.”

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

## Strict File Type Rules (MVP)

### Allowed Types (Hard Requirement)
| Field | Allowed Extension | Verified Content Type |
|------|-------------------|-----------------------|
| `architectureDiagram` | `.pdf` | `application/pdf` |
| `charter` | `.docx` | `application/vnd.openxmlformats-officedocument.wordprocessingml.document` |

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

### Example
```json
{
  "submissionId": "uuid",
  "submittedAt": "2026-02-11T17:32:10Z",
  "submittedBy": "user@company.com",
  "tags": {
    "project": "SIS",
    "domain": "student",
    "environment": "dev"
  },
  "scan": {
    "scanStatus": "pending",
    "scanProvider": null,
    "scanRequestedAt": "2026-02-11T17:32:12Z",
    "scanCompletedAt": null,
    "scanResultDetails": null
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

---

## Azure Blob Storage Requirements (Secure)

### Storage Targets
- Container: `project-artifacts` (configurable)
- Blob path convention:
  - `uploads/{yyyy}/{MM}/{dd}/{submissionId}.zip`

Example:
- `uploads/2026/02/11/2f3a9c2b-4a9f-4d1a-a9c0-0f0b7a6f1c1b.zip`

---

## Storage Authentication (Required)
- Upload API uses **Managed Identity**
- Role assignment:
  - `Storage Blob Data Contributor` scoped to the container
- Do not use storage account keys in app settings.

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

## Malware Scanning Hook (Option A: Async After Upload) — Required

### Design Goal
Uploads are stored quickly, but **nothing downstream may trust the content** until scan completion.

### Flow
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

## API Contract (MVP)

### Endpoint
`POST /api/uploads/project-artifacts`

Auth:
- Entra ID Bearer Token (required)

Content type:
- `multipart/form-data`

Parts:
- `architectureDiagram` (file, required)
- `charter` (file, required)
- `tags` (stringified JSON, required because `project` required)

Example `tags`:
```json
{
  "project": "SIS",
  "domain": "student",
  "environment": "dev"
}
```

---

## Response (201 Created)
```json
{
  "submissionId": "uuid",
  "blobPath": "uploads/2026/02/11/<submissionId>.zip",
  "zipSha256": "hex",
  "fileHashes": {
    "architectureDiagramSha256": "hex",
    "charterSha256": "hex"
  },
  "scanStatus": "pending",
  "status": "uploaded"
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

## Security Requirements (Non-Negotiable)

### Input Validation
- Validate everything server-side.
- Reject unexpected fields (allowlist form parts).

### Rate Limiting
- Per-user rate limits (and optionally per IP).

### Request Limits
- Max request body at gateway and API.

### Logging
Log (structured):
- submissionId
- user
- sizes
- verified types
- blob path
- scan status transitions

Do not log file contents.

### CORS / CSRF
- Restrict CORS to trusted origins.
- If cookie-based auth is used, enforce CSRF protection.

### Least Privilege
- Managed identity has only the minimum Storage permissions needed.

---

## Acceptance Criteria (MVP)
- Auth required; anonymous upload rejected.
- Exactly two files required:
  - `architectureDiagram` must be a valid PDF by signature.
  - `charter` must be a valid DOCX by structure.
- `project` tag required; all tags validated by strict patterns.
- Zip contains both files with fixed internal names + manifest.json.
- SHA-256 computed for both files and the zip.
- Zip uploaded to Blob Storage under naming convention.
- Blob metadata and index tags are set.
- Scan request event emitted and blob marked `scanStatus=pending`.
- Scanner updates scan status.
- Downstream consumers must only process when `scanStatus=clean`.

---

## Future Enhancements
- Multiple files per section
- Per-section tags
- Resumable uploads
- Automatic parsing/indexing
- Auto-tagging suggestions
- UI progress indicators
