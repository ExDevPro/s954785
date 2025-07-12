"""
SMTP test worker for Bulk Email Sender.

This module provides a worker for testing SMTP connections:
- Asynchronous SMTP testing
- Connection validation
- Authentication verification
- Progress reporting
"""

import smtplib
import socket
import ssl
from typing import Dict, Any, List, Optional
import time

from workers.base_worker import BaseWorker
from core.data.models import SMTPConfig, SMTPSecurityType
from core.utils.logger import get_module_logger
from core.utils.exceptions import SMTPError, SMTPAuthenticationError, NetworkError, NetworkTimeoutError

logger = get_module_logger(__name__)


class SMTPTestResult:
    """SMTP test result container."""
    
    def __init__(self, smtp_config: SMTPConfig, success: bool = False, 
                 error_message: str = "", response_time: float = 0.0):
        """
        Initialize SMTP test result.
        
        Args:
            smtp_config: SMTP configuration that was tested
            success: Whether test was successful
            error_message: Error message if test failed
            response_time: Connection response time in seconds
        """
        self.smtp_config = smtp_config
        self.success = success
        self.error_message = error_message
        self.response_time = response_time
        self.timestamp = time.time()
        
        # Additional test details
        self.server_response = ""
        self.supported_features = []
        self.max_message_size = None
        self.tls_available = False
        self.auth_methods = []


