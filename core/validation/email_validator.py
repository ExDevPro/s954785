"""
Email validation utilities for Bulk Email Sender.

This module provides comprehensive email validation including:
- Email format validation
- Domain validation
- Disposable email detection
- Bulk email validation
"""

import re
from typing import List, Dict, Set, Optional, Tuple
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
import time

try:
    import dns.resolver
    DNS_AVAILABLE = True
except ImportError:
    DNS_AVAILABLE = False

from core.utils.logger import get_module_logger
from core.utils.exceptions import ValidationError
from core.utils.helpers import normalize_email

logger = get_module_logger(__name__)


@dataclass
class EmailValidationResult:
    """Result of email validation."""
    
    email: str
    is_valid: bool
    is_format_valid: bool = False
    is_domain_valid: bool = False
    is_mx_valid: bool = False
    is_disposable: bool = False
    domain: str = ""
    error_message: str = ""
    confidence_score: float = 0.0


class EmailValidator:
    """Comprehensive email validator."""
    
    # Common disposable email domains (can be extended)
    DISPOSABLE_DOMAINS = {
        '10minutemail.com', 'tempmail.org', 'guerrillamail.com',
        'mailinator.com', 'yopmail.com', 'temp-mail.org',
        'throwaway.email', 'getnada.com', 'maildrop.cc',
        'mohmal.com', 'mytrashmail.com', 'sharklasers.com'
    }
    
    def __init__(self, check_mx: bool = True, check_disposable: bool = True, 
                 timeout: float = 5.0, max_workers: int = 4):
        """
        Initialize email validator.
        
        Args:
            check_mx: Whether to check MX records
            check_disposable: Whether to check for disposable domains
            timeout: Timeout for network operations
            max_workers: Maximum worker threads for bulk validation
        """
        self.check_mx = check_mx
        self.check_disposable = check_disposable
        self.timeout = timeout
        self.max_workers = max_workers
        
        # Cache for domain validation results
        self._domain_cache: Dict[str, bool] = {}
        self._mx_cache: Dict[str, bool] = {}
        
        # Extended disposable domain list
        self._disposable_domains = self.DISPOSABLE_DOMAINS.copy()
        self._load_extended_disposable_list()
    
    def _load_extended_disposable_list(self) -> None:
        """Load extended list of disposable email domains."""
        try:
            # Try to fetch updated list from online source
            response = requests.get(
                'https://raw.githubusercontent.com/martenson/disposable-email-domains/master/disposable_email_blocklist.conf',
                timeout=self.timeout
            )
            if response.status_code == 200:
                domains = response.text.strip().split('\n')
                self._disposable_domains.update(domain.strip() for domain in domains if domain.strip())
                logger.debug(f"Loaded {len(self._disposable_domains)} disposable domains")
        except Exception as e:
            logger.warning(f"Could not load extended disposable domain list: {e}")
    
    def validate_format(self, email: str) -> bool:
        """
        Validate email format using regex.
        
        Args:
            email: Email address to validate
            
        Returns:
            True if format is valid
        """
        # Comprehensive email regex pattern
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        
        if not re.match(pattern, email):
            return False
        
        # Additional checks
        local, domain = email.rsplit('@', 1)
        
        # Local part checks
        if len(local) > 64 or len(domain) > 255:
            return False
        
        # Check for consecutive dots
        if '..' in email:
            return False
        
        # Check for leading/trailing dots in local part
        if local.startswith('.') or local.endswith('.'):
            return False
        
        return True
    
    def validate_domain(self, domain: str) -> bool:
        """
        Validate domain existence.
        
        Args:
            domain: Domain to validate
            
        Returns:
            True if domain is valid
        """
        if not DNS_AVAILABLE:
            logger.warning("DNS resolution not available, skipping domain validation")
            return True  # Assume valid if DNS not available
            
        if domain in self._domain_cache:
            return self._domain_cache[domain]
        
        try:
            # Check if domain has A or AAAA record
            dns.resolver.resolve(domain, 'A')
            self._domain_cache[domain] = True
            return True
        except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer):
            try:
                dns.resolver.resolve(domain, 'AAAA')
                self._domain_cache[domain] = True
                return True
            except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer):
                self._domain_cache[domain] = False
                return False
        except Exception as e:
            logger.debug(f"Domain validation error for {domain}: {e}")
            self._domain_cache[domain] = False
            return False
    
    def validate_mx_record(self, domain: str) -> bool:
        """
        Validate MX record existence.
        
        Args:
            domain: Domain to check
            
        Returns:
            True if MX record exists
        """
        if not DNS_AVAILABLE:
            logger.warning("DNS resolution not available, skipping MX validation")
            return True  # Assume valid if DNS not available
            
        if domain in self._mx_cache:
            return self._mx_cache[domain]
        
        try:
            mx_records = dns.resolver.resolve(domain, 'MX')
            has_mx = len(mx_records) > 0
            self._mx_cache[domain] = has_mx
            return has_mx
        except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer):
            self._mx_cache[domain] = False
            return False
        except Exception as e:
            logger.debug(f"MX validation error for {domain}: {e}")
            self._mx_cache[domain] = False
            return False
    
    def is_disposable_domain(self, domain: str) -> bool:
        """
        Check if domain is a disposable email provider.
        
        Args:
            domain: Domain to check
            
        Returns:
            True if domain is disposable
        """
        return domain.lower() in self._disposable_domains
    
    def validate_single(self, email: str) -> EmailValidationResult:
        """
        Validate a single email address.
        
        Args:
            email: Email address to validate
            
        Returns:
            EmailValidationResult instance
        """
        email = normalize_email(email)
        result = EmailValidationResult(email=email, is_valid=False)
        
        try:
            # Format validation
            result.is_format_valid = self.validate_format(email)
            if not result.is_format_valid:
                result.error_message = "Invalid email format"
                return result
            
            # Extract domain
            result.domain = email.split('@')[1]
            
            # Disposable email check
            if self.check_disposable:
                result.is_disposable = self.is_disposable_domain(result.domain)
            
            # Domain validation
            result.is_domain_valid = self.validate_domain(result.domain)
            if not result.is_domain_valid:
                result.error_message = "Domain does not exist"
                return result
            
            # MX record validation
            if self.check_mx:
                result.is_mx_valid = self.validate_mx_record(result.domain)
                if not result.is_mx_valid:
                    result.error_message = "No MX record found for domain"
                    return result
            else:
                result.is_mx_valid = True
            
            # Calculate confidence score
            score = 0.0
            if result.is_format_valid:
                score += 25.0
            if result.is_domain_valid:
                score += 25.0
            if result.is_mx_valid:
                score += 25.0
            if not result.is_disposable:
                score += 25.0
            
            result.confidence_score = score
            result.is_valid = score >= 75.0
            
            if result.is_valid:
                result.error_message = ""
            elif result.is_disposable:
                result.error_message = "Disposable email domain"
            
        except Exception as e:
            result.error_message = f"Validation error: {e}"
            logger.exception(e, f"validating email {email}")
        
        return result
    
    def validate_bulk(self, emails: List[str], show_progress: bool = False) -> List[EmailValidationResult]:
        """
        Validate multiple email addresses in parallel.
        
        Args:
            emails: List of email addresses to validate
            show_progress: Whether to show progress updates
            
        Returns:
            List of EmailValidationResult instances
        """
        results = []
        total = len(emails)
        processed = 0
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all validation tasks
            future_to_email = {
                executor.submit(self.validate_single, email): email 
                for email in emails
            }
            
            # Collect results as they complete
            for future in as_completed(future_to_email):
                try:
                    result = future.result()
                    results.append(result)
                    processed += 1
                    
                    if show_progress and processed % 10 == 0:
                        progress = (processed / total) * 100
                        logger.info(f"Email validation progress: {processed}/{total} ({progress:.1f}%)")
                        
                except Exception as e:
                    email = future_to_email[future]
                    error_result = EmailValidationResult(
                        email=email,
                        is_valid=False,
                        error_message=f"Validation failed: {e}"
                    )
                    results.append(error_result)
                    processed += 1
        
        # Sort results to match input order
        email_to_result = {result.email: result for result in results}
        ordered_results = [email_to_result.get(normalize_email(email)) for email in emails]
        
        return [result for result in ordered_results if result is not None]
    
    def get_validation_summary(self, results: List[EmailValidationResult]) -> Dict[str, int]:
        """
        Get summary statistics for validation results.
        
        Args:
            results: List of validation results
            
        Returns:
            Summary statistics dictionary
        """
        total = len(results)
        valid = sum(1 for r in results if r.is_valid)
        invalid_format = sum(1 for r in results if not r.is_format_valid)
        invalid_domain = sum(1 for r in results if r.is_format_valid and not r.is_domain_valid)
        no_mx = sum(1 for r in results if r.is_domain_valid and not r.is_mx_valid)
        disposable = sum(1 for r in results if r.is_disposable)
        
        return {
            'total': total,
            'valid': valid,
            'invalid': total - valid,
            'invalid_format': invalid_format,
            'invalid_domain': invalid_domain,
            'no_mx_record': no_mx,
            'disposable': disposable,
            'success_rate': (valid / total * 100) if total > 0 else 0
        }
    
    def filter_valid_emails(self, results: List[EmailValidationResult]) -> List[str]:
        """
        Filter and return only valid email addresses.
        
        Args:
            results: List of validation results
            
        Returns:
            List of valid email addresses
        """
        return [result.email for result in results if result.is_valid]
    
    def export_validation_report(self, results: List[EmailValidationResult], filepath: str) -> bool:
        """
        Export validation results to CSV file.
        
        Args:
            results: List of validation results
            filepath: Output file path
            
        Returns:
            True if export successful
        """
        try:
            import csv
            from core.security.path_sanitizer import validate_data_directory
            import os
            
            # Validate output directory
            validate_data_directory(os.path.dirname(filepath))
            
            with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                
                # Write header
                writer.writerow([
                    'Email', 'Valid', 'Format Valid', 'Domain Valid', 
                    'MX Valid', 'Disposable', 'Domain', 'Error Message', 'Confidence Score'
                ])
                
                # Write results
                for result in results:
                    writer.writerow([
                        result.email,
                        result.is_valid,
                        result.is_format_valid,
                        result.is_domain_valid,
                        result.is_mx_valid,
                        result.is_disposable,
                        result.domain,
                        result.error_message,
                        f"{result.confidence_score:.1f}"
                    ])
            
            logger.info(f"Validation report exported to: {filepath}")
            return True
            
        except Exception as e:
            logger.exception(e, f"exporting validation report to {filepath}")
            return False


def validate_email_list(emails: List[str], check_mx: bool = True, 
                       check_disposable: bool = True) -> Tuple[List[str], List[EmailValidationResult]]:
    """
    Convenience function to validate a list of emails.
    
    Args:
        emails: List of email addresses
        check_mx: Whether to check MX records
        check_disposable: Whether to check for disposable domains
        
    Returns:
        Tuple of (valid_emails, all_results)
    """
    validator = EmailValidator(check_mx=check_mx, check_disposable=check_disposable)
    results = validator.validate_bulk(emails)
    valid_emails = validator.filter_valid_emails(results)
    
    return valid_emails, results


def is_valid_email_simple(email: str) -> bool:
    """
    Simple email validation for quick checks.
    
    Args:
        email: Email address
        
    Returns:
        True if email format is valid
    """
    validator = EmailValidator(check_mx=False, check_disposable=False)
    return validator.validate_format(normalize_email(email))