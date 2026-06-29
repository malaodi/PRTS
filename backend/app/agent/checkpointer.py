"""
Checkpointer manager - integrates LangGraph PostgresSaver for session persistence.
Ensures conversation state survives server restarts.
"""
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from app.config import get_settings

settings = get_settings()

_checkpointer: AsyncPostgresSaver | None = None
_ctx_stack: list = []


def _get_checkpoint_conn_string() -> str:
    """Convert async database URL to a checkpointer-compatible connection string."""
    url = settings.DATABASE_URL
    url = url.replace("+asyncpg", "")
    return url


async def get_checkpointer() -> AsyncPostgresSaver:
    """Get or create the shared AsyncPostgresSaver instance."""
    global _checkpointer, _ctx_stack
    if _checkpointer is None:
        conn_string = _get_checkpoint_conn_string()
        cm = AsyncPostgresSaver.from_conn_string(conn_string)
        _checkpointer = await cm.__aenter__()
        _ctx_stack.append(cm)
        await _checkpointer.setup()
    return _checkpointer


async def close_checkpointer():
    """Close the checkpointer connection pool."""
    global _checkpointer, _ctx_stack
    for cm in reversed(_ctx_stack):
        try:
            await cm.__aexit__(None, None, None)
        except Exception:
            pass
    _ctx_stack.clear()
    _checkpointer = None
