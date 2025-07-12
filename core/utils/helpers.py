"""
Helper utilities for Bulk Email Sender.

This module provides common utility functions used throughout the application.
"""

import os
import sys
import hashlib
import json
import re
import time
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Union, Callable, TypeVar
from email.utils import parseaddr, formataddr
import tempfile
import shutil

from core.utils.logger import get_module_logger

logger = get_module_logger(__name__)

T = TypeVar('T')


# Path and file utilities
def get_application_path() -> str:
    """
    Get the application's base path, handling both script and executable modes.
    
    Returns:
        Application base path
    """
    if getattr(sys, 'frozen', False):
        # Running as compiled executable
        return os.path.dirname(sys.executable)
    else:
        # Running as script
        return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def ensure_directory(path: str) -> str:
    """
    Ensure directory exists, create if necessary.
    
    Args:
        path: Directory path
        
    Returns:
        Absolute directory path
    """
    abs_path = os.path.abspath(path)
    os.makedirs(abs_path, exist_ok=True)
    return abs_path


def get_safe_filename(filename: str) -> str:
    """
    Convert a string to a safe filename by removing invalid characters.
    
    Args:
        filename: Original filename
        
    Returns:
        Safe filename
    """
    # Remove or replace invalid characters
    safe_filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
    safe_filename = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', safe_filename)  # Remove control characters
    safe_filename = safe_filename.strip('. ')  # Remove leading/trailing dots and spaces
    
    # Ensure filename is not empty and not too long
    if not safe_filename:
        safe_filename = 'unnamed'
    if len(safe_filename) > 255:
        safe_filename = safe_filename[:255]
    
    return safe_filename


def get_unique_filename(base_path: str, filename: str) -> str:
    """
    Get a unique filename by appending numbers if file exists.
    
    Args:
        base_path: Directory path
        filename: Desired filename
        
    Returns:
        Unique filename
    """
    safe_filename = get_safe_filename(filename)
    full_path = os.path.join(base_path, safe_filename)
    
    if not os.path.exists(full_path):
        return safe_filename
    
    name, ext = os.path.splitext(safe_filename)
    counter = 1
    
    while True:
        new_filename = f"{name}_{counter}{ext}"
        new_path = os.path.join(base_path, new_filename)
        if not os.path.exists(new_path):
            return new_filename
        counter += 1


def copy_file_safe(source: str, destination: str, overwrite: bool = False) -> bool:
    """
    Safely copy a file with error handling.
    
    Args:
        source: Source file path
        destination: Destination file path
        overwrite: Whether to overwrite existing file
        
    Returns:
        True if successful, False otherwise
    """
    try:
        if not os.path.exists(source):
            logger.error(f"Source file does not exist: {source}")
            return False
        
        if os.path.exists(destination) and not overwrite:
            logger.warning(f"Destination file exists and overwrite is False: {destination}")
            return False
        
        # Ensure destination directory exists
        ensure_directory(os.path.dirname(destination))
        
        shutil.copy2(source, destination)
        logger.debug(f"File copied successfully: {source} -> {destination}")
        return True
        
    except Exception as e:
        logger.exception(e, f"copying file {source} to {destination}")
        return False


# String utilities
def truncate_string(text: str, max_length: int, suffix: str = "...") -> str:
    """
    Truncate string to maximum length with optional suffix.
    
    Args:
        text: Input text
        max_length: Maximum length
        suffix: Suffix to add when truncating
        
    Returns:
        Truncated string
    """
    if len(text) <= max_length:
        return text
    
    if len(suffix) >= max_length:
        return suffix[:max_length]
    
    return text[:max_length - len(suffix)] + suffix


def sanitize_string(text: str, allow_unicode: bool = True) -> str:
    """
    Sanitize string by removing or replacing dangerous characters.
    
    Args:
        text: Input text
        allow_unicode: Whether to allow unicode characters
        
    Returns:
        Sanitized string
    """
    if not allow_unicode:
        # Remove non-ASCII characters
        text = text.encode('ascii', 'ignore').decode('ascii')
    
    # Remove control characters except common whitespace
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]', '', text)
    
    return text.strip()


