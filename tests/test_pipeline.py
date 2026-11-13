"""Regression checks for boundaries, evidence semantics and real persistent vector-store behavior."""
from __future__ import annotations
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "starter"))
from src.chunking import by_paragraph, fixed_size
from src.evaluation import evaluate_query, summarize
from src.ingestion import normalize_text, load_pages
from src.models import DocumentPage, Chunk
from src.run import validate_inputs
from src.store import QdrantStore


class ChunkTests(unittest.TestCase):
    def test_every_nonspace_character_covered_and_offsets_exact(self):
        text = normalize_text("Heading\n\n" + "First complete sentence. " * 40 + "\n\n" +
                              "x" * 200 + "\n\nFinal paragraph.")
        page = DocumentPage("d", "source", 1, text, {"chapter": "one"})
        for chunks in [fixed_size(page, 150, 20), by_paragraph(page, 150)]:
            covered = set()
            for chunk in chunks:
                start, end = chunk.metadata["char_start"], chunk.metadata["char_end"]
                self.assertEqual(chunk.text, text[start:end])
                self.assertLessEqual(len(chunk.text), 150)
                self.assertEqual(chunk.metadata["chapter"], "one")
                covered.update(range(start, end))
            self.assertTrue(all(i in covered for i, char in enumerate(text) if not char.isspace()))
        self.assertEqual(by_paragraph(page, 150), by_paragraph(page, 150))

    def test_invalid_boundaries_and_empty_page(self):
        page = DocumentPage("d", "s", 1, "")
        for size, overlap in [(0, 0), (10, 10), (10, -1)]:
            with self.assertRaises(ValueError):
                fixed_size(page, size, overlap)
        self.assertEqual(by_paragraph(page, 10), [])

    def test_unicode_and_paragraphs(self):
        self.assertEqual(normalize_text(" e\u0301\r\n\r\n a\u00a0b \t"), "é\n\na b")


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.q = {"id": "q", "split": "dev", "question": "why", "expected_answer": "answer",
                  "gold_source_id": "d", "gold_page": 2, "evidence_quote": "full evidence condition",
                  "alternative_gold": [{"document_id": "e", "page": 4, "evidence_quote": "alternative proof"}]}

    def hit(self, document="d", page=2, text="full evidence condition"):
        return {"document_id": document, "page": page, "text": text}

    def test_wrong_page_and_partial_evidence_are_not_hits(self):
        trace = evaluate_query(self.q, [self.hit(page=3), self.hit(text="full evidence"),
                                       self.hit(text="condition")])
        self.assertFalse(trace["hit1"])
        self.assertFalse(trace["hit3"])

    def test_alternative_gold_and_split_aggregation(self):
        trace = evaluate_query(self.q, [self.hit(page=3), self.hit("e", 4, "alternative\nproof")])
        self.assertFalse(trace["hit1"])
        self.assertTrue(trace["hit3"])
        summary = summarize([{**trace, "strategy": "A"}])["A/dev"]
        self.assertEqual((summary["hit1_count"], summary["hit3_count"], summary["n"]), (0, 1, 1))


class PersistentStoreTests(unittest.TestCase):
    # Handcrafted vectors test storage semantics only; benchmark uses real BGE vectors.
    def test_reopen_filter_idempotency_and_stale_chunk_removal(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            store = QdrantStore(directory, 3)
            first = Chunk("first", "d", "s", 1, "first", {"chapter": "one"})
            second = Chunk("second", "d", "s", 2, "second", {"chapter": "two"})
            try:
                for _ in range(2):
                    store.upsert("A", [first, second], [[1, 0, 0], [0, 1, 0]])
                    self.assertEqual(store.count("A"), 2)
                hits = store.search("A", [1, 0, 0], filters={"chapter": "two"})
                self.assertEqual([h["chunk_id"] for h in hits], ["second"])
                self.assertEqual(store.search("A", [1, 0, 0], filters={"chapter": "absent"}), [])
                with self.assertRaises(ValueError):
                    store.search("A", [1, 0, 0], filters={"untrusted": "x"})
                with self.assertRaises(ValueError):
                    store.upsert("A", [first], [[float("nan"), 0, 0]])
            finally:
                store.close()
            store = QdrantStore(directory, 3)
            try:
                self.assertEqual(store.count("A"), 2)
                store.upsert("A", [second], [[0, 1, 0]])
                self.assertEqual(store.count("A"), 1)
                self.assertEqual(store.search("A", [1, 0, 0])[0]["chunk_id"], "second")
            finally:
                store.close()

    def test_full_corpus_manifest_and_gold_validation(self):
        pages = load_pages(ROOT / "data/pages.jsonl")
        questions = json.loads((ROOT / "benchmark/questions.json").read_text(encoding="utf-8"))
        manifest = json.loads((ROOT / "data/manifest.json").read_text(encoding="utf-8"))
        validate_inputs(pages, questions, manifest)
        self.assertGreaterEqual(len(pages), 30)
        self.assertEqual(sum(q["split"] == "test" for q in questions), 5)


if __name__ == "__main__":
    unittest.main()
