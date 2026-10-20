"""Hard rule: the service never uses a paid Anthropic API key.

LLM calls go through Claude Code on the owner's subscription. If ANTHROPIC_API_KEY
is present, Claude Code would silently switch to pay-as-you-go billing, so every
entrypoint calls `enforce_no_api_key()` before doing anything else.
"""

import logging
import os

FORBIDDEN_ENV_VARS = ("ANTHROPIC_API_KEY",)

logger = logging.getLogger(__name__)


def enforce_no_api_key() -> None:
    for name in FORBIDDEN_ENV_VARS:
        if name in os.environ:
            del os.environ[name]
            logger.warning("%s was set and has been removed: subscription-only mode", name)


def sanitized_env(base: dict[str, str] | None = None) -> dict[str, str]:
    """Environment for child processes (e.g. `claude -p`) without forbidden variables."""
    env = dict(os.environ if base is None else base)
    for name in FORBIDDEN_ENV_VARS:
        env.pop(name, None)
    return env
