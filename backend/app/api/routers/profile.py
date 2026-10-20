from fastapi import APIRouter, HTTPException, status

from app.api.deps import CurrentUser, DbSession
from app.api.schemas import AnswerIn, FactIn, FactOut, FactUpdateIn, ProfileOut, QuestionOut
from app.db.models import DocumentStatus, Profile
from app.domain import documents, profile
from app.domain.accounts import AccountError
from app.workers.tasks import enqueue_parse_cv

router = APIRouter(prefix="/profile", tags=["profile"])

_NOT_FOUND = {"no_profile", "question_not_found", "fact_not_found"}


def _out(p: Profile) -> ProfileOut:
    return ProfileOut(
        status=p.status,
        version=p.version,
        parsed_at=p.parsed_at,
        prompt_version=p.prompt_version,
        facts=[FactOut.model_validate(f) for f in p.facts],
        questions=[QuestionOut.model_validate(q) for q in profile.questions_of(p)],
    )


def _error(exc: AccountError) -> HTTPException:
    code = status.HTTP_404_NOT_FOUND if exc.code in _NOT_FOUND else 422
    return HTTPException(code, exc.code)


@router.get("", response_model=ProfileOut)
async def get_profile(user: CurrentUser, db: DbSession) -> ProfileOut:
    p = await profile.get_profile(db, user.id)
    if p is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no_profile")
    return _out(p)


@router.post("/parse", response_model=ProfileOut, status_code=status.HTTP_202_ACCEPTED)
async def reparse(user: CurrentUser, db: DbSession) -> ProfileOut:
    """Parse the current CV again (e.g. after a failure). Costs one `parse` call."""
    cv = await documents.current_cv(db, user.id)
    if cv is None or cv.status != DocumentStatus.EXTRACTED:
        raise HTTPException(status.HTTP_409_CONFLICT, "no_cv_text")
    p = await profile.mark_queued(db, user.id)
    await db.commit()
    await enqueue_parse_cv(user.id)
    return _out(p)


@router.post("/questions/{question_id}/answer", response_model=ProfileOut)
async def answer(question_id: str, body: AnswerIn, user: CurrentUser, db: DbSession) -> ProfileOut:
    try:
        p = await profile.answer_question(db, user.id, question_id, body.text)
    except AccountError as exc:
        raise _error(exc) from exc
    await db.commit()
    return _out(p)


@router.post("/questions/{question_id}/dismiss", response_model=ProfileOut)
async def dismiss(question_id: str, user: CurrentUser, db: DbSession) -> ProfileOut:
    try:
        p = await profile.dismiss_question(db, user.id, question_id)
    except AccountError as exc:
        raise _error(exc) from exc
    await db.commit()
    return _out(p)


@router.post("/facts", response_model=ProfileOut, status_code=status.HTTP_201_CREATED)
async def add_fact(body: FactIn, user: CurrentUser, db: DbSession) -> ProfileOut:
    try:
        p = await profile.add_fact(db, user.id, body.type, body.value)
    except AccountError as exc:
        raise _error(exc) from exc
    await db.commit()
    return _out(p)


@router.patch("/facts/{fact_id}", response_model=ProfileOut)
async def update_fact(
    fact_id: str, body: FactUpdateIn, user: CurrentUser, db: DbSession
) -> ProfileOut:
    try:
        p = await profile.update_fact(db, user.id, fact_id, body.value)
    except AccountError as exc:
        raise _error(exc) from exc
    await db.commit()
    return _out(p)


@router.delete("/facts/{fact_id}", response_model=ProfileOut)
async def delete_fact(fact_id: str, user: CurrentUser, db: DbSession) -> ProfileOut:
    try:
        p = await profile.delete_fact(db, user.id, fact_id)
    except AccountError as exc:
        raise _error(exc) from exc
    await db.commit()
    return _out(p)
