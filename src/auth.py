"""
Authentication utilities for Milestone 4.

Password hashing uses bcrypt. Never store plaintext passwords.
"""
from __future__ import annotations

import bcrypt


def hash_password(password: str) -> str:
    """
    Hash a password using bcrypt.

    INVARIANT: The result is always a bcrypt hash, never plaintext.
    This function is the ONLY way to create password_hash values.

    Args:
        password: Plaintext password from user input

    Returns:
        Bcrypt hash string (safe to store in database)
    """
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """
    Verify a password against a bcrypt hash.

    Args:
        password: Plaintext password from user input
        password_hash: Bcrypt hash from database

    Returns:
        True if password matches, False otherwise
    """
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except (ValueError, TypeError):
        # Invalid hash format
        return False
