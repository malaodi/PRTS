from uuid import UUID
from fastapi import Depends, HTTPException, status, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.core.security import decode_access_token
from app.models.user import User
from app.models.space import SpaceMember
from app.models.space import MemberRole

security_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    try:
        payload = decode_access_token(credentials.credentials)
        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    result = await db.execute(select(User).where(User.id == UUID(user_id)))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Inactive user")

    return user


async def get_current_space_id(
    x_space_id: str | None = Header(None),
) -> UUID | None:
    if x_space_id is None:
        return None
    try:
        return UUID(x_space_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid space ID")


async def get_space_member(
    current_user: User = Depends(get_current_user),
    space_id: UUID | None = Depends(get_current_space_id),
    db: AsyncSession = Depends(get_db),
) -> SpaceMember | None:
    if space_id is None:
        return None
    result = await db.execute(
        select(SpaceMember).where(
            SpaceMember.space_id == space_id,
            SpaceMember.user_id == current_user.id,
        )
    )
    return result.scalar_one_or_none()


async def require_space_member(
    member: SpaceMember | None = Depends(get_space_member),
) -> SpaceMember:
    if member is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a member of this space")
    return member


async def require_admin(
    member: SpaceMember = Depends(require_space_member),
) -> SpaceMember:
    if member.role not in (MemberRole.OWNER, MemberRole.ADMIN):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required")
    return member


async def require_owner(
    member: SpaceMember = Depends(require_space_member),
) -> SpaceMember:
    if member.role != MemberRole.OWNER:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Owner role required")
    return member
