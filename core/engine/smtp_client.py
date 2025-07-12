"""
Email engine components for Bulk Email Sender.

This module provides the core email functionality:
- SMTP client management
- Email building and formatting
- Email sending logic
"""

import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from email.utils import formataddr
import os
import time
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass

from core.data.models import SMTPConfig, Lead, EmailTemplate, SMTPSecurityType
from core.utils.logger import get_module_logger
from core.utils.exceptions import SMTPError, SMTPAuthenticationError, EmailAttachmentError, NetworkTimeoutError
from core.security.path_sanitizer import validate_attachment_path

logger = get_module_logger(__name__)


@dataclass
class EmailMessage:
    """Email message data structure."""
    
    to_email: str
    to_name: str = ""
    subject: str = ""
    html_content: str = ""
    text_content: str = ""
    attachments: List[str] = None
    custom_headers: Dict[str, str] = None
    
    def __post_init__(self):
        if self.attachments is None:
            self.attachments = []
        if self.custom_headers is None:
            self.custom_headers = {}


class SMTPClient:
    """Manages SMTP connections and email sending."""
    
    def __init__(self, smtp_config: SMTPConfig):
        """
        Initialize SMTP client.
        
        Args:
            smtp_config: SMTP configuration
        """
        self.config = smtp_config
        self._server: Optional[smtplib.SMTP] = None
        self._connected = False
        self._authenticated = False
        
        logger.debug(f"SMTP client initialized for {smtp_config.host}:{smtp_config.port}")
    
    def connect(self) -> bool:
        """
        Establish SMTP connection.
        
        Returns:
            True if connected successfully
            
        Raises:
            SMTPError: If connection fails
        """
        try:
            if self._connected:
                return True
            
            # Create SMTP connection based on security type
            if self.config.security_type == SMTPSecurityType.SSL:
                self._server = smtplib.SMTP_SSL(
                    self.config.host,
                    self.config.port,
                    timeout=self.config.timeout
                )
            else:
                self._server = smtplib.SMTP(
                    self.config.host,
                    self.config.port,
                    timeout=self.config.timeout
                )
            
            # Send EHLO command
            self._server.ehlo()
            
            # Start TLS if required
            if self.config.use_tls and self.config.security_type != SMTPSecurityType.SSL:
                if self._server.has_extn('STARTTLS'):
                    self._server.starttls()
                    self._server.ehlo()  # Send EHLO again after STARTTLS
                else:
                    raise SMTPError("STARTTLS required but not supported by server")
            
            self._connected = True
            logger.info(f"SMTP connection established to {self.config.host}:{self.config.port}")
            return True
            
        except smtplib.SMTPConnectError as e:
            raise SMTPError(f"SMTP connection failed: {e}", smtp_host=self.config.host)
        except smtplib.SMTPServerDisconnected as e:
            raise SMTPError(f"SMTP server disconnected: {e}", smtp_host=self.config.host)
        except Exception as e:
            raise SMTPError(f"SMTP connection error: {e}", smtp_host=self.config.host)
    
    def authenticate(self) -> bool:
        """
        Authenticate with SMTP server.
        
        Returns:
            True if authenticated successfully
            
        Raises:
            SMTPAuthenticationError: If authentication fails
        """
        try:
            if not self._connected:
                self.connect()
            
            if self._authenticated:
                return True
            
            self._server.login(self.config.username, self.config.password)
            self._authenticated = True
            
            logger.info(f"SMTP authentication successful for {self.config.username}")
            return True
            
        except smtplib.SMTPAuthenticationError as e:
            raise SMTPAuthenticationError(
                f"SMTP authentication failed: {e}",
                username=self.config.username
            )
        except Exception as e:
            raise SMTPError(f"SMTP authentication error: {e}", smtp_host=self.config.host)
    
    def send_message(self, email_message: EmailMessage, from_email: Optional[str] = None,
                    from_name: Optional[str] = None) -> bool:
        """
        Send an email message.
        
        Args:
            email_message: Email message to send
            from_email: Sender email (uses SMTP username if None)
            from_name: Sender name
            
        Returns:
            True if sent successfully
            
        Raises:
            SMTPError: If sending fails
        """
        try:
            # Ensure connection and authentication
            if not self._authenticated:
                self.authenticate()
            
            # Build the email
            builder = EmailBuilder()
            mime_message = builder.build_message(
                email_message,
                from_email or self.config.username,
                from_name
            )
            
            # Send the email
            self._server.send_message(mime_message)
            
            logger.debug(f"Email sent successfully to {email_message.to_email}")
            return True
            
        except smtplib.SMTPRecipientsRefused as e:
            raise SMTPError(f"Recipients refused: {e}", recipient=email_message.to_email)
        except smtplib.SMTPSenderRefused as e:
            raise SMTPError(f"Sender refused: {e}")
        except smtplib.SMTPDataError as e:
            raise SMTPError(f"SMTP data error: {e}")
        except Exception as e:
            raise SMTPError(f"Email sending failed: {e}")
    
    def disconnect(self) -> None:
        """Disconnect from SMTP server."""
        try:
            if self._server and self._connected:
                self._server.quit()
                logger.info(f"SMTP connection closed to {self.config.host}")
        except Exception as e:
            logger.warning(f"Error closing SMTP connection: {e}")
        finally:
            self._server = None
            self._connected = False
            self._authenticated = False
    
    def is_connected(self) -> bool:
        """Check if SMTP client is connected."""
        return self._connected and self._server is not None
    
    def __enter__(self):
        """Context manager entry."""
        self.connect()
        self.authenticate()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.disconnect()


