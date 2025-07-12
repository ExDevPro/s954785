"""
Data validation utilities for Bulk Email Sender.

This module provides validation for:
- Lead data validation
- SMTP configuration validation
- Campaign data validation
- File format validation
"""

import os
import re
from typing import Any, Dict, List, Optional, Union, Tuple
from pathlib import Path
import mimetypes

from core.utils.logger import get_module_logger
from core.utils.exceptions import ValidationError
from core.utils.helpers import is_valid_email, normalize_email
from core.security.path_sanitizer import PathSanitizer

logger = get_module_logger(__name__)


class DataValidator:
    """Comprehensive data validator."""
    
    def __init__(self):
        """Initialize data validator."""
        self.path_sanitizer = PathSanitizer()
    
    def validate_lead_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate lead data structure.
        
        Args:
            data: Lead data dictionary
            
        Returns:
            Validated and normalized lead data
            
        Raises:
            ValidationError: If data is invalid
        """
        if not isinstance(data, dict):
            raise ValidationError("Lead data must be a dictionary")
        
        # Required fields
        required_fields = ['email']
        for field in required_fields:
            if field not in data or not data[field]:
                raise ValidationError(f"Required field missing: {field}")
        
        # Validate and normalize email
        email = str(data['email']).strip()
        if not is_valid_email(email):
            raise ValidationError(f"Invalid email address: {email}")
        data['email'] = normalize_email(email)
        
        # Validate optional string fields
        string_fields = ['first_name', 'last_name', 'company', 'title', 'phone']
        for field in string_fields:
            if field in data and data[field] is not None:
                value = str(data[field]).strip()
                if len(value) > 255:
                    raise ValidationError(f"Field '{field}' too long (max 255 characters)")
                data[field] = value
            else:
                data[field] = ""
        
        # Validate custom fields
        if 'custom_fields' in data:
            if not isinstance(data['custom_fields'], dict):
                raise ValidationError("Custom fields must be a dictionary")
            
            # Validate custom field names and values
            validated_custom = {}
            for key, value in data['custom_fields'].items():
                if not isinstance(key, str) or not key.strip():
                    raise ValidationError("Custom field names must be non-empty strings")
                
                clean_key = str(key).strip()
                if len(clean_key) > 100:
                    raise ValidationError(f"Custom field name too long: {clean_key}")
                
                # Convert value to string and limit length
                str_value = str(value) if value is not None else ""
                if len(str_value) > 1000:
                    raise ValidationError(f"Custom field value too long for '{clean_key}'")
                
                validated_custom[clean_key] = str_value
            
            data['custom_fields'] = validated_custom
        else:
            data['custom_fields'] = {}
        
        # Validate tags
        if 'tags' in data:
            if not isinstance(data['tags'], list):
                raise ValidationError("Tags must be a list")
            
            validated_tags = []
            for tag in data['tags']:
                clean_tag = str(tag).strip().lower()
                if clean_tag and len(clean_tag) <= 50:
                    if clean_tag not in validated_tags:
                        validated_tags.append(clean_tag)
            
            data['tags'] = validated_tags
        else:
            data['tags'] = []
        
        return data
    
    def validate_smtp_config(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate SMTP configuration data.
        
        Args:
            data: SMTP configuration dictionary
            
        Returns:
            Validated SMTP configuration
            
        Raises:
            ValidationError: If configuration is invalid
        """
        if not isinstance(data, dict):
            raise ValidationError("SMTP configuration must be a dictionary")
        
        # Required fields
        required_fields = ['host', 'port', 'username', 'password']
        for field in required_fields:
            if field not in data or not data[field]:
                raise ValidationError(f"Required SMTP field missing: {field}")
        
        # Validate host
        host = str(data['host']).strip()
        if not host:
            raise ValidationError("SMTP host cannot be empty")
        if len(host) > 255:
            raise ValidationError("SMTP host too long")
        data['host'] = host
        
        # Validate port
        try:
            port = int(data['port'])
            if not (1 <= port <= 65535):
                raise ValidationError("SMTP port must be between 1 and 65535")
            data['port'] = port
        except (ValueError, TypeError):
            raise ValidationError("SMTP port must be a valid integer")
        
        # Validate username
        username = str(data['username']).strip()
        if not username:
            raise ValidationError("SMTP username cannot be empty")
        if len(username) > 255:
            raise ValidationError("SMTP username too long")
        data['username'] = username
        
        # Validate password
        password = str(data['password'])
        if not password:
            raise ValidationError("SMTP password cannot be empty")
        if len(password) > 255:
            raise ValidationError("SMTP password too long")
        data['password'] = password
        
        # Validate optional fields
        if 'name' in data:
            name = str(data['name']).strip()
            if len(name) > 100:
                raise ValidationError("SMTP configuration name too long")
            data['name'] = name
        
        # Validate boolean fields
        bool_fields = ['use_tls']
        for field in bool_fields:
            if field in data:
                if isinstance(data[field], str):
                    data[field] = data[field].lower() in ('true', '1', 'yes', 'on')
                else:
                    data[field] = bool(data[field])
        
        # Validate timeout
        if 'timeout' in data:
            try:
                timeout = int(data['timeout'])
                if timeout < 1 or timeout > 300:
                    raise ValidationError("SMTP timeout must be between 1 and 300 seconds")
                data['timeout'] = timeout
            except (ValueError, TypeError):
                raise ValidationError("SMTP timeout must be a valid integer")
        
        # Validate rate limiting fields
        for field in ['max_emails_per_hour', 'max_emails_per_day']:
            if field in data and data[field] is not None:
                try:
                    value = int(data[field])
                    if value < 1:
                        raise ValidationError(f"{field} must be positive")
                    data[field] = value
                except (ValueError, TypeError):
                    raise ValidationError(f"{field} must be a valid integer")
        
        if 'delay_between_emails' in data:
            try:
                delay = float(data['delay_between_emails'])
                if delay < 0:
                    raise ValidationError("Delay between emails cannot be negative")
                data['delay_between_emails'] = delay
            except (ValueError, TypeError):
                raise ValidationError("Delay between emails must be a valid number")
        
        return data
    
    def validate_campaign_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate campaign data structure.
        
        Args:
            data: Campaign data dictionary
            
        Returns:
            Validated campaign data
            
        Raises:
            ValidationError: If data is invalid
        """
        if not isinstance(data, dict):
            raise ValidationError("Campaign data must be a dictionary")
        
        # Required fields
        required_fields = ['name', 'template_id', 'smtp_config_id']
        for field in required_fields:
            if field not in data or not data[field]:
                raise ValidationError(f"Required campaign field missing: {field}")
        
        # Validate name
        name = str(data['name']).strip()
        if not name:
            raise ValidationError("Campaign name cannot be empty")
        if len(name) > 200:
            raise ValidationError("Campaign name too long (max 200 characters)")
        data['name'] = name
        
        # Validate IDs
        for field in ['template_id', 'smtp_config_id']:
            value = str(data[field]).strip()
            if not value:
                raise ValidationError(f"{field} cannot be empty")
            data[field] = value
        
        # Validate lead IDs
        if 'lead_ids' in data:
            if not isinstance(data['lead_ids'], list):
                raise ValidationError("Lead IDs must be a list")
            
            validated_ids = []
            for lead_id in data['lead_ids']:
                clean_id = str(lead_id).strip()
                if clean_id and clean_id not in validated_ids:
                    validated_ids.append(clean_id)
            
            data['lead_ids'] = validated_ids
        else:
            data['lead_ids'] = []
        
        # Validate numeric fields
        numeric_fields = {
            'batch_size': (1, 1000),
            'max_retries': (0, 10),
            'total_leads': (0, None),
            'emails_sent': (0, None),
            'emails_failed': (0, None),
            'emails_pending': (0, None)
        }
        
        for field, (min_val, max_val) in numeric_fields.items():
            if field in data:
                try:
                    value = int(data[field])
                    if value < min_val:
                        raise ValidationError(f"{field} must be at least {min_val}")
                    if max_val is not None and value > max_val:
                        raise ValidationError(f"{field} must be at most {max_val}")
                    data[field] = value
                except (ValueError, TypeError):
                    raise ValidationError(f"{field} must be a valid integer")
        
        # Validate delay
        if 'delay_between_batches' in data:
            try:
                delay = float(data['delay_between_batches'])
                if delay < 0:
                    raise ValidationError("Delay between batches cannot be negative")
                data['delay_between_batches'] = delay
            except (ValueError, TypeError):
                raise ValidationError("Delay between batches must be a valid number")
        
        # Validate attachment paths
        if 'attachment_paths' in data:
            if not isinstance(data['attachment_paths'], list):
                raise ValidationError("Attachment paths must be a list")
            
            validated_paths = []
            for path in data['attachment_paths']:
                try:
                    validated_path = self.path_sanitizer.validate_file(str(path), must_exist=False)
                    if validated_path not in validated_paths:
                        validated_paths.append(validated_path)
                except ValidationError as e:
                    logger.warning(f"Invalid attachment path '{path}': {e}")
            
            data['attachment_paths'] = validated_paths
        else:
            data['attachment_paths'] = []
        
        return data
    
    def validate_template_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate email template data.
        
        Args:
            data: Template data dictionary
            
        Returns:
            Validated template data
            
        Raises:
            ValidationError: If data is invalid
        """
        if not isinstance(data, dict):
            raise ValidationError("Template data must be a dictionary")
        
        # Required field
        if 'subject' not in data or not data['subject']:
            raise ValidationError("Template subject is required")
        
        # Validate subject
        subject = str(data['subject']).strip()
        if not subject:
            raise ValidationError("Template subject cannot be empty")
        if len(subject) > 500:
            raise ValidationError("Template subject too long (max 500 characters)")
        data['subject'] = subject
        
        # Validate optional string fields
        string_fields = ['name', 'html_content', 'text_content']
        for field in string_fields:
            if field in data and data[field] is not None:
                value = str(data[field])
                # Allow longer content for email body
                max_length = 50000 if field.endswith('_content') else 200
                if len(value) > max_length:
                    raise ValidationError(f"Template {field} too long (max {max_length} characters)")
                data[field] = value
            else:
                data[field] = ""
        
        # Ensure at least one content type is provided
        if not data.get('html_content') and not data.get('text_content'):
            raise ValidationError("Template must have either HTML or text content")
        
        return data
    
    def validate_file_upload(self, filepath: str, allowed_extensions: Optional[List[str]] = None,
                           max_size_mb: Optional[float] = None) -> Dict[str, Any]:
        """
        Validate uploaded file.
        
        Args:
            filepath: Path to uploaded file
            allowed_extensions: List of allowed file extensions
            max_size_mb: Maximum file size in MB
            
        Returns:
            File information dictionary
            
        Raises:
            ValidationError: If file is invalid
        """
        # Validate file existence and path
        validated_path = self.path_sanitizer.validate_file(filepath, must_exist=True, check_readable=True)
        
        # Get file info
        file_stat = os.stat(validated_path)
        file_size = file_stat.st_size
        file_size_mb = file_size / (1024 * 1024)
        
        filename = os.path.basename(validated_path)
        file_ext = Path(validated_path).suffix.lower()
        
        # Validate file size
        if max_size_mb and file_size_mb > max_size_mb:
            raise ValidationError(f"File size ({file_size_mb:.1f} MB) exceeds maximum ({max_size_mb} MB)")
        
        # Validate file extension
        if allowed_extensions:
            if file_ext not in [ext.lower() for ext in allowed_extensions]:
                raise ValidationError(f"File extension '{file_ext}' not allowed. Allowed: {allowed_extensions}")
        
        # Get MIME type
        mime_type, _ = mimetypes.guess_type(validated_path)
        
        return {
            'path': validated_path,
            'filename': filename,
            'extension': file_ext,
            'size_bytes': file_size,
            'size_mb': file_size_mb,
            'mime_type': mime_type
        }
    
    def validate_csv_structure(self, filepath: str, required_columns: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Validate CSV file structure.
        
        Args:
            filepath: Path to CSV file
            required_columns: List of required column names
            
        Returns:
            CSV structure information
            
        Raises:
            ValidationError: If CSV structure is invalid
        """
        import csv
        
        # Validate file first
        file_info = self.validate_file_upload(filepath, ['.csv'], max_size_mb=50)
        
        try:
            with open(file_info['path'], 'r', encoding='utf-8') as csvfile:
                # Try to detect dialect
                sample = csvfile.read(1024)
                csvfile.seek(0)
                
                try:
                    dialect = csv.Sniffer().sniff(sample)
                except csv.Error:
                    dialect = csv.excel  # Default dialect
                
                reader = csv.reader(csvfile, dialect)
                
                # Read header row
                try:
                    headers = next(reader)
                except StopIteration:
                    raise ValidationError("CSV file is empty")
                
                # Clean and validate headers
                clean_headers = [str(header).strip() for header in headers]
                if not all(clean_headers):
                    raise ValidationError("CSV headers cannot be empty")
                
                # Check for duplicate headers
                if len(clean_headers) != len(set(clean_headers)):
                    raise ValidationError("CSV headers must be unique")
                
                # Check required columns
                if required_columns:
                    missing_columns = []
                    for required_col in required_columns:
                        if required_col not in clean_headers:
                            missing_columns.append(required_col)
                    
                    if missing_columns:
                        raise ValidationError(f"Missing required columns: {missing_columns}")
                
                # Count data rows
                row_count = sum(1 for _ in reader)
                
                return {
                    'file_info': file_info,
                    'headers': clean_headers,
                    'row_count': row_count,
                    'column_count': len(clean_headers),
                    'dialect': dialect
                }
        
        except UnicodeDecodeError:
            raise ValidationError("CSV file encoding not supported. Please use UTF-8 encoding.")
        except Exception as e:
            raise ValidationError(f"Failed to read CSV file: {e}")
    
    def validate_bulk_leads_data(self, leads_data: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[str]]:
        """
        Validate bulk leads data.
        
        Args:
            leads_data: List of lead data dictionaries
            
        Returns:
            Tuple of (valid_leads, error_messages)
        """
        valid_leads = []
        errors = []
        
        for i, lead_data in enumerate(leads_data):
            try:
                validated_lead = self.validate_lead_data(lead_data)
                valid_leads.append(validated_lead)
            except ValidationError as e:
                errors.append(f"Row {i+1}: {e.message}")
        
        return valid_leads, errors


# Convenience functions
def validate_email_format(email: str) -> bool:
    """
    Quick email format validation.
    
    Args:
        email: Email address
        
    Returns:
        True if format is valid
    """
    return is_valid_email(email)


def validate_required_fields(data: Dict[str, Any], required_fields: List[str]) -> None:
    """
    Validate that required fields are present and not empty.
    
    Args:
        data: Data dictionary
        required_fields: List of required field names
        
    Raises:
        ValidationError: If any required field is missing
    """
    missing_fields = []
    for field in required_fields:
        if field not in data or not data[field]:
            missing_fields.append(field)
    
    if missing_fields:
        raise ValidationError(f"Missing required fields: {missing_fields}")


def sanitize_text_input(text: str, max_length: Optional[int] = None, 
                       allow_html: bool = False) -> str:
    """
    Sanitize text input.
    
    Args:
        text: Input text
        max_length: Maximum allowed length
        allow_html: Whether to allow HTML tags
        
    Returns:
        Sanitized text
        
    Raises:
        ValidationError: If text is invalid
    """
    if not isinstance(text, str):
        text = str(text)
    
    # Strip whitespace
    text = text.strip()
    
    # Remove HTML tags if not allowed
    if not allow_html:
        import re
        text = re.sub(r'<[^>]+>', '', text)
    
    # Check length
    if max_length and len(text) > max_length:
        raise ValidationError(f"Text too long (max {max_length} characters)")
    
    return text