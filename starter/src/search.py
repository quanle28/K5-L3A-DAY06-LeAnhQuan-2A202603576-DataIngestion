"""Interactive retrieval demo against the persistent index (no gold evidence in query)."""
from __future__ import annotations
import argparse
import json
from .embeddings import MyEmbedder
from .run import ROOT
from .store import QdrantStore


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("question")
    parser.add_argument("--strategy", choices=["A", "B", "C"], default="B")
    parser.add_argument("--chapter", default=None)
    args = parser.parse_args()
    config = json.loads((ROOT / "starter/config.json").read_text())
    embedder = MyEmbedder(config["model"], str(ROOT / ".cache/models"))
    store = QdrantStore(str(ROOT / ".cache/qdrant"), embedder.dimensions)
    try:
        filters = {"chapter": args.chapter} if args.chapter else {}
        if filters and args.strategy != "C":
            parser.error("Use strategy C for the filtered retrieval configuration")
        hits = store.search(args.strategy, embedder.embed_query(args.question), 3, filters)
        print(json.dumps(hits, ensure_ascii=False, indent=2))
    finally:
        store.close()


if __name__ == "__main__":
    main()
