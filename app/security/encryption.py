from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64
from functools import lru_cache
from app.config import get_settings


@lru_cache
def get_fernet() -> Fernet:
    """Get Fernet instance for encryption/decryption."""
    settings = get_settings()
    # Derive a proper key from the encryption key
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=b"medical_app_salt_v1",  # In production, use unique salt per field
        iterations=100000,
    )
    key = base64.urlsafe_b64encode(kdf.derive(settings.encryption_key.encode()))
    return Fernet(key)


def encrypt_data(data: str) -> str:
    """Encrypt sensitive data."""
    if not data:
        return ""
    fernet = get_fernet()
    return fernet.encrypt(data.encode()).decode()


def decrypt_data(encrypted_data: str) -> str:
    """Decrypt sensitive data."""
    if not encrypted_data:
        return ""
    fernet = get_fernet()
    return fernet.decrypt(encrypted_data.encode()).decode()
