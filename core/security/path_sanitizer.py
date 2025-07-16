"""
Path sanitization utilities for Bulk Email Sender - SECURITY DISABLED
As requested by user: "i don't need any security and related protection"
"""

import os
from pathlib import Path
from typing import Optional, List

from core.utils.logger import get_module_logger

logger = get_module_logger(__name__)

class PathSanitizer:
    """Path sanitizer with security features DISABLED for desktop use"""
    
    def __init__(self, allowed_base_paths: Optional[List[str]] = None):
        """Initialize with security disabled"""
        self.allowed_base_paths = allowed_base_paths or []
        logger.info("PathSanitizer initialized with security DISABLED for desktop use")
    
    def sanitize_path(self, path: str, create_dirs: bool = False) -> str:
        """Return normalized path without security restrictions"""
        if not path:
            return ""
        
        # Just normalize the path
        normalized = os.path.normpath(path)
        
        if create_dirs:
            try:
                directory = os.path.dirname(normalized)
                if directory and not os.path.exists(directory):
                    os.makedirs(directory, exist_ok=True)
            except Exception as e:
                logger.warning(f"Could not create directory: {e}")
        
        return normalized
    
    def is_safe_path(self, path: str) -> bool:
        """Always return True since security is disabled"""
        return True
    
    def validate_path(self, path: str, must_exist: bool = False) -> bool:
        """Basic validation without security restrictions"""
        if not path:
            return False
        
        try:
            normalized_path = os.path.normpath(path)
            
            if must_exist and not os.path.exists(normalized_path):
                return False
            
            return True
        except Exception:
            return False
    
    def safe_join(self, *paths) -> str:
        """Join paths safely without security restrictions"""
        if not paths:
            return ""
        
        return os.path.normpath(os.path.join(*paths))
    
    def clean_filename(self, filename: str) -> str:
        """Basic filename cleaning without security restrictions"""
        if not filename:
            return "untitled"
        
        # Just remove some obviously problematic characters
        unsafe_chars = '<>:"|?*\x00'
        clean_name = filename
        
        for char in unsafe_chars:
            clean_name = clean_name.replace(char, '_')
        
        # Remove leading/trailing spaces and dots
        clean_name = clean_name.strip(' .')
        
        if not clean_name:
            clean_name = "untitled"
        
        return clean_name
    
    def validate_filename(self, filename: str) -> bool:
        """Basic filename validation without security restrictions"""
        if not filename:
            return False
        
        # Very basic checks
        if len(filename) > 255:
            return False
        
        return True
    
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
        For desktop applications, we only do basic validation.
        
        Args:
            path: Path to validate
            must_exist: Whether path must exist
            
        Returns:
            Normalized absolute path
            
        Raises:
            ValidationError: If path is invalid
        """
        if not path or not path.strip():
            raise ValidationError("Path cannot be empty")
        
        # Decode URL-encoded paths
        try:
            path = urllib.parse.unquote(path)
        except Exception:
            pass  # Not URL-encoded
        
        try:
            # Resolve to absolute path
            abs_path = os.path.abspath(path)
            
            # For desktop applications, skip security restrictions
            # Only check if path must exist
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
    For desktop applications, we don't need strict security restrictions.
    
    Returns:
        PathSanitizer instance with permissive settings for desktop use
    """
    # Desktop application - no path restrictions needed
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
    Validate an attachment file path - permissive validation for desktop use.
    
    Args:
        path: Attachment file path
        
    Returns:
        Validated absolute path
        
    Raises:
        ValidationError: If path is invalid
    """
    # Desktop application - allow files from anywhere
    sanitizer = PathSanitizer()  
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