def generate_unique_id() -> str:
    """
    Generate a unique identifier.
    
    Returns:
        Unique ID string
    """
    return str(uuid.uuid4())


def generate_short_id(length: int = 8) -> str:
    """
    Generate a short unique identifier.
    
    Args:
        length: ID length
        
    Returns:
        Short unique ID
    """
    return str(uuid.uuid4()).replace('-', '')[:length]


# Validation utilities
def is_valid_email(email: str) -> bool:
    """
    Validate email address format.
    
    Args:
        email: Email address to validate
        
    Returns:
        True if valid, False otherwise
    """
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email.strip()))


def normalize_email(email: str) -> str:
    """
    Normalize email address (lowercase, strip whitespace).
    
    Args:
        email: Email address
        
    Returns:
        Normalized email address
    """
    return email.strip().lower()


def parse_email_address(email_str: str) -> tuple[str, str]:
    """
    Parse email address into name and email components.
    
    Args:
        email_str: Email string (e.g., "John Doe <john@example.com>")
        
    Returns:
        Tuple of (name, email)
    """
    name, email = parseaddr(email_str)
    return name.strip(), email.strip()


def format_email_address(name: str, email: str) -> str:
    """
    Format name and email into proper email address string.
    
    Args:
        name: Display name
        email: Email address
        
    Returns:
        Formatted email address
    """
    if name:
        return formataddr((name, email))
    return email


# Time utilities
def get_timestamp() -> str:
    """
    Get current timestamp as string.
    
    Returns:
        Timestamp string
    """
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def get_file_timestamp() -> str:
    """
    Get timestamp suitable for filenames.
    
    Returns:
        File-safe timestamp string
    """
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def parse_duration(duration_str: str) -> Optional[float]:
    """
    Parse duration string into seconds.
    
    Args:
        duration_str: Duration string (e.g., "30s", "5m", "1h")
        
    Returns:
        Duration in seconds or None if invalid
    """
    pattern = r'^(\d+(?:\.\d+)?)\s*([smh]?)$'
    match = re.match(pattern, duration_str.lower().strip())
    
    if not match:
        return None
    
    value, unit = match.groups()
    value = float(value)
    
    multipliers = {'s': 1, 'm': 60, 'h': 3600, '': 1}
    return value * multipliers.get(unit, 1)


def format_duration(seconds: float) -> str:
    """
    Format duration in seconds to human-readable string.
    
    Args:
        seconds: Duration in seconds
        
    Returns:
        Formatted duration string
    """
    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        return f"{seconds/60:.1f}m"
    else:
        return f"{seconds/3600:.1f}h"


# Data utilities
def deep_merge_dicts(dict1: Dict[str, Any], dict2: Dict[str, Any]) -> Dict[str, Any]:
    """
    Deep merge two dictionaries.
    
    Args:
        dict1: Base dictionary
        dict2: Dictionary to merge into base
        
    Returns:
        Merged dictionary
    """
    result = dict1.copy()
    
    for key, value in dict2.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge_dicts(result[key], value)
        else:
            result[key] = value
    
    return result


def flatten_dict(d: Dict[str, Any], parent_key: str = '', sep: str = '.') -> Dict[str, Any]:
    """
    Flatten nested dictionary with dot notation keys.
    
    Args:
        d: Dictionary to flatten
        parent_key: Parent key prefix
        sep: Separator for keys
        
    Returns:
        Flattened dictionary
    """
    items = []
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            items.extend(flatten_dict(v, new_key, sep=sep).items())
        else:
            items.append((new_key, v))
    return dict(items)


def chunk_list(lst: List[T], chunk_size: int) -> List[List[T]]:
    """
    Split list into chunks of specified size.
    
    Args:
        lst: Input list
        chunk_size: Size of each chunk
        
    Returns:
        List of chunks
    """
    return [lst[i:i + chunk_size] for i in range(0, len(lst), chunk_size)]


