"""Reproducible CLI: ingest, freeze dev selection, evaluate held-out test, export audits."""
from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.metadata
import json
import logging
import os
import platform
import statistics
import sys
import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from .chunking import by_paragraph, fixed_size
from .embeddings import MyEmbedder
from .evaluation import canonical, gold_options, evaluate_query, summarize
from .ingestion import load_pages
from .store import PgVectorStore, QdrantStore, validate_filters

ROOT = Path(__file__).resolve().parents[2]


def write_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows) -> None:
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_inputs(pages, questions, manifest) -> None:
    if len(pages) < 30 or any(len(p.text) < 1500 for p in pages):
        raise ValueError("Need >=30 nonempty text units, each >=1500 characters")
    if manifest["page_count"] != len(pages):
        raise ValueError("Manifest page count differs from corpus")
    lookup = {(p.document_id, p.page): p for p in pages}
    declared = {(doc["source_id"], item["page"]): (doc, item)
                for doc in manifest["documents"] for item in doc["pages"]}
    if set(lookup) != set(declared):
        raise ValueError("Manifest page IDs differ from corpus")
    for key, page in lookup.items():
        doc, item = declared[key]
        if page.source != doc["source_path_or_url"] or len(page.text) != item["characters"]:
            raise ValueError(f"Manifest metadata mismatch: {key}")
        raw = ROOT / doc["local_path"]
        if digest(raw) != doc["raw_sha256"]:
            raise ValueError("Raw source checksum mismatch")
    if len({q["id"] for q in questions}) != len(questions):
        raise ValueError("Duplicate question IDs")
    for split, minimum in [("dev", 15), ("test", 5)]:
        if sum(q["split"] == split for q in questions) < minimum:
            raise ValueError(f"Insufficient {split} questions")
    if any(q["split"] not in {"dev", "test"} for q in questions):
        raise ValueError("Unknown benchmark split")
    if sum(bool(q.get("filter")) for q in questions) < 3 or not any(q.get("filter") for q in questions if q["split"] == "test"):
        raise ValueError("Require >=3 filter questions, including one test question")
    for q in questions:
        if not q["question"].strip() or not q["expected_answer"].strip():
            raise ValueError("Question or answer is empty")
        validate_filters(q.get("filter", {}))
        for gold in gold_options(q):
            page = lookup[(gold["document_id"], gold["page"])]
            evidence = canonical(gold["evidence_quote"])
            if not evidence or evidence not in canonical(page.text):
                raise ValueError(f"Gold evidence not found: {q['id']}")
            metadata = {**page.metadata, "document_id": page.document_id, "page": page.page}
            if any(metadata.get(k) != v for k, v in q.get("filter", {}).items()):
                raise ValueError(f"Filter excludes gold evidence: {q['id']}")


def export_audits(output: Path, pages, chunks_by_strategy, traces) -> None:
    lookup = {(p.document_id, p.page): p for p in pages}
    coherence = []
    for page in sorted(pages, key=lambda p: (p.document_id, p.page))[:10]:
        anchor = min(750, len(page.text) - 1)
        for strategy, chunks in chunks_by_strategy.items():
            covered = [c for c in chunks if c.document_id == page.document_id and c.page == page.page
                       and c.metadata["char_start"] <= anchor < c.metadata["char_end"]]
            coherence.append({"strategy": strategy, "document_id": page.document_id, "page": page.page,
                "source": page.source, "anchor": anchor, "source_context": page.text,
                "chunks": [asdict(c) for c in covered], "human_score_0_2": None, "human_reason": "", "reviewer": ""})
    write_jsonl(output / "coherence_samples.jsonl", coherence)
    grounding, metadata = [], []
    for trace in traces:
        if trace["split"] != "test":
            continue
        grounding.append({**trace, "human_score_0_2": None, "human_reason": "", "reviewer": ""})
        for rank, hit in enumerate(trace["hits"], 1):
            page = lookup[(hit["document_id"], hit["page"])]
            expected = {**page.metadata, "source": page.source, "page": page.page, "document_id": page.document_id}
            fields = ["source", "page", "document_id", "chapter", "version", "language"]
            correct = all(hit.get(field) == expected.get(field) for field in fields)
            offset_correct = page.text[hit["char_start"]:hit["char_end"]] == hit["text"]
            metadata.append({"strategy": trace["strategy"], "question_id": trace["question_id"], "rank": rank,
                "chunk_id": hit["chunk_id"], "source": hit["source"], "page": hit["page"], "chapter": hit["chapter"],
                "automated_complete_correct": correct and offset_correct,
                "matches_requested_filter": all(hit.get(k) == v for k, v in trace["filter_input"].items()),
                "filter_requested": bool(trace["filter_input"]),
                "human_verified": "", "human_reason": "", "reviewer": ""})
    write_jsonl(output / "grounding_samples.jsonl", grounding)
    with (output / "metadata_audit.csv").open("w", encoding="utf-8", newline="") as stream:
        if metadata:
            writer = csv.DictWriter(stream, fieldnames=list(metadata[0]))
            writer.writeheader()
            writer.writerows(metadata)


