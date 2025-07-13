"""
Centralized logging utility for Bulk Email Sender.

This module provides a centralized logging system with:
- Easy-to-use logging interface
- Performance tracking
- Error reporting
- Context-aware logging
"""

import logging
import time
import functools
from typing import Any, Dict, Optional, Callable, TypeVar, cast
from contextlib import contextmanager

from config.logging_config import get_logger, get_context_logger, log_exception, log_performance
from core.utils.exceptions import BulkEmailSenderException, handle_exception

# Type variable for decorated functions
F = TypeVar('F', bound=Callable[..., Any])


class Logger:
    """Centralized logger with convenience methods."""
    
    def __init__(self, name: str):
        """
        Initialize logger for specific module.
        
        Args:
            name: Logger name (usually __name__)
        """
        self._logger = get_logger(name)
        self._name = name
    
    def debug(self, message: str, **kwargs) -> None:
        """Log debug message with optional context."""
        if kwargs:
            message = f"{message} - {self._format_kwargs(kwargs)}"
        self._logger.debug(message)
    
    def info(self, message: str, **kwargs) -> None:
        """Log info message with optional context."""
        if kwargs:
            message = f"{message} - {self._format_kwargs(kwargs)}"
        self._logger.info(message)
    
    def warning(self, message: str, **kwargs) -> None:
        """Log warning message with optional context."""
        if kwargs:
            message = f"{message} - {self._format_kwargs(kwargs)}"
        self._logger.warning(message)
    
    def error(self, message: str, **kwargs) -> None:
        """Log error message with optional context."""
        if kwargs:
            message = f"{message} - {self._format_kwargs(kwargs)}"
        self._logger.error(message)
    
    def critical(self, message: str, **kwargs) -> None:
        """Log critical message with optional context."""
        if kwargs:
            message = f"{message} - {self._format_kwargs(kwargs)}"
        self._logger.critical(message)
    
    def exception(self, exception: Exception, context: str = "", **kwargs) -> None:
        """Log exception with full traceback and context."""
        log_exception(self._logger, exception, context)
        if kwargs:
            self.error(f"Exception context: {self._format_kwargs(kwargs)}")
    
    def performance(self, operation: str, duration: float, **kwargs) -> None:
        """Log performance metrics."""
        log_performance(self._logger, operation, duration, kwargs)
    
    def _format_kwargs(self, kwargs: Dict[str, Any]) -> str:
        """Format keyword arguments for logging."""
        return ", ".join([f"{k}={v}" for k, v in kwargs.items()])
    
    @contextmanager
    def context(self, **context_data):
        """Context manager for adding context to all log messages."""
        context_logger = get_context_logger(self._name, context_data)
        original_logger = self._logger
        
        # Temporarily replace logger with context logger
        self._logger = context_logger.logger
        
        try:
            yield context_logger
        finally:
            self._logger = original_logger
    
    def timing_context(self, operation: str):
        """Context manager for timing operations."""
        return TimingContext(self, operation)


class TimingContext:
    """Context manager for timing operations."""
    
    def __init__(self, logger: Logger, operation: str):
        """
        Initialize timing context.
        
        Args:
            logger: Logger instance
            operation: Operation name
        """
        self.logger = logger
        self.operation = operation
        self.start_time: Optional[float] = None
        self.end_time: Optional[float] = None
    
    def __enter__(self):
        """Start timing."""
        self.start_time = time.time()
        self.logger.debug(f"Starting operation: {self.operation}")
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """End timing and log results."""
        self.end_time = time.time()
        duration = self.end_time - (self.start_time or 0)
        
        if exc_type is None:
            self.logger.performance(self.operation, duration)
            self.logger.debug(f"Completed operation: {self.operation} in {duration:.3f}s")
        else:
            self.logger.performance(f"{self.operation}_failed", duration)
            self.logger.error(f"Failed operation: {self.operation} after {duration:.3f}s")
    
    @property
    def duration(self) -> Optional[float]:
        """Get current or final duration."""
        if self.start_time is None:
            return None
        end = self.end_time or time.time()
        return end - self.start_time


def get_module_logger(name: str) -> Logger:
    """
    Get a logger instance for a module.
    
    Args:
        name: Module name (usually __name__)
        
    Returns:
        Logger instance
    """
    return Logger(name)


