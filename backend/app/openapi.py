"""Dump the OpenAPI schema for frontend type generation: `make gen-types`."""

import json

from app.main import app

if __name__ == "__main__":
    print(json.dumps(app.openapi(), indent=2))
