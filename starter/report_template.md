# Báo cáo cá nhân — Day 06: Python Tutorial Data Ingestion

- Học viên: Le Anh Quan; MSSV: 2A202603576; lớp L3A (theo tên repo; cần xác nhận cách viết tên có dấu).
- Repo: https://github.com/quanle28/K5-L3A-DAY06-LeAnhQuan-2A202603576-DataIngestion
- Thí nghiệm hoàn tất ngày 13/11/2026, khoảng 11:37 giờ Asia/Bangkok.
- Code, câu hỏi và phân tích có Codex hỗ trợ. Các nhãn audit AI chưa được học viên xác nhận; không giả nhận AI là người chấm thủ công.

## Dữ liệu và pipeline

Corpus gồm 10 chương Python Tutorial, CPython tag v3.12.0; bản RST gốc và PSF License Version 2 lưu tại [data/raw](../../data/raw/). Ví dụ code cấp phép kép PSF/0BSD. [Manifest](../../data/manifest.json) ghi URL, thời điểm truy cập, SHA-256, ranh giới và số ký tự từng đơn vị.

Có **77 đơn vị text**, tổng **196.826 ký tự**. Theo GUIDE cho nguồn không phân trang: chia tuần tự, không chồng lặp, mục tiêu 2.400 ký tự, ưu tiên hết đoạn và bảo đảm mỗi đơn vị ≥1.500 ký tự. Không gọi đây là 77 trang PDF; physical_pages là null. Không dùng format-example.json làm corpus.

Pipeline: RST → làm sạch target/index/ruler/inline role → Unicode NFC/khoảng trắng → đơn vị nguồn → chunk → semantic embedding → Qdrant persistent → cosine top-3 → trace/metric/audit. Không có OCR hoặc file lỗi trong lần chuẩn bị corpus. Chuẩn hóa bỏ thụt đầu dòng nên code phục vụ retrieval, không dùng làm ví dụ chạy được. Còn một số markup RST/comment gây nhiễu. Hàm đọc PDF được bổ sung nhưng chưa kiểm thử bằng corpus PDF thực tế.

Model **BAAI/bge-small-en-v1.5**, quantized ONNX từ qdrant/bge-small-en-v1.5-onnx-q, **384 chiều**, MIT. [Model lock](../../starter/model_lock.json) lưu revision aa8f8b060edb00e03bfdd08813a2949946c8ba55 và SHA-256 từng file. FastEmbed 0.6.1/ONNX Runtime 1.19.2 chạy CPU 2 threads, raw English query/document qua query_embed/passage_embed, không thêm prefix; cùng model giữa A/B/C. Token dài nhất A 261, B/C 429, dưới giới hạn 512 nên không có chunk bị cắt token ở lần chạy này.

Qdrant client 1.15.1 local persistent tại .cache/qdrant, collections day6_A/B/C; exact cosine. Đây là backend Qdrant chính thức, không tự viết tìm kiếm vector bằng Python/SQLite. PostgreSQL adapter là lựa chọn bổ sung, chưa chạy integration vì máy không có Docker/PostgreSQL. Môi trường thực tế Python 3.9.7/Windows; đầy đủ phiên bản tại [run_info](../../results/run_info.json) và [dependency lock](../../results/requirements-lock.txt).

Metadata: document_id/source/page giúp về đúng chương/đơn vị; chapter lấy từ tên file gốc để lọc; language=en và version=3.12.0 từ snapshot. page/offset là integer; các trường còn lại là string. source_char_start/end tính trong chương chuẩn hóa, char_start/end trong đơn vị nguồn. Không suy đoán effective_date. Filter chỉ nhận các trường cho phép, kiểu string/integer, equality.

ID chunk là hash của nguồn, trang, phương pháp, offset và text. Upsert theo UUID ổn định, xóa chunk cũ không còn trong snapshot đầy đủ. Nạp lại A **472 → 472**, B/C **281 → 281**. Kiểm thử riêng xác nhận persistence khi mở lại và xóa stale chunk khi đổi nguồn. Local mode không có transaction bao trùm toàn bộ replace; nếu tiến trình dừng giữa chừng cần chạy lại ingest đầy đủ.

## Cấu hình và benchmark

| Strategy | Chunk | Filter |
|---|---|---|
| A | Fixed 500 ký tự, overlap 50, không vượt đơn vị nguồn | Không |
| B | Gom đoạn tối đa 900 ký tự; đoạn dài tách theo câu/từ; không overlap | Không |
| C | Hoàn toàn giống B | Lọc chapter khi câu hỏi cung cấp phạm vi |

B–C chỉ thay filter. A–B thay phương pháp **và size/overlap**, nên chỉ kết luận về gói chiến lược; chưa cô lập riêng phương pháp chunking. Giữ nguyên corpus, model, store, cosine, top-k và benchmark.

