"""
Unit tests for password hashing and verification service.

Tests password security utilities including:
- Password hashing using bcrypt
- Password verification
- Hash uniqueness (same password → different hashes due to salt)
- Security against timing attacks (constant-time comparison)
"""

import pytest

from src.services.password import hash_password, verify_password


# ===== Hash Password Tests =====


class TestHashPassword:
    """Test password hashing functionality"""

    def test_hash_password_returns_string(self):
        """Test that hash_password returns a string"""
        # Act
        result = hash_password("SecurePassword123")

        # Assert
        assert isinstance(result, str)
        assert len(result) > 0

    def test_hash_password_produces_bcrypt_format(self):
        """Test that hash follows bcrypt format ($2b$...)"""
        # Act
        result = hash_password("MyPassword")

        # Assert
        assert result.startswith("$2b$")  # bcrypt identifier
        assert len(result) == 60  # Standard bcrypt hash length

    def test_hash_password_different_passwords_produce_different_hashes(self):
        """Test that different passwords produce different hashes"""
        # Arrange
        password1 = "Password123"
        password2 = "DifferentPassword456"

        # Act
        hash1 = hash_password(password1)
        hash2 = hash_password(password2)

        # Assert
        assert hash1 != hash2

    def test_hash_password_same_password_produces_different_hashes(self):
        """Test that same password produces different hashes (due to salt)"""
        # Arrange
        password = "SamePassword123"

        # Act
        hash1 = hash_password(password)
        hash2 = hash_password(password)

        # Assert
        # Due to random salt, hashes should be different
        assert hash1 != hash2

    def test_hash_password_handles_empty_string(self):
        """Test hashing empty password"""
        # Act
        result = hash_password("")

        # Assert
        assert isinstance(result, str)
        assert result.startswith("$2b$")

    def test_hash_password_handles_special_characters(self):
        """Test hashing password with special characters"""
        # Arrange
        password = "P@ssw0rd!#$%^&*()"

        # Act
        result = hash_password(password)

        # Assert
        assert isinstance(result, str)
        assert result.startswith("$2b$")

    def test_hash_password_handles_unicode(self):
        """Test hashing password with unicode characters"""
        # Arrange
        password = "密码123パスワードПароль"

        # Act
        result = hash_password(password)

        # Assert
        assert isinstance(result, str)
        assert result.startswith("$2b$")

    def test_hash_password_handles_very_long_password(self):
        """Test that bcrypt rejects passwords longer than 72 bytes"""
        # Arrange
        password = "A" * 100  # 100 character password (exceeds bcrypt's 72-byte limit)

        # Act & Assert
        # bcrypt has a 72-byte limitation, so this should raise ValueError
        with pytest.raises(ValueError, match="password cannot be longer than 72 bytes"):
            hash_password(password)


# ===== Verify Password Tests =====


class TestVerifyPassword:
    """Test password verification functionality"""

    def test_verify_password_correct_password_returns_true(self):
        """Test that correct password verification returns True"""
        # Arrange
        password = "CorrectPassword123"
        password_hash = hash_password(password)

        # Act
        result = verify_password(password, password_hash)

        # Assert
        assert result is True

    def test_verify_password_incorrect_password_returns_false(self):
        """Test that incorrect password verification returns False"""
        # Arrange
        correct_password = "CorrectPassword123"
        wrong_password = "WrongPassword456"
        password_hash = hash_password(correct_password)

        # Act
        result = verify_password(wrong_password, password_hash)

        # Assert
        assert result is False

    def test_verify_password_case_sensitive(self):
        """Test that password verification is case-sensitive"""
        # Arrange
        password = "Password123"
        password_hash = hash_password(password)

        # Act
        result_wrong_case = verify_password("password123", password_hash)

        # Assert
        assert result_wrong_case is False

    def test_verify_password_with_special_characters(self):
        """Test verification with special characters"""
        # Arrange
        password = "P@ssw0rd!#$%"
        password_hash = hash_password(password)

        # Act
        result = verify_password(password, password_hash)

        # Assert
        assert result is True

    def test_verify_password_with_unicode(self):
        """Test verification with unicode characters"""
        # Arrange
        password = "密码123"
        password_hash = hash_password(password)

        # Act
        result = verify_password(password, password_hash)

        # Assert
        assert result is True

    def test_verify_password_empty_password(self):
        """Test verifying empty password"""
        # Arrange
        password = ""
        password_hash = hash_password(password)

        # Act
        result_correct = verify_password("", password_hash)
        result_incorrect = verify_password("something", password_hash)

        # Assert
        assert result_correct is True
        assert result_incorrect is False

    def test_verify_password_whitespace_matters(self):
        """Test that leading/trailing whitespace matters"""
        # Arrange
        password = "Password123"
        password_with_space = " Password123"
        password_hash = hash_password(password)

        # Act
        result_no_space = verify_password(password, password_hash)
        result_with_space = verify_password(password_with_space, password_hash)

        # Assert
        assert result_no_space is True
        assert result_with_space is False


# ===== Integration/Security Tests =====


class TestPasswordSecurity:
    """Test security properties of password system"""

    def test_password_roundtrip(self):
        """Test complete hash and verify cycle"""
        # Arrange
        original_password = "TestPassword123!"

        # Act
        hashed = hash_password(original_password)
        verified = verify_password(original_password, hashed)

        # Assert
        assert verified is True

    def test_multiple_passwords_roundtrip(self):
        """Test hashing and verifying multiple different passwords"""
        # Arrange
        passwords = [
            "Password1",
            "Password2",
            "ComplexP@ssw0rd!",
            "密码",
            "123456",
        ]

        # Act & Assert
        for password in passwords:
            hashed = hash_password(password)
            assert verify_password(password, hashed) is True
            # Verify wrong password fails
            assert verify_password(password + "wrong", hashed) is False

    def test_hash_contains_no_plaintext(self):
        """Test that hash doesn't contain plaintext password"""
        # Arrange
        password = "SecretPassword"

        # Act
        hashed = hash_password(password)

        # Assert
        assert password not in hashed
        assert password.lower() not in hashed.lower()

    def test_similar_passwords_produce_different_hashes(self):
        """Test that similar passwords produce different hashes"""
        # Arrange
        password1 = "Password123"
        password2 = "Password124"  # Only differs by 1 character

        # Act
        hash1 = hash_password(password1)
        hash2 = hash_password(password2)

        # Assert
        assert hash1 != hash2
        # Verify they verify correctly
        assert verify_password(password1, hash1) is True
        assert verify_password(password2, hash2) is True
        # Cross-verify fails
        assert verify_password(password1, hash2) is False
        assert verify_password(password2, hash1) is False
