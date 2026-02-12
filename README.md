# DOCUPLOAD

Secure document upload service with Azure Blob Storage integration for PDF (architectural diagrams) and DOCX (charter documents).

## 🌐 Live Deployment

**Production URL:** https://usabc-upload.livelyforest-d06a98a0.eastus.azurecontainerapps.io/

The service is deployed on Azure Container Apps and ready for use.

## 📋 Features

- ✅ Secure file validation (PDF and DOCX signature verification)
- ✅ SHA-256 hashing for files and final zip packages
- ✅ Azure Blob Storage integration with metadata and index tags
- ✅ Manifest generation with complete submission details
- ✅ Embeddable widget for integration into other applications
- ✅ RESTful API for programmatic access
- ✅ Docker containerized for easy deployment

## 🚀 Quick Start (Local Development)

### Setup

1.  **Create a virtual environment:**
    ```bash
    python -m venv venv
    ```

2.  **Activate variable environment:**
    -   Windows: `venv\Scripts\activate`
    -   Mac/Linux: `source venv/bin/activate`

3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Create `.env` file** (for Azure Blob Storage):
    ```env
    AZURE_STORAGE_ACCOUNT_URL=https://your-storage-account.blob.core.windows.net
    AZURE_STORAGE_ACCOUNT_NAME=your-storage-account
    AZURE_STORAGE_ACCOUNT_KEY=your-storage-key
    AZURE_CONTAINER_NAME=your-container
    ```

5.  **Run the application:**
    ```bash
    python app.py
    ```

6.  **View the demo:**
    Open [http://localhost:5000](http://localhost:5000) in your browser.

## 📖 Usage

### Option 1: Web Form
Navigate to the service URL and use the interactive form to upload files.

### Option 2: Embed Widget
Add this to any HTML page:
```html
<div id="docupload-widget"></div>
<script src="https://usabc-upload.livelyforest-d06a98a0.eastus.azurecontainerapps.io/widget.js"></script>
```

### Option 3: API Integration
```bash
curl -X POST https://usabc-upload.livelyforest-d06a98a0.eastus.azurecontainerapps.io/upload \
  -F "architectureDiagram=@diagram.pdf" \
  -F "charter=@charter.docx" \
  -F 'tags={"project":"myproject","environment":"dev"}'
```

**Required Fields:**
- `architectureDiagram` - PDF file (validated by signature)
- `charter` - DOCX file (validated by signature)
- `tags` - JSON object with at least `project` field (lowercase, alphanumeric, hyphens only)

**Response:**
```json
{
  "submissionId": "uuid",
  "blobPath": "uploads/2026/02/12/uuid.zip",
  "zipSha256": "hash",
  "fileHashes": {
    "architectureDiagramSha256": "hash",
    "charterSha256": "hash"
  },
  "scanStatus": "pending",
  "status": "uploaded"
}
```

## 🔒 File Storage

Uploaded files are stored in Azure Blob Storage:
- **Container:** `usabc-uploads-stage`
- **Path:** `uploads/YYYY/MM/DD/{submissionId}.zip`
- **Contents:** 
  - `files/architecture-diagram.pdf`
  - `files/charter.docx`
  - `manifest.json` (complete metadata)

## 🐳 Docker Deployment

### Build locally:
```bash
docker build -t docupload:latest .
docker run -p 5000:5000 --env-file .env docupload:latest
```

### Deploy to Azure Container Apps:
See [deploy-guide.md](deploy-guide.md) for detailed deployment instructions.

## 📚 Documentation

- [Deployment Guide](deploy-guide.md) - Complete deployment instructions
- [Deployment Info](deployment-info.md) - Current deployment details and management commands
- [Specification](web-form-upload-spec.md) - Full MVP specification

## 🛠️ Technology Stack

- **Backend:** Python 3.11, Flask
- **Storage:** Azure Blob Storage
- **Deployment:** Azure Container Apps
- **Container Registry:** Azure Container Registry
- **Authentication:** Storage Account Keys (configurable to Managed Identity)

## 📝 License

MIT

5.  **View the demo:**
    Open [http://localhost:5000](http://localhost:5000) in your browser.

## Embed Instructions

To embed the upload widget on another site:

1.  Include the script:
    ```html
    <script src="http://your-server-url/static/widget.js"></script>
    ```

2.  Add the container div where you want the widget to appear:
    ```html
    <div id="docupload-widget"></div>
    ```
