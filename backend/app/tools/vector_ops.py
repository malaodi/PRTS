"""
Milvus vector operations — used ONLY for:
1. Team document chunk embeddings (docs_{space_id})
2. Marketplace asset recommendation (marketplace_assets)

NOT used for memory (memory is file-based, visible, editable).
"""
import json
import os
from typing import List, Dict, Optional

from app.config import get_settings

settings = get_settings()

MILVUS_HOST = os.getenv("MILVUS_HOST", "localhost")
MILVUS_PORT = int(os.getenv("MILVUS_PORT", "19530"))
EMBEDDING_DIM = 1024

_collections_initialized: set = set()


def _get_client():
    """Lazy-initialize Milvus client. Returns None if unavailable."""
    try:
        from pymilvus import connections
        alias = f"prts_{MILVUS_HOST}"
        try:
            connections.get_connection_addr(alias)
            return alias
        except Exception:
            connections.connect(
                alias=alias,
                host=MILVUS_HOST,
                port=MILVUS_PORT,
            )
            return alias
    except ImportError:
        return None
    except Exception:
        return None


def _get_embedding_model():
    """Lazy-load embedding model. Uses text-embedding-3-small if API key set, else falls back."""
    if settings.OPENAI_API_KEY:
        from langchain_openai import OpenAIEmbeddings
        return OpenAIEmbeddings(
            model="text-embedding-3-small",
            openai_api_key=settings.OPENAI_API_KEY,
        )
    return None


def _ensure_collection(alias: str, collection_name: str, dim: int = EMBEDDING_DIM):
    """Ensure a Milvus collection exists. Idempotent."""
    if collection_name in _collections_initialized:
        return True
    try:
        from pymilvus import Collection, FieldSchema, CollectionSchema, DataType, utility
    except ImportError:
        return False

    if not utility.has_collection(collection_name, using=alias):
        fields = [
            FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
            FieldSchema(name="content", dtype=DataType.VARCHAR, max_length=65535),
            FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=dim),
            FieldSchema(name="metadata", dtype=DataType.VARCHAR, max_length=4096),
        ]
        schema = CollectionSchema(fields, description=collection_name)
        Collection(collection_name, schema, using=alias)

        index_params = {
            "metric_type": "COSINE",
            "index_type": "IVF_FLAT",
            "params": {"nlist": 128},
        }
        col = Collection(collection_name, using=alias)
        col.create_index(field_name="embedding", index_params=index_params)

    _collections_initialized.add(collection_name)
    return True


async def embed_and_store(collection_name: str, texts: List[str], metadata: List[Dict] | None = None):
    """Embed texts and store in a Milvus collection.

    Args:
        collection_name: Target collection name
        texts: List of text chunks to embed
        metadata: Optional metadata dicts for each chunk
    """
    alias = _get_client()
    if not alias:
        return False

    embeddings = None
    model = _get_embedding_model()
    if model:
        try:
            result = await model.aembed_documents(texts)
            embeddings = result
        except Exception:
            return False

    if not embeddings:
        return False

    if not _ensure_collection(alias, collection_name):
        return False

    try:
        from pymilvus import Collection
        col = Collection(collection_name, using=alias)
        col.load()

        data = []
        for i, (text, emb) in enumerate(zip(texts, embeddings)):
            meta = json.dumps(metadata[i] if metadata else {})
            data.append({
                "content": text[:65535],
                "embedding": emb,
                "metadata": meta[:4096],
            })

        col.insert(data)
        col.flush()
        return True
    except Exception:
        return False


async def vector_search(
    collection_name: str,
    query: str,
    top_k: int = 5,
    filter_expr: str = "",
) -> List[Dict]:
    """Semantic search in a Milvus collection.

    Args:
        collection_name: Target collection name
        query: Search query text
        top_k: Number of results to return
        filter_expr: Optional Milvus filter expression
    Returns:
        List of {'content': str, 'score': float, 'metadata': dict}
    """
    alias = _get_client()
    if not alias:
        return []

    query_embedding = None
    model = _get_embedding_model()
    if model:
        try:
            result = await model.aembed_query(query)
            query_embedding = result
        except Exception:
            return []

    if not query_embedding:
        return []

    if not _ensure_collection(alias, collection_name):
        return []

    try:
        from pymilvus import Collection
        col = Collection(collection_name, using=alias)
        col.load()

        search_params = {"metric_type": "COSINE", "params": {"nprobe": 10}}
        expr = filter_expr if filter_expr else None
        results = col.search(
            data=[query_embedding],
            anns_field="embedding",
            param=search_params,
            limit=top_k,
            expr=expr,
            output_fields=["content", "metadata"],
        )

        hits = []
        for result_list in results:
            for hit in result_list:
                meta = {}
                try:
                    meta = json.loads(hit.entity.get("metadata", "{}"))
                except Exception:
                    pass
                hits.append({
                    "content": hit.entity.get("content", ""),
                    "score": float(hit.score),
                    "metadata": meta,
                })
        return hits
    except Exception:
        return []
