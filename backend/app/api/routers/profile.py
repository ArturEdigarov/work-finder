from fastapi import APIRouter, HTTPException, status

from app.api.deps import CurrentUser, DbSession
from app.api.schemas import FactOut, ProfileOut
from app.db.models import DocumentStatus, Profile
from app.domain import documents, profile
from app.workers.tasks import enqueue_parse_cv

router = APIRouter(prefix="/profile", tags=["profile"])


def _out(p: Profile) -> ProfileOut:
    return ProfileOut.model_validate(
        {
            "status": p.status,
            "version": p.version,
            "parsed_at": p.parsed_at,
            "prompt_version": p.prompt_version,
            "facts": [FactOut.model_validate(f) for f in p.facts],
        }
    )


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
