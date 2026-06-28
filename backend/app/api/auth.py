from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models.user import User
from app.models.space import Space, SpaceMember, MemberRole
from app.core.security import verify_password, get_password_hash, create_access_token
from app.schemas.auth import UserCreate, UserLogin, Token, UserOut
from app.api.deps import get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=Token, status_code=status.HTTP_201_CREATED)
async def register(data: UserCreate, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(
        select(User).where(
            (User.email == data.email) | (User.username == data.username)
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email or username already registered")

    user = User(
        email=data.email,
        username=data.username,
        hashed_password=get_password_hash(data.password),
        display_name=data.display_name or data.username,
    )
    db.add(user)
    await db.flush()

    personal_space = Space(
        name=f"{user.display_name or user.username} 的空间",
        type="personal",
        owner_id=user.id,
    )
    db.add(personal_space)
    await db.flush()

    membership = SpaceMember(
        space_id=personal_space.id,
        user_id=user.id,
        role=MemberRole.OWNER,
    )
    db.add(membership)

    token = create_access_token(user.id)
    return Token(access_token=token)


@router.post("/login", response_model=Token)
async def login(data: UserLogin, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.username == data.username))
    user = result.scalar_one_or_none()
    if not user or not verify_password(data.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    token = create_access_token(user.id)
    return Token(access_token=token)


@router.get("/me", response_model=UserOut)
async def get_me(current_user: User = Depends(get_current_user)):
    return UserOut(
        id=str(current_user.id),
        email=current_user.email,
        username=current_user.username,
        display_name=current_user.display_name,
        is_active=current_user.is_active,
    )
