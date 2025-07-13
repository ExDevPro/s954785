import os
import re
import sys

# Add project root to path for imports
BASE_PATH = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
if BASE_PATH not in sys.path:
    sys.path.insert(0, BASE_PATH)

# Email validation setup
_email_validator = None
_email_pattern = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')

try:
    from core.validation.email_validator import EmailValidator
    _email_validator = EmailValidator()
except ImportError:
    # Will use regex fallback
    pass

def is_valid_email(address: str) -> bool:
    """
    Return True if the given address is a valid email, False otherwise.
    """
    if not address or not isinstance(address, str):
        return False
    
    if _email_validator:
        try:
            result = _email_validator.validate_email(address)
            return result.is_valid
        except Exception:
            pass
    
    # Fallback to basic regex validation
    return bool(_email_pattern.match(address.strip()))

def replace_placeholders(template: str, data: dict) -> str:
    """
    Replace {placeholder} tokens in the template with values from data.
    Unmatched tokens remain unchanged.
    """
    def _repl(match):
        key = match.group(1)
        return str(data.get(key, match.group(0)))

    pattern = re.compile(r"\{([^}]+)\}")
    return pattern.sub(_repl, template)
