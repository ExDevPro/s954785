"""
Encryption utilities for Bulk Email Sender.

This module provides encryption and decryption functionality for:
- Credential encryption
- Secure data storage
- Configuration protection
"""

import os
import base64
import hashlib
from typing import Optional, Union
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from core.utils.logger import get_module_logger
from core.utils.exceptions import EncryptionError

logger = get_module_logger(__name__)


class EncryptionManager:
    """Manages encryption and decryption operations."""
    
    def __init__(self, password: Optional[str] = None, salt: Optional[bytes] = None):
        """
        Initialize encryption manager.
        
        Args:
            password: Master password for encryption
            salt: Salt for key derivation (generated if not provided)
        """
        self._cipher: Optional[Fernet] = None
        self._password = password
        self._salt = salt or self._generate_salt()
        
        if password:
            self._initialize_cipher(password)
    
    def _generate_salt(self) -> bytes:
        """Generate a random salt for key derivation."""
        return os.urandom(16)
    
    def _derive_key(self, password: str, salt: bytes) -> bytes:
        """
        Derive encryption key from password and salt.
        
        Args:
            password: Master password
            salt: Salt bytes
            
        Returns:
            Derived key bytes
        """
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        return base64.urlsafe_b64encode(kdf.derive(password.encode()))
    
    def _initialize_cipher(self, password: str) -> None:
        """
        Initialize the cipher with derived key.
        
        Args:
            password: Master password
        """
        try:
            key = self._derive_key(password, self._salt)
            self._cipher = Fernet(key)
            logger.debug("Encryption cipher initialized successfully")
        except Exception as e:
            raise EncryptionError(f"Failed to initialize encryption cipher: {e}")
    
    def set_password(self, password: str) -> None:
        """
        Set or change the master password.
        
        Args:
            password: New master password
        """
        self._password = password
        self._initialize_cipher(password)
    
    def encrypt_string(self, plaintext: str) -> str:
        """
        Encrypt a string and return base64-encoded result.
        
        Args:
            plaintext: String to encrypt
            
        Returns:
            Base64-encoded encrypted string
            
        Raises:
            EncryptionError: If encryption fails
        """
        if not self._cipher:
            raise EncryptionError("Encryption not initialized - password required")
        
        try:
            encrypted_bytes = self._cipher.encrypt(plaintext.encode('utf-8'))
            return base64.urlsafe_b64encode(encrypted_bytes).decode('utf-8')
        except Exception as e:
            raise EncryptionError(f"Failed to encrypt string: {e}")
    
    def decrypt_string(self, encrypted_text: str) -> str:
        """
        Decrypt a base64-encoded encrypted string.
        
        Args:
            encrypted_text: Base64-encoded encrypted string
            
        Returns:
            Decrypted plaintext string
            
        Raises:
            EncryptionError: If decryption fails
        """
        if not self._cipher:
            raise EncryptionError("Encryption not initialized - password required")
        
        try:
            encrypted_bytes = base64.urlsafe_b64decode(encrypted_text.encode('utf-8'))
            decrypted_bytes = self._cipher.decrypt(encrypted_bytes)
            return decrypted_bytes.decode('utf-8')
        except Exception as e:
            raise EncryptionError(f"Failed to decrypt string: {e}", operation="decryption")
    
    def encrypt_bytes(self, data: bytes) -> bytes:
        """
        Encrypt bytes data.
        
        Args:
            data: Bytes to encrypt
            
        Returns:
            Encrypted bytes
            
        Raises:
            EncryptionError: If encryption fails
        """
        if not self._cipher:
            raise EncryptionError("Encryption not initialized - password required")
        
        try:
            return self._cipher.encrypt(data)
        except Exception as e:
            raise EncryptionError(f"Failed to encrypt bytes: {e}")
    
    def decrypt_bytes(self, encrypted_data: bytes) -> bytes:
        """
        Decrypt bytes data.
        
        Args:
            encrypted_data: Encrypted bytes
            
        Returns:
            Decrypted bytes
            
        Raises:
            EncryptionError: If decryption fails
        """
        if not self._cipher:
            raise EncryptionError("Encryption not initialized - password required")
        
        try:
            return self._cipher.decrypt(encrypted_data)
        except Exception as e:
            raise EncryptionError(f"Failed to decrypt bytes: {e}", operation="decryption")
    
    def encrypt_file(self, input_path: str, output_path: str) -> None:
        """
        Encrypt a file.
        
        Args:
            input_path: Path to input file
            output_path: Path to output encrypted file
            
        Raises:
            EncryptionError: If file encryption fails
        """
        try:
            with open(input_path, 'rb') as infile:
                data = infile.read()
            
            encrypted_data = self.encrypt_bytes(data)
            
            with open(output_path, 'wb') as outfile:
                # Write salt first, then encrypted data
                outfile.write(len(self._salt).to_bytes(4, 'big'))
                outfile.write(self._salt)
                outfile.write(encrypted_data)
            
            logger.info(f"File encrypted successfully: {input_path} -> {output_path}")
            
        except Exception as e:
            raise EncryptionError(f"Failed to encrypt file {input_path}: {e}")
    
    def decrypt_file(self, input_path: str, output_path: str) -> None:
        """
        Decrypt a file.
        
        Args:
            input_path: Path to encrypted file
            output_path: Path to output decrypted file
            
        Raises:
            EncryptionError: If file decryption fails
        """
        try:
            with open(input_path, 'rb') as infile:
                # Read salt length and salt
                salt_length = int.from_bytes(infile.read(4), 'big')
                salt = infile.read(salt_length)
                encrypted_data = infile.read()
            
            # Create temporary cipher with file's salt
            old_salt = self._salt
            self._salt = salt
            self._initialize_cipher(self._password)
            
            try:
                decrypted_data = self.decrypt_bytes(encrypted_data)
            finally:
                # Restore original salt
                self._salt = old_salt
                self._initialize_cipher(self._password)
            
            with open(output_path, 'wb') as outfile:
                outfile.write(decrypted_data)
            
            logger.info(f"File decrypted successfully: {input_path} -> {output_path}")
            
        except Exception as e:
            raise EncryptionError(f"Failed to decrypt file {input_path}: {e}", operation="decryption")
    
    def get_salt_b64(self) -> str:
        """Get base64-encoded salt for storage."""
        return base64.urlsafe_b64encode(self._salt).decode('utf-8')
    
    def set_salt_b64(self, salt_b64: str) -> None:
        """
        Set salt from base64-encoded string.
        
        Args:
            salt_b64: Base64-encoded salt
        """
        self._salt = base64.urlsafe_b64decode(salt_b64.encode('utf-8'))
        if self._password:
            self._initialize_cipher(self._password)
    
    def verify_password(self, password: str) -> bool:
        """
        Verify if password is correct by testing encryption/decryption.
        
        Args:
            password: Password to verify
            
        Returns:
            True if password is correct, False otherwise
        """
        try:
            test_text = "verification_test"
            temp_manager = EncryptionManager(password, self._salt)
            encrypted = temp_manager.encrypt_string(test_text)
            decrypted = temp_manager.decrypt_string(encrypted)
            return decrypted == test_text
        except Exception:
            return False


