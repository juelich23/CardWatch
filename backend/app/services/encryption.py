"""
AES-256 encryption service for sensitive credential storage
"""
import os
import base64
from hashlib import sha256
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
from app.config import get_settings


class EncryptionService:
    """AES-256-CBC encryption service for sensitive credential storage"""

    def __init__(self):
        settings = get_settings()
        # Derive 32-byte key from secret_key using SHA-256
        # In production, use a dedicated ENCRYPTION_KEY env var
        self.key = self._derive_key(settings.secret_key)

    def _derive_key(self, secret: str) -> bytes:
        """Derive 32-byte AES key from secret"""
        return sha256(secret.encode()).digest()

    def encrypt(self, plaintext: str) -> tuple[str, str]:
        """
        Encrypt plaintext using AES-256-CBC

        Returns:
            tuple of (encrypted_data_base64, iv_base64)
        """
        iv = os.urandom(16)
        cipher = Cipher(algorithms.AES(self.key), modes.CBC(iv), backend=default_backend())
        encryptor = cipher.encryptor()

        # PKCS7 padding
        data = plaintext.encode('utf-8')
        padding_length = 16 - (len(data) % 16)
        padded_data = data + bytes([padding_length] * padding_length)

        encrypted = encryptor.update(padded_data) + encryptor.finalize()

        return base64.b64encode(encrypted).decode('ascii'), base64.b64encode(iv).decode('ascii')

    def decrypt(self, encrypted_b64: str, iv_b64: str) -> str:
        """
        Decrypt AES-256-CBC encrypted data

        Args:
            encrypted_b64: Base64-encoded encrypted data
            iv_b64: Base64-encoded initialization vector

        Returns:
            Decrypted plaintext
        """
        encrypted = base64.b64decode(encrypted_b64)
        iv = base64.b64decode(iv_b64)

        cipher = Cipher(algorithms.AES(self.key), modes.CBC(iv), backend=default_backend())
        decryptor = cipher.decryptor()

        padded_data = decryptor.update(encrypted) + decryptor.finalize()

        # Remove PKCS7 padding
        padding_length = padded_data[-1]
        return padded_data[:-padding_length].decode('utf-8')


# Singleton instance
_encryption_service = None


def get_encryption_service() -> EncryptionService:
    """Get or create the singleton EncryptionService instance"""
    global _encryption_service
    if _encryption_service is None:
        _encryption_service = EncryptionService()
    return _encryption_service
