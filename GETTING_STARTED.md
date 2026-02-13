# Getting Started: Integrate USABC Upload Service

**Quick Start Guide for Developers**

This guide will help you integrate the USABC Document Upload Service into your web application in under 10 minutes.

---

## 🎯 Before You Begin

**You will need:**
- The USABC upload endpoint URL (provided below)
- A web form that collects user information and files
- Basic knowledge of HTML forms or JavaScript

**Endpoint URL:**
```
https://usabc-upload.livelyforest-d06a98a0.eastus.azurecontainerapps.io/rfpi-submit
```

**Features you get automatically:**
- ✅ Email confirmation sent to submitter
- ✅ Virus scanning with Microsoft Defender
- ✅ Secure cloud storage with Azure
- ✅ File validation and hashing
- ✅ Rate limiting (20 uploads/hour per IP)

---

## 🚀 Quick Start: 3 Integration Methods

### Method 1: Direct HTML Form (Simplest)

**Use this if:** You just want a simple form that submits directly to our endpoint.

```html
<!DOCTYPE html>
<html>
<head>
    <title>RFPI Proposal Submission</title>
</head>
<body>
    <h1>Submit Your RFPI Proposal</h1>
    
    <form action="https://usabc-upload.livelyforest-d06a98a0.eastus.azurecontainerapps.io/rfpi-submit" 
          method="POST" 
          enctype="multipart/form-data">
        
        <!-- 1. APPLICANT INFORMATION (All Required) -->
        <h2>Applicant Information</h2>
        
        <label>Proposal Title:</label>
        <input type="text" name="proposalTitle" required><br>
        
        <label>Entity Name:</label>
        <input type="text" name="entityName" required><br>
        
        <label>Entity UEI:</label>
        <input type="text" name="entityUEI" required><br>
        
        <label>Email Address:</label>
        <input type="email" name="email" required><br>
        
        <label>First Name:</label>
        <input type="text" name="firstName" required><br>
        
        <label>Last Name:</label>
        <input type="text" name="lastName" required><br>
        
        <label>Phone Number:</label>
        <input type="tel" name="phone" required><br>
        
        <!-- 2. REQUIRED FILE UPLOADS -->
        <h2>Required Documents</h2>
        
        <label>RFPI Proposal (PDF):</label>
        <input type="file" name="rfpiProposal" accept=".pdf" required><br>
        
        <label>Financial Documents (PDF):</label>
        <input type="file" name="financialDocuments" accept=".pdf" required><br>
        
        <label>Additional Documents (PDF):</label>
        <input type="file" name="additionalDocuments" accept=".pdf" required><br>
        
        <label>Budget Justification (Excel):</label>
        <input type="file" name="budgetJustification" accept=".xls,.xlsx" required><br>
        
        <!-- 3. OPTIONAL FILE UPLOADS -->
        <h2>Optional Budget Documents</h2>
        
        <label>Optional Budget Tier 1 (Excel):</label>
        <input type="file" name="optionalBudget1" accept=".xls,.xlsx"><br>
        
        <label>Optional Budget Tier 2 (Excel):</label>
        <input type="file" name="optionalBudget2" accept=".xls,.xlsx"><br>
        
        <!-- 4. SUBMIT -->
        <button type="submit">Submit Proposal</button>
    </form>
    
    <p><strong>Note:</strong> Maximum file size: 25MB per file, 50MB total</p>
</body>
</html>
```

**What happens when submitted:**
1. Form data is sent to USABC service
2. Files are validated (PDF/Excel signatures checked)
3. Files are scanned for malware
4. Confirmation email sent to the email address provided
5. Browser receives JSON response with submission ID

---

### Method 2: JavaScript with Fetch API (Recommended)

**Use this if:** You want to show progress, handle errors gracefully, or stay on the same page.

