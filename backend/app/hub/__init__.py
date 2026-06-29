"""
LangSmith integration module.
Provides tracing, hub marketplace, and feedback collection.
"""
import os
from functools import wraps
from typing import Callable, Any

from langsmith import traceable
from langsmith import Client as LangSmithClient

from app.config import get_settings

settings = get_settings()

_langsmith_client: LangSmithClient | None = None


def get_langsmith_client() -> LangSmithClient | None:
    global _langsmith_client
    if _langsmith_client is None and settings.LANGCHAIN_API_KEY:
        try:
            _langsmith_client = LangSmithClient()
        except Exception:
            _langsmith_client = None
    return _langsmith_client


def trace(name: str | None = None):
    """Decorator to trace function calls in LangSmith."""
    def decorator(func: Callable) -> Callable:
        if not settings.LANGCHAIN_API_KEY:
            return func

        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            client = get_langsmith_client()
            if client is None:
                return await func(*args, **kwargs)
            trace_func = traceable(name=name or func.__name__)(func)
            return await trace_func(*args, **kwargs)

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            client = get_langsmith_client()
            if client is None:
                return func(*args, **kwargs)
            trace_func = traceable(name=name or func.__name__)(func)
            return trace_func(*args, **kwargs)

        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


# ─── Hub Operations ──────────────────────────────────────────

def hub_pull(namespace: str, asset_type: str = "prompt") -> dict | None:
    """Pull an asset from LangSmith Hub.

    Args:
        namespace: Hub namespace (e.g., 'my-team/my-agent-prompt')
        asset_type: Type of asset ('prompt', 'tool', 'agent')
    """
    client = get_langsmith_client()
    if client is None:
        return {"error": "LangSmith API key not configured"}

    try:
        if asset_type == "prompt":
            from langchain import hub
            prompt = hub.pull(namespace)
            return {"type": "prompt", "namespace": namespace, "object": prompt}
    except Exception as e:
        return {"error": str(e)}

    return None


def hub_push(namespace: str, asset: Any, description: str = "") -> dict:
    """Push an asset to LangSmith Hub.

    Args:
        namespace: Hub namespace
        asset: The asset object to push (None if only publishing via Milvus)
        description: Human-readable description
    """
    client = get_langsmith_client()
    if client is None:
        return {"error": "LangSmith API key not configured"}

    if asset is None:
        return {"status": "skipped", "namespace": namespace, "message": "Milvus-only publish, no LangSmith hub asset"}

    try:
        from langchain import hub
        hub.push(namespace, asset)
        return {"status": "published", "namespace": namespace}
    except Exception as e:
        return {"error": str(e)}


def record_feedback(run_id: str, score: float, comment: str = "") -> bool:
    """Record user feedback for a LangSmith run."""
    client = get_langsmith_client()
    if client is None:
        return False

    try:
        client.create_feedback(
            run_id=run_id,
            key="user_rating",
            score=score,
            comment=comment,
        )
        return True
    except Exception:
        return False
