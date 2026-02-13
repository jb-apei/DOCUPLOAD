"""
Email notification module using Azure Communication Services
Sends confirmation emails to file submitters with submission details
"""
import os
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

# Azure Communication Services configuration
ACS_CONNECTION_STRING = os.environ.get("AZURE_COMMUNICATION_CONNECTION_STRING")
ACS_SENDER_ADDRESS = os.environ.get("AZURE_COMMUNICATION_SENDER_ADDRESS", "noreply@uploads.uscar.org")

# Flag to disable email in local development
EMAIL_ENABLED = bool(ACS_CONNECTION_STRING)

try:
    from azure.communication.email import EmailClient
    ACS_AVAILABLE = True
except ImportError:
    ACS_AVAILABLE = False
    if EMAIL_ENABLED:
        logger.warning("Azure Communication Services SDK not available. Email notifications will be disabled.")


def format_file_size(size_bytes):
    """Format file size in human-readable format"""
    for unit in ['bytes', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} TB"


def send_rfpi_confirmation_email(submission_data):
    """
    Send confirmation email for RFPI proposal submission

    Args:
        submission_data: Dictionary containing:
            - submissionId: Unique submission ID
            - email: Recipient email address
            - entityName: Entity name
            - proposalTitle: Proposal title
            - firstName: Submitter's first name
            - lastName: Submitter's last name
            - rfpiTitle: RFPI title from URL parameter (optional)
            - submittedAt: Submission timestamp (ISO format)
            - files: List of file dictionaries with documentType, originalFileName, sizeBytes
            - scanStatus: Virus scan status (clean/pending/malicious)
            - blobPath: Azure blob storage path

    Returns:
        Dictionary with 'success' (bool) and 'message' (str)
    """
    if not EMAIL_ENABLED or not ACS_AVAILABLE:
        logger.info(f"EMAIL_DISABLED: Would have sent email to {submission_data.get('email')} for submission {submission_data.get('submissionId')}")
        return {"success": False, "message": "Email service not configured"}

    try:
        recipient_email = submission_data.get('email')
        submission_id = submission_data.get('submissionId')

        if not recipient_email:
            logger.warning(f"EMAIL_SKIP: No recipient email for submission {submission_id}")
            return {"success": False, "message": "No recipient email provided"}

        # Parse timestamp for display
        submitted_at = submission_data.get('submittedAt', '')
        try:
            dt = datetime.fromisoformat(submitted_at)
            formatted_date = dt.strftime("%B %d, %Y at %I:%M %p %Z")
        except:
            formatted_date = submitted_at

        # Build file summary
        files = submission_data.get('files', [])
        file_count = len(files)
        total_size = sum(f.get('sizeBytes', 0) for f in files)

        file_list_html = ""
        file_list_text = ""
        for file_info in files:
            doc_type = file_info.get('documentType', 'unknown')
            filename = file_info.get('originalFileName', 'unknown')
            size = format_file_size(file_info.get('sizeBytes', 0))
            file_list_html += f"          <li><strong>{doc_type}</strong>: {filename} ({size})</li>\n"
            file_list_text += f"  - {doc_type}: {filename} ({size})\n"

        # Scan status message
        scan_status = submission_data.get('scanStatus', 'pending')
        scan_message_html = ""
        scan_message_text = ""
        if scan_status == "clean":
            scan_message_html = '<p style="color: #28a745; margin: 10px 0;"><strong>✓ Security Scan: PASSED</strong> - All files have been scanned and are clean.</p>'
            scan_message_text = "✓ Security Scan: PASSED - All files have been scanned and are clean.\n"
        elif scan_status == "pending":
            scan_message_html = '<p style="color: #ffc107; margin: 10px 0;"><strong>⏳ Security Scan: IN PROGRESS</strong> - Files are being scanned for security threats.</p>'
            scan_message_text = "⏳ Security Scan: IN PROGRESS - Files are being scanned for security threats.\n"

        # Email content
        first_name = submission_data.get('firstName', '')
        entity_name = submission_data.get('entityName', 'Your organization')
        proposal_title = submission_data.get('proposalTitle', 'Your RFPI proposal')
        rfpi_title = submission_data.get('rfpiTitle', '')

        # Build subject line with RFPI title if provided
        if rfpi_title:
            subject = f"RFPI Proposal Received - {rfpi_title} - {proposal_title}"
        else:
            subject = f"RFPI Proposal Received - {proposal_title}"

        html_body = f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
          <div style="max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #ddd; border-radius: 8px;">
            <h2 style="color: #003366; border-bottom: 2px solid #005599; padding-bottom: 10px;">
              USABC RFPI Proposal Submission Confirmed
            </h2>

            <p>Dear {first_name},</p>

            <p>Thank you for submitting your RFPI proposal to USABC. We have successfully received your submission.</p>

            <div style="background-color: #f8f9fa; padding: 15px; border-radius: 5px; margin: 20px 0;">
              <h3 style="color: #005599; margin-top: 0;">Submission Details</h3>
              <p style="margin: 5px 0;"><strong>Submission ID:</strong> {submission_id}</p>
              <p style="margin: 5px 0;"><strong>Entity:</strong> {entity_name}</p>
              <p style="margin: 5px 0;"><strong>Proposal Title:</strong> {proposal_title}</p>
              <p style="margin: 5px 0;"><strong>Submitted:</strong> {formatted_date}</p>
            </div>

            {scan_message_html}

            <div style="margin: 20px 0;">
              <h3 style="color: #005599;">Files Received ({file_count} files, {format_file_size(total_size)} total)</h3>
              <ul style="list-style-type: none; padding-left: 0;">
{file_list_html}
              </ul>
            </div>

            <div style="background-color: #e7f3ff; padding: 15px; border-left: 4px solid #005599; margin: 20px 0;">
              <p style="margin: 0;"><strong>What happens next?</strong></p>
              <p style="margin: 10px 0 0 0;">Your submission will be reviewed by the USABC team. If we need any additional information or clarification, we will contact you at <strong>{recipient_email}</strong>.</p>
            </div>

            <p style="margin-top: 30px; color: #666; font-size: 0.9em;">
              Please keep this confirmation email for your records. If you have any questions about your submission,
              please reference your Submission ID: <strong>{submission_id}</strong>
            </p>

            <hr style="border: none; border-top: 1px solid #ddd; margin: 30px 0;">

            <p style="color: #666; font-size: 0.85em; margin: 0;">
              United States Advanced Battery Consortium (USABC)<br>
              This is an automated message. Please do not reply directly to this email.
            </p>
          </div>
        </body>
        </html>
        """

        text_body = f"""
