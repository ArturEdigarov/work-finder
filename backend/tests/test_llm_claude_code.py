"""ClaudeCodeSubscriptionProvider against a fake `claude` binary — never spends the subscription."""

import json
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pytest
from pydantic import BaseModel

from app.core.config import Settings
from app.llm.claude_code import ClaudeCodeSubscriptionProvider, parse_reset_at
from app.llm.provider import (
    LLMAuthError,
    LLMInvalidOutput,
    LLMKind,
    LLMRateLimited,
    LLMRequest,
    LLMUnavailable,
)

FAKE_CLAUDE = f"""#!{sys.executable}
import json, os, sys, time
state = os.environ["FAKE_CLAUDE_DIR"]
steps = json.load(open(os.path.join(state, "steps.json")))
calls = os.path.join(state, "calls")
n = len(os.listdir(calls))
step = steps[min(n, len(steps) - 1)]
with open(os.path.join(calls, f"{{n}}.json"), "w") as f:
    json.dump({{"argv": sys.argv[1:], "env": dict(os.environ), "cwd": os.getcwd(),
               "cwd_files": os.listdir("."), "stdin": sys.stdin.read()}}, f)
time.sleep(step.get("sleep", 0))
sys.stdout.write(step.get("stdout", ""))
sys.stderr.write(step.get("stderr", ""))
sys.exit(step.get("exit", 0))
"""


Berlin = ZoneInfo("Europe/Berlin")


class Answer(BaseModel):
    ok: bool
    word: str


def envelope(structured: Any = None, **overrides: Any) -> str:
    """Shape copied from a real `claude -p --output-format json --json-schema` response."""
    data: dict[str, Any] = {
        "type": "result",
        "subtype": "success",
        "is_error": False,
        "api_error_status": None,
        "result": json.dumps(structured),
        "structured_output": structured,
        "usage": {"input_tokens": 2, "output_tokens": 74, "cache_read_input_tokens": 0},
        "modelUsage": {
            "claude-haiku-4-5": {"outputTokens": 18},
            "claude-sonnet-5": {"outputTokens": 74},
        },
    }
    data.update(overrides)
    return json.dumps(data)


class FakeClaude:
    def __init__(self, root: Path) -> None:
        self.root = root
        (root / "calls").mkdir()
        self.bin = root / "claude"
        self.bin.write_text(FAKE_CLAUDE)
        self.bin.chmod(0o755)

    def steps(self, *steps: dict[str, Any]) -> None:
        (self.root / "steps.json").write_text(json.dumps(steps))

    def calls(self) -> list[dict[str, Any]]:
        files = sorted((self.root / "calls").iterdir(), key=lambda p: int(p.stem))
        return [json.loads(p.read_text()) for p in files]


