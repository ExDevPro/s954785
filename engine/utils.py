import os
import re
from email_validator import validate_email, EmailNotValidError

BASE_PATH = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))

def is_valid_email(address: str) -> bool:
    """
    Return True if the given address is a valid email, False otherwise.
    """
    try:
        validate_email(address)
        return True
    except EmailNotValidError:
        return False

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