def log_function_call(logger: Logger, include_args: bool = False, include_result: bool = False):
    """
    Decorator to log function calls.
    
    Args:
        logger: Logger instance
        include_args: Include function arguments in log
        include_result: Include function result in log
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            func_name = f"{func.__module__}.{func.__name__}"
            
            # Log function entry
            log_msg = f"Calling {func_name}"
            if include_args and (args or kwargs):
                arg_strs = [str(arg) for arg in args]
                kwarg_strs = [f"{k}={v}" for k, v in kwargs.items()]
                all_args = arg_strs + kwarg_strs
                log_msg += f" with args: ({', '.join(all_args)})"
            
            logger.debug(log_msg)
            
            # Time the function execution
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                duration = time.time() - start_time
                
                # Log successful completion
                log_msg = f"Completed {func_name} in {duration:.3f}s"
                if include_result:
                    log_msg += f" with result: {result}"
                
                logger.debug(log_msg)
                logger.performance(func_name, duration)
                
                return result
                
            except Exception as e:
                duration = time.time() - start_time
                logger.error(f"Failed {func_name} after {duration:.3f}s")
                logger.exception(e, f"in {func_name}")
                raise
        
        return cast(F, wrapper)
    return decorator


def log_method_call(include_args: bool = False, include_result: bool = False):
    """
    Decorator to log method calls (automatically uses class logger).
    
    Args:
        include_args: Include method arguments in log
        include_result: Include method result in log
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            # Get logger from self if available
            if hasattr(self, '_logger'):
                logger = self._logger
            elif hasattr(self, 'logger'):
                logger = self.logger
            else:
                logger = get_module_logger(f"{self.__class__.__module__}.{self.__class__.__name__}")
            
            func_name = f"{self.__class__.__name__}.{func.__name__}"
            
            # Log method entry
            log_msg = f"Calling {func_name}"
            if include_args and (args or kwargs):
                arg_strs = [str(arg) for arg in args]
                kwarg_strs = [f"{k}={v}" for k, v in kwargs.items()]
                all_args = arg_strs + kwarg_strs
                log_msg += f" with args: ({', '.join(all_args)})"
            
            logger.debug(log_msg)
            
            # Time the method execution
            start_time = time.time()
            try:
                result = func(self, *args, **kwargs)
                duration = time.time() - start_time
                
                # Log successful completion
                log_msg = f"Completed {func_name} in {duration:.3f}s"
                if include_result:
                    log_msg += f" with result: {result}"
                
                logger.debug(log_msg)
                logger.performance(func_name, duration)
                
                return result
                
            except Exception as e:
                duration = time.time() - start_time
                logger.error(f"Failed {func_name} after {duration:.3f}s")
                logger.exception(e, f"in {func_name}")
                raise
        
        return cast(F, wrapper)
    return decorator


def safe_execute(logger: Logger, operation: str, default_return: Any = None):
    """
    Decorator for safe execution with error handling.
    
    Args:
        logger: Logger instance
        operation: Operation description
        default_return: Default return value on error
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except BulkEmailSenderException as e:
                logger.error(f"Failed {operation}: {getattr(e, 'message', str(e))}")
                logger.exception(e, operation)
                return default_return
            except Exception as e:
                handled_exception = handle_exception(e, {'operation': operation})
                logger.error(f"Failed {operation}: {getattr(handled_exception, 'message', str(handled_exception))}")
                logger.exception(handled_exception, operation)
                return default_return
        
        return cast(F, wrapper)
    return decorator


# Global logger instances for different modules
smtp_logger = get_module_logger('smtp')
sender_logger = get_module_logger('sender')
ui_logger = get_module_logger('ui')
worker_logger = get_module_logger('worker')
security_logger = get_module_logger('security')
data_logger = get_module_logger('data')
config_logger = get_module_logger('config')


# Convenience functions for quick logging
def log_smtp_operation(message: str, **kwargs) -> None:
    """Log SMTP operation."""
    smtp_logger.info(message, **kwargs)


def log_email_sent(recipient: str, subject: str, success: bool = True, **kwargs) -> None:
    """Log email sending result."""
    if success:
        sender_logger.info(f"Email sent successfully", recipient=recipient, subject=subject, **kwargs)
    else:
        sender_logger.error(f"Failed to send email", recipient=recipient, subject=subject, **kwargs)


def log_ui_action(action: str, **kwargs) -> None:
    """Log UI action."""
    ui_logger.info(f"UI action: {action}", **kwargs)


def log_worker_status(worker_type: str, status: str, **kwargs) -> None:
    """Log worker status."""
    worker_logger.info(f"Worker {worker_type}: {status}", **kwargs)


def log_security_event(event: str, severity: str = "info", **kwargs) -> None:
    """Log security event."""
    if severity == "critical":
        security_logger.critical(f"Security event: {event}", **kwargs)
    elif severity == "error":
        security_logger.error(f"Security event: {event}", **kwargs)
    elif severity == "warning":
        security_logger.warning(f"Security event: {event}", **kwargs)
    else:
        security_logger.info(f"Security event: {event}", **kwargs)


def log_data_operation(operation: str, success: bool = True, **kwargs) -> None:
    """Log data operation."""
    if success:
        data_logger.info(f"Data operation successful: {operation}", **kwargs)
    else:
        data_logger.error(f"Data operation failed: {operation}", **kwargs)