# Hash utilities
def get_file_hash(filepath: str, algorithm: str = 'sha256') -> Optional[str]:
    """
    Get file hash using specified algorithm.
    
    Args:
        filepath: Path to file
        algorithm: Hash algorithm (md5, sha1, sha256, sha512)
        
    Returns:
        File hash or None if error
    """
    try:
        hash_obj = hashlib.new(algorithm)
        with open(filepath, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_obj.update(chunk)
        return hash_obj.hexdigest()
    except Exception as e:
        logger.exception(e, f"calculating hash for {filepath}")
        return None


def get_string_hash(text: str, algorithm: str = 'sha256') -> str:
    """
    Get string hash using specified algorithm.
    
    Args:
        text: Input text
        algorithm: Hash algorithm
        
    Returns:
        Text hash
    """
    hash_obj = hashlib.new(algorithm)
    hash_obj.update(text.encode('utf-8'))
    return hash_obj.hexdigest()


# JSON utilities
def safe_json_load(filepath: str) -> Optional[Dict[str, Any]]:
    """
    Safely load JSON file with error handling.
    
    Args:
        filepath: Path to JSON file
        
    Returns:
        Parsed JSON data or None if error
    """
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.exception(e, f"loading JSON file {filepath}")
        return None


def safe_json_save(data: Dict[str, Any], filepath: str, indent: int = 2) -> bool:
    """
    Safely save data to JSON file with error handling.
    
    Args:
        data: Data to save
        filepath: Path to JSON file
        indent: JSON indentation
        
    Returns:
        True if successful, False otherwise
    """
    try:
        ensure_directory(os.path.dirname(filepath))
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=indent, ensure_ascii=False)
        return True
    except Exception as e:
        logger.exception(e, f"saving JSON file {filepath}")
        return False


# Retry utilities
def retry_operation(
    operation: Callable[[], T],
    max_retries: int = 3,
    delay: float = 1.0,
    backoff_factor: float = 2.0,
    exceptions: tuple = (Exception,)
) -> T:
    """
    Retry operation with exponential backoff.
    
    Args:
        operation: Function to retry
        max_retries: Maximum number of retries
        delay: Initial delay between retries
        backoff_factor: Delay multiplier for each retry
        exceptions: Exception types to catch and retry
        
    Returns:
        Operation result
        
    Raises:
        Last exception if all retries fail
    """
    last_exception = None
    current_delay = delay
    
    for attempt in range(max_retries + 1):
        try:
            return operation()
        except exceptions as e:
            last_exception = e
            if attempt == max_retries:
                break
            
            logger.warning(f"Operation failed (attempt {attempt + 1}/{max_retries + 1}): {e}")
            time.sleep(current_delay)
            current_delay *= backoff_factor
    
    if last_exception:
        raise last_exception
    else:
        raise RuntimeError("Retry operation failed without exception")


# System utilities
def get_system_info() -> Dict[str, Any]:
    """
    Get system information.
    
    Returns:
        System information dictionary
    """
    import platform
    
    return {
        'platform': platform.platform(),
        'system': platform.system(),
        'release': platform.release(),
        'version': platform.version(),
        'machine': platform.machine(),
        'processor': platform.processor(),
        'python_version': platform.python_version(),
        'python_implementation': platform.python_implementation(),
    }


def get_memory_usage() -> Dict[str, Any]:
    """
    Get current memory usage information.
    
    Returns:
        Memory usage dictionary
    """
    import psutil
    
    process = psutil.Process()
    memory_info = process.memory_info()
    
    return {
        'rss': memory_info.rss,  # Resident Set Size
        'vms': memory_info.vms,  # Virtual Memory Size
        'percent': process.memory_percent(),
        'available': psutil.virtual_memory().available,
        'total': psutil.virtual_memory().total
    }