USABC RFPI Proposal Submission Confirmed

Dear {first_name},

Thank you for submitting your RFPI proposal to USABC. We have successfully received your submission.

SUBMISSION DETAILS
------------------
Submission ID: {submission_id}
Entity: {entity_name}
Proposal Title: {proposal_title}
Submitted: {formatted_date}

{scan_message_text}
FILES RECEIVED ({file_count} files, {format_file_size(total_size)} total)
-------------
{file_list_text}

WHAT HAPPENS NEXT?
------------------
Your submission will be reviewed by the USABC team. If we need any additional information or clarification,
we will contact you at {recipient_email}.

Please keep this confirmation email for your records. If you have any questions about your submission,
please reference your Submission ID: {submission_id}

---
United States Advanced Battery Consortium (USABC)
This is an automated message. Please do not reply directly to this email.
        """

        # Send email via Azure Communication Services
        email_client = EmailClient.from_connection_string(ACS_CONNECTION_STRING)

        message = {
            "senderAddress": ACS_SENDER_ADDRESS,
            "recipients": {
                "to": [{"address": recipient_email}],
            },
            "content": {
                "subject": subject,
                "plainText": text_body,
                "html": html_body
            }
        }

        logger.info(f"EMAIL_SENDING: To {recipient_email} for submission {submission_id}")
        poller = email_client.begin_send(message)
        result = poller.result()

        logger.info(f"EMAIL_SENT: Successfully sent to {recipient_email} for submission {submission_id} - Message ID: {result.get('messageId') if isinstance(result, dict) else result.message_id}")
        return {
            "success": True,
            "message": f"Confirmation email sent to {recipient_email}",
            "messageId": result.get('messageId') if isinstance(result, dict) else result.message_id
        }

    except Exception as e:
        logger.error(f"EMAIL_ERROR: Failed to send email for submission {submission_data.get('submissionId')} - {str(e)}", exc_info=True)
        return {
            "success": False,
            "message": f"Failed to send confirmation email: {str(e)}"
        }


def send_upload_confirmation_email(submission_data):
    """
    Send confirmation email for simple project artifacts upload

    Args:
        submission_data: Dictionary containing:
            - submissionId: Unique submission ID
            - email: Recipient email address (optional, from metadata or form)
            - submittedAt: Submission timestamp (ISO format)
            - fileCount: Number of files uploaded
            - totalSize: Total size in bytes
            - scanStatus: Virus scan status (clean/pending/malicious)
            - blobPath: Azure blob storage path

    Returns:
        Dictionary with 'success' (bool) and 'message' (str)
    """
    if not EMAIL_ENABLED or not ACS_AVAILABLE:
        logger.info(f"EMAIL_DISABLED: Would have sent email for submission {submission_data.get('submissionId')}")
        return {"success": False, "message": "Email service not configured"}

    try:
        recipient_email = submission_data.get('email')
        submission_id = submission_data.get('submissionId')

        if not recipient_email:
            logger.info(f"EMAIL_SKIP: No recipient email for upload submission {submission_id}")
            return {"success": False, "message": "No recipient email provided"}

        # Parse timestamp
        submitted_at = submission_data.get('submittedAt', '')
        try:
            dt = datetime.fromisoformat(submitted_at)
            formatted_date = dt.strftime("%B %d, %Y at %I:%M %p %Z")
        except:
            formatted_date = submitted_at

        file_count = submission_data.get('fileCount', 0)
        total_size = format_file_size(submission_data.get('totalSize', 0))

        # Scan status message
        scan_status = submission_data.get('scanStatus', 'pending')
        if scan_status == "clean":
            scan_message = "✓ Security Scan: PASSED - All files have been scanned and are clean."
        elif scan_status == "pending":
            scan_message = "⏳ Security Scan: IN PROGRESS - Files are being scanned for security threats."
        else:
            scan_message = "Security scan status: " + scan_status

        subject = f"File Upload Received - Submission {submission_id[:8]}"

        text_body = f"""
