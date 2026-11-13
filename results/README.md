# Kết quả thực chạy

- `frozen_plan.json`: checksum corpus/benchmark/config, split và tiêu chí trước retrieval.
- `selection.json`: chọn B từ dev, lưu trước truy vấn test.
- `traces_dev.jsonl` / `traces_test.jsonl` / `traces.jsonl`: đủ 60 truy vấn, 180 kết quả top-3, text/score/metadata/gold/nhãn hit tự động.
- `metrics.json`: Hit@1 và Evidence Hit@3 riêng dev/test.
- `resources.json`: chunk/token/time, chi phí API, kiểm tra nạp lại.
- `chunks_A/B/C.jsonl`: snapshot các chunk đã ingest.
- `run_info.json`: phiên bản thực tế và thời điểm chạy. `pipeline.log` giữ cả lỗi tải model do mạng bị chặn ở lần đầu; không thay bằng mock.
- `coherence_samples.jsonl`: 10 vị trí cố định × 3 strategy, văn bản chunk và source context.
- `grounding_samples.jsonl`: 5 test × 3 strategy, toàn bộ top-3.
- `metadata_audit.csv`: 45 kết quả test, đối chiếu metadata/offset tự động; cột human để trống.
- `ai_coherence_review.csv`, `ai_grounding_review.csv`: nhận xét của Codex sau khi đọc text, có điểm và lý do; **không phải nhãn thủ công đã được học viên xác nhận**.
- `audit_summary.json`: tổng hợp nhãn AI và metadata tự động, tách rõ provenance.
- `equivalent_evidence_review.json` / `metrics_ai_reviewed.json`: audit AI bổ sung cho evidence tương đương của q07/q13; giữ nguyên gold/trace/metric gốc, cần học viên xác nhận.
- `reproducibility_check.json`: chạy lại toàn bộ sau model lock, đối chiếu 60 query, top-3 và metric với lần đo gốc.
- `requirements-lock.txt`: phiên bản thư viện thực tế của môi trường Windows/Python 3.9.7 dùng lần chạy này.

Chỉ điền các cột `human_*`/`reviewer` sau khi học viên tự đọc mẫu và kiểm chứng. Không đổi tên nhãn AI thành nhãn của học viên. Nếu làm lại benchmark, dùng `--output results/new_run` để không ghi đè các mẫu human đã chấm.
