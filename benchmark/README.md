# Benchmark Python Tutorial 3.12.0

20 câu tiếng Anh, phù hợp model BGE tiếng Anh và corpus tiếng Anh. Câu do Codex hỗ trợ soạn; evidence được kiểm tra bằng substring sau chuẩn hóa, không giả nhận là nhãn thủ công của học viên.

- Dev: q01–q15, chương introduction/controlflow/datastructures/inputoutput/errors.
- Test: q16–q20, chương modules/classes/venv; tách theo chương trước lần retrieval đầu tiên.
- Metadata filter: q05 (controlflow), q08 (datastructures), q18 (classes, test). Phạm vi được nêu ngay trong câu hỏi, không suy từ gold source.
- Các chương stdlib/stdlib2 làm distractor. Các chương có khái niệm giao nhau nên split theo chương không loại bỏ hoàn toàn nguy cơ rò rỉ ngữ nghĩa.
- Tiêu chí chọn: dev Hit@3 cao nhất, rồi Hit@1, ít chunk, cuối cùng tên strategy theo thứ tự chữ cái. Quy tắc và checksum được ghi trong results/frozen_plan.json trước retrieval.
- Evidence Hit: cùng document_id, page và đủ toàn bộ quote trong **một** chunk; cho phép alternative_gold trong schema. Không ghép nhiều chunk để nâng metric bắt buộc.
- Source page là đơn vị text theo manifest, không phải trang PDF. Có thể đọc nguồn RST hoặc pages.jsonl để kiểm chứng.
- Nếu chỉnh corpus/câu hỏi/config sau khi chạy: dùng thư mục kết quả mới và khai báo thí nghiệm mới; không trình bày test đã xem là holdout độc lập.

Tái tạo câu hỏi: từ root chạy `python starter/scripts/build_benchmark.py`. Không tự động chạy lại script này trong pipeline.
