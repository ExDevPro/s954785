"""
Path sanitization utilities for Bulk Email Sender.

This module provides utilities for:
- Path validation and sanitization
- Directory traversal prevention
- Safe file operations
"""

import os
import re
from pathlib import Path
from typing import Optional, List
import urllib.parse

from core.utils.logger import get_module_logger
from core.utils.exceptions import ValidationError

logger = get_module_logger(__name__)


class PathSanitizer:
    """Handles path sanitization and validation."""
    
    # Dangerous path patterns (only for actual security threats)
    DANGEROUS_PATTERNS = [
        r'\.\.[/\\]',  # Directory traversal attempts
        r'[<>"|?*]',   # Invalid filename characters  
        r'[\x00-\x1f\x7f-\x9f]',  # Control characters
    ]
    
    # Reserved Windows filenames
    WINDOWS_RESERVED = {
        'CON', 'PRN', 'AUX', 'NUL',
        'COM1', 'COM2', 'COM3', 'COM4', 'COM5', 'COM6', 'COM7', 'COM8', 'COM9',
        'LPT1', 'LPT2', 'LPT3', 'LPT4', 'LPT5', 'LPT6', 'LPT7', 'LPT8', 'LPT9'
    }
    
    def __init__(self, allowed_base_paths: Optional[List[str]] = None):
        """
        Initialize path sanitizer.
        
        Args:
            allowed_base_paths: List of allowed base paths for operations
        """
        self.allowed_base_paths = []
        if allowed_base_paths:
            for path in allowed_base_paths:
                self.allowed_base_paths.append(os.path.abspath(path))
    
    def sanitize_filename(self, filename: str) -> str:
        """
        Sanitize a filename by removing dangerous characters.
        
        Args:
            filename: Original filename
            
        Returns:
            Sanitized filename
            
        Raises:
            ValidationError: If filename cannot be sanitized
        """
        if not filename or not filename.strip():
            raise ValidationError("Filename cannot be empty")
        
        # Remove path separators
        sanitized = filename.replace('/', '_').replace('\\', '_')
        
        # Remove dangerous characters
        for pattern in self.DANGEROUS_PATTERNS:
            sanitized = re.sub(pattern, '_', sanitized)
        
        # Remove leading/trailing dots and spaces
        sanitized = sanitized.strip('. ')
        
        # Check for Windows reserved names
        name_without_ext = os.path.splitext(sanitized)[0].upper()
        if name_without_ext in self.WINDOWS_RESERVED:
            sanitized = f"_{sanitized}"
        
        # Ensure filename is not empty after sanitization
        if not sanitized:
            raise ValidationError("Filename becomes empty after sanitization")
        
        # Limit length
        if len(sanitized) > 255:
            name, ext = os.path.splitext(sanitized)
            max_name_length = 255 - len(ext)
            sanitized = name[:max_name_length] + ext
        
        logger.debug(f"Sanitized filename: '{filename}' -> '{sanitized}'")
        return sanitized
    
    def validate_path(self, path: str, must_exist: bool = False) -> str:
        """
        Validate and normalize a file path.
        
        Args:
            path: Path to validate
            must_exist: Whether path must exist
            
        Returns:
            Normalized absolute path
            
        Raises:
            ValidationError: If path is invalid or dangerous
        """
        if not path or not path.strip():
            raise ValidationError("Path cannot be empty")
        
        # Decode URL-encoded paths
        try:
            path = urllib.parse.unquote(path)
        except Exception:
            pass  # Not URL-encoded
        
        # Check for dangerous patterns
        for pattern in self.DANGEROUS_PATTERNS:
            if re.search(pattern, path, re.IGNORECASE):
                raise ValidationError(f"Path contains dangerous pattern: {path}")
        
        try:
            # Resolve to absolute path
            abs_path = os.path.abspath(path)
            
            # Check if path is within allowed base paths
            if self.allowed_base_paths:
                is_allowed = False
                for base_path in self.allowed_base_paths:
                    if abs_path.startswith(base_path):
                        is_allowed = True
                        break
                
                if not is_allowed:
                    raise ValidationError(f"Path is outside allowed directories: {path}")
            
            # Check if path must exist
            if must_exist and not os.path.exists(abs_path):
                raise ValidationError(f"Path does not exist: {path}")
            
            logger.debug(f"Validated path: '{path}' -> '{abs_path}'")
            return abs_path
            
        except OSError as e:
            raise ValidationError(f"Invalid path: {path} ({e})")
    
    def validate_directory(self, path: str, create_if_missing: bool = False) -> str:
        """
        Validate a directory path.
        
        Args:
            path: Directory path to validate
            create_if_missing: Create directory if it doesn't exist
            
        Returns:
            Normalized absolute directory path
            
        Raises:
            ValidationError: If directory is invalid
        """
        abs_path = self.validate_path(path, must_exist=False)
        
        if os.path.exists(abs_path):
            if not os.path.isdir(abs_path):
                raise ValidationError(f"Path exists but is not a directory: {path}")
        elif create_if_missing:
            try:
                os.makedirs(abs_path, exist_ok=True)
                logger.info(f"Created directory: {abs_path}")
            except OSError as e:
                raise ValidationError(f"Cannot create directory {path}: {e}")
        
        return abs_path
    
    def validate_file(self, path: str, must_exist: bool = True, check_readable: bool = False, 
                     check_writable: bool = False) -> str:
        """
        Validate a file path.
        
        Args:
            path: File path to validate
            must_exist: Whether file must exist
            check_readable: Check if file is readable
            check_writable: Check if file is writable
            
        Returns:
            Normalized absolute file path
            
        Raises:
            ValidationError: If file is invalid
        """
        abs_path = self.validate_path(path, must_exist=must_exist)
        
        if os.path.exists(abs_path):
            if not os.path.isfile(abs_path):
                raise ValidationError(f"Path exists but is not a file: {path}")
            
            if check_readable and not os.access(abs_path, os.R_OK):
                raise ValidationError(f"File is not readable: {path}")
            
            if check_writable and not os.access(abs_path, os.W_OK):
                raise ValidationError(f"File is not writable: {path}")
        
        return abs_path
    
    def get_safe_temp_path(self, filename: str, base_temp_dir: Optional[str] = None) -> str:
        """
        Get a safe temporary file path.
        
        Args:
            filename: Desired filename
            base_temp_dir: Base temporary directory (uses system temp if None)
            
        Returns:
            Safe temporary file path
        """
        import tempfile
        
        sanitized_filename = self.sanitize_filename(filename)
        
        if base_temp_dir:
            temp_dir = self.validate_directory(base_temp_dir, create_if_missing=True)
        else:
            temp_dir = tempfile.gettempdir()
        
        # Generate unique filename if file exists
        counter = 0
        base_name, ext = os.path.splitext(sanitized_filename)
        
        while True:
            if counter == 0:
                test_filename = sanitized_filename
            else:
                test_filename = f"{base_name}_{counter}{ext}"
            
            test_path = os.path.join(temp_dir, test_filename)
            if not os.path.exists(test_path):
                return test_path
            
            counter += 1
            if counter > 1000:  # Prevent infinite loop
                raise ValidationError("Cannot generate unique temporary filename")
    
    def is_safe_path(self, path: str) -> bool:
        """
        Check if a path is safe without raising exceptions.
        
        Args:
            path: Path to check
            
        Returns:
            True if path is safe, False otherwise
        """
        try:
            self.validate_path(path)
            return True
        except ValidationError:
            return False
    
    def extract_safe_paths_from_list(self, paths: List[str]) -> List[str]:
        """
        Extract safe paths from a list, filtering out dangerous ones.
        
        Args:
            paths: List of paths to filter
            
        Returns:
            List of safe paths
        """
        safe_paths = []
        for path in paths:
            try:
                safe_path = self.validate_path(path)
                safe_paths.append(safe_path)
            except ValidationError as e:
                logger.warning(f"Filtered out unsafe path '{path}': {e}")
        
        return safe_paths


