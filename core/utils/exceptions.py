"""
Custom exception hierarchy for Bulk Email Sender.

This module provides a comprehensive exception system with:
- Hierarchical exception classes
- Error codes for programmatic handling
- User-friendly error messages
- Error context and recovery suggestions
"""

from typing import Optional, Dict, Any, List
from enum import Enum


class ErrorCode(Enum):
    """Error codes for programmatic exception handling."""
    
    # General errors (1000-1999)
    UNKNOWN_ERROR = 1000
    CONFIGURATION_ERROR = 1001
    VALIDATION_ERROR = 1002
    PERMISSION_ERROR = 1003
    RESOURCE_ERROR = 1004
    
    # Network errors (2000-2999)
    NETWORK_CONNECTION_ERROR = 2000
    NETWORK_TIMEOUT_ERROR = 2001
    NETWORK_DNS_ERROR = 2002
    NETWORK_SSL_ERROR = 2003
    
    # SMTP errors (3000-3999)
    SMTP_CONNECTION_ERROR = 3000
    SMTP_AUTHENTICATION_ERROR = 3001
    SMTP_SEND_ERROR = 3002
    SMTP_INVALID_RECIPIENT = 3003
    SMTP_QUOTA_EXCEEDED = 3004
    SMTP_BLOCKED = 3005
    
    # Email errors (4000-4999)
    EMAIL_INVALID_FORMAT = 4000
    EMAIL_ATTACHMENT_ERROR = 4001
    EMAIL_SIZE_EXCEEDED = 4002
    EMAIL_TEMPLATE_ERROR = 4003
    
    # Data errors (5000-5999)
    DATA_FILE_NOT_FOUND = 5000
    DATA_FILE_CORRUPTED = 5001
    DATA_INVALID_FORMAT = 5002
    DATA_DUPLICATE_ENTRY = 5003
    DATA_MISSING_FIELD = 5004
    
    # Security errors (6000-6999)
    SECURITY_ENCRYPTION_ERROR = 6000
    SECURITY_DECRYPTION_ERROR = 6001
    SECURITY_INVALID_CREDENTIALS = 6002
    SECURITY_ACCESS_DENIED = 6003
    
    # Worker/Threading errors (7000-7999)
    WORKER_INITIALIZATION_ERROR = 7000
    WORKER_EXECUTION_ERROR = 7001
    WORKER_TIMEOUT_ERROR = 7002
    WORKER_CANCELLED = 7003


class BulkEmailSenderException(Exception):
    """Base exception class for Bulk Email Sender application."""
    
    def __init__(
        self,
        message: str,
        error_code: ErrorCode = ErrorCode.UNKNOWN_ERROR,
        context: Optional[Dict[str, Any]] = None,
        suggestion: Optional[str] = None,
        recoverable: bool = True,
        original_exception: Optional[Exception] = None
    ):
        """
        Initialize base exception.
        
        Args:
            message: Human-readable error message
            error_code: Programmatic error code
            context: Additional context information
            suggestion: Recovery suggestion for users
            recoverable: Whether error is recoverable
            original_exception: Original exception that caused this error
        """
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.context = context or {}
        self.suggestion = suggestion
        self.recoverable = recoverable
        self.original_exception = original_exception
    
    def get_user_message(self) -> str:
        """Get user-friendly error message."""
        user_msg = self.message
        if self.suggestion:
            user_msg += f"\n\nSuggestion: {self.suggestion}"
        return user_msg
    
    def get_full_context(self) -> Dict[str, Any]:
        """Get complete error context."""
        context = {
            'error_code': self.error_code.value,
            'error_name': self.error_code.name,
            'message': self.message,
            'recoverable': self.recoverable,
            'suggestion': self.suggestion,
            'context': self.context
        }
        
        if self.original_exception:
            context['original_exception'] = {
                'type': type(self.original_exception).__name__,
                'message': str(self.original_exception)
            }
        
        return context


# Application specific exceptions
class ApplicationError(BulkEmailSenderException):
    """General application errors."""
    
    def __init__(self, message: str, **kwargs):
        super().__init__(
            message,
            error_code=ErrorCode.UNKNOWN_ERROR,
            suggestion="Please check the application logs for more details",
            **kwargs
        )


# Configuration related exceptions
class ConfigurationError(BulkEmailSenderException):
    """Configuration-related errors."""
    
    def __init__(self, message: str, config_key: Optional[str] = None, **kwargs):
        context = kwargs.get('context', {})
        if config_key:
            context['config_key'] = config_key
        
        super().__init__(
            message,
            error_code=ErrorCode.CONFIGURATION_ERROR,
            context=context,
            suggestion="Check configuration files and environment variables",
            **kwargs
        )