class SMTPTestWorker(BaseWorker):
    """Worker for testing SMTP connections."""
    
    def __init__(self, timeout: float = 30.0):
        """
        Initialize SMTP test worker.
        
        Args:
            timeout: Timeout for SMTP operations
        """
        super().__init__("smtp_test", timeout)
        self._default_timeout = timeout
    
    def _execute(self, smtp_configs: List[SMTPConfig], detailed_test: bool = True) -> List[SMTPTestResult]:
        """
        Execute SMTP testing for multiple configurations.
        
        Args:
            smtp_configs: List of SMTP configurations to test
            detailed_test: Whether to perform detailed feature testing
            
        Returns:
            List of SMTPTestResult instances
        """
        results = []
        total_configs = len(smtp_configs)
        
        self._update_progress(
            current=0,
            total=total_configs,
            message="Starting SMTP connection tests...",
            details={'phase': 'initialization'}
        )
        
        for i, smtp_config in enumerate(smtp_configs):
            self._check_cancellation()
            self._check_pause()
            
            self._update_progress(
                current=i,
                message=f"Testing SMTP: {smtp_config.host}:{smtp_config.port}",
                details={'current_host': smtp_config.host, 'phase': 'testing'}
            )
            
            try:
                result = self._test_single_smtp(smtp_config, detailed_test)
                results.append(result)
                
                # Log result
                if result.success:
                    self._logger.info(f"SMTP test successful: {smtp_config.host}:{smtp_config.port} "
                                    f"({result.response_time:.2f}s)")
                else:
                    self._logger.warning(f"SMTP test failed: {smtp_config.host}:{smtp_config.port} - "
                                       f"{result.error_message}")
                
            except Exception as e:
                error_result = SMTPTestResult(
                    smtp_config=smtp_config,
                    success=False,
                    error_message=f"Test error: {str(e)}"
                )
                results.append(error_result)
                self._logger.exception(e, f"testing SMTP {smtp_config.host}:{smtp_config.port}")
            
            # Small delay between tests to avoid overwhelming servers
            time.sleep(0.5)
        
        self._update_progress(
            current=total_configs,
            message="SMTP testing completed",
            details={'phase': 'completed', 'successful_tests': sum(1 for r in results if r.success)}
        )
        
        return results
    
    def _test_single_smtp(self, smtp_config: SMTPConfig, detailed_test: bool = True) -> SMTPTestResult:
        """
        Test a single SMTP configuration.
        
        Args:
            smtp_config: SMTP configuration to test
            detailed_test: Whether to perform detailed testing
            
        Returns:
            SMTPTestResult instance
        """
        start_time = time.time()
        server = None
        
        try:
            # Determine timeout for this test
            timeout = smtp_config.timeout if smtp_config.timeout > 0 else self._default_timeout
            
            # Create SMTP connection based on security type
            if smtp_config.security_type == SMTPSecurityType.SSL:
                # SSL/TLS connection
                server = smtplib.SMTP_SSL(
                    smtp_config.host, 
                    smtp_config.port, 
                    timeout=timeout
                )
            else:
                # Plain or STARTTLS connection
                server = smtplib.SMTP(
                    smtp_config.host, 
                    smtp_config.port, 
                    timeout=timeout
                )
            
            # Send EHLO command
            ehlo_response = server.ehlo()
            if ehlo_response[0] != 250:
                raise SMTPError(f"EHLO command failed: {ehlo_response[1].decode()}")
            
            result = SMTPTestResult(
                smtp_config=smtp_config,
                success=False,  # Will be set to True if all tests pass
                response_time=time.time() - start_time
            )
            
            # Store server response
            result.server_response = ehlo_response[1].decode() if ehlo_response[1] else ""
            
            # Check for STARTTLS if required
            if smtp_config.use_tls and smtp_config.security_type != SMTPSecurityType.SSL:
                if server.has_extn('STARTTLS'):
                    result.tls_available = True
                    server.starttls()
                    # Send EHLO again after STARTTLS
                    server.ehlo()
                else:
                    raise SMTPError("STARTTLS required but not supported by server")
            
            # Test authentication
            try:
                server.login(smtp_config.username, smtp_config.password)
                auth_successful = True
            except smtplib.SMTPAuthenticationError as e:
                raise SMTPAuthenticationError(
                    f"Authentication failed: {str(e)}",
                    username=smtp_config.username
                )
            except smtplib.SMTPException as e:
                raise SMTPError(f"SMTP authentication error: {str(e)}")
            
            # Perform detailed testing if requested
            if detailed_test:
                self._perform_detailed_testing(server, result)
            
            # If we get here, all tests passed
            result.success = True
            result.response_time = time.time() - start_time
            
            return result
        
        except socket.timeout:
            raise NetworkTimeoutError(
                f"SMTP connection timeout to {smtp_config.host}:{smtp_config.port}",
                host=smtp_config.host,
                port=smtp_config.port,
                timeout=timeout
            )
        
        except socket.gaierror as e:
            raise NetworkError(
                f"DNS resolution failed for {smtp_config.host}: {str(e)}",
                host=smtp_config.host,
                port=smtp_config.port
            )
        
        except ConnectionRefusedError:
            raise NetworkError(
                f"Connection refused to {smtp_config.host}:{smtp_config.port}",
                host=smtp_config.host,
                port=smtp_config.port
            )
        
        except ssl.SSLError as e:
            raise SMTPError(
                f"SSL/TLS error connecting to {smtp_config.host}:{smtp_config.port}: {str(e)}",
                smtp_host=smtp_config.host
            )
        
        except smtplib.SMTPConnectError as e:
            raise SMTPError(
                f"SMTP connection error to {smtp_config.host}:{smtp_config.port}: {str(e)}",
                smtp_host=smtp_config.host,
                smtp_code=e.smtp_code if hasattr(e, 'smtp_code') else None
            )
        
        except smtplib.SMTPServerDisconnected:
            raise SMTPError(
                f"SMTP server disconnected: {smtp_config.host}:{smtp_config.port}",
                smtp_host=smtp_config.host
            )
        
        except smtplib.SMTPException as e:
            raise SMTPError(
                f"SMTP error: {str(e)}",
                smtp_host=smtp_config.host
            )
        
        finally:
            # Always close the connection
            if server:
                try:
                    server.quit()
                except Exception:
                    pass  # Ignore errors when closing
    
    def _perform_detailed_testing(self, server: smtplib.SMTP, result: SMTPTestResult) -> None:
        """
        Perform detailed SMTP server testing.
        
        Args:
            server: Connected SMTP server
            result: Result object to update with details
        """
        try:
            # Get supported features
            if hasattr(server, 'esmtp_features'):
                result.supported_features = list(server.esmtp_features.keys())
            
            # Check authentication methods
            if server.has_extn('AUTH'):
                auth_methods = server.esmtp_features.get('auth', '').split()
                result.auth_methods = [method.upper() for method in auth_methods if method]
            
            # Check maximum message size
            if server.has_extn('SIZE'):
                try:
                    size_limit = server.esmtp_features.get('size')
                    if size_limit:
                        result.max_message_size = int(size_limit)
                except (ValueError, TypeError):
                    pass
            
            # Check TLS availability
            result.tls_available = server.has_extn('STARTTLS')
            
        except Exception as e:
            # Don't fail the entire test for detailed feature detection
            self._logger.debug(f"Error during detailed SMTP testing: {e}")


