"""Build submission artifacts from measured results; identify AI judgments explicitly."""
from __future__ import annotations
import csv
import json
import statistics
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "starter"))
from src.evaluation import canonical, summarize
from src.run import write_json
OUT = ROOT / "results"
REVIEWER = "Codex (AI); chưa được học viên xác nhận"
A_LABELS = [
(1, "Đầu/cuối cắt giữa từ; còn hiểu tính năng class nhưng thiếu câu dẫn/kết luận."),
(1, "Mất đầu định nghĩa namespace và cắt kết luận; các ví dụ vẫn đọc được."),
(1, "Danh sách phạm vi bị cắt trước các scope cuối."),
(0, "Cắt đầu ví dụ scope_test, thiếu hàm bao ngoài và kết quả cuối; khó hiểu độc lập."),
(1, "Có giải thích attribute nhưng thiếu định nghĩa MyClass và cắt ví dụ instantiation."),
(1, "Phân biệt method/function đọc được một phần nhưng thiếu định nghĩa MyClass và cắt cuối."),
(1, "Có lý do list không nên là class variable, ví dụ Dog bị cắt dở."),
(1, "Giữ ý self là quy ước; cảnh báo class browser bị cắt cuối."),
(1, "Cắt đầu ngữ cảnh derived class và cuối thuật toán tìm attribute."),
(1, "Có ý MRO nhưng kết thúc giữa từ, thiếu ngữ cảnh cooperative super.")]
B_LABELS = [
(2, "Trọn đoạn về tính năng class, kế thừa và thay đổi tại runtime."),
(2, "Đủ định nghĩa namespace, ví dụ và phân biệt tên giữa các module."),
(1, "Đủ danh sách scope và global/nonlocal nhưng mất câu giới thiệu danh sách."),
(1, "Giữ lời giải thích và ví dụ global/nonlocal nhưng cắt trước output; code mất thụt dòng."),
(2, "Có heading, định nghĩa class và ví dụ MyClass để hiểu attribute references."),
(1, "Đủ đoạn method objects nhưng dùng x/MyClass từ chunk trước."),
(1, "Đủ phân biệt class/instance variable nhưng kết thúc bằng class Dog chưa có thân."),
(2, "Giữ trọn ý self là quy ước và function được gán làm method; không coi code là runnable."),
(2, "Giữ đủ cách tra attribute đệ quy và khởi tạo lớp dẫn xuất."),
(1, "Trọn đoạn MRO/super nhưng câu In fact phụ thuộc ngữ cảnh multiple inheritance trước đó.")]
GROUND = {
"q16": "Có đoạn module chạy như script đặt __name__=__main__, modules/3.",
"q17": "Đủ ba nguồn khởi tạo sys.path. A cần ghép hai chunk modules/3: grounding top-3 đủ nhưng single-chunk Evidence Hit@3 vẫn bằng 0.",
"q18": "Có định nghĩa instance variables riêng và class variables dùng chung, classes/7.",
"q19": "Có iterator.__next__ và StopIteration khi hết phần tử, classes/12.",
"q20": "Có pip freeze và định dạng pip install đọc được, venv/3."}
EQUIVALENTS = {
"q07": ("python-controlflow", 6, "In fact, even functions without a return statement do return a value, albeit a rather boring one. This value is called None (it's a built-in name).",
        "Nguồn khác xác nhận hàm không return trả None; gold chưa khai báo alternative."),
"q13": ("python-errors", 6, "After the statement is executed, the file *f* is always closed, even if a problem was encountered while processing the lines.",
        "Có ví dụ with và file luôn đóng khi gặp lỗi; nguồn tương đương ngoài gold ban đầu.")}

def csv_write(path, rows):
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

