"""Print fresh secrets for .env: `make keygen`."""

import base64
import os


def main() -> None:
    enc_key = base64.b64encode(os.urandom(32)).decode()
    hash_key = base64.b64encode(os.urandom(32)).decode()
    print(f"FIELD_ENCRYPTION_KEYS=1:{enc_key}")
    print(f"EMAIL_HASH_KEY={hash_key}")


if __name__ == "__main__":
    main()
