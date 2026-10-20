from app.api.schemas import UserOut
from app.db.models import User


def user_out(user: User) -> UserOut:
    return UserOut(
        id=user.id,
        email=user.email,
        role=user.role,
        locale=user.locale,
        telegram_linked=user.telegram_chat_id is not None,
        created_at=user.created_at,
    )