[20 câu](../../benchmark/questions.json) được tạo và kiểm tra evidence tồn tại trước retrieval: q01–q15 dev; q16–q20 test, thuộc modules/classes/venv; dev thuộc introduction/controlflow/datastructures/inputoutput/errors. stdlib/stdlib2 thêm distractor. Filter: q05, q08, q18 (test). Phạm vi nêu trong câu hỏi, không lấy từ gold source/answer. Tất cả câu có đáp án trong corpus.

Quy tắc chọn: dev Evidence Hit@3, rồi dev Hit@1, rồi ít chunk, rồi tên strategy. [Frozen plan](../../results/frozen_plan.json) lưu checksum/split/quy tắc trước retrieval; [selection](../../results/selection.json) chọn **B trước khi chạy test**. Không chỉnh chiến lược dựa trên test.

## Kết quả thực chạy

Bảng là metric tự động **strict frozen-quote**: đúng document/page và chứa toàn bộ quote đã chốt trong **một chunk**. Không ghép nhiều chunk cho Hit@3.

| Strategy | Split | Hit@1 (n/N) | Evidence Hit@3 (n/N) | Chunk count | Chunk/embedding + lưu/nạp lại | API |
|---|---|---|---|---|---|---|
{{METRICS}}

Chi phí API 0 USD; chưa đo điện/phần cứng/mạng. Tổng lần chạy khoảng 99,72 giây, không gồm cài thư viện/tải model. Thời gian bảng gồm hai lần upsert để kiểm tra idempotency, chưa gồm toàn bộ khởi tạo/query. C tái sử dụng embedding cache của B nên không thể kết luận filter giúp embedding nhanh hơn. A có 216.448 ký tự/60.818 token chunk; B/C có 196.423 ký tự/54.506 token. B/C giảm 191 chunk (~40,5%), ít lặp do không overlap nhưng mỗi chunk dài hơn. C lưu collection riêng cho thí nghiệm; sản phẩm thực tế có thể dùng chung index B và bật filter khi cần.

**Bằng chứng tương đương:** đọc trace phát hiện q07 có đáp án None ở controlflow/6, q13 có bằng chứng file luôn đóng ở errors/6. Đây là nguồn hợp lệ chưa khai báo alternative, không nên coi là retrieval sai thực sự. Giữ nguyên gold và metric strict để truy vết; [6 nhãn AI review](../../results/equivalent_evidence_review.json) và [metric bổ sung](../../results/metrics_ai_reviewed.json) đề xuất A dev Hit@1 **6/15**, Hit@3 **12/15**; B/C dev Hit@1 **10/15**, Hit@3 **14/15**. Test không đổi. Đây là audit sau chạy cần học viên xác nhận, không phải điểm chấm người; không dùng để đổi lựa chọn B.

## Coherence, metadata và grounding

Các điểm coherence/grounding dưới đây do **Codex đọc text và đề xuất**; không phải nhãn thủ công đã được tác giả xác nhận. Metadata đủ/đúng là đối chiếu tự động với corpus/offset. Học viên cần đọc và điền trường human trước khi nhận đã hoàn tất yêu cầu audit thủ công.

| Strategy | Coherence AI /2 (n) | Metadata tự động đủ/đúng | Filter top-3 tuân thủ | Grounding AI số mức 0/1/2; TB |
|---|---|---|---|---|
{{AUDITS}}

Coherence chọn 10 (document_id,page) đầu theo thứ tự từ điển, anchor=750 trước khi xem điểm; chấm chunk phủ anchor cho cả A/B/C. Các vị trí đều ở classes/1–10, mẫu bị lệch về một chương. [Nguồn/chunk](../../results/coherence_samples.jsonl), [nhãn AI/lý do](../../results/ai_coherence_review.csv). A hay cắt giữa từ/câu/ví dụ. B/C giữ đoạn tốt hơn nhưng còn thiếu ngữ cảnh hoặc kết thúc trước thân class/output, nên không mặc định paragraph chunk đạt 2.

Metadata kiểm tra 5 test × 3 hits = 15 bản ghi/strategy, tổng 45. source/page/chapter/version/language/document_id và offsets đều khớp corpus. [Bảng metadata](../../results/metadata_audit.csv) có cột human còn trống. Test chỉ q18 có filter nên A/B cũng đạt 1/1 tự nhiên, chưa chứng minh không cần filter. Toàn bộ ba câu filter: A 3/3, B 2/3, C 3/3. B/q05 trả một chunk errors/5 ngoài phạm vi controlflow; C loại nó, nhưng Hit@3 vẫn bằng nhau vì B đã có evidence đúng. chapter giúp thu hẹp phạm vi; hạn chế là phải có input đúng của người dùng và chỉ kiểm tra ba câu.

