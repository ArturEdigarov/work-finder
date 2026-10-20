import base64
import json
from typing import Any

from sqlalchemy import Text
from sqlalchemy.engine import Dialect
from sqlalchemy.types import TypeDecorator

from app.core.crypto import get_cipher


class EncryptedString(TypeDecorator[str]):
    """Transparently encrypts on write and decrypts on read.

    ``context`` is the AAD (usually "<table>.<column>") — it must stay stable
    for the lifetime of the column, otherwise existing rows stop decrypting.
    Encrypted columns cannot be filtered or sorted in SQL; use a separate hash column.
    """

    impl = Text
    cache_ok = True

    def __init__(self, context: str) -> None:
        super().__init__()
        self.context = context

    def process_bind_param(self, value: str | None, dialect: Dialect) -> str | None:
        return None if value is None else get_cipher().encrypt(value, self.context)

    def process_result_value(self, value: str | None, dialect: Dialect) -> str | None:
        return None if value is None else get_cipher().decrypt(value, self.context)


class EncryptedJSON(TypeDecorator[Any]):
    impl = Text
    cache_ok = True

    def __init__(self, context: str) -> None:
        super().__init__()
        self.context = context

    def process_bind_param(self, value: Any, dialect: Dialect) -> str | None:
        if value is None:
            return None
        return get_cipher().encrypt(json.dumps(value, ensure_ascii=False), self.context)

    def process_result_value(self, value: str | None, dialect: Dialect) -> Any:
        return None if value is None else json.loads(get_cipher().decrypt(value, self.context))


class EncryptedBytes(TypeDecorator[bytes]):
    """Binary payloads (uploaded files). Stored as encrypted base64 text."""

    impl = Text
    cache_ok = True

    def __init__(self, context: str) -> None:
        super().__init__()
        self.context = context

    def process_bind_param(self, value: bytes | None, dialect: Dialect) -> str | None:
        if value is None:
            return None
        return get_cipher().encrypt(base64.b64encode(value).decode(), self.context)

    def process_result_value(self, value: str | None, dialect: Dialect) -> bytes | None:
        return (
            None if value is None else base64.b64decode(get_cipher().decrypt(value, self.context))
        )