class ValidationError(BulkEmailSenderException):
    """Data validation errors."""
    
    def __init__(self, message: str, field: Optional[str] = None, value: Optional[Any] = None, **kwargs):
        context = kwargs.get('context', {})
        if field:
            context['field'] = field
        if value is not None:
            context['value'] = str(value)
        
        super().__init__(
            message,
            error_code=ErrorCode.VALIDATION_ERROR,
            context=context,
            suggestion="Please check the input data and try again",
            **kwargs
        )


# Network related exceptions
class NetworkError(BulkEmailSenderException):
    """Base class for network-related errors."""
    
    def __init__(self, message: str, host: Optional[str] = None, port: Optional[int] = None, **kwargs):
        context = kwargs.get('context', {})
        if host:
            context['host'] = host
        if port:
            context['port'] = port
        
        super().__init__(
            message,
            error_code=ErrorCode.NETWORK_CONNECTION_ERROR,
            context=context,
            suggestion="Check network connection and firewall settings",
            **kwargs
        )


class NetworkTimeoutError(NetworkError):
    """Network timeout errors."""
    
    def __init__(self, message: str, timeout: Optional[float] = None, **kwargs):
        context = kwargs.get('context', {})
        if timeout:
            context['timeout'] = timeout
        
        super().__init__(
            message,
            error_code=ErrorCode.NETWORK_TIMEOUT_ERROR,
            context=context,
            suggestion="Increase timeout value or check network stability",
            **kwargs
        )


# SMTP related exceptions
class SMTPError(BulkEmailSenderException):
    """Base class for SMTP-related errors."""
    
    def __init__(self, message: str, smtp_host: Optional[str] = None, smtp_code: Optional[int] = None, **kwargs):
        context = kwargs.get('context', {})
        if smtp_host:
            context['smtp_host'] = smtp_host
        if smtp_code:
            context['smtp_code'] = smtp_code
        
        super().__init__(
            message,
            error_code=ErrorCode.SMTP_CONNECTION_ERROR,
            context=context,
            suggestion="Check SMTP settings and credentials",
            **kwargs
        )


class SMTPAuthenticationError(SMTPError):
    """SMTP authentication errors."""
    
    def __init__(self, message: str, username: Optional[str] = None, **kwargs):
        context = kwargs.get('context', {})
        if username:
            context['username'] = username
        
        super().__init__(
            message,
            error_code=ErrorCode.SMTP_AUTHENTICATION_ERROR,
            context=context,
            suggestion="Verify username, password, and SMTP server settings",
            **kwargs
        )


class SMTPSendError(SMTPError):
    """SMTP message sending errors."""
    
    def __init__(self, message: str, recipient: Optional[str] = None, **kwargs):
        context = kwargs.get('context', {})
        if recipient:
            context['recipient'] = recipient
        
        super().__init__(
            message,
            error_code=ErrorCode.SMTP_SEND_ERROR,
            context=context,
            suggestion="Check recipient email address and try again",
            **kwargs
        )


# Email related exceptions
class EmailError(BulkEmailSenderException):
    """Base class for email-related errors."""
    
    def __init__(self, message: str, **kwargs):
        super().__init__(
            message,
            error_code=ErrorCode.EMAIL_INVALID_FORMAT,
            suggestion="Check email format and content",
            **kwargs
        )


class EmailAttachmentError(EmailError):
    """Email attachment errors."""
    
    def __init__(self, message: str, filename: Optional[str] = None, **kwargs):
        context = kwargs.get('context', {})
        if filename:
            context['filename'] = filename
        
        super().__init__(
            message,
            error_code=ErrorCode.EMAIL_ATTACHMENT_ERROR,
            context=context,
            suggestion="Check attachment file exists and is not corrupted",
            **kwargs
        )


# Data related exceptions
class DataError(BulkEmailSenderException):
    """Base class for data-related errors."""
    
    def __init__(self, message: str, **kwargs):
        super().__init__(
            message,
            error_code=ErrorCode.DATA_FILE_NOT_FOUND,
            suggestion="Check file path and permissions",
            **kwargs
        )


class DataFileError(DataError):
    """Data file errors."""
    
    def __init__(self, message: str, filepath: Optional[str] = None, **kwargs):
        context = kwargs.get('context', {})
        if filepath:
            context['filepath'] = filepath
        
        super().__init__(
            message,
            context=context,
            **kwargs
        )


