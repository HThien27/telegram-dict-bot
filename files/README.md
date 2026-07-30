# Telegram Dictionary Bot

Bot tra từ điển Anh-Việt / Việt-Anh chạy trên Vercel (Python Serverless Functions).

## Cấu trúc project

```
telegram-dict-bot/
├── app.py             # Flask app chứa toàn bộ logic bot (entrypoint để Vercel tự nhận diện)
├── requirements.txt   # Thư viện cần cài
└── README.md
```

## Các bước triển khai

### 1. Test thử ở local (không bắt buộc, nhưng nên làm để chắc code chạy đúng)

```bash
cd telegram-dict-bot
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
export BOT_TOKEN="123456:ABC-DEF..."   # Windows: set BOT_TOKEN=...
python app.py
```

(Bạn có thể tự thêm `app.run(debug=True)` ở cuối `app.py` khi test local, nhớ xoá/không ảnh hưởng khi deploy lên Vercel vì Vercel tự quản lý việc chạy server.)

### 2. Đẩy code lên GitHub

Vercel deploy dễ nhất khi liên kết với 1 repo GitHub:

```bash
git init
git add .
git commit -m "Init telegram dictionary bot"
# tạo repo mới trên GitHub rồi push lên
git remote add origin <link-repo-cua-ban>
git push -u origin main
```

### 3. Deploy lên Vercel

1. Vào [vercel.com](https://vercel.com) → **New Project** → chọn repo vừa push.
2. Vercel sẽ tự nhận diện đây là Python project (nhờ có `requirements.txt` + entrypoint `app.py`).
3. Trong phần **Environment Variables**, thêm biến:
   - `BOT_TOKEN` = token bot bạn lấy từ BotFather
4. Bấm **Deploy**. Sau khi xong, bạn sẽ có 1 URL dạng: `https://ten-project-cua-ban.vercel.app`

### 4. Đăng ký Webhook cho Telegram

Đây là bước để "báo" cho Telegram biết mỗi khi có tin nhắn thì gửi tới đâu. Chạy lệnh sau (thay `BOT_TOKEN` và URL Vercel của bạn):

```bash
curl "https://api.telegram.org/bot<BOT_TOKEN>/setWebhook?url=https://ten-project-cua-ban.vercel.app/api/webhook"
```

Nếu thấy kết quả trả về `"ok":true` là thành công.

Kiểm tra webhook đã đăng ký đúng chưa:

```bash
curl "https://api.telegram.org/bot<BOT_TOKEN>/getWebhookInfo"
```

### 5. Test bot

Mở Telegram, tìm bot của bạn, gõ `/start`, rồi thử:
- Gõ `hello` → bot trả phiên âm + nghĩa tiếng Việt + link nghe phát âm
- Gõ `xin chào` → bot dịch sang tiếng Anh

## Cách hoạt động (tóm tắt)

1. Telegram gửi tin nhắn mới tới `POST /api/webhook`
2. Bot kiểm tra text có ký tự dấu tiếng Việt không:
   - Có → gọi Google Translate (qua `deep-translator`) dịch Việt → Anh
   - Không → coi là từ tiếng Anh, gọi Free Dictionary API lấy phiên âm/audio/nghĩa, rồi dịch nghĩa sang tiếng Việt
3. Gửi kết quả lại cho người dùng qua Telegram API (`sendMessage`)

## Lưu ý

- Free Dictionary API và Google Translate (qua deep-translator) đều miễn phí, không cần API key.
- Lần đầu gọi bot sau một thời gian dài không dùng có thể hơi chậm (server "ngủ" rồi thức dậy) — đây là đặc điểm bình thường của serverless free tier, không phải lỗi.
- Không cần khai báo thẻ thanh toán ở đâu trong toàn bộ setup này.
