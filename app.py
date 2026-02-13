import os
import io
import json
import uuid
import datetime
from zoneinfo import ZoneInfo
import hashlib
import zipfile
import re
import logging
from flask import Flask, request, jsonify, send_from_directory, g
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.utils import secure_filename
from dotenv import load_dotenv

# Azure imports
from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient

# Virus scanning imports
import scanner
from scanner import wait_for_scan_result, quarantine_blob, update_blob_scan_status, ScanResult

# Email notification imports
import email_notifier
from email_notifier import send_rfpi_confirmation_email, send_generic_submission_email

load_dotenv()

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# Rate limiting configuration
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["100 per hour"],
    storage_uri="memory://",
    headers_enabled=True
)

# Configuration
UPLOAD_TEMP_FOLDER = 'uploads/temp'
LOCAL_STORAGE_FALLBACK = 'uploads/final'  # Used if Azure is not configured
MAX_FILE_SIZE = 25 * 1024 * 1024  # 25MB
MAX_TOTAL_SIZE = 50 * 1024 * 1024 # 50MB
AZURE_STORAGE_ACCOUNT_URL = os.environ.get("AZURE_STORAGE_ACCOUNT_URL")
AZURE_STORAGE_ACCOUNT_NAME = os.environ.get("AZURE_STORAGE_ACCOUNT_NAME")
AZURE_STORAGE_ACCOUNT_KEY = os.environ.get("AZURE_STORAGE_ACCOUNT_KEY")
AZURE_CONTAINER_NAME = os.environ.get("AZURE_CONTAINER_NAME", "project-artifacts")

app.config['MAX_CONTENT_LENGTH'] = MAX_TOTAL_SIZE + (1024 * 1024) # Add buffer for metadata

for path in [UPLOAD_TEMP_FOLDER, LOCAL_STORAGE_FALLBACK]:
    if not os.path.exists(path):
        os.makedirs(path)

# --- Request Logging Middleware ---

@app.before_request
def log_request_info():
    """Log incoming request details"""
    g.request_start_time = datetime.datetime.now(ZoneInfo("America/New_York"))
    logger.info(f"REQUEST: {request.method} {request.path} from {request.remote_addr} - User-Agent: {request.user_agent}")

@app.after_request
def log_response_info(response):
    """Log response details and duration"""
    if hasattr(g, 'request_start_time'):
        duration = (datetime.datetime.now(ZoneInfo("America/New_York")) - g.request_start_time).total_seconds()
        logger.info(f"RESPONSE: {request.method} {request.path} - Status: {response.status_code} - Duration: {duration:.3f}s")
    return response

@app.errorhandler(429)
def ratelimit_handler(e):
    """Handle rate limit exceeded"""
    logger.warning(f"RATE_LIMIT_EXCEEDED: {request.remote_addr} attempted {request.method} {request.path}")
    return jsonify({
        "error": "RateLimitExceeded",
        "message": "Too many requests. Please try again later.",
        "retry_after": e.description
    }), 429

# --- Validation Helpers ---

def validate_tag_key(key):
    return re.match(r'^[a-z0-9-]{1,32}$', key) is not None

def validate_tag_value(value):
    return re.match(r'^[A-Za-z0-9 _.-]{1,64}$', value) is not None

def validate_pdf_signature(stream):
    """Check if stream starts with %PDF-"""
    start_pos = stream.tell()
    stream.seek(0)
    header = stream.read(5)
    stream.seek(start_pos)
    return header.startswith(b'%PDF-')

def validate_docx_signature(stream):
    """Check if stream starts with PK (Zip container) and contains word/document.xml"""
    start_pos = stream.tell()
    stream.seek(0)
    header = stream.read(2)

    # DOCX is a zip file, so it must start with PK
    if not header.startswith(b'PK'):
        stream.seek(start_pos)
        return False

    # Verify it's actually a DOCX by checking for word/document.xml
    try:
        stream.seek(0)
        with zipfile.ZipFile(stream, 'r') as docx_zip:
            # Check if word/document.xml exists in the zip
            if 'word/document.xml' not in docx_zip.namelist():
                stream.seek(start_pos)
                return False
    except (zipfile.BadZipFile, KeyError):
        stream.seek(start_pos)
        return False

    stream.seek(start_pos)
    return True


def validate_excel_signature(stream):
    """Check if stream is a valid Excel file (XLS or XLSX)"""
    start_pos = stream.tell()
    stream.seek(0)
    header = stream.read(8)
    stream.seek(start_pos)

    # XLSX is a zip file (starts with PK)
    if header.startswith(b'PK'):
        return True

    # XLS file signature (older format)
    if header.startswith(b'\xD0\xCF\x11\xE0\xA1\xB1\x1A\xE1'):
        return True

    return False

def validate_pptx_signature(stream):
    """Check if stream is a valid PowerPoint file (PPTX)"""
    start_pos = stream.tell()
    stream.seek(0)
    header = stream.read(2)

    # PPTX is a zip file, so it must start with PK
    if not header.startswith(b'PK'):
        stream.seek(start_pos)
        return False

    # Verify it's actually a PPTX by checking for ppt/ folder
    try:
        stream.seek(0)
        with zipfile.ZipFile(stream, 'r') as pptx_zip:
            # Check if ppt/ folder exists
            namelist = pptx_zip.namelist()
            if any(name.startswith('ppt/') for name in namelist):
                stream.seek(start_pos)
                return True
    except (zipfile.BadZipFile, KeyError):
        stream.seek(start_pos)
        return False

    stream.seek(start_pos)
    return False

def validate_text_signature(stream):
    """Check if stream is a valid text file (TXT, CSV)"""
    start_pos = stream.tell()
    stream.seek(0)
    try:
        # Read first 1KB and try to decode as UTF-8
        sample = stream.read(1024)
        sample.decode('utf-8')
        stream.seek(start_pos)
        return True
    except UnicodeDecodeError:
        stream.seek(start_pos)
        return False

