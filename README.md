# Day 06 — Python Tutorial Data Ingestion

Bài của **Le Anh Quan — 2A202603576 — L3A**. Đã triển khai pipeline và chạy benchmark thật trên **77 đơn vị nội dung**, **20 câu hỏi (15 dev / 5 test)**, **3 cấu hình A/B/C**.

Dùng BGE 384 chiều chạy CPU và Qdrant lưu trên đĩa, không cần API key hoặc Docker. **B được chọn bằng dev trước khi chạy test.**

| Cấu hình | Dev Hit@1 | Dev Evidence Hit@3 | Test Hit@1 | Test Evidence Hit@3 | Chunk |
|---|---|---|---|---|---|
| A — fixed 500, overlap 50 | 5/15 | 10/15 | 3/5 | 4/5 | 472 |
| B — paragraph tối đa 900 | 9/15 | 12/15 | 4/5 | 5/5 | 281 |
| C — B + filter chapter | 9/15 | 12/15 | 4/5 | 5/5 | 281 |

Đây là metric tự động strict với quote đã chốt. Rà soát AI phát hiện nguồn tương đương cho q07/q13; xem [metric bổ sung](results/metrics_ai_reviewed.json) và [báo cáo](report/individual/2A202603576_LeAnhQuan.md). Nhãn coherence/grounding là **AI đề xuất, chưa phải audit thủ công được học viên xác nhận**. Các trường human còn trống để học viên tự kiểm chứng trước khi nộp.

## Cài đặt và chạy

Thực tế đã kiểm tra trên Windows, Python 3.9.7. Có thể tạo môi trường Python 3.11 riêng; dependency lock lưu đúng môi trường lần đo tại results/requirements-lock.txt. Dùng môi trường .venv-lab vì .venv cũ trỏ tới Python không còn truy cập được.

Từ thư mục gốc, PowerShell:

~~~powershell
python -m venv .venv-lab
.\.venv-lab\Scripts\python.exe -m pip install -r starter/requirements.txt

# Không cần tải lại corpus: nguồn được cấp phép đã có trong data/raw.
.\.venv-lab\Scripts\python.exe starter/scripts/prepare_corpus.py

# Kiểm thử
.\.venv-lab\Scripts\python.exe -m unittest discover -s tests -v

# Chạy lại vào thư mục riêng để giữ kết quả gốc và nhãn đã chấm
Push-Location starter
..\.venv-lab\Scripts\python.exe -m src.run --output ../results/reproduced
Pop-Location
~~~

Lần đầu cần mạng tải model ONNX khoảng 67 MB. Model được khóa revision và kiểm tra SHA-256 tại [model_lock.json](starter/model_lock.json); khi đã có file local, không cần mạng. Không có fallback vector giả. .cache/models chứa model, .cache/embeddings.json chứa cache vector, .cache/qdrant chứa collections bền vững. Không commit các thư mục này.

Có thể chạy từng giai đoạn từ starter:

~~~powershell
..\.venv-lab\Scripts\python.exe -m src.run --phase validate --output ../results/reproduced
..\.venv-lab\Scripts\python.exe -m src.run --phase dev --output ../results/reproduced
..\.venv-lab\Scripts\python.exe -m src.run --phase test --output ../results/reproduced
~~~

validate kiểm tra ≥30 đơn vị, độ dài, manifest/checksum, evidence, split/filter rồi ghi frozen plan. dev chọn cấu hình và lưu selection trước test. Nếu checksum corpus/benchmark/config thay đổi, pipeline từ chối dùng lại frozen plan: cần thư mục kết quả mới và khai báo thí nghiệm mới. Không chạy đồng thời hai tiến trình dùng cùng Qdrant local directory.

## Demo truy xuất

Từ starter, sau khi chạy pipeline:

~~~powershell
..\.venv-lab\Scripts\python.exe -m src.search "Which three sources initialize sys.path for module lookup?" --strategy B
..\.venv-lab\Scripts\python.exe -m src.search "Which variables are shared by all instances?" --strategy C --chapter classes
~~~

Kết quả trả top-3 với score cosine, text, source/page/chapter và offsets. Query không dùng gold answer/source.

## Dữ liệu và artifacts

- [Corpus/manifest/giấy phép](data/README.md): 10 chương CPython v3.12.0, 77 đơn vị text ≥1.500 ký tự; không phải trang PDF.
- [Benchmark](benchmark/README.md): 20 câu, split theo chương và 3 câu filter.
- [Cấu hình](starter/config.json): A fixed; B paragraph; C giống B và chỉ bật filter theo input.
- [Kết quả và audit](results/README.md): 60 trace truy vấn, 180 kết quả top-3, metrics, chunks, tài nguyên, log, mẫu human và nhãn AI riêng.
- [Nhật ký thí nghiệm](artifacts/experiment_log.csv).
- [Báo cáo cá nhân](report/individual/2A202603576_LeAnhQuan.md).
- [Đề bài gốc](ASSIGNMENT.md), [rubric](RUBRIC.md), [quy tắc](RULES.md), [hướng dẫn nộp](SUBMISSION.md).

B/C nạp lại không trùng; stale chunks bị xóa khi ingest snapshot mới. 7 unittest đã qua, có kiểm tra persistence/filter/evidence/offset và source validation. API cost = 0 USD, chưa tính điện/phần cứng/mạng. A–B thay cả phương pháp và size/overlap, không kết luận riêng ảnh hưởng của phương pháp; B–C chỉ thay filter. Test nhỏ, chưa suy rộng ngoài corpus tiếng Anh này.

PostgreSQL + pgvector adapter được bổ sung ở starter/src/store.py nhưng **chưa integration test**. Backend mặc định đã kiểm chứng là Qdrant; không cần thiết lập PostgreSQL để tái lập kết quả trên.

## Trước khi nộp

Học viên cần xác nhận tên có dấu/lớp trong [STUDENT.md](STUDENT.md), đọc mẫu audit và ghi nhãn human thực sự. Code/báo cáo chưa commit hoặc push; chưa gửi link cho giảng viên. Các con số trong báo cáo lấy từ lần chạy thực tế, không thay nhãn AI thành nhãn người.

Nguồn giấy phép: [Python PSF](https://docs.python.org/3.12/license.html), [BGE MIT](https://huggingface.co/BAAI/bge-small-en-v1.5). Raw sources và giấy phép được giữ trong data/raw.
