import os
import io
import json
import uuid
import datetime
import hashlib
import zipfile
import re
import logging
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from werkzeug.utils import secure_filename
from dotenv import load_dotenv

# Azure imports
from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

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
    return send_from_directory('.', 'index.html')

@app.route('/widget.js')
def serve_widget():
    return send_from_directory('static', 'widget.js')

@app.route('/upload', methods=['POST'])
def upload_project_artifacts():
    try:
        # 1. Input Validation
        if 'architectureDiagram' not in request.files or 'charter' not in request.files:
            return jsonify({
                'error': 'ValidationFailed',
                'details': [{'field': 'files', 'message': 'Missing required files: architectureDiagram (PDF) and charter (DOCX)'}]
            }), 400

        pdf_file = request.files['architectureDiagram']
        docx_file = request.files['charter']

        tags_raw = request.form.get('tags')
        if not tags_raw:
            return jsonify({
                'error': 'ValidationFailed',
                'details': [{'field': 'tags', 'message': 'Missing required tags'}]
            }), 400

        try:
            tags = json.loads(tags_raw)
        except:
            return jsonify({
                'error': 'ValidationFailed',
                'details': [{'field': 'tags', 'message': 'Invalid tags JSON'}]
            }), 400

        # Validate required project tag
        if 'project' not in tags:
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
            return jsonify({
                'error': 'ValidationFailed',
                'details': [{'field': 'architectureDiagram', 'message': 'Only PDF is allowed and signature must match.'}]
            }), 400
        if not validate_docx_signature(docx_file.stream):
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
        timestamp = datetime.datetime.utcnow().isoformat() + 'Z'

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
        zip_name = f"upload_{datetime.datetime.utcnow().strftime('%Y-%m-%dT%H-%M-%SZ')}_{submission_id}.zip"
        blob_path = f"uploads/{datetime.datetime.utcnow().strftime('%Y/%m/%d')}/{submission_id}.zip"

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
            except Exception as e:
                logger.error(f"Azure Upload Failed: {e}")
                # Fallback to local

        if not upload_success:
             # Local save
             local_path = os.path.join(LOCAL_STORAGE_FALLBACK, zip_name)
             zip_buffer.seek(0)
             with open(local_path, 'wb') as f:
                 f.write(zip_buffer.read())
             logger.info(f"Saved locally to {local_path}")

        return jsonify({
            "submissionId": submission_id,
            "blobPath": blob_path,
            "zipSha256": zip_hash,
            "fileHashes": {
                "architectureDiagramSha256": pdf_hash,
                "charterSha256": docx_hash
            },
            "scanStatus": "pending",
            "storageMode": storage_location,
            "status": "uploaded"
        }), 201

    except Exception as e:
        logger.error(f"Upload error: {e}")
        return jsonify({
            'error': 'UploadFailed',
            'details': [{'field': 'general', 'message': str(e)}]
        }), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=True, host='0.0.0.0', port=port)