Grounding đọc top-3 trên 5 test/strategy, thang 0/1/2 theo GUIDE. [Mẫu](../../results/grounding_samples.jsonl), [nhãn AI/lý do](../../results/ai_grounding_review.csv). A/q17 đủ ba nguồn sys.path khi đọc hai chunk modules/3, nên AI đề xuất grounding=2 dù single-chunk Hit@3=0. Không thay metric bắt buộc bằng multi-chunk. Đây là chất lượng bằng chứng retrieval, không phải độ chính xác câu trả lời LLM.

## Phân tích lỗi và lựa chọn

1. **A/q17, python-modules đơn vị 3**: danh sách sys.path bị cắt ở chunk thứ hai trong top-3; phần cuối nằm chunk thứ ba. Không có một chunk đủ quote nên Hit@3 thất bại. B/q17 giữ đủ danh sách ở top-1.
2. **B/C/q04, python-controlflow đơn vị 2**: câu hỏi cần break thoát vòng lặp bao trong cùng; top-3 lấy controlflow/3 (else/continue), datastructures/3 (nested comprehension), controlflow/5 (match guard). Không có câu innermost enclosing loop. Đây là lỗi xếp hạng/gói chunk thật trên dev, trong khi A hit. Chunk lớn có thể trộn ý làm vector thiếu tập trung.
3. **B/C/q16, python-modules đơn vị 3**: top-1 modules/1 giải thích tên module thông thường, chưa có trường hợp script; evidence __main__ đúng ở hạng 2 (A hạng 3). Hit@1 chưa đạt 5/5 dù Hit@3 B/C đạt 5/5.
4. **q07/q13** là gold thiếu alternative, không phải ví dụ retrieval sai; đã có audit bổ sung.

Chọn **B theo dev đã chốt**. C có ích khi cần bảo đảm phạm vi; mẫu này chưa cho thấy tăng Hit@3. Không chọn lại theo test. A có nhiều chunk/lặp và hay cắt evidence. B giữ evidence tốt hơn trong corpus này nhưng còn lỗi retrieval/ngữ cảnh. A–B là so sánh gói cấu hình; B–C mới cô lập một yếu tố filter.

## Giới hạn và hướng cải tiến

Test chỉ 5 câu, mỗi câu làm điểm thay đổi 20 điểm phần trăm; chỉ một lần đo CPU, cache và thứ tự A→B→C ảnh hưởng thời gian. Corpus tiếng Anh từ một bộ tài liệu; không suy rộng sang tiếng Việt/PDF scan. AI cùng hỗ trợ soạn/chấm nên có thiên lệch, chưa có người chấm độc lập. Split theo chương vẫn chia sẻ khái niệm. Gold ban đầu chưa đủ alternative; metric substring là proxy bảo thủ. Model quantized có thể khác bản float. Chưa đo RSS/dung lượng index hay đánh giá generation.

Khi mở rộng: coi test hiện tại là đã xem; tạo holdout mới trước thí nghiệm, bổ sung alternative gold có kiểm chứng, thêm người chấm, lấy mẫu coherence nhiều chương, giữ indentation code. So sánh A/B cùng size/overlap để cô lập phương pháp; đo cold/warm riêng, nhiều lần và RAM/dung lượng. Không điều chỉnh theo test cũ.

## Tái lập và trạng thái bài nộp

Xem [README](../../README.md) để setup/run/demo query. Đã chạy **7 unittest**: phủ ký tự không trắng/offset/Unicode, evidence thiếu/sai trang/alternative, metric theo split, persistence/filter/idempotency/xóa stale chunk, kiểm tra manifest/corpus/gold. Vector nhỏ tự đặt chỉ dùng cho unit test storage; benchmark dùng BGE thật.

Lần chạy lại toàn bộ sau khi khóa model/cache cho cùng 60 truy vấn giữ nguyên metric, lựa chọn B và thứ tự chunk top-3; sai khác score cosine tối đa khoảng 6,54×10⁻⁸. [Biên bản tái lập](../../results/reproducibility_check.json) lưu kết quả đối chiếu; không dùng lần chạy lại để tinh chỉnh theo test.

Lần tải model đầu gặp quyền symlink Windows, thư viện retry thành công; lần load tiếp bị sandbox chặn mạng, chạy lại bằng cache thật và thêm model lock/checksum. Log giữ lỗi; không fallback mock. Sau benchmark chỉ sửa mô tả query (FastEmbed không thêm prefix), khóa model/cache, thêm tài liệu/demo; không chỉnh corpus, câu hỏi hoặc A/B/C.

Học viên cần xác nhận tên có dấu/lớp, hiểu code, kiểm chứng nhãn AI và điền audit human. Repo có thay đổi local, chưa có commit chốt mới và chưa push/nộp link. Không ghi commit chưa tạo hoặc nhận đã gửi bài.

Tham khảo: [giấy phép Python](https://docs.python.org/3.12/license.html), [BGE](https://huggingface.co/BAAI/bge-small-en-v1.5), [Qdrant local](https://github.com/qdrant/qdrant-client#local-mode); nguồn và giấy phép gốc lưu trong repo.
