import os
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

from app.database import get_db
from app.models.user import User
from app.models.space import Space, SpaceMember
from app.models.connection import Connection, ConnectionFieldValue, OwnerLevel, FieldType
from app.api.deps import get_current_user, get_current_space_id, require_space_member, require_admin

router = APIRouter(prefix="/credentials", tags=["credentials"])


class ConnectionFieldDef(BaseModel):
    key: str
    label: str
    type: str = "secret"
    owner_level: str = "team"


class ConnectionCreate(BaseModel):
    slug: str
    display_name: str
    fields: list[ConnectionFieldDef] = []


class ConnectionOut(BaseModel):
    id: str
    space_id: str
    slug: str
    display_name: str
    fields: list | None

    model_config = {"from_attributes": True}


class FieldValueSet(BaseModel):
    field_key: str
    value: str
    owner_level: str = "user"


@router.get("", response_model=list[ConnectionOut])
async def list_connections(
    current_user: User = Depends(get_current_user),
    space_id: UUID | None = Depends(get_current_space_id),
    db: AsyncSession = Depends(get_db),
):
    conditions = [Connection.space_id == space_id] if space_id else []
    result = await db.execute(select(Connection).where(*conditions))
    connections = result.scalars().all()
    return [
        ConnectionOut(
            id=str(c.id),
            space_id=str(c.space_id),
            slug=c.slug,
            display_name=c.display_name,
            fields=[
                {**f, "value": "***" if f.get("type") == "secret" else f.get("value", "")}
                for f in (c.fields or [])
            ],
        )
        for c in connections
    ]


@router.post("", response_model=ConnectionOut, status_code=status.HTTP_201_CREATED)
async def create_connection(
    data: ConnectionCreate,
    current_user: User = Depends(get_current_user),
    space_id: UUID | None = Depends(get_current_space_id),
    member: SpaceMember = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    actual_space_id = space_id or member.space_id

    existing = await db.execute(
        select(Connection).where(
            Connection.space_id == actual_space_id,
            Connection.slug == data.slug,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Connection slug already exists in this space")

    connection = Connection(
        space_id=actual_space_id,
        slug=data.slug,
        display_name=data.display_name,
        fields=[f.model_dump() for f in data.fields],
    )
    db.add(connection)
    await db.flush()

    fields_out = connection.fields or []
    for f in fields_out:
        if f.get("type") == "secret":
            f["value"] = "***"

    return ConnectionOut(
        id=str(connection.id),
        space_id=str(connection.space_id),
        slug=connection.slug,
        display_name=connection.display_name,
        fields=fields_out,
    )


@router.delete("/{connection_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_connection(
    connection_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Connection).where(Connection.id == connection_id))
    connection = result.scalar_one_or_none()
    if connection:
        await db.delete(connection)
