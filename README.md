# DOCUPLOAD

Secure document upload service with Azure Blob Storage integration. Supports multiple file types and flexible form integration.

## 🌐 Live Deployment

**Production URL:** https://usabc-upload.livelyforest-d06a98a0.eastus.azurecontainerapps.io/

The service is deployed on Azure Container Apps and ready for use.

## 📋 Features

- ✅ **Flexible file uploads** - Accept any number of files from any form
- ✅ **Multiple file types** - PDF, DOCX, XLSX, XLS, PPTX, PNG, JPG, TXT, CSV
- ✅ Secure file validation with content signature verification
- ✅ **Automated virus scanning** with Microsoft Defender for Storage
- ✅ **Email notifications** - Automated confirmation emails to submitters
- ✅ **Rate limiting** (20 uploads/hour, 100 requests/hour per IP)
- ✅ **Automatic quarantine** for malicious files
- ✅ Comprehensive logging for all upload attempts and scan results
- ✅ SHA-256 hashing for files and final zip packages
- ✅ Azure Blob Storage integration with metadata and index tags
- ✅ Manifest generation with complete submission details
- ✅ Embeddable widget for integration into other applications
- ✅ RESTful API for programmatic access
- ✅ Docker containerized for easy deployment
- ✅ Eastern Time (EST/EDT) timezone support

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
    
    # Optional: Email notifications (requires Azure Communication Services)
    AZURE_COMMUNICATION_CONNECTION_STRING=endpoint=https://...;accesskey=...
    AZURE_COMMUNICATION_SENDER_ADDRESS=noreply@uploads.uscar.org
    ```

5.  **Run the application:**
    ```bash
    python app.py
    ```

6.  **View the demo:**
    Open [http://localhost:5000](http://localhost:5000) in your browser.

## 📖 Usage

### Available Endpoints

The service offers three endpoints for different use cases:

#### 1. **`/submit` - Flexible Upload (NEW!)** ⭐ Recommended
The most flexible endpoint that accepts **any number of files** with **any field names**. Perfect for embedding in any form.

**Supported file types:** PDF, DOCX, XLSX, XLS, PPTX, PNG, JPG, TXT, CSV

**Example:**
```bash
curl -X POST http://localhost:5000/submit \
  -F "document=@contract.pdf" \
  -F "formId=my-contract-form" \
  -F 'tags={"department":"Legal","project":"Alpha"}'
```

📘 **[Full API Documentation](FLEXIBLE_UPLOAD_API.md)** | 🧪 **[Try Example Form](example-flexible-form.html)**

#### 2. `/upload` - Project Artifacts (Legacy)
Original endpoint for architecture diagrams and charter documents.

**Required files:** `architectureDiagram` (PDF), `charter` (DOCX)

#### 3. `/rfpi-submit` - RFPI Proposals (Legacy)
Specialized endpoint for USABC RFPI proposal submissions with specific required files.

### Integration Examples

#### Option 1: Flexible Upload (Any Form)
```html
<form id="myForm">
  <input type="file" name="document1" required>
  <input type="file" name="document2">
  <button type="submit">Upload</button>
</form>

<script>
document.getElementById('myForm').addEventListener('submit', async (e) => {
  e.preventDefault();
  const formData = new FormData(e.target);
  formData.append('formId', 'my-custom-form');
  formData.append('tags', JSON.stringify({'project': 'MyProject'}));
  
  const response = await fetch('/submit', {
    method: 'POST',
    body: formData
  });
  
  const result = await response.json();
  console.log('Submission ID:', result.submissionId);
});
</script>
```

#### Option 2: Embed Widget
Add this to any HTML page:
```html
<div id="docupload-widget"></div>
<script src="https://usabc-upload.livelyforest-d06a98a0.eastus.azurecontainerapps.io/widget.js"></script>
```

#### Option 3: Legacy API Integration
```bash
curl -X POST https://usabc-upload.livelyforest-d06a98a0.eastus.azurecontainerapps.io/upload \
  -F "architectureDiagram=@diagram.pdf" \
  -F "charter=@charter.docx" \
  -F 'tags={"project":"myproject","environment":"dev"}'
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

**Use the deployment script to preserve environment variables:**
```powershell
.\deploy.ps1 -Version "v1.5"
```

See [Deployment Best Practices](DEPLOYMENT_BEST_PRACTICES.md) for critical deployment guidelines.

## 📚 Documentation

- **[GETTING_STARTED.md](GETTING_STARTED.md)** - **Quick integration guide for developers**
- **[SUPPORT.md](SUPPORT.md)** - Troubleshooting guide and common issues
- **[Deployment Best Practices](DEPLOYMENT_BEST_PRACTICES.md)** - CRITICAL: Read before deploying
- [Deployment Info](deployment-info.md) - Current deployment details and management commands
- [Deployment Guide](deploy-guide.md) - Complete deployment instructions
- [Specification](web-form-upload-spec.md) - Full MVP specification
- **[Third-Party Integration Guide](THIRD_PARTY_INTEGRATION.md)** - Advanced integration patterns and examples
- **[Virus Scanning Documentation](VIRUS_SCANNING.md)** - Azure Defender malware scanning setup and monitoring
- **[Admin Request Document](ADMIN_REQUEST.md)** - Configuration tasks requiring administrator access

## 🔒 Security Features

### Virus Scanning
- **Microsoft Defender for Storage** integration
- Automated malware scanning on upload
- Hash reputation analysis using Microsoft threat intelligence
- Automatic quarantine of infected files
- Real-time scan results (typically 10-30 seconds)

### Email Notifications
- **Automated confirmation emails** sent to submitters via Azure Communication Services
- Professional HTML emails with submission details and file summary
- Scan status included in confirmation (clean/pending)
- Graceful degradation if email service not configured

### Rate Limiting
- 100 requests per hour per IP (general)
- 20 uploads per hour per IP (upload endpoints)
- Rate limit headers in all responses

### Comprehensive Logging
- All upload attempts logged with client IP
- Validation failures tracked
- Scan results logged (clean/malicious/pending)
- Email delivery status logged
- Quarantine operations logged

See [VIRUS_SCANNING.md](VIRUS_SCANNING.md) for setup instructions.

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