class CredentialManager:
    """Manages encrypted credential storage."""
    
    def __init__(self, encryption_manager: EncryptionManager):
        """
        Initialize credential manager.
        
        Args:
            encryption_manager: Encryption manager instance
        """
        self.encryption = encryption_manager
        self._credentials = {}
    
    def store_credential(self, key: str, value: str) -> None:
        """
        Store an encrypted credential.
        
        Args:
            key: Credential identifier
            value: Credential value to encrypt
        """
        try:
            encrypted_value = self.encryption.encrypt_string(value)
            self._credentials[key] = encrypted_value
            logger.debug(f"Credential stored: {key}")
        except Exception as e:
            logger.error(f"Failed to store credential {key}: {e}")
            raise
    
    def get_credential(self, key: str) -> Optional[str]:
        """
        Retrieve and decrypt a credential.
        
        Args:
            key: Credential identifier
            
        Returns:
            Decrypted credential value or None if not found
        """
        if key not in self._credentials:
            return None
        
        try:
            encrypted_value = self._credentials[key]
            return self.encryption.decrypt_string(encrypted_value)
        except Exception as e:
            logger.error(f"Failed to retrieve credential {key}: {e}")
            return None
    
    def remove_credential(self, key: str) -> bool:
        """
        Remove a stored credential.
        
        Args:
            key: Credential identifier
            
        Returns:
            True if removed, False if not found
        """
        if key in self._credentials:
            del self._credentials[key]
            logger.debug(f"Credential removed: {key}")
            return True
        return False
    
    def list_credentials(self) -> list[str]:
        """Get list of stored credential keys."""
        return list(self._credentials.keys())
    
    def export_encrypted(self) -> dict[str, str]:
        """Export all encrypted credentials."""
        return self._credentials.copy()
    
    def import_encrypted(self, credentials: dict[str, str]) -> None:
        """
        Import encrypted credentials.
        
        Args:
            credentials: Dictionary of encrypted credentials
        """
        self._credentials.update(credentials)
        logger.info(f"Imported {len(credentials)} credentials")