class EmailBuilder:
    """Builds email messages from templates and data."""
    
    def __init__(self):
        """Initialize email builder."""
        pass
    
    def build_message(self, email_message: EmailMessage, from_email: str,
                     from_name: Optional[str] = None) -> MIMEMultipart:
        """
        Build MIME email message.
        
        Args:
            email_message: Email message data
            from_email: Sender email address
            from_name: Sender name
            
        Returns:
            MIMEMultipart message object
        """
        # Create multipart message
        msg = MIMEMultipart('alternative')
        
        # Set headers
        msg['Subject'] = email_message.subject
        msg['From'] = formataddr((from_name or "", from_email))
        msg['To'] = formataddr((email_message.to_name or "", email_message.to_email))
        
        # Add custom headers
        for header, value in email_message.custom_headers.items():
            msg[header] = value
        
        # Add text content if available
        if email_message.text_content:
            text_part = MIMEText(email_message.text_content, 'plain', 'utf-8')
            msg.attach(text_part)
        
        # Add HTML content if available
        if email_message.html_content:
            html_part = MIMEText(email_message.html_content, 'html', 'utf-8')
            msg.attach(html_part)
        
        # Add attachments
        for attachment_path in email_message.attachments:
            try:
                self._add_attachment(msg, attachment_path)
            except Exception as e:
                logger.error(f"Failed to add attachment {attachment_path}: {e}")
                raise EmailAttachmentError(f"Failed to add attachment: {e}", filename=attachment_path)
        
        return msg
    
    def build_from_template(self, template: EmailTemplate, lead: Lead,
                           from_email: str, from_name: Optional[str] = None,
                           attachments: Optional[List[str]] = None) -> MIMEMultipart:
        """
        Build email message from template and lead data.
        
        Args:
            template: Email template
            lead: Lead data for personalization
            from_email: Sender email address
            from_name: Sender name
            attachments: List of attachment file paths
            
        Returns:
            MIMEMultipart message object
        """
        # Prepare template variables
        variables = {
            'first_name': lead.first_name,
            'last_name': lead.last_name,
            'full_name': lead.full_name,
            'email': lead.email,
            'company': lead.company,
            'title': lead.title,
            'phone': lead.phone
        }
        
        # Add custom fields
        variables.update(lead.custom_fields)
        
        # Render template
        subject, html_content, text_content = template.render(variables)
        
        # Create email message
        email_message = EmailMessage(
            to_email=lead.email,
            to_name=lead.display_name,
            subject=subject,
            html_content=html_content,
            text_content=text_content,
            attachments=attachments or []
        )
        
        return self.build_message(email_message, from_email, from_name)
    
    def _add_attachment(self, msg: MIMEMultipart, filepath: str) -> None:
        """
        Add attachment to email message.
        
        Args:
            msg: MIMEMultipart message
            filepath: Path to attachment file
        """
        # Validate attachment path
        validated_path = validate_attachment_path(filepath)
        
        with open(validated_path, 'rb') as attachment:
            part = MIMEBase('application', 'octet-stream')
            part.set_payload(attachment.read())
        
        # Encode file in ASCII characters to send by email
        encoders.encode_base64(part)
        
        # Add header with filename
        filename = os.path.basename(validated_path)
        part.add_header(
            'Content-Disposition',
            f'attachment; filename= {filename}'
        )
        
        msg.attach(part)
        logger.debug(f"Added attachment: {filename}")