```html
<!DOCTYPE html>
<html>
<head>
    <title>RFPI Proposal Submission</title>
    <style>
        .loading { display: none; color: blue; }
        .success { display: none; color: green; }
        .error { display: none; color: red; }
    </style>
</head>
<body>
    <h1>Submit Your RFPI Proposal</h1>
    
    <form id="rfpiForm">
        <!-- Same form fields as Method 1 -->
        <label>Proposal Title:</label>
        <input type="text" name="proposalTitle" required><br>
        
        <label>Entity Name:</label>
        <input type="text" name="entityName" required><br>
        
        <label>Entity UEI:</label>
        <input type="text" name="entityUEI" required><br>
        
        <label>Email Address:</label>
        <input type="email" name="email" required><br>
        
        <label>First Name:</label>
        <input type="text" name="firstName" required><br>
        
        <label>Last Name:</label>
        <input type="text" name="lastName" required><br>
        
        <label>Phone Number:</label>
        <input type="tel" name="phone" required><br>
        
        <h2>Required Documents</h2>
        <label>RFPI Proposal (PDF):</label>
        <input type="file" name="rfpiProposal" accept=".pdf" required><br>
        
        <label>Financial Documents (PDF):</label>
        <input type="file" name="financialDocuments" accept=".pdf" required><br>
        
        <label>Additional Documents (PDF):</label>
        <input type="file" name="additionalDocuments" accept=".pdf" required><br>
        
        <label>Budget Justification (Excel):</label>
        <input type="file" name="budgetJustification" accept=".xls,.xlsx" required><br>
        
        <button type="submit">Submit Proposal</button>
    </form>
    
    <div class="loading" id="loading">Uploading files and scanning for malware... Please wait.</div>
    <div class="success" id="success"></div>
    <div class="error" id="error"></div>
    
    <script>
        document.getElementById('rfpiForm').addEventListener('submit', async (e) => {
            e.preventDefault(); // Prevent default form submission
            
            // Show loading message
            document.getElementById('loading').style.display = 'block';
            document.getElementById('success').style.display = 'none';
            document.getElementById('error').style.display = 'none';
            
            // Collect form data
            const formData = new FormData(e.target);
            
            try {
                // Submit to USABC service
                const response = await fetch(
                    'https://usabc-upload.livelyforest-d06a98a0.eastus.azurecontainerapps.io/rfpi-submit',
                    {
                        method: 'POST',
                        body: formData
                    }
                );
                
                // Hide loading
                document.getElementById('loading').style.display = 'none';
                
                if (response.ok) {
                    // SUCCESS - Parse response
                    const result = await response.json();
                    
                    // Show success message
                    document.getElementById('success').innerHTML = `
                        <h2>✅ Submission Successful!</h2>
                        <p><strong>Submission ID:</strong> ${result.submissionId}</p>
                        <p><strong>Files:</strong> ${result.fileCount} files uploaded</p>
                        <p><strong>Scan Status:</strong> ${result.scanStatus}</p>
                        <p>A confirmation email has been sent to your email address.</p>
                    `;
                    document.getElementById('success').style.display = 'block';
                    
                    // Optional: Reset form
                    e.target.reset();
                    
                } else {
                    // ERROR - Parse error response
                    const errorData = await response.json();
                    
                    // Show error message
                    let errorHtml = '<h2>❌ Submission Failed</h2><ul>';
                    
                    if (errorData.error === 'ValidationFailed') {
                        errorData.details.forEach(err => {
                            errorHtml += `<li><strong>${err.field}:</strong> ${err.message}</li>`;
                        });
                    } else if (errorData.error === 'MalwareDetected') {
                        errorHtml += '<li><strong>Security Alert:</strong> Malware detected in uploaded files. Please scan your computer.</li>';
                    } else if (errorData.error === 'RateLimitExceeded') {
                        errorHtml += '<li>Too many submissions. Please wait and try again later.</li>';
                    } else {
                        errorHtml += `<li>${errorData.error || 'Unknown error occurred'}</li>`;
                    }
                    
                    errorHtml += '</ul>';
                    document.getElementById('error').innerHTML = errorHtml;
                    document.getElementById('error').style.display = 'block';
                }
                
            } catch (err) {
                // NETWORK ERROR
                document.getElementById('loading').style.display = 'none';
                document.getElementById('error').innerHTML = `
                    <h2>❌ Network Error</h2>
                    <p>Unable to connect to the upload service. Please check your internet connection and try again.</p>
                    <p>Error: ${err.message}</p>
                `;
                document.getElementById('error').style.display = 'block';
            }
        });
    </script>
</body>
</html>
```

**Advantages:**
- ✅ User stays on the same page
- ✅ Real-time feedback during upload
- ✅ Better error handling and display
- ✅ Can track upload progress
- ✅ Can reset form after success

---

### Method 3: cURL (Testing / Command Line)

**Use this for:** Testing the endpoint, automated scripts, or backend integrations.

