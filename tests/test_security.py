"""Unit tests for security functions."""
from datetime import datetime, timedelta
import pytest
from app.security.password import (
    hash_password,
    verify_password,
    validate_password_strength,
    generate_secure_token,
)
from app.security.encryption import encrypt_data, decrypt_data
from app.security.jwt import create_access_token, create_refresh_token, verify_token


class TestPasswordHashing:
    """Tests for password hashing functions."""
    
    def test_hash_password_returns_string(self):
        """Hash should return a string."""
        hashed = hash_password("TestPassword123!")
        assert isinstance(hashed, str)
        assert len(hashed) > 0
    
    def test_hash_password_different_each_time(self):
        """Same password should produce different hashes (salt)."""
        hash1 = hash_password("TestPassword123!")
        hash2 = hash_password("TestPassword123!")
        assert hash1 != hash2
    
    def test_verify_password_correct(self):
        """Correct password should verify."""
        password = "TestPassword123!"
        hashed = hash_password(password)
        assert verify_password(password, hashed) is True
    
    def test_verify_password_incorrect(self):
        """Incorrect password should not verify."""
        hashed = hash_password("TestPassword123!")
        assert verify_password("WrongPassword123!", hashed) is False
    
    def test_verify_password_empty(self):
        """Empty password should not verify."""
        hashed = hash_password("TestPassword123!")
        assert verify_password("", hashed) is False


class TestPasswordValidation:
    """Tests for password strength validation."""
    
    def test_valid_password(self):
        """Valid password should pass."""
        is_valid, error = validate_password_strength("SecurePass123!")
        assert is_valid is True
        assert error == ""
    
    def test_too_short(self):
        """Short password should fail."""
        is_valid, error = validate_password_strength("Short1!")
        assert is_valid is False
        assert "12 characters" in error
    
    def test_no_uppercase(self):
        """Password without uppercase should fail."""
        is_valid, error = validate_password_strength("securepass123!")
        assert is_valid is False
        assert "uppercase" in error
    
    def test_no_lowercase(self):
        """Password without lowercase should fail."""
        is_valid, error = validate_password_strength("SECUREPASS123!")
        assert is_valid is False
        assert "lowercase" in error
    
    def test_no_digit(self):
        """Password without digit should fail."""
        is_valid, error = validate_password_strength("SecurePassword!")
        assert is_valid is False
        assert "digit" in error
    
    def test_no_special_char(self):
        """Password without special char should fail."""
        is_valid, error = validate_password_strength("SecurePass1234")
        assert is_valid is False
        assert "special" in error
    
    def test_common_pattern(self):
        """Password with common pattern should fail."""
        is_valid, error = validate_password_strength("Password1234!")
        assert is_valid is False
        assert "common" in error


class TestSecureToken:
    """Tests for secure token generation."""
    
    def test_token_length(self):
        """Token should have expected length."""
        token = generate_secure_token(32)
        assert len(token) > 0
    
    def test_token_unique(self):
        """Each token should be unique."""
        tokens = [generate_secure_token(32) for _ in range(100)]
        assert len(set(tokens)) == 100


class TestEncryption:
    """Tests for data encryption."""
    
    def test_encrypt_decrypt_roundtrip(self):
        """Data should survive encrypt/decrypt cycle."""
        original = "Sensitive patient data"
        encrypted = encrypt_data(original)
        decrypted = decrypt_data(encrypted)
        assert decrypted == original
    
    def test_encrypted_different_from_original(self):
        """Encrypted data should differ from original."""
        original = "Sensitive patient data"
        encrypted = encrypt_data(original)
        assert encrypted != original
    
    def test_empty_string(self):
        """Empty string should work."""
        encrypted = encrypt_data("")
        decrypted = decrypt_data(encrypted)
        assert decrypted == ""
    
    def test_unicode_data(self):
        """Unicode data should work."""
        original = "患者データ 🏥"
        encrypted = encrypt_data(original)
        decrypted = decrypt_data(encrypted)
        assert decrypted == original


class TestJWT:
    """Tests for JWT token functions."""
    
    def test_create_access_token(self):
        """Access token should be created."""
        token = create_access_token("user-123", "patient")
        assert isinstance(token, str)
        assert len(token) > 0
    
    def test_create_refresh_token(self):
        """Refresh token should be created."""
        token = create_refresh_token("user-123", "patient")
        assert isinstance(token, str)
        assert len(token) > 0
    
    def test_verify_access_token(self):
        """Valid access token should verify."""
        token = create_access_token("user-123", "patient")
        data = verify_token(token, expected_type="access")
        assert data is not None
        assert data.user_id == "user-123"
        assert data.role == "patient"
    
    def test_verify_refresh_token(self):
        """Valid refresh token should verify."""
        token = create_refresh_token("user-123", "doctor")
        data = verify_token(token, expected_type="refresh")
        assert data is not None
        assert data.user_id == "user-123"
        assert data.role == "doctor"
    
    def test_wrong_token_type(self):
        """Token with wrong type should not verify."""
        token = create_access_token("user-123", "patient")
        data = verify_token(token, expected_type="refresh")
        assert data is None

    def test_reject_token_wrong_algorithm(self):
        """Token signed with an unexpected algorithm should be rejected.

        Regression test for the algorithm-confusion class of JWT
        vulnerabilities (e.g. CVE-2024-33663 in python-jose <=3.3.0):
        verify_token() must not accept a token just because it decodes
        successfully — it must also reject tokens signed with an
        algorithm other than the one configured for this app.
        """
        from jose import jwt as jose_jwt
        from app.config import get_settings

        settings = get_settings()
        payload = {
            "sub": "user-123",
            "role": "patient",
            "type": "access",
            "exp": datetime.utcnow() + timedelta(minutes=5),
            "iat": datetime.utcnow(),
        }
        forged_token = jose_jwt.encode(payload, settings.secret_key, algorithm="HS512")

        data = verify_token(forged_token, expected_type="access")
        assert data is None
    
    def test_invalid_token(self):
        """Invalid token should not verify."""
        data = verify_token("invalid.token.here", expected_type="access")
        assert data is None
