from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models.user import User
from app.models.space import Space, SpaceMember, MemberRole, SpaceType
from app.schemas.space import SpaceCreate, SpaceUpdate, SpaceOut, MemberOut, MemberRoleUpdate, MemberInvite
from app.api.deps import get_current_user

router = APIRouter(prefix="/spaces", tags=["spaces"])


async def get_member_for_space(
    space_id: UUID,
    current_user: User,
    db: AsyncSession,
    required: bool = True,
) -> SpaceMember | None:
    result = await db.execute(
        select(SpaceMember).where(
            SpaceMember.space_id == space_id,
            SpaceMember.user_id == current_user.id,
        )
    )
    member = result.scalar_one_or_none()
    if required and member is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a member of this space")
    return member


async def require_admin_for_space(
    space_id: UUID,
    current_user: User,
    db: AsyncSession,
) -> SpaceMember:
    member = await get_member_for_space(space_id, current_user, db, required=True)
    if member.role not in (MemberRole.OWNER, MemberRole.ADMIN):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required")
    return member


async def require_owner_for_space(
    space_id: UUID,
    current_user: User,
    db: AsyncSession,
) -> SpaceMember:
    member = await get_member_for_space(space_id, current_user, db, required=True)
    if member.role != MemberRole.OWNER:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Owner role required")
    return member


@router.get("", response_model=list[SpaceOut])
async def list_spaces(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Space)
        .join(SpaceMember, Space.id == SpaceMember.space_id)
        .where(SpaceMember.user_id == current_user.id)
    )
    spaces = result.scalars().all()
    return [
        SpaceOut(
            id=str(s.id),
            name=s.name,
            type=s.type.value if isinstance(s.type, SpaceType) else s.type,
            owner_id=str(s.owner_id),
            team_context=s.team_context,
            member_count=s.member_count,
        )
        for s in spaces
    ]