def create_application_sanitizer() -> PathSanitizer:
    """
    Create a path sanitizer configured for the application.
    
    Returns:
        PathSanitizer instance with application-specific settings
    """
    # For imports and user file operations, we need to be more permissive
    # Only basic security checks, no strict path restrictions for file imports
    return PathSanitizer(allowed_base_paths=None)


def sanitize_upload_filename(filename: str) -> str:
    """
    Sanitize a filename from user upload.
    
    Args:
        filename: Original filename
        
    Returns:
        Sanitized filename
    """
    sanitizer = PathSanitizer()
    return sanitizer.sanitize_filename(filename)


def validate_attachment_path(path: str) -> str:
    """
    Validate an attachment file path - use permissive validation for user imports.
    
    Args:
        path: Attachment file path
        
    Returns:
        Validated absolute path
        
    Raises:
        ValidationError: If path is invalid
    """
    # For user file imports, use basic validation without strict path restrictions
    sanitizer = PathSanitizer()  # No allowed_base_paths restriction
    return sanitizer.validate_file(path, must_exist=True, check_readable=True)


def validate_data_directory(path: str, create_if_missing: bool = True) -> str:
    """
    Validate a data directory path.
    
    Args:
        path: Directory path
        create_if_missing: Create directory if missing
        
    Returns:
        Validated absolute directory path
        
    Raises:
        ValidationError: If directory is invalid
    """
    sanitizer = create_application_sanitizer()
    return sanitizer.validate_directory(path, create_if_missing=create_if_missing)


def get_safe_export_path(filename: str, base_dir: Optional[str] = None) -> str:
    """
    Get a safe path for exporting files.
    
    Args:
        filename: Desired filename
        base_dir: Base directory (uses user documents if None)
        
    Returns:
        Safe export file path
    """
    if base_dir is None:
        base_dir = os.path.expanduser('~/Documents')
    
    sanitizer = create_application_sanitizer()
    safe_dir = sanitizer.validate_directory(base_dir, create_if_missing=True)
    safe_filename = sanitizer.sanitize_filename(filename)
    
    return os.path.join(safe_dir, safe_filename)