class FileError(DataFileError):
    """Simple file error alias for UI compatibility."""
    
    def __init__(self, message: str, filepath: Optional[str] = None, **kwargs):
        super().__init__(message, filepath, **kwargs)


# Security related exceptions
class SecurityError(BulkEmailSenderException):
    """Base class for security-related errors."""
    
    def __init__(self, message: str, **kwargs):
        super().__init__(
            message,
            error_code=ErrorCode.SECURITY_ENCRYPTION_ERROR,
            suggestion="Check security settings and permissions",
            recoverable=False,
            **kwargs
        )


class EncryptionError(SecurityError):
    """Encryption/decryption errors."""
    
    def __init__(self, message: str, operation: str = "encryption", **kwargs):
        context = kwargs.get('context', {})
        context['operation'] = operation
        
        error_code = (ErrorCode.SECURITY_ENCRYPTION_ERROR 
                     if operation == "encryption" 
                     else ErrorCode.SECURITY_DECRYPTION_ERROR)
        
        super().__init__(
            message,
            error_code=error_code,
            context=context,
            **kwargs
        )


# Worker/Threading related exceptions
class WorkerError(BulkEmailSenderException):
    """Base class for worker/threading errors."""
    
    def __init__(self, message: str, worker_type: Optional[str] = None, **kwargs):
        context = kwargs.get('context', {})
        if worker_type:
            context['worker_type'] = worker_type
        
        super().__init__(
            message,
            error_code=ErrorCode.WORKER_EXECUTION_ERROR,
            context=context,
            suggestion="Try restarting the operation",
            **kwargs
        )


class WorkerTimeoutError(WorkerError):
    """Worker timeout errors."""
    
    def __init__(self, message: str, timeout: Optional[float] = None, **kwargs):
        context = kwargs.get('context', {})
        if timeout:
            context['timeout'] = timeout
        
        super().__init__(
            message,
            error_code=ErrorCode.WORKER_TIMEOUT_ERROR,
            context=context,
            suggestion="Increase timeout or check system resources",
            **kwargs
        )


class WorkerCancelledException(WorkerError):
    """Worker cancellation exceptions."""
    
    def __init__(self, message: str = "Operation was cancelled", **kwargs):
        super().__init__(
            message,
            error_code=ErrorCode.WORKER_CANCELLED,
            suggestion="Operation was cancelled by user",
            recoverable=False,
            **kwargs
        )


# Exception utilities
def handle_exception(exception: Exception, context: Optional[Dict[str, Any]] = None) -> BulkEmailSenderException:
    """
    Convert a generic exception to a BulkEmailSenderException.
    
    Args:
        exception: Original exception
        context: Additional context
        
    Returns:
        BulkEmailSenderException instance
    """
    if isinstance(exception, BulkEmailSenderException):
        return exception
    
    # Map common exception types
    exception_type = type(exception).__name__
    message = str(exception)
    
    if "connection" in message.lower() or "network" in message.lower():
        return NetworkError(
            f"Network error: {message}",
            context=context,
            original_exception=exception
        )
    elif "timeout" in message.lower():
        return NetworkTimeoutError(
            f"Timeout error: {message}",
            context=context,
            original_exception=exception
        )
    elif "smtp" in message.lower() or "mail" in message.lower():
        return SMTPError(
            f"SMTP error: {message}",
            context=context,
            original_exception=exception
        )
    elif "file" in message.lower() or "path" in message.lower():
        return DataFileError(
            f"File error: {message}",
            context=context,
            original_exception=exception
        )
    else:
        return BulkEmailSenderException(
            f"Unexpected error ({exception_type}): {message}",
            context=context,
            original_exception=exception
        )


def get_error_summary(exceptions: List[BulkEmailSenderException]) -> Dict[str, Any]:
    """
    Get summary of multiple exceptions.
    
    Args:
        exceptions: List of exceptions
        
    Returns:
        Summary dictionary
    """
    if not exceptions:
        return {}
    
    error_counts = {}
    recoverable_count = 0
    critical_count = 0
    
    for exc in exceptions:
        error_type = exc.error_code.name
        error_counts[error_type] = error_counts.get(error_type, 0) + 1
        
        if exc.recoverable:
            recoverable_count += 1
        else:
            critical_count += 1
    
    return {
        'total_errors': len(exceptions),
        'recoverable_errors': recoverable_count,
        'critical_errors': critical_count,
        'error_breakdown': error_counts,
        'most_common_error': max(error_counts.items(), key=lambda x: x[1])[0] if error_counts else None
    }