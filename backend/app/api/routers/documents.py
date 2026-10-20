from typing import Annotated, Literal

from fastapi import APIRouter, File, HTTPException, UploadFile, status

from app.api.deps import CurrentUser, DbSession
from app.api.schemas import DocumentOut
from app.db.models import Document, DocumentStatus
from app.domain import documents, profile
from app.domain.accounts import AccountError
from app.workers.tasks import enqueue_parse_cv

router = APIRouter(prefix="/documents", tags=["documents"])

_ERROR_STATUS = {
    "file_too_large": status.HTTP_413_CONTENT_TOO_LARGE,
    "unsupported_file_type": status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
}


def _out(doc: Document) -> DocumentOut:
    doc_status: Literal["extracted", "no_text"] = (
        "extracted" if doc.status == "extracted" else "no_text"
    )
    return DocumentOut(
        id=doc.id,
        filename=doc.filename,
        content_type=doc.content_type,
        size_bytes=doc.size_bytes,
        status=doc_status,
        text_chars=len(doc.text or ""),
        created_at=doc.created_at,
    )


@router.post("/cv", response_model=DocumentOut, status_code=status.HTTP_201_CREATED)
async def upload_cv(
    file: Annotated[UploadFile, File(description="Lebenslauf as PDF or DOCX, max 5 MB")],
    user: CurrentUser,
    db: DbSession,
) -> DocumentOut:
    data = await file.read(documents.MAX_FILE_BYTES + 1)  # never read more than the limit
    try:
        doc = await documents.upload_cv(db, user, filename=file.filename or "", data=data)
    except AccountError as exc:
        raise HTTPException(_ERROR_STATUS.get(exc.code, 422), exc.code) from exc
    await db.commit()
    if doc.status == DocumentStatus.EXTRACTED:
        await profile.mark_queued(db, user.id)
        await db.commit()  # the worker reads the CV on its own connection
        await enqueue_parse_cv(user.id)
    return _out(doc)


@router.get("/cv", response_model=DocumentOut)
async def get_cv(user: CurrentUser, db: DbSession) -> DocumentOut:
    doc = await documents.current_cv(db, user.id)
    if doc is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no_cv")
    return _out(doc)


@router.delete("/cv", status_code=status.HTTP_204_NO_CONTENT)
async def delete_cv(user: CurrentUser, db: DbSession) -> None:
    await documents.delete_cv(db, user)
    await db.commit()
