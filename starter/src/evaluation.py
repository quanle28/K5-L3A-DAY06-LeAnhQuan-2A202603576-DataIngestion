"""Strict single-chunk evidence retrieval; never infer human audit labels."""
from __future__ import annotations

from collections import defaultdict
from typing import Any
from .ingestion import normalize_text


def canonical(text: str) -> str:
    return " ".join(normalize_text(text).split())


def gold_options(question: dict[str, Any]) -> list[dict[str, Any]]:
    primary = {"document_id": question["gold_source_id"], "page": question["gold_page"],
               "evidence_quote": question["evidence_quote"]}
    return [primary, *question.get("alternative_gold", [])]


def evidence_hit(question: dict[str, Any], hit: dict[str, Any]) -> bool:
    return any(hit["document_id"] == gold["document_id"] and hit["page"] == gold["page"]
               and canonical(gold["evidence_quote"]) in canonical(hit["text"])
               for gold in gold_options(question))


def evaluate_query(question: dict[str, Any], hits: list[dict[str, Any]]) -> dict[str, Any]:
    scored = [{**hit, "evidence_hit": evidence_hit(question, hit)} for hit in hits[:3]]
    return {"question_id": question["id"], "split": question["split"],
            "question": question["question"], "filter_input": question.get("filter", {}),
            "expected_answer": question["expected_answer"], "gold": gold_options(question),
            "hit1": bool(scored and scored[0]["evidence_hit"]),
            "hit3": any(hit["evidence_hit"] for hit in scored), "hits": scored}


def summarize(traces: list[dict[str, Any]]) -> dict[str, Any]:
    grouped = defaultdict(list)
    for trace in traces:
        grouped[(trace["strategy"], trace["split"])].append(trace)
    output = {}
    for (strategy, split), rows in sorted(grouped.items()):
        n = len(rows)
        output[f"{strategy}/{split}"] = {"strategy": strategy, "split": split, "n": n,
            "hit1_count": sum(t["hit1"] for t in rows), "hit3_count": sum(t["hit3"] for t in rows),
            "hit1": sum(t["hit1"] for t in rows) / n, "hit3": sum(t["hit3"] for t in rows) / n}
    return output