class EmailSender:
    """High-level email sending coordinator."""
    
    def __init__(self, smtp_config: SMTPConfig, max_retries: int = 3,
                 retry_delay: float = 1.0):
        """
        Initialize email sender.
        
        Args:
            smtp_config: SMTP configuration
            max_retries: Maximum retry attempts for failed sends
            retry_delay: Delay between retries in seconds
        """
        self.smtp_config = smtp_config
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self._client: Optional[SMTPClient] = None
        
    def send_single_email(self, email_message: EmailMessage,
                         from_email: Optional[str] = None,
                         from_name: Optional[str] = None) -> bool:
        """
        Send a single email with retry logic.
        
        Args:
            email_message: Email message to send
            from_email: Sender email address
            from_name: Sender name
            
        Returns:
            True if sent successfully
            
        Raises:
            SMTPError: If all retry attempts fail
        """
        last_error = None
        
        for attempt in range(self.max_retries + 1):
            try:
                with SMTPClient(self.smtp_config) as client:
                    success = client.send_message(email_message, from_email, from_name)
                    if success:
                        return True
                
            except Exception as e:
                last_error = e
                
                if attempt < self.max_retries:
                    logger.warning(f"Email send attempt {attempt + 1} failed, retrying: {e}")
                    time.sleep(self.retry_delay * (2 ** attempt))  # Exponential backoff
                else:
                    logger.error(f"All email send attempts failed for {email_message.to_email}")
        
        if last_error:
            raise last_error
        
        return False
    
    def send_template_email(self, template: EmailTemplate, lead: Lead,
                           from_email: Optional[str] = None,
                           from_name: Optional[str] = None,
                           attachments: Optional[List[str]] = None) -> bool:
        """
        Send email using template and lead data.
        
        Args:
            template: Email template
            lead: Lead data
            from_email: Sender email address
            from_name: Sender name
            attachments: List of attachment file paths
            
        Returns:
            True if sent successfully
        """
        try:
            # Build email message from template
            builder = EmailBuilder()
            variables = {
                'first_name': lead.first_name,
                'last_name': lead.last_name,
                'full_name': lead.full_name,
                'email': lead.email,
                'company': lead.company,
                'title': lead.title,
                'phone': lead.phone
            }
            variables.update(lead.custom_fields)
            
            # Render template
            subject, html_content, text_content = template.render(variables)
            
            # Create email message
            email_message = EmailMessage(
                to_email=lead.email,
                to_name=lead.display_name,
                subject=subject,
                html_content=html_content,
                text_content=text_content,
                attachments=attachments or []
            )
            
            return self.send_single_email(email_message, from_email, from_name)
            
        except Exception as e:
            logger.error(f"Failed to send template email to {lead.email}: {e}")
            raise
    
    def test_connection(self) -> bool:
        """
        Test SMTP connection without sending email.
        
        Returns:
            True if connection successful
        """
        try:
            with SMTPClient(self.smtp_config) as client:
                return client.is_connected()
        except Exception as e:
            logger.error(f"SMTP connection test failed: {e}")
            return False


# Convenience functions
def send_test_email(smtp_config: SMTPConfig, test_recipient: str,
                   from_email: Optional[str] = None) -> bool:
    """
    Send a test email to verify SMTP configuration.
    
    Args:
        smtp_config: SMTP configuration to test
        test_recipient: Email address to send test to
        from_email: Sender email address
        
    Returns:
        True if test email sent successfully
    """
    try:
        sender = EmailSender(smtp_config)
        
        test_message = EmailMessage(
            to_email=test_recipient,
            subject="Test Email from Bulk Email Sender",
            text_content="This is a test email to verify SMTP configuration.",
            html_content="<p>This is a test email to verify SMTP configuration.</p>"
        )
        
        return sender.send_single_email(test_message, from_email)
        
    except Exception as e:
        logger.error(f"Test email failed: {e}")
        return False