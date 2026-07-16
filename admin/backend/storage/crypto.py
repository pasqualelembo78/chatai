"""Encryption utilities for sensitive data."""

import os
import base64
import hashlib
import logging

logger = logging.getLogger(__name__)


def _get_master_key():
    key = os.environ.get("MASTER_KEY", "")
    if not key:
        logger.warning("MASTER_KEY not set, using derived key (INSECURE)")
        key = hashlib.sha256(b"chatai-insecure-fallback-key").hexdigest()
    return key[:64]


def encrypt_value(plaintext):
    if not plaintext:
        return ""
    try:
        from cryptography.fernet import Fernet
        master = _get_master_key()
        fernet_key = base64.urlsafe_b64encode(hashlib.sha256(master.encode()).digest())
        cipher = Fernet(fernet_key)
        return cipher.encrypt(plaintext.encode()).decode()
    except ImportError:
        logger.warning("cryptography not installed, storing in plaintext")
        return plaintext
    except Exception as e:
        logger.error(f"Encryption failed: {e}")
        return ""


def decrypt_value(ciphertext):
    if not ciphertext:
        return ""
    try:
        from cryptography.fernet import Fernet, InvalidToken
        master = _get_master_key()
        fernet_key = base64.urlsafe_b64encode(hashlib.sha256(master.encode()).digest())
        cipher = Fernet(fernet_key)
        return cipher.decrypt(ciphertext.encode()).decode()
    except ImportError:
        return ciphertext
    except (InvalidToken, Exception) as e:
        logger.error(f"Decryption failed: {e}")
        return ""