USABC File Upload Confirmation

Thank you for your file submission to USABC. We have successfully received your upload.

SUBMISSION DETAILS
------------------
Submission ID: {submission_id}
Submitted: {formatted_date}
Files: {file_count}
Total Size: {total_size}

{scan_message}

Please keep this confirmation email for your records. If you have any questions about your submission,
please reference your Submission ID: {submission_id}

---
United States Advanced Battery Consortium (USABC)
This is an automated message. Please do not reply directly to this email.
        """

        # Send email
        email_client = EmailClient.from_connection_string(ACS_CONNECTION_STRING)

        message = {
            "senderAddress": ACS_SENDER_ADDRESS,
            "recipients": {
                "to": [{"address": recipient_email}],
            },
            "content": {
                "subject": subject,
                "plainText": text_body
            }
        }

        logger.info(f"EMAIL_SENDING: To {recipient_email} for upload {submission_id}")
        poller = email_client.begin_send(message)
        result = poller.result()

        logger.info(f"EMAIL_SENT: Successfully sent to {recipient_email} for upload {submission_id}")
        return {
            "success": True,
            "message": f"Confirmation email sent to {recipient_email}",
            "messageId": result.get('messageId') if isinstance(result, dict) else result.message_id
        }

    except Exception as e:
        logger.error(f"EMAIL_ERROR: Failed to send upload email for {submission_data.get('submissionId')} - {str(e)}", exc_info=True)
        return {
            "success": False,
            "message": f"Failed to send confirmation email: {str(e)}"
        }