def generate_password_hash(password: str, salt: Optional[bytes] = None) -> tuple[str, str]:
    """
    Generate a hash of the password for verification purposes.
    
    Args:
        password: Password to hash
        salt: Optional salt (generated if not provided)
        
    Returns:
        Tuple of (hash, salt) as base64 strings
    """
    if salt is None:
        salt = os.urandom(32)
    
    pwdhash = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000)
    
    hash_b64 = base64.urlsafe_b64encode(pwdhash).decode('utf-8')
    salt_b64 = base64.urlsafe_b64encode(salt).decode('utf-8')
    
    return hash_b64, salt_b64


def verify_password_hash(password: str, stored_hash: str, stored_salt: str) -> bool:
    """
    Verify password against stored hash.
    
    Args:
        password: Password to verify
        stored_hash: Stored password hash (base64)
        stored_salt: Stored salt (base64)
        
    Returns:
        True if password matches, False otherwise
    """
    try:
        salt = base64.urlsafe_b64decode(stored_salt.encode('utf-8'))
        hash_b64, _ = generate_password_hash(password, salt)
        return hash_b64 == stored_hash
    except Exception:
        return False


def generate_random_password(length: int = 16, include_symbols: bool = True) -> str:
    """
    Generate a random password.
    
    Args:
        length: Password length
        include_symbols: Include symbol characters
        
    Returns:
        Random password string
    """
    import secrets
    import string
    
    alphabet = string.ascii_letters + string.digits
    if include_symbols:
        alphabet += "!@#$%^&*"
    
    return ''.join(secrets.choice(alphabet) for _ in range(length))


# Global encryption manager instance
_encryption_manager: Optional[EncryptionManager] = None


def get_encryption_manager() -> Optional[EncryptionManager]:
    """Get global encryption manager instance."""
    return _encryption_manager


def init_encryption(password: str, salt: Optional[str] = None) -> EncryptionManager:
    """
    Initialize global encryption manager.
    
    Args:
        password: Master password
        salt: Optional base64-encoded salt
        
    Returns:
        EncryptionManager instance
    """
    global _encryption_manager
    
    salt_bytes = None
    if salt:
        salt_bytes = base64.urlsafe_b64decode(salt.encode('utf-8'))
    
    _encryption_manager = EncryptionManager(password, salt_bytes)
    logger.info("Global encryption manager initialized")
    return _encryption_manager