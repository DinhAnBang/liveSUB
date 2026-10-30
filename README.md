# liveSub

Phụ đề trực tiếp cho Windows, dùng faster-whisper để nhận dạng tiếng nói và
Argos Translate hoặc Ollama để dịch trên máy. Ứng dụng không dùng Azure hay
OpenAI API và không cần API key.

## Chạy ứng dụng

Cần Python 3.12 và Internet ở lần cài đặt hoặc tải model đầu tiên. Mở PowerShell
trong thư mục dự án:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe liveSUB.py
```

Chọn `system` để thu tiếng phát ra từ máy, `mic` để thu micro, hoặc `both` để
trộn hai nguồn. `Ctrl+Shift+S` bật hoặc dừng phiên.

Mặc định ứng dụng dùng Whisper `small` trên CPU và Argos để dịch. Lần đầu dùng
cặp ngôn ngữ mới, Argos sẽ tải gói dịch miễn phí. Nhật → Việt có thể đi qua
tiếng Anh. Nếu muốn dùng Ollama, cài Ollama riêng, tải model cục bộ (ví dụ
`ollama pull qwen3:4b`), rồi chọn `ollama` trong giao diện. Chế độ Ollama chỉ
gửi yêu cầu tới `127.0.0.1`.

Model tải về nằm trong `models/`. Cài đặt cá nhân nằm trong
`liveSUB_settings.json`; file này không chứa API key. Lịch sử phụ đề chỉ giữ
trong cửa sổ của phiên hiện tại.

## Cấu trúc source

```text
liveSUB.py             Điểm chạy
livesub/settings.py    Cài đặt và đường dẫn
livesub/session.py     Điều phối phiên và hàng đợi sự kiện
livesub/audio/         Thiết bị, thu âm, VAD, chia đoạn
livesub/engines/       Whisper, Argos, Ollama
livesub/ui/            Cửa sổ chính và phụ đề nổi
```

Luồng xử lý: giao diện tạo cài đặt phiên → thu âm → chia đoạn → nhận dạng →
dịch → gửi kết quả về giao diện. Tkinter chỉ được cập nhật trên luồng giao diện.
