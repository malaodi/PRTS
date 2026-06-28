"""
Credential injection system for PRTS tools.
Provides both os.environ injection (CVO_CONN_ prefix) and ctx.connections interface.
"""
import os
import json
import base64
from uuid import UUID
from typing import Any, Optional
from dataclasses import dataclass, field
from cryptography.fernet import Fernet

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.connection import Connection, ConnectionFieldValue, OwnerLevel
from app.config import get_settings

settings = get_settings()

CVO_PREFIX = "CVO_CONN_"


def _get_cipher() -> Fernet | None:
    key = settings.SECRET_KEY.encode("utf-8")
    padded = key.ljust(32, b"\x00")[:32]
    encoded = base64.urlsafe_b64encode(padded)
    return Fernet(encoded)


def encrypt_value(value: str) -> str:
    cipher = _get_cipher()
    if cipher is None:
        return value
    return cipher.encrypt(value.encode("utf-8")).decode("utf-8")


def decrypt_value(encrypted_value: str) -> str:
    cipher = _get_cipher()
    if cipher is None:
        return encrypted_value
    try:
        return cipher.decrypt(encrypted_value.encode("utf-8")).decode("utf-8")
    except Exception:
        return encrypted_value


@dataclass
class ConnectionContext:
    """Provides credential reading for tools via ctx.connections interface."""
    _values: dict[str, dict[str, str]] = field(default_factory=dict)

    def __getitem__(self, connection_slug: str) -> dict[str, str]:
        return self._values.get(connection_slug, {})

    def get(self, connection_slug: str, default: Any = None) -> dict[str, str]:
        return self._values.get(connection_slug, default)


async def load_credentials(
    db: AsyncSession,
    space_id: UUID,
    user_id: UUID,
) -> ConnectionContext:
    """Load all connection credentials for a space/user into a ConnectionContext."""
    ctx = ConnectionContext()

    result = await db.execute(
        select(Connection).where(Connection.space_id == space_id)
    )
    connections = result.scalars().all()

    for conn in connections:
        conn_values: dict[str, str] = {}

        field_values_result = await db.execute(
            select(ConnectionFieldValue).where(
                ConnectionFieldValue.connection_id == conn.id,
                (ConnectionFieldValue.owner_level == OwnerLevel.TEAM) |
                (
                    (ConnectionFieldValue.owner_level == OwnerLevel.USER) &
                    (ConnectionFieldValue.user_id == user_id)
                ),
            )
        )
        field_values = field_values_result.scalars().all()

        for fv in field_values:
            if fv.encrypted_value:
                conn_values[fv.field_key] = decrypt_value(fv.encrypted_value)

        fields = conn.fields or []
        for field_def in fields:
            key = field_def.get("key", "")
            if key in conn_values:
                continue
            if field_def.get("owner_level") == "team" and field_def.get("value"):
                if field_def.get("type") == "secret":
                    conn_values[key] = decrypt_value(field_def["value"])
                else:
                    conn_values[key] = field_def["value"]

        if conn_values:
            ctx._values[conn.slug] = conn_values

    return ctx


def inject_into_env(ctx: ConnectionContext):
    """Inject credentials into os.environ with CVO_CONN_ prefix."""
    for slug, fields in ctx._values.items():
        for field_key, value in fields.items():
            env_key = f"{CVO_PREFIX}{slug.upper()}_{field_key.upper()}"
            os.environ[env_key] = value


def clear_from_env(ctx: ConnectionContext):
    """Remove injected credentials from os.environ."""
    for slug, fields in ctx._values.items():
        for field_key in fields:
            env_key = f"{CVO_PREFIX}{slug.upper()}_{field_key.upper()}"
            os.environ.pop(env_key, None)
