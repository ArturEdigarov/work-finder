import base64
import os

import pytest

from app.core.crypto import DecryptionError, FieldCipher, email_lookup_hash
from app.core.env_guard import enforce_no_api_key, sanitized_env


def test_api_key_is_removed_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-should-never-be-used")
    enforce_no_api_key()
    assert "ANTHROPIC_API_KEY" not in os.environ


def test_sanitized_env_for_child_processes() -> None:
    env = sanitized_env({"ANTHROPIC_API_KEY": "x", "PATH": "/bin"})
    assert env == {"PATH": "/bin"}


KEY1 = os.urandom(32)
KEY2 = os.urandom(32)


def test_encrypt_roundtrip_and_randomized() -> None:
    cipher = FieldCipher({1: KEY1})
    a = cipher.encrypt("max@example.com", "users.email")
    b = cipher.encrypt("max@example.com", "users.email")
    assert a != b  # random nonce
    assert "max@" not in a
    assert cipher.decrypt(a, "users.email") == "max@example.com"


def test_tampering_is_detected() -> None:
    cipher = FieldCipher({1: KEY1})
    token = cipher.encrypt("secret", "ctx")
    prefix, payload = token.split(":")
    raw = bytearray(base64.b64decode(payload))
    raw[-1] ^= 1
    with pytest.raises(DecryptionError):
        cipher.decrypt(f"{prefix}:{base64.b64encode(bytes(raw)).decode()}", "ctx")


def test_ciphertext_bound_to_column() -> None:
    cipher = FieldCipher({1: KEY1})
    token = cipher.encrypt("secret", "users.email")
    with pytest.raises(DecryptionError):
        cipher.decrypt(token, "profiles.data")


def test_key_rotation() -> None:
    old = FieldCipher({1: KEY1})
    token_v1 = old.encrypt("secret", "ctx")
    rotated = FieldCipher({1: KEY1, 2: KEY2})
    assert rotated.decrypt(token_v1, "ctx") == "secret"
    assert rotated.encrypt("secret", "ctx").startswith("v2:")


def test_email_hash_is_normalized() -> None:
    assert email_lookup_hash(" Max@Example.com ") == email_lookup_hash("max@example.com")
