# Corpus: Python Tutorial 3.12.0

Nguồn cố định: CPython tag `v3.12.0`, 10 chương Tutorial. Bản gốc RST và giấy phép nằm trong [raw](raw/). Chỉ lưu tài liệu công khai được PSF cấp phép; không dùng dữ liệu cá nhân.

- [manifest.json](manifest.json): URL nguồn, giấy phép, ngày tải thực tế, SHA-256, ranh giới và số ký tự từng đơn vị.
- [pages.jsonl](pages.jsonl): 77 đơn vị, tổng 196.826 ký tự nội dung, không chồng lặp. Mỗi đơn vị ≥1.500 ký tự, mục tiêu 2.400 và ưu tiên ranh giới đoạn. Đây là đơn vị text theo GUIDE, không phải 77 trang PDF.
- Metadata `chapter` lấy từ tên chương gốc; `version=3.12.0` từ tag nguồn; `language=en` từ tài liệu gốc.
- `source_char_start/end` tính trên toàn chương sau chuẩn hóa; `char_start/end` của chunk tính trong đơn vị nguồn.
- Chuẩn hóa NFC, khoảng trắng, bỏ target/index/ruler RST, chuyển inline role thành text. Giữ phần lớn prose và code nhưng bỏ thụt đầu dòng: đoạn code phục vụ retrieval, không dùng làm mã có thể chạy. Một số dấu RST/comment biên tập vẫn còn và có thể gây nhiễu.
- Không có OCR/PDF trong corpus này. Manifest ghi `physical_pages=null`; không có file hoặc trang lỗi khi chuẩn bị corpus.

Từ root:

```powershell
# Dùng bản gốc đã lưu:
python starter/scripts/prepare_corpus.py
# Tải lại đúng tag nếu cần mạng:
python starter/scripts/prepare_corpus.py --download
```

Tái tạo corpus thay đổi thời điểm truy cập trong manifest nhưng phải giữ nguyên checksum pages.jsonl. Không chỉnh nguồn/câu hỏi sau khi xem test rồi báo đó là holdout mới.