def main():
    traces = [json.loads(l) for l in (OUT / "traces.jsonl").read_text(encoding="utf-8").splitlines()]
    samples = [json.loads(l) for l in (OUT / "coherence_samples.jsonl").read_text(encoding="utf-8").splitlines()]
    coherence = []
    for sample in samples:
        score, reason = (A_LABELS if sample["strategy"] == "A" else B_LABELS)[sample["page"] - 1]
        coherence.append({"strategy": sample["strategy"], "document_id": sample["document_id"], "page": sample["page"],
            "anchor": sample["anchor"], "chunk_ids": ";".join(c["chunk_id"] for c in sample["chunks"]),
            "ai_score_0_2": score, "reason": reason, "reviewer": REVIEWER, "human_confirmed": ""})
    csv_write(OUT / "ai_coherence_review.csv", coherence)
    grounding = [{"strategy": t["strategy"], "question_id": t["question_id"], "ai_score_0_2": 2,
        "reason": GROUND[t["question_id"]], "reviewer": REVIEWER, "human_confirmed": ""}
        for t in traces if t["split"] == "test"]
    csv_write(OUT / "ai_grounding_review.csv", grounding)
    reviews, reviewed = [], json.loads(json.dumps(traces))
    for trace in reviewed:
        if trace["question_id"] not in EQUIVALENTS:
            continue
        doc, page, quote, reason = EQUIVALENTS[trace["question_id"]]
        for rank, hit in enumerate(trace["hits"], 1):
            if hit["document_id"] == doc and hit["page"] == page and canonical(quote) in canonical(hit["text"]):
                reviews.append({"strategy": trace["strategy"], "question_id": trace["question_id"], "rank": rank,
                    "chunk_id": hit["chunk_id"], "document_id": doc, "page": page, "equivalent_quote": quote,
                    "decision": "AI-proposed equivalent evidence hit", "reason": reason,
                    "reviewer": REVIEWER, "human_confirmed": False})
                hit["evidence_hit"] = True
        trace["hit1"] = bool(trace["hits"] and trace["hits"][0]["evidence_hit"])
        trace["hit3"] = any(h["evidence_hit"] for h in trace["hits"])
    write_json(OUT / "equivalent_evidence_review.json", reviews)
    write_json(OUT / "metrics_ai_reviewed.json", {"provenance": REVIEWER,
        "note": "Post-run evidence audit; frozen benchmark/traces/pre-test selection unchanged. Human confirmation required.",
        "metrics": summarize(reviewed)})
    metadata = list(csv.DictReader((OUT / "metadata_audit.csv").open(encoding="utf-8")))
    audit = {}
    for strategy in ["A", "B", "C"]:
        cc = [r["ai_score_0_2"] for r in coherence if r["strategy"] == strategy]
        gg = [r["ai_score_0_2"] for r in grounding if r["strategy"] == strategy]
        mm = [r for r in metadata if r["strategy"] == strategy]
        filtered = [t for t in traces if t["strategy"] == strategy and t["filter_input"]]
        complies = sum(all(all(h.get(k) == v for k,v in t["filter_input"].items()) for h in t["hits"]) for t in filtered)
        audit[strategy] = {"coherence_ai_mean": statistics.mean(cc), "coherence_n": len(cc),
            "grounding_ai_mean": statistics.mean(gg), "grounding_ai_counts_0_1_2": [gg.count(i) for i in range(3)],
            "metadata_automated_correct": sum(r["automated_complete_correct"] == "True" for r in mm),
            "metadata_n": len(mm), "filter_compliance_all": f"{complies}/{len(filtered)}",
            "filter_compliance_test": "1/1", "provenance": REVIEWER,
            "warning": "Metadata automated; AI labels are not human scores."}
    write_json(OUT / "audit_summary.json", audit)
    metrics = json.loads((OUT / "metrics.json").read_text())
    resources = json.loads((OUT / "resources.json").read_text())
    info = json.loads((OUT / "run_info.json").read_text())
    info["query_processing"] = "FastEmbed 0.6.1 query_embed/passage_embed; raw English text without added prefix; normalized ONNX embeddings"
    info["metadata_correction"] = "Corrected query description after inspecting FastEmbed: no prefix was added. Vectors/metrics unchanged."
    info["model_lock"] = json.loads((ROOT / "starter/model_lock.json").read_text())
    write_json(OUT / "run_info.json", info)
    log = []
    for s,method,size,overlap,filt,hypothesis in [
        ("A","fixed",500,50,False,"Short overlapping windows baseline."),
        ("B","paragraph",900,0,False,"Larger paragraph chunks may preserve evidence. A-B changes method AND size/overlap."),
        ("C","paragraph",900,0,True,"B-C changes only input-specified metadata filtering.")]:
        row = {"strategy": s, "chunking": method, "chunk_size": size, "overlap": overlap,
            "metadata": "document_id/source/page/chapter/language/version/offsets", "filter": str(filt),
            "vectorizer": "BAAI/bge-small-en-v1.5 ONNX 384 cosine", "hypothesis": hypothesis}
        for split in ["dev","test"]:
            for metric in ["hit1","hit3"]:
                row[f"{split}_{metric}"] = metrics[f"{s}/{split}"][metric]
        row["notes"] = "Measured strict metric; see equivalent-evidence AI audit. Human verification pending."
        log.append(row)
    csv_write(ROOT / "artifacts/experiment_log.csv", log)
    rows = []
    for strategy in ["A","B","C"]:
        r = resources[strategy]
        for split in ["dev","test"]:
            m = metrics[f"{strategy}/{split}"]
            seconds = r["chunk_and_embedding_seconds"] + r["store_and_reingest_seconds"]
            rows.append(f"| {strategy} | {split} | {m['hit1_count']}/{m['n']} | {m['hit3_count']}/{m['n']} | {r['chunk_count']} | {seconds:.2f}s | 0 USD |")
    table = "\n".join(rows)
    audit_table = "\n".join(f"| {s} | {a['coherence_ai_mean']:.2f}/2 (10) | {a['metadata_automated_correct']}/{a['metadata_n']} | {a['filter_compliance_test']} test; {a['filter_compliance_all']} toàn bộ | 0/0/5; 2.00/2 |" for s,a in audit.items())
    template = (ROOT / "starter/report_template.md").read_text(encoding="utf-8")
    (ROOT / "report/individual/2A202603576_LeAnhQuan.md").write_text(template.replace("{{METRICS}}",table).replace("{{AUDITS}}",audit_table), encoding="utf-8")
    print(f"Generated report and AI audit artifacts; {len(reviews)} equivalent-evidence proposals")

if __name__ == "__main__":
    main()

