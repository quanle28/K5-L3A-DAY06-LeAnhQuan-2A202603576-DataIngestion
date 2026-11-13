# Pipeline Python Tutorial — BGE + Qdrant

Pipeline đã hiện thực đầy đủ tại src/. Backend mặc định Qdrant persistent, embedding BGE thật chạy CPU, không cần key/Docker. Xem [README gốc dự án](../README.md) để cài và tái lập.

Từ thư mục starter, sau khi cài requirements.txt:

~~~powershell
..\.venv-lab\Scripts\python.exe -m src.run
~~~

Kết quả mặc định ở ../results; nên dùng --output ../results/reproduced khi chạy lại để giữ nguyên lần đo và nhãn audit. Cấu hình trong config.json, model revision/checksum trong model_lock.json.

- ingestion.py: Unicode/whitespace, đọc PDF có log trang rỗng và đọc corpus JSONL.
- chunking.py: fixed overlap và gom đoạn; ID/offset ổn định.
- embeddings.py: FastEmbed ONNX thật; khóa model và cache theo revision; không mock fallback.
- store.py: Qdrant persistent exact cosine; lọc metadata, upsert/xóa stale; PostgreSQL adapter tùy chọn.
- evaluation.py: full evidence trong một chunk, đúng nguồn/trang, alternative gold, tổng hợp dev/test.
- run.py: validate/freeze, ingest ba cấu hình, kiểm tra nạp lại, chọn dev trước test, trace/metrics/audit.
- search.py: CLI query vào index đã lưu.
- scripts/prepare_corpus.py: tái tạo corpus từ nguồn RST có giấy phép.
- scripts/build_benchmark.py: tái tạo benchmark đã soạn; không tự chạy trong pipeline.
- scripts/finalize_report.py: kết xuất báo cáo/artifacts AI của lần đo gốc; phần nhận xét trong report_template.md.

## PostgreSQL tùy chọn

docker-compose.yml/init.sql/check_setup.py giữ lựa chọn PostgreSQL + pgvector của đề. Nếu dùng, đổi store thành pgvector trong bản sao config, cung cấp DATABASE_URL qua starter/.env, cài Docker và chạy setup theo cấu hình Compose. API key không cần vì embedding vẫn local.

Backend PostgreSQL chưa được integration test trên máy này. Kết quả đã công bố dùng Qdrant; không đổi backend rồi coi là cùng thí nghiệm. Khi đổi config phải dùng --output mới. Không commit .env.