```bash
# Basic test with all required fields
curl -X POST \
  https://usabc-upload.livelyforest-d06a98a0.eastus.azurecontainerapps.io/rfpi-submit \
  -F "proposalTitle=Advanced Battery Management System" \
  -F "entityName=Example Corporation" \
  -F "entityUEI=ABC123456789" \
  -F "email=john.doe@example.com" \
  -F "firstName=John" \
  -F "lastName=Doe" \
  -F "phone=555-1234" \
  -F "rfpiProposal=@/path/to/proposal.pdf" \
  -F "financialDocuments=@/path/to/financial.pdf" \
  -F "additionalDocuments=@/path/to/additional.pdf" \
  -F "budgetJustification=@/path/to/budget.xlsx"
```

**With optional files:**
```bash
curl -X POST \
  https://usabc-upload.livelyforest-d06a98a0.eastus.azurecontainerapps.io/rfpi-submit \
  -F "proposalTitle=Advanced Battery Management System" \
  -F "entityName=Example Corporation" \
  -F "entityUEI=ABC123456789" \
  -F "email=john.doe@example.com" \
  -F "firstName=John" \
  -F "lastName=Doe" \
  -F "phone=555-1234" \
  -F "rfpiProposal=@proposal.pdf" \
  -F "financialDocuments=@financial.pdf" \
  -F "additionalDocuments=@additional.pdf" \
  -F "budgetJustification=@budget.xlsx" \
  -F "optionalBudget1=@tier1-budget.xlsx" \
  -F "optionalBudget2=@tier2-budget.xlsx"
```

---

## 📋 Required Fields Reference

### Text Fields (All Required)
| Field Name | Type | Description | Example |
|------------|------|-------------|---------|
| `proposalTitle` | string | Title of the proposal | "Advanced Battery Technology" |
| `entityName` | string | Organization name | "ABC Corporation" |
| `entityUEI` | string | Unique Entity Identifier | "ABC123456789" |
| `email` | email | Submitter's email (receives confirmation) | "john@example.com" |
| `firstName` | string | Submitter's first name | "John" |
| `lastName` | string | Submitter's last name | "Doe" |
| `phone` | string | Contact phone number | "555-123-4567" |

### File Fields

**Required Files:**
| Field Name | Type | Max Size | Description |
|------------|------|----------|-------------|
| `rfpiProposal` | PDF | 25 MB | Main RFPI proposal document |
| `financialDocuments` | PDF | 25 MB | Financial documentation |
| `additionalDocuments` | PDF | 25 MB | Supporting documents |
| `budgetJustification` | Excel | 25 MB | Budget breakdown (.xls or .xlsx) |

**Optional Files:**
| Field Name | Type | Max Size | Description |
|------------|------|----------|-------------|
| `optionalBudget1` | Excel | 25 MB | Tier 1 budget details (.xls or .xlsx) |
| `optionalBudget2` | Excel | 25 MB | Tier 2 budget details (.xls or .xlsx) |

**Total submission limit:** 50 MB

---

## ✅ Success Response

When a submission succeeds, you'll receive a `201 Created` status with JSON:

```json
{
  "submissionId": "51d79467-0052-48a7-a1a9-2fd7d0d9e2ca",
  "blobPath": "rfpi-submissions/2026/02/12/51d79467-0052-48a7-a1a9-2fd7d0d9e2ca.zip",
  "zipSha256": "a1b2c3d4...",
  "fileCount": 4,
  "scanStatus": "clean",
  "scanDetails": {},
  "storageMode": "azure",
  "status": "uploaded",
  "emailSent": true,
  "emailRecipient": "john@example.com"
}
```

**Key fields:**
- `submissionId` - Unique ID for this submission (save this!)
- `fileCount` - Number of files successfully uploaded
- `scanStatus` - Virus scan result: `"clean"`, `"pending"`, or `"malicious"`
- `emailSent` - `true` if confirmation email was sent
- `emailRecipient` - Email address that received confirmation

---

## ❌ Error Responses

### Validation Error (400 Bad Request)
```json
{
  "error": "ValidationFailed",
  "details": [
    {
      "field": "email",
      "message": "Required field missing"
    },
    {
      "field": "rfpiProposal",
      "message": "PDF file required"
    }
  ]
}
```

**Fix:** Check that all required fields are provided and files are correct format.

### Malware Detected (403 Forbidden)
```json
{
  "error": "MalwareDetected",
  "submissionId": "51d79467-0052-48a7-a1a9-2fd7d0d9e2ca",
  "scanStatus": "malicious",
  "scanDetails": "Malware detected: Win32/Trojan",
  "quarantined": true,
  "message": "File failed security scan and has been quarantined"
}
```

**Fix:** Scan the user's computer for malware. Files were quarantined and not stored.