class BulkSMTPTestWorker(BaseWorker):
    """Worker for testing multiple SMTP configurations in parallel."""
    
    def __init__(self, max_concurrent: int = 5, timeout: float = 30.0):
        """
        Initialize bulk SMTP test worker.
        
        Args:
            max_concurrent: Maximum concurrent SMTP tests
            timeout: Timeout for each SMTP test
        """
        super().__init__("bulk_smtp_test", timeout * 10)  # Overall timeout
        self.max_concurrent = max_concurrent
        self.smtp_timeout = timeout
    
    def _execute(self, smtp_configs: List[SMTPConfig], detailed_test: bool = True) -> Dict[str, Any]:
        """
        Execute bulk SMTP testing with parallel execution.
        
        Args:
            smtp_configs: List of SMTP configurations to test
            detailed_test: Whether to perform detailed testing
            
        Returns:
            Dictionary with test results and summary
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed
        
        total_configs = len(smtp_configs)
        results = []
        completed = 0
        
        self._update_progress(
            current=0,
            total=total_configs,
            message="Starting bulk SMTP testing...",
            details={'phase': 'initialization', 'concurrent_limit': self.max_concurrent}
        )
        
        with ThreadPoolExecutor(max_workers=self.max_concurrent) as executor:
            # Submit all test tasks
            future_to_config = {}
            for smtp_config in smtp_configs:
                future = executor.submit(self._test_single_config, smtp_config, detailed_test)
                future_to_config[future] = smtp_config
            
            # Collect results as they complete
            for future in as_completed(future_to_config):
                self._check_cancellation()
                
                smtp_config = future_to_config[future]
                
                try:
                    result = future.result()
                    results.append(result)
                    
                    completed += 1
                    self._update_progress(
                        current=completed,
                        message=f"Completed SMTP test: {smtp_config.host}:{smtp_config.port}",
                        details={
                            'phase': 'testing',
                            'last_tested': f"{smtp_config.host}:{smtp_config.port}",
                            'success': result.success
                        }
                    )
                    
                except Exception as e:
                    error_result = SMTPTestResult(
                        smtp_config=smtp_config,
                        success=False,
                        error_message=f"Test execution error: {str(e)}"
                    )
                    results.append(error_result)
                    
                    completed += 1
                    self._update_progress(
                        current=completed,
                        message=f"Failed SMTP test: {smtp_config.host}:{smtp_config.port}",
                        details={
                            'phase': 'testing',
                            'last_tested': f"{smtp_config.host}:{smtp_config.port}",
                            'success': False,
                            'error': str(e)
                        }
                    )
                    
                    self._logger.exception(e, f"bulk SMTP test for {smtp_config.host}:{smtp_config.port}")
        
        # Generate summary
        successful_tests = [r for r in results if r.success]
        failed_tests = [r for r in results if not r.success]
        
        summary = {
            'total_tested': len(results),
            'successful': len(successful_tests),
            'failed': len(failed_tests),
            'success_rate': (len(successful_tests) / len(results) * 100) if results else 0,
            'average_response_time': sum(r.response_time for r in successful_tests) / len(successful_tests) if successful_tests else 0,
            'fastest_server': min(successful_tests, key=lambda r: r.response_time) if successful_tests else None,
            'slowest_server': max(successful_tests, key=lambda r: r.response_time) if successful_tests else None
        }
        
        self._update_progress(
            current=total_configs,
            message="Bulk SMTP testing completed",
            details={
                'phase': 'completed',
                'summary': summary
            }
        )
        
        return {
            'results': results,
            'summary': summary,
            'successful_configs': [r.smtp_config for r in successful_tests],
            'failed_configs': [r.smtp_config for r in failed_tests]
        }
    
    def _test_single_config(self, smtp_config: SMTPConfig, detailed_test: bool) -> SMTPTestResult:
        """
        Test a single SMTP configuration (used in thread pool).
        
        Args:
            smtp_config: SMTP configuration to test
            detailed_test: Whether to perform detailed testing
            
        Returns:
            SMTPTestResult instance
        """
        # Create a single-use test worker for this configuration
        test_worker = SMTPTestWorker(timeout=self.smtp_timeout)
        
        try:
            results = test_worker._test_single_smtp(smtp_config, detailed_test)
            return results
        except Exception as e:
            return SMTPTestResult(
                smtp_config=smtp_config,
                success=False,
                error_message=str(e)
            )


def test_smtp_connection(smtp_config: SMTPConfig, timeout: float = 30.0, 
                        detailed: bool = False) -> SMTPTestResult:
    """
    Convenience function to test a single SMTP connection.
    
    Args:
        smtp_config: SMTP configuration to test
        timeout: Connection timeout
        detailed: Whether to perform detailed testing
        
    Returns:
        SMTPTestResult instance
    """
    worker = SMTPTestWorker(timeout=timeout)
    return worker._test_single_smtp(smtp_config, detailed)


def test_multiple_smtp_configs(smtp_configs: List[SMTPConfig], 
                              max_concurrent: int = 5,
                              timeout: float = 30.0,
                              detailed: bool = False) -> Dict[str, Any]:
    """
    Convenience function to test multiple SMTP configurations.
    
    Args:
        smtp_configs: List of SMTP configurations to test
        max_concurrent: Maximum concurrent tests
        timeout: Timeout per test
        detailed: Whether to perform detailed testing
        
    Returns:
        Dictionary with test results and summary
    """
    worker = BulkSMTPTestWorker(max_concurrent=max_concurrent, timeout=timeout)
    return worker._execute(smtp_configs, detailed)