@pytest.fixture
def fake(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> FakeClaude:
    monkeypatch.setenv("FAKE_CLAUDE_DIR", str(tmp_path))
    return FakeClaude(tmp_path)


def provider(fake: FakeClaude, **settings: Any) -> ClaudeCodeSubscriptionProvider:
    return ClaudeCodeSubscriptionProvider(Settings(claude_bin=str(fake.bin), **settings))


def request(prompt: str = "CV: Max Mustermann, Koch") -> LLMRequest[Answer]:
    return LLMRequest(
        kind=LLMKind.SCORE, user_id=uuid.uuid4(), system="You are a JSON API.", prompt=prompt,
        output=Answer,
    )  # fmt: skip


async def test_success(fake: FakeClaude, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-must-not-leak")
    monkeypatch.setenv("CLAUDECODE", "1")
    fake.steps({"stdout": envelope({"ok": True, "word": "pong"})})

    result = await provider(fake).complete(request())

    assert result.data == Answer(ok=True, word="pong")
    assert result.provider == "claude_code"
    assert result.model == "claude-sonnet-5"
    assert result.usage == {"input_tokens": 2, "output_tokens": 74, "cache_read_input_tokens": 0}

    [call] = fake.calls()
    argv = call["argv"]
    assert argv[:3] == ["-p", "--output-format", "json"]
    assert argv[argv.index("--model") + 1] == "sonnet"
    assert argv[argv.index("--tools") + 1] == ""
    assert argv[argv.index("--setting-sources") + 1] == ""
    assert "--no-session-persistence" in argv and "--strict-mcp-config" in argv
    assert "--bare" not in argv  # --bare authenticates with an API key only
    assert json.loads(argv[argv.index("--json-schema") + 1])["required"] == ["ok", "word"]
    # personal data goes through stdin, never argv
    assert call["stdin"] == "CV: Max Mustermann, Koch"
    assert not any("Mustermann" in a for a in argv)
    # no API key, no parent session, empty working directory
    assert "ANTHROPIC_API_KEY" not in call["env"]
    assert "CLAUDECODE" not in call["env"]
    assert call["cwd_files"] == []
    assert "ws-llm-" in call["cwd"]


async def test_invalid_output_is_retried_once(fake: FakeClaude) -> None:
    fake.steps(
        {"stdout": envelope({"ok": "maybe"})},
        {"stdout": envelope({"ok": False, "word": "second"})},
    )
    result = await provider(fake).complete(request())
    assert result.data.word == "second"
    assert len(fake.calls()) == 2


async def test_invalid_output_twice_fails(fake: FakeClaude) -> None:
    fake.steps({"stdout": envelope({"nope": 1})})
    with pytest.raises(LLMInvalidOutput):
        await provider(fake).complete(request())
    assert len(fake.calls()) == 2


async def test_falls_back_to_text_result(fake: FakeClaude) -> None:
    fake.steps({"stdout": envelope(None, result='{"ok": true, "word": "text"}')})
    result = await provider(fake).complete(request())
    assert result.data.word == "text"


async def test_rate_limit_from_envelope(fake: FakeClaude) -> None:
    fake.steps(
        {
            "stdout": envelope(
                None,
                is_error=True,
                api_error_status=429,
                result="You've hit your limit · resets 3pm (Europe/Berlin)",
            ),
            "exit": 1,
        }
    )
    with pytest.raises(LLMRateLimited) as exc:
        await provider(fake).complete(request())
    assert exc.value.reset_at is not None
    assert exc.value.reset_at.astimezone(Berlin).hour == 15
    assert len(fake.calls()) == 1  # a limit is never retried


async def test_rate_limit_from_plain_text(fake: FakeClaude) -> None:
    fake.steps({"stdout": "Claude AI usage limit reached|1760961600", "exit": 1})
    with pytest.raises(LLMRateLimited) as exc:
        await provider(fake).complete(request())
    assert exc.value.reset_at == datetime.fromtimestamp(1760961600, UTC)


async def test_auth_error(fake: FakeClaude) -> None:
    fake.steps({"stderr": "Not logged in · Please run /login", "exit": 1})
    with pytest.raises(LLMAuthError):
        await provider(fake).complete(request())


async def test_unknown_error_is_transient(fake: FakeClaude) -> None:
    fake.steps({"stdout": envelope(None, is_error=True, result="Overloaded"), "exit": 1})
    with pytest.raises(LLMUnavailable):
        await provider(fake).complete(request())


async def test_timeout(fake: FakeClaude) -> None:
    fake.steps({"sleep": 5})
    with pytest.raises(LLMUnavailable, match="timed out"):
        await provider(fake, llm_timeout_seconds=1).complete(request())


async def test_missing_binary(tmp_path: Path) -> None:
    p = ClaudeCodeSubscriptionProvider(Settings(claude_bin=str(tmp_path / "nope")))
    with pytest.raises(LLMAuthError, match="not found"):
        await p.complete(request())


NOW = datetime(2026, 10, 20, 10, 0, tzinfo=Berlin)  # 10:00 Berlin


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("resets 3pm (Europe/Berlin)", datetime(2026, 10, 20, 15, 0, tzinfo=Berlin)),
        ("resets at 15:30 (Europe/Berlin)", datetime(2026, 10, 20, 15, 30, tzinfo=Berlin)),
        ("resets 9am (Europe/Berlin)", datetime(2026, 10, 21, 9, 0, tzinfo=Berlin)),  # tomorrow
        ("resets 12am (Europe/Berlin)", datetime(2026, 10, 21, 0, 0, tzinfo=Berlin)),
        ("limit reached|1760961600", datetime.fromtimestamp(1760961600, UTC)),
        ("limit reached, try later", None),
        ("resets 99pm", None),
    ],
)
def test_parse_reset_at(text: str, expected: datetime | None) -> None:
    assert parse_reset_at(text, now=NOW) == expected
