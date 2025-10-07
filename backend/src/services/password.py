"""
Password hashing and verification utilities using bcrypt.
"""

import bcrypt


def hash_password(password: str) -> str:
    """
    Hash a password using bcrypt.

    Args:
        password: Plain text password

    Returns:
        Bcrypt password hash
    """
    password_bytes = password.encode("utf-8")
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password_bytes, salt)
    return hashed.decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """
    Verify a password against its hash.

    Args:
        password: Plain text password to verify
        password_hash: Stored bcrypt hash

    Returns:
        True if password matches hash
    """
    password_bytes = password.encode("utf-8")
    hash_bytes = password_hash.encode("utf-8")
    return bcrypt.checkpw(password_bytes, hash_bytes)