### Rate Limit (429 Too Many Requests)
```json
{
  "error": "RateLimitExceeded",
  "message": "Too many requests. Please try again later.",
  "retry_after": "52 minutes"
}
```

**Fix:** Wait before submitting again. Limit is 20 uploads per hour per IP address.

### Server Error (500 Internal Server Error)
```json
{
  "error": "UploadFailed",
  "details": [
    {
      "field": "general",
      "message": "Internal server error"
    }
  ]
}
```

**Fix:** Retry the request. If problem persists, contact support.

---

## 🎨 URL Parameters (Optional)

You can pass the RFPI title in the URL to have it appear in the confirmation email subject:

```
https://usabc-upload.livelyforest-d06a98a0.eastus.azurecontainerapps.io/rfpi-submit?rfpi-title=Battery+Management+Systems+Q1+2026
```

**Email subject will be:**
```
RFPI Proposal Received - Battery Management Systems Q1 2026 - [Proposal Title]
```

**Example in HTML form:**
```html
<form action="https://usabc-upload.livelyforest-d06a98a0.eastus.azurecontainerapps.io/rfpi-submit?rfpi-title=Battery+Research+Q1+2026" 
      method="POST" 
      enctype="multipart/form-data">
    <!-- form fields -->
</form>
```

---

## 🧪 Testing Your Integration

### 1. Test with Small Files First
Create dummy PDF and Excel files under 1 MB to test functionality before using real documents.

### 2. Check the Response
Your integration should handle all possible responses:
- ✅ `201 Created` - Success
- ❌ `400 Bad Request` - Validation error
- ❌ `403 Forbidden` - Malware detected
- ❌ `429 Too Many Requests` - Rate limited
- ❌ `500 Internal Server Error` - Server issue

### 3. Verify Email Delivery
Submit with a real email address and confirm you receive the confirmation email.

### 4. Test Rate Limiting
Submit 20+ times in an hour to see rate limiting in action.

### 5. Check Rate Limit Headers
All responses include these headers:
```
X-RateLimit-Limit: 20
X-RateLimit-Remaining: 15
X-RateLimit-Reset: 1707782400
```

---

## 🐛 Common Issues & Solutions

### Issue: "Required field missing" error
**Cause:** Missing a required text field or file.  
**Fix:** Check that ALL 7 text fields and 4 file fields are included.

### Issue: "Must be a valid PDF file" error
**Cause:** File is not a real PDF (renamed .txt file, corrupted, etc.)  
**Fix:** Ensure files are actual PDF/Excel files, not just renamed.

### Issue: Email confirmation not received
**Cause:** Email in spam folder or email service not configured.  
**Fix:** Check spam folder. Contact support if emails consistently fail.

### Issue: "Network error" or CORS error
**Cause:** Browser security blocking cross-origin requests.  
**Fix:** CORS is enabled on the endpoint. Check browser console for specific error.

### Issue: Large files fail to upload
**Cause:** Files exceed size limits (25MB per file, 50MB total).  
**Fix:** Compress files or reduce quality before upload.

### Issue: "Rate limit exceeded"
**Cause:** Submitted more than 20 times in one hour from same IP.  
**Fix:** Wait for rate limit to reset (check `X-RateLimit-Reset` header).

---

## 📞 Need Help?

- **Technical Documentation:** See [THIRD_PARTY_INTEGRATION.md](THIRD_PARTY_INTEGRATION.md) for advanced integration
- **Troubleshooting:** See [SUPPORT.md](SUPPORT.md) for common issues
- **Virus Scanning:** See [VIRUS_SCANNING.md](VIRUS_SCANNING.md) for security details
- **Support:** Contact your USABC administrator

---

## 🚀 Next Steps

1. **Copy Method 2 (JavaScript)** into your application
2. **Customize the form** with your branding/styling
3. **Test with dummy files** to verify integration
4. **Add error handling** for better user experience
5. **Deploy** to your production environment

**That's it!** Your form is now integrated with the USABC Upload Service.

---

**Quick Reference:**
- **Endpoint:** `https://usabc-upload.livelyforest-d06a98a0.eastus.azurecontainerapps.io/rfpi-submit`
- **Method:** `POST`
- **Content-Type:** `multipart/form-data`
- **Required Fields:** 7 text fields + 4 files
- **Optional Fields:** 2 additional Excel files
- **Rate Limit:** 20 uploads/hour per IP
- **Max Size:** 25MB per file, 50MB total
- **Features:** Email confirmation, virus scanning, cloud storage
