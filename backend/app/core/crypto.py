"""Field-level encryption for personal data (GDPR).

Format of a stored value: ``v<key_id>:<base64(nonce || ciphertext+tag)>``.

* AES-256-GCM: authenticated — any tampering raises ``DecryptionError``.
* Key rotation: several keys can be configured; the highest id encrypts,
  any configured id decrypts. Old rows are re-encrypted lazily on write.
* Associated data (AAD) binds a ciphertext to its column (e.g. ``"users.email"``),
  so an encrypted value cannot be copied into another column and still decrypt.
"""

import base64
import hashlib
import hmac
import os
from functools import lru_cache

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.core.config import get_settings

NONCE_SIZE = 12
KEY_SIZE = 32


class CryptoConfigError(RuntimeError):
    pass


class DecryptionError(ValueError):
    pass


def parse_keys(raw: str) -> dict[int, bytes]:
    keys: dict[int, bytes] = {}
    for part in filter(None, (p.strip() for p in raw.split(","))):
        key_id, _, b64 = part.partition(":")
        if not key_id.isdigit() or not b64:
            raise CryptoConfigError("FIELD_ENCRYPTION_KEYS must look like '1:<base64>,2:<base64>'")
        key = base64.b64decode(b64)
        if len(key) != KEY_SIZE:
            raise CryptoConfigError(f"Encryption key {key_id} must be {KEY_SIZE} bytes")
        keys[int(key_id)] = key
    if not keys:
        raise CryptoConfigError("FIELD_ENCRYPTION_KEYS is empty — run `make keygen`")
    return keys


class FieldCipher:
    def __init__(self, keys: dict[int, bytes]) -> None:
        self._aeads = {key_id: AESGCM(key) for key_id, key in keys.items()}
        self._current_id = max(keys)

    def encrypt(self, plaintext: str, context: str) -> str:
        nonce = os.urandom(NONCE_SIZE)
        ciphertext = self._aeads[self._current_id].encrypt(
            nonce, plaintext.encode(), context.encode()
        )
        return f"v{self._current_id}:" + base64.b64encode(nonce + ciphertext).decode()

    def decrypt(self, token: str, context: str) -> str:
        prefix, _, payload = token.partition(":")
        if not prefix.startswith("v") or not prefix[1:].isdigit():
            raise DecryptionError("Malformed encrypted value")
        aead = self._aeads.get(int(prefix[1:]))
        if aead is None:
            raise DecryptionError(f"Unknown encryption key id {prefix[1:]}")
        raw = base64.b64decode(payload)
        try:
            return aead.decrypt(raw[:NONCE_SIZE], raw[NONCE_SIZE:], context.encode()).decode()
        except InvalidTag as exc:
            raise DecryptionError("Encrypted value failed authentication") from exc


@lru_cache
def get_cipher() -> FieldCipher:
    return FieldCipher(parse_keys(get_settings().field_encryption_keys.get_secret_value()))


def normalize_email(email: str) -> str:
    return email.strip().lower()


def email_lookup_hash(email: str) -> str:
    """Deterministic keyed hash: lets us enforce uniqueness and find users by email
    without storing the email in plaintext."""
    key_b64 = get_settings().email_hash_key.get_secret_value()
    if not key_b64:
        raise CryptoConfigError("EMAIL_HASH_KEY is empty — run `make keygen`")
    key = base64.b64decode(key_b64)
    return hmac.new(key, normalize_email(email).encode(), hashlib.sha256).hexdigest()


def token_hash(token: str) -> str:
    """Hash for high-entropy random tokens (sessions, link tokens). We store only the hash,
    so a database leak does not leak usable session cookies."""
    return hashlib.sha256(token.encode()).hexdigest()
