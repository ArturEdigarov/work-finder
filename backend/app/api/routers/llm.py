from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.deps import CurrentUser, DbSession
from app.api.schemas import LlmKindUsageOut, LlmStatusOut
from app.llm.gate import LLMGate, get_gate

router = APIRouter(prefix="/llm", tags=["llm"])


@router.get("/status", response_model=LlmStatusOut)
async def llm_status(
    user: CurrentUser, db: DbSession, gate: Annotated[LLMGate, Depends(get_gate)]
) -> LlmStatusOut:
    status = await gate.status(db, user)
    return LlmStatusOut(
        provider=status.provider,
        available=status.available,
        paused_until=status.paused_until,
        day=status.day,
        usage=[LlmKindUsageOut(kind=u.kind.value, used=u.used, cap=u.cap) for u in status.usage],
    )