def validate_image_signature(stream):
    """Check if stream is a valid image file (PNG, JPG, JPEG)"""
    start_pos = stream.tell()
    stream.seek(0)
    header = stream.read(10)
    stream.seek(start_pos)

    # PNG signature
    if header.startswith(b'\x89PNG\r\n\x1a\n'):
        return True

    # JPEG signature
    if header.startswith(b'\xFF\xD8\xFF'):
        return True

    return False

def detect_file_type(stream, filename):
    """Detect file type from content signature and return (type, mime_type, extension)"""
    # Try each validator
    if validate_pdf_signature(stream):
        return ('pdf', 'application/pdf', '.pdf')
    elif validate_docx_signature(stream):
        return ('docx', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', '.docx')
    elif validate_excel_signature(stream):
        # Check extension to differentiate XLS vs XLSX
        ext = os.path.splitext(filename)[1].lower()
        if ext == '.xls':
            return ('xls', 'application/vnd.ms-excel', '.xls')
        else:
            return ('xlsx', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', '.xlsx')
    elif validate_pptx_signature(stream):
        return ('pptx', 'application/vnd.openxmlformats-officedocument.presentationml.presentation', '.pptx')
    elif validate_image_signature(stream):
        ext = os.path.splitext(filename)[1].lower()
        if ext == '.png':
            return ('png', 'image/png', '.png')
        else:
            return ('jpeg', 'image/jpeg', '.jpg')
    elif validate_text_signature(stream):
        ext = os.path.splitext(filename)[1].lower()
        if ext == '.csv':
            return ('csv', 'text/csv', '.csv')
        else:
            return ('txt', 'text/plain', '.txt')
    else:
        return (None, None, None)

def compute_sha256(stream):
    sha = hashlib.sha256()
    start_pos = stream.tell()
    stream.seek(0)
    while True:
        chunk = stream.read(65536)
        if not chunk:
            break
        sha.update(chunk)
    stream.seek(start_pos)
    return sha.hexdigest()

def normalize_tag_for_index(value):
    """Normalize tag value for Azure Blob Index Tags (lowercase, spaces to underscores)"""
    return str(value).lower().replace(' ', '_')[:256]  # Azure tag value limit

def handle_reserved_tags(user_tags):
    """Handle reserved tag keys by prefixing with 'user.' if collision occurs"""
    reserved_keys = {
        'documentType', 'sourceForm', 'submittedAt', 'submittedBy',
        'submissionId', 'scanStatus', 'scanProvider', 'scanRequestedAt',
        'scanCompletedAt'
    }

    effective_tags = {}
    for key, value in user_tags.items():
        if key in reserved_keys:
            # Prefix with 'user.' to avoid collision
            effective_tags[f'user.{key}'] = value
        else:
            effective_tags[key] = value

    return effective_tags

@app.route('/')
def index():
    return send_from_directory('.', 'rfpi-form.html')

@app.route('/widget.js')
def serve_widget():
    return send_from_directory('static', 'widget.js')

@app.route('/health')
def health_check():
    """Health check endpoint for load balancer and monitoring"""
    return jsonify({
        "status": "healthy",
        "service": "usabc-upload",
        "version": "v1.3",
        "timestamp": datetime.datetime.now(ZoneInfo("America/New_York")).isoformat()
    }), 200

@app.route('/upload', methods=['POST'])
@limiter.limit("20 per hour")  # More restrictive for upload endpoint
def upload_project_artifacts():
    client_ip = request.remote_addr
    logger.info(f"UPLOAD_START: New upload request from {client_ip}")
    try:
        # 1. Input Validation
        if 'architectureDiagram' not in request.files or 'charter' not in request.files:
            logger.warning(f"UPLOAD_VALIDATION_FAILED: Missing required files from {client_ip}")
            return jsonify({
                'error': 'ValidationFailed',
                'details': [{'field': 'files', 'message': 'Missing required files: architectureDiagram (PDF) and charter (DOCX)'}]
            }), 400

        pdf_file = request.files['architectureDiagram']
        docx_file = request.files['charter']

        tags_raw = request.form.get('tags')
        if not tags_raw:
            logger.warning(f"UPLOAD_VALIDATION_FAILED: Missing tags from {client_ip}")
            return jsonify({
                'error': 'ValidationFailed',
                'details': [{'field': 'tags', 'message': 'Missing required tags'}]
            }), 400

        try:
            tags = json.loads(tags_raw)
        except:
            logger.warning(f"UPLOAD_VALIDATION_FAILED: Invalid JSON in tags from {client_ip}")
            return jsonify({
                'error': 'ValidationFailed',
                'details': [{'field': 'tags', 'message': 'Invalid tags JSON'}]
            }), 400

        # Validate required project tag
        if 'project' not in tags:
            logger.warning(f"UPLOAD_VALIDATION_FAILED: Missing 'project' tag from {client_ip}")
            return jsonify({
                'error': 'ValidationFailed',
                'details': [{'field': 'tags', 'message': 'Missing required tag: project'}]
            }), 400

        # Validate tag formats
        validated_tags = {}
        for k, v in tags.items():
            if not validate_tag_key(k) or not validate_tag_value(v):
                return jsonify({
                    'error': 'ValidationFailed',
                    'details': [{'field': 'tags', 'message': f'Invalid tag format: {k}={v}'}]
                }), 400
            validated_tags[k] = v

        # Handle reserved tag collisions
        effective_tags = handle_reserved_tags(validated_tags)

        # 2. File Type & Signature Validation
        if not validate_pdf_signature(pdf_file.stream):
            logger.warning(f"UPLOAD_VALIDATION_FAILED: Invalid PDF signature from {client_ip} - file: {pdf_file.filename}")
            return jsonify({
                'error': 'ValidationFailed',
                'details': [{'field': 'architectureDiagram', 'message': 'Only PDF is allowed and signature must match.'}]
            }), 400
        if not validate_docx_signature(docx_file.stream):
            logger.warning(f"UPLOAD_VALIDATION_FAILED: Invalid DOCX signature from {client_ip} - file: {docx_file.filename}")
            return jsonify({
                'error': 'ValidationFailed',
                'details': [{'field': 'charter', 'message': 'Only DOCX is allowed, signature must match, and must contain word/document.xml.'}]
            }), 400

        # 3. Processing (Hashing and sizes)
        pdf_file.stream.seek(0)
        pdf_content = pdf_file.stream.read()
        pdf_size = len(pdf_content)
        pdf_file.stream.seek(0)
        pdf_hash = compute_sha256(pdf_file.stream)

        docx_file.stream.seek(0)
        docx_content = docx_file.stream.read()
        docx_size = len(docx_content)
        docx_file.stream.seek(0)
        docx_hash = compute_sha256(docx_file.stream)

        submission_id = str(uuid.uuid4())
        # Use Eastern Time for timestamps (handles EST/EDT automatically)
        eastern = ZoneInfo("America/New_York")
        timestamp = datetime.datetime.now(eastern).isoformat()

        # 4. Create Zip & Manifest
        manifest = {
            "submissionId": submission_id,
            "submittedAt": timestamp,
            "submittedBy": "user@example.com", # Placeholder
            "tags": effective_tags,
            "scan": {"scanStatus": "pending"},
            "files": [
                {
                    "field": "architectureDiagram",
                    "documentType": "architecture-diagram",
                    "originalFileName": secure_filename(pdf_file.filename),
                    "storedPathInZip": "files/architecture-diagram.pdf",
                    "contentTypeVerified": "application/pdf",
                    "sizeBytes": pdf_size,
                    "sha256": pdf_hash,
                    "effectiveTags": {
                        "documentType": "architecture-diagram",
                        "sourceForm": "upload-project-artifacts",
                        **effective_tags
                    }
                },
                {
                    "field": "charter",
                    "documentType": "charter",
                    "originalFileName": secure_filename(docx_file.filename),
                    "storedPathInZip": "files/charter.docx",
                    "contentTypeVerified": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    "sizeBytes": docx_size,
                    "sha256": docx_hash,
                    "effectiveTags": {
                        "documentType": "charter",
                        "sourceForm": "upload-project-artifacts",
                        **effective_tags
                    }
                }
            ]
        }

        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            # Add files with fixed names
            zip_file.writestr("files/architecture-diagram.pdf", pdf_content)
            zip_file.writestr("files/charter.docx", docx_content)
            # Add manifest
            zip_file.writestr("manifest.json", json.dumps(manifest, indent=2))

        zip_buffer.seek(0)
        zip_hash = compute_sha256(zip_buffer)
        zip_buffer.seek(0, 2)  # Seek to end
        zip_size = zip_buffer.tell()
        zip_buffer.seek(0)

        # Update manifest with zip metadata
        manifest["zip"] = {
            "zipSha256": zip_hash,
            "zipSizeBytes": zip_size
        }

        # Recreate zip with updated manifest
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            zip_file.writestr("files/architecture-diagram.pdf", pdf_content)
            zip_file.writestr("files/charter.docx", docx_content)
            zip_file.writestr("manifest.json", json.dumps(manifest, indent=2))

        zip_buffer.seek(0)

        # Update manifest with zip hash (conceptually circular/tricky if inside, usually track outside or update metadata)
        # The spec says "Store in manifest.json ... AND blob metadata".
        # Actually changing the manifest inside the zip changes the zip hash.
        # We usually store zipSha256 in the response and blob metadata, NOT inside the zip manifest itself
        # (unless we do a multi-pass, but then the hash changes).
        # Spec text: "Store in: manifest.json" -> This implies a logical impossiblity effectively if the manifest is inside the zip.
        # I'll stick to putting it in metadata and response, scan event, etc.
        # Valid interpretation: manifest inside zip describes the CONTENTS (files), global metadata describes the ZIP.

        # 5. Storage (Azure or Local Fallback)
        eastern = ZoneInfo("America/New_York")
        now_et = datetime.datetime.now(eastern)
        zip_name = f"upload_{now_et.strftime('%Y-%m-%dT%H-%M-%S')}_{submission_id}.zip"
        blob_path = f"uploads/{now_et.strftime('%Y/%m/%d')}/{submission_id}.zip"

        upload_success = False
        storage_location = "local"

        if AZURE_STORAGE_ACCOUNT_URL:
            try:
                # Use account key if available, otherwise use Managed Identity
                if AZURE_STORAGE_ACCOUNT_KEY:
                    blob_service_client = BlobServiceClient(
                        account_url=AZURE_STORAGE_ACCOUNT_URL,
                        credential=AZURE_STORAGE_ACCOUNT_KEY
                    )
                else:
                    credential = DefaultAzureCredential()
                    blob_service_client = BlobServiceClient(
                        account_url=AZURE_STORAGE_ACCOUNT_URL,
                        credential=credential
                    )
                container_client = blob_service_client.get_container_client(AZURE_CONTAINER_NAME)
                # Check if container exists
                if not container_client.exists():
                     container_client.create_container()

                blob_client = container_client.get_blob_client(blob_path)

                metadata = {
                    "submissionId": submission_id,
                    "sourceForm": "upload-project-artifacts",
                    "scanStatus": "pending",
                    "zipSha256": zip_hash,
                    "submittedAt": timestamp,
                    "docTypes": "architecture-diagram,charter"
                }

                # Normalize tags for Azure Blob Index
                tags_for_index = {
                    "project": normalize_tag_for_index(effective_tags.get("project", "unknown")),
                    "scanStatus": "pending",
                    "sourceForm": "upload-project-artifacts"
                }

                # Add optional tags if present
                if "environment" in effective_tags:
                    tags_for_index["environment"] = normalize_tag_for_index(effective_tags["environment"])
                if "domain" in effective_tags:
                    tags_for_index["domain"] = normalize_tag_for_index(effective_tags["domain"])

                zip_buffer.seek(0)
                blob_client.upload_blob(zip_buffer, metadata=metadata, tags=tags_for_index)
                upload_success = True
                storage_location = "azure"
                logger.info(f"UPLOAD_SUCCESS: {submission_id} uploaded to Azure at {blob_path} - {zip_size} bytes")

                # Virus scanning with Azure Defender
                logger.info(f"SCAN_START: Initiating virus scan for {submission_id}")
                scan_status, scan_details = wait_for_scan_result(blob_client, timeout=30)

                if scan_status == ScanResult.MALICIOUS:
                    logger.error(f"SCAN_MALICIOUS: Malware detected in {submission_id} - {scan_details}")
                    # Quarantine the infected file
                    quarantine_result = quarantine_blob(blob_client, blob_service_client, scan_status, scan_details)
                    return jsonify({
                        "error": "MalwareDetected",
                        "submissionId": submission_id,
                        "scanStatus": "malicious",
                        "scanDetails": scan_details,
                        "quarantined": quarantine_result.get("quarantined", False),
                        "message": "File failed security scan and has been quarantined"
                    }), 403

                elif scan_status == ScanResult.CLEAN:
                    logger.info(f"SCAN_CLEAN: File {submission_id} passed virus scan")
                    update_blob_scan_status(blob_client, "clean", scan_details)
                    manifest["scan"]["scanStatus"] = "clean"
                    manifest["scan"]["scanDetails"] = scan_details

                else:
                    # Pending, timeout, or error - mark as pending but allow proceed
                    logger.warning(f"SCAN_PENDING: Scan not completed for {submission_id} - {scan_status}")
                    update_blob_scan_status(blob_client, "pending", scan_details)
                    manifest["scan"]["scanStatus"] = "pending"
                    manifest["scan"]["scanNote"] = "Scan in progress or defender not enabled"

            except Exception as e:
                logger.error(f"UPLOAD_AZURE_FAILED: {submission_id} - {str(e)}")
                # Fallback to local

        if not upload_success:
             # Local save
             local_path = os.path.join(LOCAL_STORAGE_FALLBACK, zip_name)
             zip_buffer.seek(0)
             with open(local_path, 'wb') as f:
                 f.write(zip_buffer.read())
             logger.info(f"UPLOAD_FALLBACK: {submission_id} saved locally to {local_path} - {zip_size} bytes")

        return jsonify({
            "submissionId": submission_id,
            "blobPath": blob_path,
            "zipSha256": zip_hash,
            "fileHashes": {
                "architectureDiagramSha256": pdf_hash,
                "charterSha256": docx_hash
            },
            "scanStatus": manifest["scan"]["scanStatus"],
            "scanDetails": manifest["scan"].get("scanDetails", {}),
            "storageMode": storage_location,
            "status": "uploaded"
        }), 201

    except Exception as e:
        logger.error(f"UPLOAD_ERROR: Failed from {client_ip} - {str(e)}", exc_info=True)
        return jsonify({
            'error': 'UploadFailed',
            'details': [{'field': 'general', 'message': str(e)}]
        }), 500


@app.route('/submit', methods=['POST'])
@limiter.limit("20 per hour")
def flexible_submit():
    """Flexible file upload endpoint that accepts any number of files with any field names"""
    client_ip = request.remote_addr
    logger.info(f"FLEXIBLE_SUBMIT_START: New submission from {client_ip}")
    
    try:
        # 1. Check if any files were uploaded
        if not request.files:
            logger.warning(f"FLEXIBLE_SUBMIT_VALIDATION_FAILED: No files uploaded from {client_ip}")
            return jsonify({
                'error': 'ValidationFailed',
                'details': [{'field': 'files', 'message': 'At least one file is required'}]
            }), 400

        # 2. Get tags (optional but recommended)
        tags_raw = request.form.get('tags', '{}')
        try:
            tags = json.loads(tags_raw)
        except:
            logger.warning(f"FLEXIBLE_SUBMIT_VALIDATION_FAILED: Invalid JSON in tags from {client_ip}")
            return jsonify({
                'error': 'ValidationFailed',
                'details': [{'field': 'tags', 'message': 'Invalid tags JSON format'}]
            }), 400

        # Validate tag formats
        validated_tags = {}
        for k, v in tags.items():
            if not validate_tag_key(k) or not validate_tag_value(v):
                return jsonify({
                    'error': 'ValidationFailed',
                    'details': [{'field': 'tags', 'message': f'Invalid tag format: {k}={v}'}]
                }), 400
            validated_tags[k] = v

        # Handle reserved tag collisions
        effective_tags = handle_reserved_tags(validated_tags)

        # 3. Get form identifier (optional)
        form_id = request.form.get('formId', 'generic-form')
        
        # 4. Process all uploaded files
        files_data = []
        total_size = 0
        file_errors = []

        for field_name in request.files:
            file_obj = request.files[field_name]
            
            # Skip empty files
            if not file_obj or file_obj.filename == '':
                continue

            # Detect file type
            file_type, mime_type, extension = detect_file_type(file_obj.stream, file_obj.filename)
            
            if not file_type:
                file_errors.append({
                    'field': field_name,
                    'filename': file_obj.filename,
                    'message': 'Unsupported file type or invalid file signature'
                })
                continue

            # Read file content
            file_obj.stream.seek(0)
            content = file_obj.stream.read()
            file_size = len(content)

            # Check individual file size
            if file_size > MAX_FILE_SIZE:
                file_errors.append({
                    'field': field_name,
                    'filename': file_obj.filename,
                    'message': f'File size {file_size} bytes exceeds maximum {MAX_FILE_SIZE} bytes'
                })
                continue

            total_size += file_size

            # Compute hash
            file_hash = hashlib.sha256(content).hexdigest()

            # Create sanitized storage name
            base_name = os.path.splitext(secure_filename(file_obj.filename))[0]
            stored_name = f"{secure_filename(field_name)}_{base_name}{extension}"

            files_data.append({
                'field': field_name,
                'documentType': secure_filename(field_name),
                'originalFileName': secure_filename(file_obj.filename),
                'storedPathInZip': f'files/{stored_name}',
                'contentTypeVerified': mime_type,
                'fileType': file_type,
                'sizeBytes': file_size,
                'sha256': file_hash,
                'content': content,
                'effectiveTags': {
                    'documentType': secure_filename(field_name),
                    'sourceForm': form_id,
                    **effective_tags
                }
            })

        # Check if we have any valid files
        if not files_data:
            logger.warning(f"FLEXIBLE_SUBMIT_VALIDATION_FAILED: No valid files from {client_ip}")
            return jsonify({
                'error': 'ValidationFailed',
                'details': file_errors if file_errors else [{'field': 'files', 'message': 'No valid files uploaded'}]
            }), 400

        # Check total size
        if total_size > MAX_TOTAL_SIZE:
            logger.warning(f"FLEXIBLE_SUBMIT_VALIDATION_FAILED: Total size {total_size} exceeds limit from {client_ip}")
            return jsonify({
                'error': 'ValidationFailed',
                'details': [{'field': 'files', 'message': f'Total file size {total_size} bytes exceeds maximum {MAX_TOTAL_SIZE} bytes'}]
            }), 400

        # 5. Create manifest
        submission_id = str(uuid.uuid4())
        eastern = ZoneInfo("America/New_York")
        timestamp = datetime.datetime.now(eastern).isoformat()

        logger.info(f"FLEXIBLE_SUBMIT_PROCESSING: {submission_id} from {client_ip} - Form: {form_id}, Files: {len(files_data)}, Size: {total_size}")

        manifest = {
            "submissionId": submission_id,
            "submittedAt": timestamp,
            "sourceForm": form_id,
            "submittedBy": request.form.get('submittedBy', 'anonymous'),
            "tags": effective_tags,
            "scan": {"scanStatus": "pending"},
            "files": [{k: v for k, v in f.items() if k != 'content'} for f in files_data]
        }

        # 6. Create zip
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for file_data in files_data:
                zip_file.writestr(file_data['storedPathInZip'], file_data['content'])
            zip_file.writestr("manifest.json", json.dumps(manifest, indent=2))

        zip_buffer.seek(0)
        zip_hash = compute_sha256(zip_buffer)
        zip_buffer.seek(0, 2)
        zip_size = zip_buffer.tell()
        zip_buffer.seek(0)

        manifest["zip"] = {"zipSha256": zip_hash, "zipSizeBytes": zip_size}

        # Recreate zip with updated manifest
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for file_data in files_data:
                zip_file.writestr(file_data['storedPathInZip'], file_data['content'])
            zip_file.writestr("manifest.json", json.dumps(manifest, indent=2))

        zip_buffer.seek(0)

        # 7. Upload to Azure Blob Storage
        now_et = datetime.datetime.now(eastern)
        zip_name = f"submission_{now_et.strftime('%Y-%m-%dT%H-%M-%S')}_{submission_id}.zip"
        blob_path = f"submissions/{now_et.strftime('%Y/%m/%d')}/{submission_id}.zip"

        upload_success = False
        storage_location = "local"

        if AZURE_STORAGE_ACCOUNT_URL:
            try:
                if AZURE_STORAGE_ACCOUNT_KEY:
                    blob_service_client = BlobServiceClient(
                        account_url=AZURE_STORAGE_ACCOUNT_URL,
                        credential=AZURE_STORAGE_ACCOUNT_KEY
                    )
                else:
                    credential = DefaultAzureCredential()
                    blob_service_client = BlobServiceClient(
                        account_url=AZURE_STORAGE_ACCOUNT_URL,
                        credential=credential
                    )
                container_client = blob_service_client.get_container_client(AZURE_CONTAINER_NAME)
                if not container_client.exists():
                    container_client.create_container()

                blob_client = container_client.get_blob_client(blob_path)

                metadata = {
                    "submissionId": submission_id,
                    "sourceForm": form_id,
                    "scanStatus": "pending",
                    "zipSha256": zip_hash,
                    "submittedAt": timestamp,
                    "fileCount": str(len(files_data))
                }

                # Add custom tags from form
                for key, value in effective_tags.items():
                    metadata[f"tag_{key}"] = str(value)[:256]  # Limit length

                # Normalize tags for Azure Blob Index
                tags_for_index = {
                    "sourceForm": normalize_tag_for_index(form_id),
                    "scanStatus": "pending",
                    "fileCount": str(len(files_data))
                }

                # Add user tags to index (up to 10 total)
                index_tag_count = len(tags_for_index)
                for key, value in effective_tags.items():
                    if index_tag_count >= 10:
                        break
                    tags_for_index[key] = normalize_tag_for_index(value)
                    index_tag_count += 1

                zip_buffer.seek(0)
                blob_client.upload_blob(zip_buffer, metadata=metadata, tags=tags_for_index)
                upload_success = True
                storage_location = "azure"
                logger.info(f"FLEXIBLE_SUBMIT_SUCCESS: {submission_id} uploaded to Azure at {blob_path} - {zip_size} bytes")

                # Virus scanning with Azure Defender
                logger.info(f"FLEXIBLE_SUBMIT_SCAN_START: Initiating virus scan for {submission_id}")
                scan_status, scan_details = wait_for_scan_result(blob_client, timeout=30)

                if scan_status == ScanResult.MALICIOUS:
                    logger.error(f"FLEXIBLE_SUBMIT_SCAN_MALICIOUS: Malware detected in {submission_id} - {scan_details}")
                    quarantine_result = quarantine_blob(blob_client, blob_service_client, scan_status, scan_details)
                    return jsonify({
                        "error": "MalwareDetected",
                        "submissionId": submission_id,
                        "scanStatus": "malicious",
                        "scanDetails": scan_details,
                        "quarantined": quarantine_result.get("quarantined", False),
                        "message": "File failed security scan and has been quarantined"
                    }), 403

                elif scan_status == ScanResult.CLEAN:
                    logger.info(f"FLEXIBLE_SUBMIT_SCAN_CLEAN: File {submission_id} passed virus scan")
                    update_blob_scan_status(blob_client, "clean", scan_details)
                    manifest["scan"]["scanStatus"] = "clean"
                    manifest["scan"]["scanDetails"] = scan_details

                else:
                    logger.warning(f"FLEXIBLE_SUBMIT_SCAN_PENDING: Scan not completed for {submission_id} - {scan_status}")
                    update_blob_scan_status(blob_client, "pending", scan_details)
                    manifest["scan"]["scanStatus"] = "pending"
                    manifest["scan"]["scanNote"] = "Scan in progress or defender not enabled"

            except Exception as e:
                logger.error(f"FLEXIBLE_SUBMIT_AZURE_FAILED: {submission_id} - {str(e)}")

        if not upload_success:
            local_path = os.path.join(LOCAL_STORAGE_FALLBACK, zip_name)
            zip_buffer.seek(0)
            with open(local_path, 'wb') as f:
                f.write(zip_buffer.read())
            logger.info(f"FLEXIBLE_SUBMIT_FALLBACK: {submission_id} saved locally to {local_path} - {zip_size} bytes")

        # 8. Send confirmation email (if email provided)
        email_sent = False
        # Check for email in multiple form fields
        recipient_email = request.form.get('email') or request.form.get('submittedBy')
        # Validate it looks like an email (contains @)
        if recipient_email and '@' in recipient_email:
            email_result = send_generic_submission_email({
                "submissionId": submission_id,
                "email": recipient_email,
                "submittedBy": request.form.get('submittedBy', recipient_email),
                "sourceForm": form_id,
                "submittedAt": timestamp,
                "files": files_data,
                "scanStatus": manifest["scan"]["scanStatus"],
                "scanDetails": manifest["scan"].get("scanDetails", {}),
                "blobPath": blob_path,
                "tags": effective_tags
            })
            if email_result.get("success"):
                email_sent = True
                logger.info(f"FLEXIBLE_SUBMIT_EMAIL_SENT: Confirmation email sent to {recipient_email}")
            else:
                logger.warning(f"FLEXIBLE_SUBMIT_EMAIL_FAILED: {email_result.get('message')}")
        else:
            logger.info(f"FLEXIBLE_SUBMIT_NO_EMAIL: No valid email provided for submission {submission_id}")

        # 9. Build response
        response_data = {
            "submissionId": submission_id,
            "blobPath": blob_path,
            "zipSha256": zip_hash,
            "fileCount": len(files_data),
            "files": [{
                "field": f["field"],
                "originalFileName": f["originalFileName"],
                "fileType": f["fileType"],
                "sizeBytes": f["sizeBytes"],
                "sha256": f["sha256"]
            } for f in files_data],
            "scanStatus": manifest["scan"]["scanStatus"],
            "scanDetails": manifest["scan"].get("scanDetails", {}),
            "storageMode": storage_location,
            "status": "uploaded"
        }

        # Add warnings if any files were rejected
        if file_errors:
            response_data["warnings"] = file_errors

        # Add email status if sending was attempted
        if email_sent:
            response_data["emailSent"] = True
            response_data["emailRecipient"] = recipient_email

        return jsonify(response_data), 201

    except Exception as e:
        logger.error(f"FLEXIBLE_SUBMIT_ERROR: Failed from {client_ip} - {str(e)}", exc_info=True)
        return jsonify({
            'error': 'UploadFailed',
            'details': [{'field': 'general', 'message': str(e)}]
        }), 500


@app.route('/rfpi-submit', methods=['POST'])
@limiter.limit("20 per hour")  # More restrictive for upload endpoint
def submit_rfpi_proposal():
    client_ip = request.remote_addr
    logger.info(f"RFPI_SUBMIT_START: New RFPI submission from {client_ip}")
    """Handle USABC RFPI Proposal Form submissions"""
    try:
        # 1. Validate form fields
        required_fields = [
            'proposalTitle', 'entityName', 'entityUEI', 'email',
            'firstName', 'lastName', 'phone'
        ]

        missing_fields = [f for f in required_fields if not request.form.get(f)]
        if missing_fields:
            logger.warning(f"RFPI_VALIDATION_FAILED: Missing fields {missing_fields} from {client_ip}")
            return jsonify({
                'error': 'ValidationFailed',
                'details': [{'field': f, 'message': f'Required field missing'} for f in missing_fields]
            }), 400

        # 2. Validate file uploads
        required_files = {
            'rfpiProposal': 'PDF',
            'financialDocuments': 'PDF',
            'additionalDocuments': 'PDF',
            'budgetJustification': 'Excel'
        }

        file_errors = []
        for field_name, file_type in required_files.items():
            if field_name not in request.files:
                file_errors.append({'field': field_name, 'message': f'{file_type} file required'})
            elif request.files[field_name].filename == '':
                file_errors.append({'field': field_name, 'message': f'{file_type} file required'})

        if file_errors:
            logger.warning(f"RFPI_VALIDATION_FAILED: File errors from {client_ip} - {file_errors}")
            return jsonify({'error': 'ValidationFailed', 'details': file_errors}), 400

        # 3. Get files
        rfpi_proposal = request.files['rfpiProposal']
        financial_docs = request.files['financialDocuments']
        additional_docs = request.files['additionalDocuments']
        budget_justification = request.files['budgetJustification']

        # Optional files
        optional_budget_1 = request.files.get('optionalBudget1')
        optional_budget_2 = request.files.get('optionalBudget2')

        # 4. Validate file signatures
        if not validate_pdf_signature(rfpi_proposal.stream):
            logger.warning(f"RFPI_VALIDATION_FAILED: Invalid RFPI proposal PDF from {client_ip} - {rfpi_proposal.filename}")
            return jsonify({
                'error': 'ValidationFailed',
                'details': [{'field': 'rfpiProposal', 'message': 'Must be a valid PDF file'}]
            }), 400

        if not validate_pdf_signature(financial_docs.stream):
            logger.warning(f"RFPI_VALIDATION_FAILED: Invalid financial docs PDF from {client_ip} - {financial_docs.filename}")
            return jsonify({
                'error': 'ValidationFailed',
                'details': [{'field': 'financialDocuments', 'message': 'Must be a valid PDF file'}]
            }), 400

        if not validate_pdf_signature(additional_docs.stream):
            logger.warning(f"RFPI_VALIDATION_FAILED: Invalid additional docs PDF from {client_ip} - {additional_docs.filename}")
            return jsonify({
                'error': 'ValidationFailed',
                'details': [{'field': 'additionalDocuments', 'message': 'Must be a valid PDF file'}]
            }), 400

        if not validate_excel_signature(budget_justification.stream):
            logger.warning(f"RFPI_VALIDATION_FAILED: Invalid Excel file from {client_ip} - {budget_justification.filename}")
            return jsonify({
                'error': 'ValidationFailed',
                'details': [{'field': 'budgetJustification', 'message': 'Must be a valid Excel file (.xls or .xlsx)'}]
            }), 400

        # 5. Process files and compute hashes
        files_data = []

        # Process each required file
        for file_obj, field_name, doc_type, stored_name in [
            (rfpi_proposal, 'rfpiProposal', 'rfpi-proposal', 'rfpi-proposal.pdf'),
            (financial_docs, 'financialDocuments', 'financial-documents', 'financial-documents.pdf'),
            (additional_docs, 'additionalDocuments', 'additional-documents', 'additional-documents.pdf'),
            (budget_justification, 'budgetJustification', 'budget-justification',
             f"budget-justification{os.path.splitext(budget_justification.filename)[1]}")
        ]:
            file_obj.stream.seek(0)
            content = file_obj.stream.read()
            file_obj.stream.seek(0)

            files_data.append({
                'field': field_name,
                'documentType': doc_type,
                'originalFileName': secure_filename(file_obj.filename),
                'storedPathInZip': f'files/{stored_name}',
                'sizeBytes': len(content),
                'sha256': hashlib.sha256(content).hexdigest(),
                'content': content
            })

        # Process optional files
        if optional_budget_1 and optional_budget_1.filename:
            if validate_excel_signature(optional_budget_1.stream):
                optional_budget_1.stream.seek(0)
                content = optional_budget_1.stream.read()
                files_data.append({
                    'field': 'optionalBudget1',
                    'documentType': 'optional-budget-tier1',
                    'originalFileName': secure_filename(optional_budget_1.filename),
                    'storedPathInZip': f'files/optional-budget-tier1{os.path.splitext(optional_budget_1.filename)[1]}',
                    'sizeBytes': len(content),
                    'sha256': hashlib.sha256(content).hexdigest(),
                    'content': content
                })

        if optional_budget_2 and optional_budget_2.filename:
            if validate_excel_signature(optional_budget_2.stream):
                optional_budget_2.stream.seek(0)
                content = optional_budget_2.stream.read()
                files_data.append({
                    'field': 'optionalBudget2',
                    'documentType': 'optional-budget-tier2',
                    'originalFileName': secure_filename(optional_budget_2.filename),
                    'storedPathInZip': f'files/optional-budget-tier2{os.path.splitext(optional_budget_2.filename)[1]}',
                    'sizeBytes': len(content),
                    'sha256': hashlib.sha256(content).hexdigest(),
                    'content': content
                })

        # 6. Create manifest
        submission_id = str(uuid.uuid4())
        # Use Eastern Time for timestamps (handles EST/EDT automatically)
        eastern = ZoneInfo("America/New_York")
        timestamp = datetime.datetime.now(eastern).isoformat()

        entity_name = request.form.get('entityName', 'unknown')
        proposal_title = request.form.get('proposalTitle', 'untitled')
        logger.info(f"RFPI_PROCESSING: {submission_id} from {client_ip} - Entity: {entity_name}, Proposal: {proposal_title}, Files: {len(files_data)}")

        manifest = {
            "submissionId": submission_id,
            "submittedAt": timestamp,
            "formType": "usabc-rfpi-proposal",
            "applicantInfo": {
                "proposalTitle": request.form.get('proposalTitle'),
                "entityName": request.form.get('entityName'),
                "entityUEI": request.form.get('entityUEI'),
                "email": request.form.get('email'),
                "firstName": request.form.get('firstName'),
                "lastName": request.form.get('lastName'),
                "phone": request.form.get('phone')
            },
            "rfpiInfo": {
                "title": request.args.get('rfpi-title', ''),
                "category": request.args.get('rfpi-category', '')
            },
            "scan": {"scanStatus": "pending"},
            "files": [{k: v for k, v in f.items() if k != 'content'} for f in files_data]
        }

        # 7. Create zip
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for file_data in files_data:
                zip_file.writestr(file_data['storedPathInZip'], file_data['content'])
            zip_file.writestr("manifest.json", json.dumps(manifest, indent=2))

        zip_buffer.seek(0)
        zip_hash = compute_sha256(zip_buffer)
        zip_buffer.seek(0, 2)
        zip_size = zip_buffer.tell()
        zip_buffer.seek(0)

        manifest["zip"] = {"zipSha256": zip_hash, "zipSizeBytes": zip_size}

        # Recreate zip with updated manifest
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for file_data in files_data:
                zip_file.writestr(file_data['storedPathInZip'], file_data['content'])
            zip_file.writestr("manifest.json", json.dumps(manifest, indent=2))

        zip_buffer.seek(0)

        # 8. Upload to Azure Blob Storage
        eastern = ZoneInfo("America/New_York")
        now_et = datetime.datetime.now(eastern)
        zip_name = f"rfpi_{now_et.strftime('%Y-%m-%dT%H-%M-%S')}_{submission_id}.zip"
        blob_path = f"rfpi-submissions/{now_et.strftime('%Y/%m/%d')}/{submission_id}.zip"

        upload_success = False
        storage_location = "local"

        if AZURE_STORAGE_ACCOUNT_URL:
            try:
                if AZURE_STORAGE_ACCOUNT_KEY:
                    blob_service_client = BlobServiceClient(
                        account_url=AZURE_STORAGE_ACCOUNT_URL,
                        credential=AZURE_STORAGE_ACCOUNT_KEY
                    )
                else:
                    credential = DefaultAzureCredential()
                    blob_service_client = BlobServiceClient(
                        account_url=AZURE_STORAGE_ACCOUNT_URL,
                        credential=credential
                    )
                container_client = blob_service_client.get_container_client(AZURE_CONTAINER_NAME)
                if not container_client.exists():
                    container_client.create_container()

                blob_client = container_client.get_blob_client(blob_path)

                metadata = {
                    "submissionId": submission_id,
                    "formType": "usabc-rfpi-proposal",
                    "entityName": request.form.get('entityName'),
                    "proposalTitle": request.form.get('proposalTitle'),
                    "scanStatus": "pending",
                    "zipSha256": zip_hash,
                    "submittedAt": timestamp
                }

                tags_for_index = {
                    "formType": "usabc-rfpi-proposal",
                    "entityName": normalize_tag_for_index(request.form.get('entityName', 'unknown')),
                    "scanStatus": "pending"
                }

                zip_buffer.seek(0)
                blob_client.upload_blob(zip_buffer, metadata=metadata, tags=tags_for_index)
                upload_success = True
                storage_location = "azure"
                logger.info(f"RFPI_SUCCESS: {submission_id} uploaded to Azure at {blob_path} - entity: {entity_name}")

                # Virus scanning with Azure Defender
                logger.info(f"RFPI_SCAN_START: Initiating virus scan for {submission_id}")
                scan_status, scan_details = wait_for_scan_result(blob_client, timeout=30)

                if scan_status == ScanResult.MALICIOUS:
                    logger.error(f"RFPI_SCAN_MALICIOUS: Malware detected in {submission_id} - {scan_details}")
                    quarantine_result = quarantine_blob(blob_client, blob_service_client, scan_status, scan_details)
                    return jsonify({
                        "error": "MalwareDetected",
                        "submissionId": submission_id,
                        "scanStatus": "malicious",
                        "scanDetails": scan_details,
                        "quarantined": quarantine_result.get("quarantined", False),
                        "message": "File failed security scan and has been quarantined"
                    }), 403

                elif scan_status == ScanResult.CLEAN:
                    logger.info(f"RFPI_SCAN_CLEAN: File {submission_id} passed virus scan")
                    update_blob_scan_status(blob_client, "clean", scan_details)
                    manifest["scan"]["scanStatus"] = "clean"
                    manifest["scan"]["scanDetails"] = scan_details

                else:
                    logger.warning(f"RFPI_SCAN_PENDING: Scan not completed for {submission_id} - {scan_status}")
                    update_blob_scan_status(blob_client, "pending", scan_details)
                    manifest["scan"]["scanStatus"] = "pending"
                    manifest["scan"]["scanNote"] = "Scan in progress or defender not enabled"

            except Exception as e:
                logger.error(f"RFPI_AZURE_FAILED: {submission_id} - {str(e)}")

        if not upload_success:
            local_path = os.path.join(LOCAL_STORAGE_FALLBACK, zip_name)
            zip_buffer.seek(0)
            with open(local_path, 'wb') as f:
                f.write(zip_buffer.read())
            logger.info(f"RFPI_FALLBACK: {submission_id} saved locally to {local_path} - {zip_size} bytes")

        # Send confirmation email
        email_result = send_rfpi_confirmation_email({
            "submissionId": submission_id,
            "email": request.form.get('email'),
            "entityName": request.form.get('entityName'),
            "proposalTitle": request.form.get('proposalTitle'),
            "firstName": request.form.get('firstName'),
            "lastName": request.form.get('lastName'),
            "rfpiTitle": request.args.get('rfpi-title', ''),
            "submittedAt": timestamp,
            "files": manifest["files"],
            "scanStatus": manifest["scan"]["scanStatus"],
            "blobPath": blob_path
        })

        response_data = {
            "submissionId": submission_id,
            "blobPath": blob_path,
            "zipSha256": zip_hash,
            "fileCount": len(files_data),
            "scanStatus": manifest["scan"]["scanStatus"],
            "scanDetails": manifest["scan"].get("scanDetails", {}),
            "storageMode": storage_location,
            "status": "uploaded"
        }

        # Add email status if sending was attempted
        if email_result.get("success"):
            response_data["emailSent"] = True
            response_data["emailRecipient"] = request.form.get('email')

        return jsonify(response_data), 201

    except Exception as e:
        logger.error(f"RFPI_ERROR: Failed from {client_ip} - {str(e)}", exc_info=True)
        return jsonify({
            'error': 'UploadFailed',
            'details': [{'field': 'general', 'message': str(e)}]
        }), 500


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=True, host='0.0.0.0', port=port)
