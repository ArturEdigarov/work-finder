"""Structured profile built from the Lebenslauf. Shared by the API, the bot and the worker.

The profile is a list of facts; cover letters and CV variants (phase 6) may only use
facts and must reference their ids. Re-parsing replaces facts with `source == "cv"` and
keeps what the user answered or edited.
"""

import secrets
import uuid
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from datetime import UTC, datetime
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import DocumentStatus, Profile, ProfileStatus, User
from app.domain.documents import current_cv
from app.llm.gate import LLMDeferred, LLMForbidden, LLMGate
from app.llm.prompts import cv_parse
from app.llm.provider import LLMInvalidOutput, LLMUnavailable

log = structlog.get_logger()

SessionFactory = Callable[[], AbstractAsyncContextManager[AsyncSession]]

MAX_CV_CHARS = 30_000  # ~8k tokens; real CVs are far below
LANGUAGE_NAMES = {"de": "German", "en": "English", "ru": "Russian", "uk": "Ukrainian"}

Fact = dict[str, Any]


def new_fact_id() -> str:
    return f"f_{secrets.token_hex(4)}"


def _fact(type_: str, value: dict[str, Any], source: str = "cv") -> Fact:
    return {"id": new_fact_id(), "type": type_, "value": value, "source": source}


def facts_from_parse(out: cv_parse.CvParseOut) -> list[Fact]:
    facts: list[Fact] = []
    if out.full_name:
        facts.append(_fact("personal", {"full_name": out.full_name}))
    location = {k: v for k, v in {"city": out.city, "postcode": out.postcode,
                                  "country": out.country}.items() if v}  # fmt: skip
    if location:
        facts.append(_fact("location", location))
    if out.profession:
        facts.append(_fact("profession", {"name": out.profession}))
    facts += [_fact("desired_role", {"name": r}) for r in out.desired_roles]
    facts += [_fact("experience", e.model_dump(exclude_none=True)) for e in out.experience]
    facts += [_fact("education", e.model_dump(exclude_none=True)) for e in out.education]
    facts += [_fact("skill", {"name": s}) for s in out.skills]
    facts += [_fact("language", lang.model_dump(exclude_none=True)) for lang in out.languages]
    facts += [_fact("certificate", c.model_dump(exclude_none=True)) for c in out.certificates]
    facts += [_fact("driving_license", {"class": d}) for d in out.driving_licenses]
    facts += [_fact("other", {"text": o}) for o in out.other]
    return facts


async def get_profile(db: AsyncSession, user_id: uuid.UUID) -> Profile | None:
    return await db.scalar(select(Profile).where(Profile.user_id == user_id))


async def mark_queued(db: AsyncSession, user_id: uuid.UUID) -> Profile:
    """Before enqueueing `parse_cv`: the UI shows "queued" right away."""
    profile = await get_profile(db, user_id)
    if profile is None:
        profile = Profile(user_id=user_id, status=ProfileStatus.QUEUED, facts=[], version=0)
        db.add(profile)
    else:
        profile.status = ProfileStatus.QUEUED
    await db.flush()
    return profile


async def _set_status(session_factory: SessionFactory, user_id: uuid.UUID, status: str) -> None:
    async with session_factory() as db:
        profile = await get_profile(db, user_id)
        if profile is not None:
            profile.status = status
            await db.commit()


async def run_cv_parse(session_factory: SessionFactory, gate: LLMGate, user_id: uuid.UUID) -> None:
    """Parse the user's current CV into facts. Called by the `parse_cv` task.

    Re-raises `LLMDeferred` / `LLMUnavailable` so the queue retries later.
    """
    async with session_factory() as db:
        user = await db.get(User, user_id)
        document = await current_cv(db, user_id)
        if user is None or document is None or document.status != DocumentStatus.EXTRACTED:
            log.info("cv_parse_skipped", user_id=str(user_id))
            return
        document_id, text, locale = document.id, document.text or "", user.locale
        profile = await mark_queued(db, user_id)
        profile.status = ProfileStatus.PARSING
        await db.commit()

    req = cv_parse.PROMPT.build(
        user_id=user_id,
        language=LANGUAGE_NAMES.get(locale, "English"),
        cv_text=text[:MAX_CV_CHARS],
    )
    try:
        result = await gate.call(req)
    except (LLMDeferred, LLMUnavailable):
        await _set_status(session_factory, user_id, ProfileStatus.QUEUED)
        raise
    except LLMForbidden:
        await _set_status(session_factory, user_id, ProfileStatus.UNAVAILABLE)
        return
    except LLMInvalidOutput:
        await _set_status(session_factory, user_id, ProfileStatus.FAILED)
        log.warning("cv_parse_invalid_output", user_id=str(user_id))
        return

    new_facts = facts_from_parse(result.data)
    if not new_facts:
        # A CV with text always yields something; an empty answer is a model failure.
        await _set_status(session_factory, user_id, ProfileStatus.FAILED)
        log.warning("cv_parse_empty", user_id=str(user_id))
        return

    async with session_factory() as db:
        latest = await current_cv(db, user_id)
        if latest is None or latest.id != document_id:
            # Replaced or deleted during the call: drop the stale result; the job queued
            # for the new upload parses the current file.
            log.info("cv_parse_stale", user_id=str(user_id))
            stale = await get_profile(db, user_id)
            if stale is not None:
                # A new upload queued its own parse; without a CV there is nothing to do.
                stale.status = ProfileStatus.QUEUED if latest else ProfileStatus.FAILED
                await db.commit()
            return
        stored = await get_profile(db, user_id)
        assert stored is not None
        profile = stored
        kept = [f for f in profile.facts if f.get("source") != "cv"]
        profile.facts = new_facts + kept
        profile.suggested_questions = [m.model_dump() for m in result.data.missing_info]
        profile.source_document_id = document_id
        profile.prompt_version = req.prompt_version
        profile.version += 1
        profile.parsed_at = datetime.now(UTC)
        profile.status = ProfileStatus.READY
        await db.commit()
        log.info(
            "cv_parsed",
            user_id=str(user_id),
            facts=len(profile.facts),
            questions=len(profile.suggested_questions),
            version=profile.version,
        )


async def export_profile(db: AsyncSession, user_id: uuid.UUID) -> dict[str, Any] | None:
    profile = await get_profile(db, user_id)
    if profile is None:
        return None
    return {
        "status": profile.status,
        "version": profile.version,
        "parsed_at": profile.parsed_at.isoformat() if profile.parsed_at else None,
        "facts": profile.facts,
        "suggested_questions": profile.suggested_questions,
    }
