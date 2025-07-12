"""
Logging configuration for Bulk Email Sender.

This module provides centralized logging setup with support for:
- Multiple log levels
- File and console output
- Log rotation
- Structured logging
"""

import logging
import logging.handlers
import os
import sys
from typing import Optional, Dict, Any
from pathlib import Path

from config.settings import get_config


class ColoredFormatter(logging.Formatter):
    """Formatter that adds colors to console output."""
    
    COLORS = {
        'DEBUG': '\033[36m',    # Cyan
        'INFO': '\033[32m',     # Green
        'WARNING': '\033[33m',  # Yellow
        'ERROR': '\033[31m',    # Red
        'CRITICAL': '\033[35m', # Magenta
    }
    RESET = '\033[0m'
    
    def format(self, record):
        if hasattr(record, 'levelname') and record.levelname in self.COLORS:
            record.levelname = f"{self.COLORS[record.levelname]}{record.levelname}{self.RESET}"
        return super().format(record)


def setup_logging(
    log_level: Optional[str] = None,
    log_file: Optional[str] = None,
    console_output: bool = True,
    file_output: bool = True
) -> None:
    """
    Setup centralized logging configuration.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Custom log file path
        console_output: Enable console output
        file_output: Enable file output
    """
    config = get_config()
    
    # Get configuration values
    if log_level is None:
        log_level = config.get('logging.level', 'INFO')
    
    log_format = config.get('logging.format', 
                           '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    max_file_size = config.get('logging.max_file_size_mb', 10) * 1024 * 1024
    backup_count = config.get('logging.backup_count', 5)
    
    # Set up root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper()))
    
    # Clear existing handlers
    root_logger.handlers.clear()
    
    # Create formatters
    file_formatter = logging.Formatter(log_format)
    console_formatter = ColoredFormatter(log_format)
    
    # Setup file logging
    if file_output:
        if log_file is None:
            logs_dir = os.path.join(config.base_path, config.get('paths.logs_dir', 'logs'))
            os.makedirs(logs_dir, exist_ok=True)
            log_file = os.path.join(logs_dir, 'bulk_email_sender.log')
        
        # Rotating file handler
        file_handler = logging.handlers.RotatingFileHandler(
            log_file, 
            maxBytes=max_file_size,
            backupCount=backup_count,
            encoding='utf-8'
        )
        file_handler.setFormatter(file_formatter)
        file_handler.setLevel(getattr(logging, log_level.upper()))
        root_logger.addHandler(file_handler)
        
        # Error log file
        error_log_file = os.path.join(os.path.dirname(log_file), 'errors.log')
        error_handler = logging.handlers.RotatingFileHandler(
            error_log_file,
            maxBytes=max_file_size,
            backupCount=backup_count,
            encoding='utf-8'
        )
        error_handler.setFormatter(file_formatter)
        error_handler.setLevel(logging.ERROR)
        root_logger.addHandler(error_handler)
    
    # Setup console logging
    if console_output:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(console_formatter)
        console_handler.setLevel(getattr(logging, log_level.upper()))
        root_logger.addHandler(console_handler)
    
    # Log startup message
    logger = logging.getLogger(__name__)
    logger.info(f"Logging initialized - Level: {log_level}")
    if file_output:
        logger.info(f"Log file: {log_file}")


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance for the given name.
    
    Args:
        name: Logger name (usually __name__)
        
    Returns:
        Logger instance
    """
    return logging.getLogger(name)


def setup_module_loggers() -> None:
    """Setup specific loggers for different modules."""
    # SMTP logger
    smtp_logger = logging.getLogger('smtp')
    smtp_logger.setLevel(logging.INFO)
    
    # Email sending logger
    sender_logger = logging.getLogger('sender')
    sender_logger.setLevel(logging.INFO)
    
    # Security logger
    security_logger = logging.getLogger('security')
    security_logger.setLevel(logging.WARNING)
    
    # UI logger
    ui_logger = logging.getLogger('ui')
    ui_logger.setLevel(logging.INFO)
    
    # Worker logger
    worker_logger = logging.getLogger('worker')
    worker_logger.setLevel(logging.INFO)


def log_exception(logger: logging.Logger, exception: Exception, context: str = "") -> None:
    """
    Log an exception with full traceback.
    
    Args:
        logger: Logger instance
        exception: Exception to log
        context: Additional context information
    """
    import traceback
    
    error_msg = f"Exception in {context}: {str(exception)}" if context else f"Exception: {str(exception)}"
    logger.error(error_msg)
    logger.error(f"Traceback: {traceback.format_exc()}")


def log_performance(logger: logging.Logger, operation: str, duration: float, details: Optional[Dict[str, Any]] = None) -> None:
    """
    Log performance metrics.
    
    Args:
        logger: Logger instance
        operation: Operation name
        duration: Duration in seconds
        details: Additional details dictionary
    """
    msg = f"Performance - {operation}: {duration:.3f}s"
    if details:
        detail_str = ", ".join([f"{k}={v}" for k, v in details.items()])
        msg += f" ({detail_str})"
    
    logger.info(msg)


class ContextLogger:
    """Logger with context information."""
    
    def __init__(self, logger: logging.Logger, context: Dict[str, Any]):
        """
        Initialize context logger.
        
        Args:
            logger: Base logger
            context: Context information to include in all log messages
        """
        self.logger = logger
        self.context = context
    
    def _format_message(self, message: str) -> str:
        """Format message with context."""
        context_str = ", ".join([f"{k}={v}" for k, v in self.context.items()])
        return f"[{context_str}] {message}"
    
    def debug(self, message: str) -> None:
        """Log debug message with context."""
        self.logger.debug(self._format_message(message))
    
    def info(self, message: str) -> None:
        """Log info message with context."""
        self.logger.info(self._format_message(message))
    
    def warning(self, message: str) -> None:
        """Log warning message with context."""
        self.logger.warning(self._format_message(message))
    
    def error(self, message: str) -> None:
        """Log error message with context."""
        self.logger.error(self._format_message(message))
    
    def critical(self, message: str) -> None:
        """Log critical message with context."""
        self.logger.critical(self._format_message(message))
    
    def exception(self, exception: Exception, context_msg: str = "") -> None:
        """Log exception with context."""
        log_exception(self.logger, exception, context_msg)


def get_context_logger(name: str, context: Dict[str, Any]) -> ContextLogger:
    """
    Get a context logger instance.
    
    Args:
        name: Logger name
        context: Context information
        
    Returns:
        ContextLogger instance
    """
    logger = get_logger(name)
    return ContextLogger(logger, context)