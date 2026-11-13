"""Real local ONNX embeddings; failures propagate instead of returning mock vectors."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Protocol


class Embedder(Protocol):
    model_name: str
    dimensions: int
    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...
    def embed_query(self, question: str) -> list[float]: ...


class MyEmbedder:
    def __init__(self, model_name: str = "BAAI/bge-small-en-v1.5", cache_dir: str = ".cache/models") -> None:
        from fastembed import TextEmbedding
        self.model_name = model_name
        model_path = None
        lock_path = Path(__file__).resolve().parents[1] / "model_lock.json"
        lock = json.loads(lock_path.read_text()) if lock_path.exists() else None
        self.model_revision = lock["revision"] if lock and lock["model"] == model_name else "unlocked"
        if lock and lock["model"] == model_name:
            cached = Path(cache_dir) / ("models--" + lock["repository"].replace("/", "--")) / "snapshots" / lock["revision"]
            direct = Path(cache_dir) / ("locked-" + lock["revision"])
            if cached.exists():
                model_path = cached
            elif all((direct / name).exists() for name in lock["files_sha256"]):
                model_path = direct
            else:
                from huggingface_hub import snapshot_download
                model_path = Path(snapshot_download(repo_id=lock["repository"], revision=lock["revision"],
                    allow_patterns=list(lock["files_sha256"]), local_dir=str(direct),
                    local_files_only=os.getenv("FASTEMBED_OFFLINE") == "1"))
            for name, expected in lock["files_sha256"].items():
                if hashlib.sha256((model_path / name).read_bytes()).hexdigest() != expected:
                    raise ValueError(f"Model checksum mismatch: {name}")
        self.model = TextEmbedding(model_name=model_name, cache_dir=cache_dir, threads=2,
                                   local_files_only=os.getenv("FASTEMBED_OFFLINE") == "1",
                                   specific_model_path=str(model_path) if model_path else None)
        self.dimensions = len(next(self.model.embed(["dimension probe"])))
        self.cache_path = Path(cache_dir).parent / "embeddings.json"
        self.cache = json.loads(self.cache_path.read_text()) if self.cache_path.exists() else {}

    def _key(self, text: str, role: str) -> str:
        return hashlib.sha256(f"{self.model_name}|{self.model_revision}|fastembed-0.6.1-raw|{role}|{text}".encode()).hexdigest()

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        missing = list(dict.fromkeys(text for text in texts if self._key(text, "document") not in self.cache))
        if missing:
            vectors = list(self.model.passage_embed(missing, batch_size=32))
            for text, vector in zip(missing, vectors):
                self.cache[self._key(text, "document")] = vector.tolist()
            self._save()
        return [self.cache[self._key(text, "document")] for text in texts]

    def embed_query(self, question: str) -> list[float]:
        key = self._key(question, "query")
        if key not in self.cache:
            self.cache[key] = next(self.model.query_embed([question])).tolist()
            self._save()
        return self.cache[key]

    def _save(self) -> None:
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.cache_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(self.cache), encoding="utf-8")
        temporary.replace(self.cache_path)
