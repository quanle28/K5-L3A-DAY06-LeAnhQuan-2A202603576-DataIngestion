"""Persistent vector stores with strict dimensions and allowlisted metadata filters."""
from __future__ import annotations

import math
import uuid
from typing import Any
from .models import Chunk

FILTER_FIELDS = {"chapter", "language", "version", "document_id", "page"}


def validate_vector(vector: list[float], dimensions: int) -> None:
    if len(vector) != dimensions or not all(math.isfinite(v) for v in vector):
        raise ValueError("Vector has invalid dimension or non-finite values")
    if not any(vector):
        raise ValueError("Cosine search requires a nonzero vector")


def validate_filters(filters: dict[str, Any]) -> None:
    if not set(filters).issubset(FILTER_FIELDS):
        raise ValueError("Unsupported metadata filter")
    if any(not isinstance(v, (str, int)) or isinstance(v, bool) for v in filters.values()):
        raise ValueError("Filters must be string or integer equality conditions")


def payload(chunk: Chunk) -> dict[str, Any]:
    return {**chunk.metadata, "chunk_id": chunk.chunk_id, "document_id": chunk.document_id,
            "source": chunk.source, "page": chunk.page, "text": chunk.text}


class QdrantStore:
    """Qdrant local persistent mode, exact cosine search for this small corpus."""
    def __init__(self, path: str, dimensions: int) -> None:
        from qdrant_client import QdrantClient
        self.client = QdrantClient(path=path)
        self.dimensions = dimensions

    @staticmethod
    def collection(strategy: str) -> str:
        if strategy not in {"A", "B", "C"}:
            raise ValueError("Unknown strategy")
        return f"day6_{strategy}"

    def create_schema(self) -> None:
        pass  # Collections are created on first ingestion.

    def upsert(self, strategy: str, chunks: list[Chunk], vectors: list[list[float]]) -> None:
        from qdrant_client import models
        if len(chunks) != len(vectors):
            raise ValueError("Chunk/vector count mismatch")
        if len({c.chunk_id for c in chunks}) != len(chunks):
            raise ValueError("Duplicate chunk IDs")
        for vector in vectors:
            validate_vector(vector, self.dimensions)
        name = self.collection(strategy)
        if not self.client.collection_exists(name):
            self.client.create_collection(name, vectors_config=models.VectorParams(
                size=self.dimensions, distance=models.Distance.COSINE))
        config = self.client.get_collection(name).config.params.vectors
        if config.size != self.dimensions or config.distance != models.Distance.COSINE:
            raise ValueError("Existing collection configuration does not match")
        old_ids = set()
        offset = None
        while True:
            points, offset = self.client.scroll(name, limit=256, offset=offset,
                                                with_payload=False, with_vectors=False)
            old_ids.update(str(p.id) for p in points)
            if offset is None:
                break
        points = [models.PointStruct(id=str(uuid.uuid5(uuid.NAMESPACE_URL, c.chunk_id)),
                                    vector=v, payload=payload(c)) for c, v in zip(chunks, vectors)]
        for start in range(0, len(points), 128):
            self.client.upsert(name, points=points[start:start + 128], wait=True)
        stale = old_ids - {str(p.id) for p in points}
        if stale:
            self.client.delete(name, points_selector=models.PointIdsList(points=sorted(stale)), wait=True)

    def search(self, strategy: str, query_vector: list[float], top_k: int = 3,
               filters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        from qdrant_client import models
        validate_vector(query_vector, self.dimensions)
        validate_filters(filters or {})
        if top_k <= 0:
            raise ValueError("top_k must be positive")
        conditions = [models.FieldCondition(key=k, match=models.MatchValue(value=v))
                      for k, v in (filters or {}).items()]
        hits = self.client.query_points(self.collection(strategy), query=query_vector, limit=top_k,
            query_filter=models.Filter(must=conditions) if conditions else None,
            search_params=models.SearchParams(exact=True), with_payload=True).points
        return [{**hit.payload, "score": hit.score} for hit in hits]

    def count(self, strategy: str) -> int:
        return self.client.count(self.collection(strategy), exact=True).count

    def close(self) -> None:
        self.client.close()


class PgVectorStore:
    """Optional PostgreSQL backend. Used only when explicitly selected."""
    def __init__(self, database_url: str, dimensions: int) -> None:
        import psycopg
        if dimensions <= 0:
            raise ValueError("dimensions must be positive")
        self.dimensions = dimensions
        self.connection = psycopg.connect(database_url, connect_timeout=5)

    def create_schema(self) -> None:
        with self.connection.transaction(), self.connection.cursor() as cursor:
            cursor.execute("CREATE EXTENSION IF NOT EXISTS vector")
            cursor.execute(f"""CREATE TABLE IF NOT EXISTS day6_chunks (
                strategy text NOT NULL, chunk_id text NOT NULL, payload jsonb NOT NULL,
                embedding vector({int(self.dimensions)}) NOT NULL,
                PRIMARY KEY(strategy, chunk_id))""")
            cursor.execute("SELECT atttypmod FROM pg_attribute WHERE attrelid='day6_chunks'::regclass AND attname='embedding'")
            if cursor.fetchone()[0] != self.dimensions:
                raise ValueError("Existing pgvector dimension mismatch")

    def upsert(self, strategy: str, chunks: list[Chunk], vectors: list[list[float]]) -> None:
        from psycopg.types.json import Jsonb
        if len(chunks) != len(vectors):
            raise ValueError("Chunk/vector count mismatch")
        if len({c.chunk_id for c in chunks}) != len(chunks):
            raise ValueError("Duplicate chunk IDs")
        for vector in vectors:
            validate_vector(vector, self.dimensions)
        # Full strategy snapshot, transactional: changed/deleted pages leave no stale chunks.
        with self.connection.transaction(), self.connection.cursor() as cursor:
            cursor.execute("DELETE FROM day6_chunks WHERE strategy=%s", (strategy,))
            cursor.executemany("INSERT INTO day6_chunks VALUES (%s,%s,%s,%s::vector)",
                [(strategy, c.chunk_id, Jsonb(payload(c)), str(v)) for c, v in zip(chunks, vectors)])

    def search(self, strategy: str, query_vector: list[float], top_k: int = 3,
               filters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        from psycopg.types.json import Jsonb
        validate_vector(query_vector, self.dimensions)
        validate_filters(filters or {})
        if top_k <= 0:
            raise ValueError("top_k must be positive")
        with self.connection.cursor() as cursor:
            cursor.execute("""SELECT payload, 1 - (embedding <=> %s::vector) AS score
                FROM day6_chunks WHERE strategy=%s AND payload @> %s
                ORDER BY embedding <=> %s::vector, chunk_id LIMIT %s""",
                (str(query_vector), strategy, Jsonb(filters or {}), str(query_vector), top_k))
            return [{**p, "score": float(score)} for p, score in cursor.fetchall()]

    def count(self, strategy: str) -> int:
        with self.connection.cursor() as cursor:
            cursor.execute("SELECT count(*) FROM day6_chunks WHERE strategy=%s", (strategy,))
            return cursor.fetchone()[0]

    def close(self) -> None:
        self.connection.close()
