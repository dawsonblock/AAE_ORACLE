"""Storage subsystem — unified interface over all persistence backends.

Re-exports the five concrete store classes so callers can import from
``aae.storage`` without knowing the internal layout.
"""
from .artifact_store import ArtifactStore
from .graph_store_adapter import GraphStoreAdapter
from .postgres_store import PostgresStore
from .redis_store import RedisStore
from .vector_store_adapter import VectorStoreAdapter

__all__ = [
    "ArtifactStore",
    "GraphStoreAdapter",
    "PostgresStore",
    "RedisStore",
    "VectorStoreAdapter",
]