def execute(args, output: Path) -> None:
    started = time.perf_counter()
    config_path = Path(args.config).resolve()
    config = json.loads(config_path.read_text(encoding="utf-8"))
    pages = load_pages(ROOT / "data/pages.jsonl")
    questions = json.loads((ROOT / "benchmark/questions.json").read_text(encoding="utf-8"))
    manifest = json.loads((ROOT / "data/manifest.json").read_text(encoding="utf-8"))
    validate_inputs(pages, questions, manifest)
    if config["metric"] != "cosine" or config["top_k"] != 3:
        raise ValueError("This benchmark requires cosine top-3")
    if {**config["strategies"]["B"], "filter": True} != config["strategies"]["C"]:
        raise ValueError("B/C must differ ONLY in filter")
    hashes = {"corpus": digest(ROOT / "data/pages.jsonl"), "benchmark": digest(ROOT / "benchmark/questions.json"),
              "config": digest(config_path)}
    frozen_path = output / "frozen_plan.json"
    if frozen_path.exists():
        if json.loads(frozen_path.read_text())["hashes"] != hashes:
            raise ValueError("Frozen inputs changed. Use a new output directory and disclose a new experiment.")
    else:
        if args.phase == "test":
            raise ValueError("Run dev first; test requires a frozen dev selection")
        write_json(frozen_path, {"created_at_utc": datetime.now(timezone.utc).isoformat(), "hashes": hashes,
            "configuration": config, "split": {s: [q["id"] for q in questions if q["split"] == s] for s in ["dev", "test"]},
            "provenance": "AI-assisted benchmark; not human-authored or blindly human-verified."})
    if args.phase == "validate":
        print(f"Inputs OK: {len(pages)} content units / {len(questions)} evidence-verified questions")
        return
    initialization_start = time.perf_counter()
    embedder = MyEmbedder(config["model"], str(ROOT / ".cache/models"))
    initialization_seconds = time.perf_counter() - initialization_start
    if config["store"] == "qdrant":
        store = QdrantStore(str(ROOT / ".cache/qdrant"), embedder.dimensions)
    elif config["store"] == "pgvector":
        from dotenv import load_dotenv
        load_dotenv(ROOT / "starter/.env")
        store = PgVectorStore(os.environ["DATABASE_URL"], embedder.dimensions)
        store.create_schema()
    else:
        raise ValueError("Unsupported vector store")
    chunks_by_strategy, resources = {}, {}
    try:
        for strategy, spec in config["strategies"].items():
            t0 = time.perf_counter()
            chunks = [chunk for page in pages for chunk in (
                fixed_size(page, spec["size"], spec["overlap"]) if spec["chunking"] == "fixed"
                else by_paragraph(page, spec["size"]))]
            vectors = embedder.embed_documents([c.text for c in chunks])
            embed_seconds = time.perf_counter() - t0
            t1 = time.perf_counter()
            store.upsert(strategy, chunks, vectors)
            first_count = store.count(strategy)
            store.upsert(strategy, chunks, vectors)
            second_count = store.count(strategy)
            if first_count != len(chunks) or second_count != first_count:
                raise RuntimeError("Idempotency verification failed")
            lengths = [len(c.text) for c in chunks]
            token_lengths = [len(embedder.model.model.tokenizer.encode(c.text).ids) for c in chunks]
            chunks_by_strategy[strategy] = chunks
            resources[strategy] = {"chunk_count": len(chunks), "total_characters": sum(lengths),
                "total_tokens": sum(token_lengths), "max_tokens": max(token_lengths),
                "length_min": min(lengths), "length_mean": statistics.mean(lengths),
                "length_median": statistics.median(lengths), "length_max": max(lengths),
                "chunk_and_embedding_seconds": embed_seconds,
                "store_and_reingest_seconds": time.perf_counter() - t1,
                "count_first": first_count, "count_reingest": second_count, "api_cost_usd": 0,
                "cache_note": "B/C share document text; embedding cache reused. Model download/probe excluded."}
            write_jsonl(output / f"chunks_{strategy}.jsonl", [asdict(c) for c in chunks])
            print(f"{strategy}: {len(chunks)} chunks; re-ingest {first_count} -> {second_count}", flush=True)
        traces = []
        if args.phase in {"all", "dev"}:
            for strategy in config["strategies"]:
                for q in questions:
                    if q["split"] != "dev":
                        continue
                    filters = q.get("filter", {}) if config["strategies"][strategy]["filter"] else {}
                    t0 = time.perf_counter()
                    hits = store.search(strategy, embedder.embed_query(q["question"]), 3, filters)
                    traces.append({**evaluate_query(q, hits), "strategy": strategy,
                                   "applied_filter": filters, "retrieval_seconds": time.perf_counter() - t0})
            dev_metrics = summarize(traces)
            winner = sorted(config["strategies"], key=lambda s: (-dev_metrics[f"{s}/dev"]["hit3"],
                -dev_metrics[f"{s}/dev"]["hit1"], resources[s]["chunk_count"], s))[0]
            selection = {"selected_strategy": winner, "rule": config["selection_rule"],
                         "hashes": hashes, "dev_metrics": dev_metrics,
                         "selected_at_utc": datetime.now(timezone.utc).isoformat(),
                         "test_evaluated_before_selection": False}
            write_json(output / "selection.json", selection)
            write_jsonl(output / "traces_dev.jsonl", traces)
            print(f"Frozen dev selection: {winner}", flush=True)
        if args.phase in {"all", "test"}:
            selection = json.loads((output / "selection.json").read_text())
            if selection["hashes"] != hashes:
                raise ValueError("Dev selection does not match frozen inputs")
            if not traces:
                traces = [json.loads(line) for line in (output / "traces_dev.jsonl").read_text(encoding="utf-8").splitlines()]
            test_traces = []
            for strategy in config["strategies"]:
                for q in questions:
                    if q["split"] != "test":
                        continue
                    filters = q.get("filter", {}) if config["strategies"][strategy]["filter"] else {}
                    t0 = time.perf_counter()
                    hits = store.search(strategy, embedder.embed_query(q["question"]), 3, filters)
                    test_traces.append({**evaluate_query(q, hits), "strategy": strategy,
                                        "applied_filter": filters, "retrieval_seconds": time.perf_counter() - t0})
            traces += test_traces
            write_jsonl(output / "traces_test.jsonl", test_traces)
        write_jsonl(output / "traces.jsonl", traces)
        write_json(output / "metrics.json", summarize(traces))
        write_json(output / "resources.json", resources)
        export_audits(output, pages, chunks_by_strategy, traces)
        packages = ["fastembed", "qdrant-client", "onnxruntime", "tokenizers", "numpy", "pypdf", "psycopg"]
        write_json(output / "run_info.json", {"completed_at_utc": datetime.now(timezone.utc).isoformat(),
            "python": sys.version, "platform": platform.platform(),
            "packages": {p: importlib.metadata.version(p) for p in packages},
            "model": embedder.model_name, "dimensions": embedder.dimensions,
            "query_processing": "FastEmbed 0.6.1 query_embed/passage_embed; raw English text without added prefix; ONNX normalized embeddings",
            "model_initialization_seconds": initialization_seconds,
            "elapsed_seconds": time.perf_counter() - started,
            "store": config["store"], "search": "exact cosine", "hashes": hashes,
            "api_cost_usd": 0, "cost_scope": "API only; electricity/hardware/network not measured",
            "human_audit_status": "Pending student verification; exported fields intentionally blank",
            "command": f"python -m src.run --phase {args.phase}"})
        print(json.dumps(summarize(traces), indent=2), flush=True)
    finally:
        store.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default=str(ROOT / "starter/config.json"))
    parser.add_argument("--output", default=str(ROOT / "results"))
    parser.add_argument("--phase", choices=["all", "validate", "dev", "test"], default="all")
    args = parser.parse_args()
    output = Path(args.output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(filename=output / "pipeline.log", level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s %(message)s", encoding="utf-8")
    try:
        execute(args, output)
    except Exception:
        logging.exception("Pipeline failed; no mock fallback used")
        raise


if __name__ == "__main__":
    main()
