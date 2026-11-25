"""Password hashing with argon2id (argon2-cffi defaults)."""
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

_hasher = PasswordHasher()


def hash_password(plaintext: str) -> str:
    return _hasher.hash(plaintext)


def verify_password(plaintext: str, password_hash: str) -> bool:
    """True only for a matching password. Never raises on bad input or a malformed hash."""
    try:
        return _hasher.verify(password_hash, plaintext)
    except (VerificationError, InvalidHashError):
        return False