@router.post("", response_model=SpaceOut, status_code=status.HTTP_201_CREATED)
async def create_space(
    data: SpaceCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    space = Space(
        name=data.name,
        type=data.type,
        owner_id=current_user.id,
        team_context=data.team_context,
    )
    db.add(space)
    await db.flush()

    membership = SpaceMember(
        space_id=space.id,
        user_id=current_user.id,
        role=MemberRole.OWNER,
    )
    db.add(membership)

    return SpaceOut(
        id=str(space.id),
        name=space.name,
        type=space.type.value if isinstance(space.type, SpaceType) else space.type,
        owner_id=str(space.owner_id),
        team_context=space.team_context,
        member_count=1,
    )


@router.get("/{space_id}", response_model=SpaceOut)
async def get_space(
    space_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ = await get_member_for_space(space_id, current_user, db)
    result = await db.execute(select(Space).where(Space.id == space_id))
    space = result.scalar_one_or_none()
    if not space:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Space not found")
    return SpaceOut(
        id=str(space.id),
        name=space.name,
        type=space.type.value if isinstance(space.type, SpaceType) else space.type,
        owner_id=str(space.owner_id),
        team_context=space.team_context,
        member_count=space.member_count,
    )


@router.patch("/{space_id}", response_model=SpaceOut)
async def update_space(
    space_id: UUID,
    data: SpaceUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ = await require_admin_for_space(space_id, current_user, db)
    result = await db.execute(select(Space).where(Space.id == space_id))
    space = result.scalar_one_or_none()
    if not space:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Space not found")

    if data.name is not None:
        space.name = data.name
    if data.team_context is not None:
        space.team_context = data.team_context

    await db.flush()
    return SpaceOut(
        id=str(space.id),
        name=space.name,
        type=space.type.value if isinstance(space.type, SpaceType) else space.type,
        owner_id=str(space.owner_id),
        team_context=space.team_context,
        member_count=space.member_count,
    )


@router.delete("/{space_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_space(
    space_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ = await require_owner_for_space(space_id, current_user, db)
    result = await db.execute(select(Space).where(Space.id == space_id))
    space = result.scalar_one_or_none()
    if space and space.type == SpaceType.PERSONAL:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot delete personal space")
    if space:
        await db.delete(space)


@router.get("/{space_id}/members", response_model=list[MemberOut])
async def list_members(
    space_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ = await get_member_for_space(space_id, current_user, db)
    result = await db.execute(
        select(SpaceMember, User)
        .join(User, SpaceMember.user_id == User.id)
        .where(SpaceMember.space_id == space_id)
    )
    rows = result.all()
    return [
        MemberOut(
            id=str(sm.id),
            user_id=str(sm.user_id),
            username=u.username,
            email=u.email,
            display_name=u.display_name,
            role=sm.role.value if isinstance(sm.role, MemberRole) else sm.role,
            joined_at=sm.joined_at.isoformat() if sm.joined_at else None,
        )
        for sm, u in rows
    ]


@router.post("/{space_id}/members/invite", response_model=MemberOut, status_code=status.HTTP_201_CREATED)
async def invite_member(
    space_id: UUID,
    data: MemberInvite,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ = await require_admin_for_space(space_id, current_user, db)

    user_result = await db.execute(select(User).where(User.email == data.email))
    invited_user = user_result.scalar_one_or_none()
    if not invited_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    existing_result = await db.execute(
        select(SpaceMember).where(
            SpaceMember.space_id == space_id,
            SpaceMember.user_id == invited_user.id,
        )
    )
    if existing_result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User is already a member")

    new_member = SpaceMember(
        space_id=space_id,
        user_id=invited_user.id,
        role=MemberRole(data.role),
    )
    db.add(new_member)

    space_result = await db.execute(select(Space).where(Space.id == space_id))
    space = space_result.scalar_one()
    space.member_count += 1

    await db.flush()
    return MemberOut(
        id=str(new_member.id),
        user_id=str(new_member.user_id),
        username=invited_user.username,
        email=invited_user.email,
        display_name=invited_user.display_name,
        role=new_member.role.value if isinstance(new_member.role, MemberRole) else new_member.role,
        joined_at=new_member.joined_at.isoformat() if new_member.joined_at else None,
    )


@router.patch("/{space_id}/members/{member_id}/role", response_model=MemberOut)
async def update_member_role(
    space_id: UUID,
    member_id: UUID,
    data: MemberRoleUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    current_member = await require_admin_for_space(space_id, current_user, db)

    target_result = await db.execute(
        select(SpaceMember, User)
        .join(User, SpaceMember.user_id == User.id)
        .where(SpaceMember.id == member_id, SpaceMember.space_id == space_id)
    )
    row = target_result.one_or_none()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")
    sm, u = row

    new_role = MemberRole(data.role)
    if new_role == MemberRole.OWNER and current_member.role != MemberRole.OWNER:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only owner can transfer ownership")

    sm.role = new_role
    await db.flush()
    return MemberOut(
        id=str(sm.id),
        user_id=str(sm.user_id),
        username=u.username,
        email=u.email,
        display_name=u.display_name,
        role=sm.role.value,
        joined_at=sm.joined_at.isoformat() if sm.joined_at else None,
    )


@router.delete("/{space_id}/members/{member_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_member(
    space_id: UUID,
    member_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    current_member = await require_admin_for_space(space_id, current_user, db)

    result = await db.execute(
        select(SpaceMember).where(
            SpaceMember.id == member_id, SpaceMember.space_id == space_id
        )
    )
    target = result.scalar_one_or_none()
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")
    if target.role == MemberRole.OWNER:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot remove the owner")
    if current_member.role == MemberRole.ADMIN and target.role == MemberRole.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin cannot remove another admin")

    space_result = await db.execute(select(Space).where(Space.id == space_id))
    space = space_result.scalar_one()
    space.member_count -= 1

    await db.delete(target)
