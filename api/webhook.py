"""
Telegram Dictionary Bot
- Nếu input là tiếng Việt -> dịch sang tiếng Anh
- Nếu input là tiếng Anh -> trả về phiên âm + audio + nghĩa tiếng Việt

Chạy trên Vercel Python Serverless Function (webhook mode).
"""

import os
import re
import time
import requests
import unicodedata
from flask import Flask, request, jsonify
from deep_translator import GoogleTranslator

app = Flask(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
# Nên setup biến môi trường này trên Vercel và setWebhook với secret_token tương ứng
WEBHOOK_SECRET = os.environ.get("WEBHOOK_SECRET", "")

def ask_gemini(prompt: str):
    if not GEMINI_API_KEY:
        return "Lỗi: Bot chưa được cấu hình GEMINI_API_KEY. Bạn hãy liên hệ Admin để thêm API Key nhé!"
        
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    headers = {"Content-Type": "application/json"}
    payload = {
        "contents": [{"parts": [{"text": prompt}]}]
    }
    max_retries = 2
    for attempt in range(max_retries):
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=8).json()
            if "candidates" in resp and resp["candidates"]:
                return resp["candidates"][0]["content"]["parts"][0]["text"].strip()
            elif "error" in resp:
                error_msg = resp["error"].get("message", "Lỗi không xác định")
                if "high demand" in error_msg.lower() and attempt < max_retries - 1:
                    time.sleep(1)
                    continue
                return f"Lỗi từ Google: {error_msg}"
            else:
                return "Xin lỗi, AI không thể xử lý câu hỏi này (không rõ nguyên nhân)."
        except requests.exceptions.Timeout:
             return "Xin lỗi, AI phản hồi quá chậm. Vui lòng thử lại sau."
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(1)
                continue
            return f"Xin lỗi, có lỗi xảy ra khi kết nối với AI ({e})."


# Regex nhận diện ký tự có dấu tiếng Việt
VIETNAMESE_CHARS = re.compile(
    r"[àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡ"
    r"ùúụủũưừứựửữỳýỵỷỹđ]",
    re.IGNORECASE,
)

def is_vietnamese(text: str) -> bool:
    """Đoán input là tiếng Việt nếu có ký tự dấu tiếng Việt."""
    return bool(VIETNAMESE_CHARS.search(text))


def translate_text(text: str, source: str, target: str):
    try:
        return GoogleTranslator(source=source, target=target).translate(text)
    except Exception:
        return None

def get_vietnamese_meanings(word: str):
    url = "https://translate.googleapis.com/translate_a/single"
    params = {
        "client": "gtx",
        "sl": "en",
        "tl": "vi",
        "dt": ["t", "bd"],
        "q": word
    }
    try:
        resp = requests.get(url, params=params, timeout=5).json()
        primary = resp[0][0][0]
        
        alternatives = []
        if len(resp) > 1 and resp[1]:
            for pos_group in resp[1]:
                pos = pos_group[0]
                
                pos_mapped = {
                    "noun": "N",
                    "verb": "V",
                    "adjective": "Adj",
                    "adverb": "Adv",
                    "pronoun": "Pro",
                    "preposition": "Prep",
                    "conjunction": "Conj",
                    "interjection": "Int"
                }.get(pos.lower(), pos.capitalize())
                
                words = pos_group[1][:3]
                
                capitalized_words = []
                for w in words:
                    w = w.strip()
                    if w:
                        capitalized_words.append(w[0].upper() + w[1:])
                
                # HTML escape/replace instead of markdown
                words_str = ", ".join(capitalized_words).replace("<", "&lt;").replace(">", "&gt;")
                words_str = unicodedata.normalize("NFC", words_str)
                alternatives.append(f"• ({pos_mapped}) {words_str}")
                
        safe_vi = primary.strip()
        if safe_vi: safe_vi = safe_vi[0].upper() + safe_vi[1:]
        safe_vi = safe_vi.replace("<", "&lt;").replace(">", "&gt;")
        safe_vi = unicodedata.normalize("NFC", safe_vi)
        
        result = []
        if primary.lower() != word.lower() and safe_vi:
            result.append(f"• Nghĩa chính: {safe_vi}")
            
        if alternatives:
            result.extend(alternatives)
            
        return result
    except Exception:
        short = translate_text(word, "en", "vi")
        if not short or short.lower() == word.lower():
            if GEMINI_API_KEY:
                short = ask_gemini(f"Dịch từ tiếng Anh sau sang tiếng Việt (chỉ trả lời nghĩa ngắn gọn nhất, không giải thích): '{word}'")
        if short and short.lower() != word.lower() and "lỗi" not in short.lower():
            safe_vi = short.strip()
            if safe_vi: safe_vi = safe_vi[0].upper() + safe_vi[1:]
            safe_vi = safe_vi.replace("<", "&lt;").replace(">", "&gt;")
            safe_vi = unicodedata.normalize("NFC", safe_vi)
            return [f"• Nghĩa: {safe_vi}"]
        return []

def lookup_english_word(word: str):
    """Gọi Free Dictionary API, nếu lỗi thì dùng Gemini."""
    phonetic = ""
    audio_url = ""
    english_example = ""
    is_valid = False
    try:
        resp = requests.get(
            f"https://api.dictionaryapi.dev/api/v2/entries/en/{word}", timeout=4
        )
        if resp.status_code == 200:
            is_valid = True
            for entry in resp.json():
                if not phonetic:
                    phonetic = entry.get("phonetic", "")
                for p in entry.get("phonetics", []):
                    if not phonetic and p.get("text"):
                        phonetic = p["text"]
                    if not audio_url and p.get("audio"):
                        audio_url = p["audio"]
                
                if not english_example:
                    for m in entry.get("meanings", []):
                        for d in m.get("definitions", []):
                            if d.get("example"):
                                english_example = d["example"]
                                break
                        if english_example:
                            break
    except Exception:
        pass

    import urllib.parse
    safe_word = urllib.parse.quote(word)
    if not audio_url:
        audio_url = f"https://translate.google.com/translate_tts?ie=UTF-8&q={safe_word}&tl=en&client=tw-ob"

    if is_valid:
        meanings = get_vietnamese_meanings(word)
        if not meanings:
            meanings = ["• Nghĩa: (Hiện tại không thể dịch sang tiếng Việt)"]

        example_text = ""
        if english_example:
            example_vi = translate_text(english_example, "en", "vi")
            english_example_escaped = english_example.replace("<", "&lt;").replace(">", "&gt;")
            if example_vi:
                 example_vi_escaped = example_vi.replace("<", "&lt;").replace(">", "&gt;")
                 example_text = f"💡 <b>Ví dụ:</b> <i>{english_example_escaped}</i>\n({example_vi_escaped})"
            else:
                 example_text = f"💡 <b>Ví dụ:</b> <i>{english_example_escaped}</i>"

        return {"phonetic": phonetic, "audio": audio_url, "meanings": meanings, "example": example_text}

    # FALLBACK: Nếu Free Dictionary chết (bị Vercel block/timeout), nhờ luôn Gemini làm từ điển!
    if GEMINI_API_KEY:
        prompt = (
            f"Đóng vai từ điển, cung cấp thông tin cho từ tiếng Anh '{word}' theo đúng định dạng sau:\n"
            "🔊 Phiên âm: /.../\n"
            "📖 Nghĩa: (các nghĩa chính)\n"
            "💡 Ví dụ: (1 câu ví dụ tiếng Anh)\n"
            "🇻🇳 Dịch ví dụ: (dịch câu ví dụ)\n"
            "Chỉ in ra kết quả như định dạng, không dùng markdown, không chào hỏi, sử dụng các thẻ HTML <b>, <i>, <code> nếu cần nhấn mạnh."
        )
        gemini_fallback = ask_gemini(prompt)
        if "lỗi" not in gemini_fallback.lower() and len(gemini_fallback) > 10:
             return {"is_gemini": True, "text": gemini_fallback, "audio": audio_url}

    return {"error": "not_found"}

def send_message(chat_id, text: str):
    try:
        resp = requests.post(
            f"{TELEGRAM_API}/sendMessage",
            json={
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": False,
            },
            timeout=5,
        ).json()
        if resp.get("ok"):
            return resp.get("result", {}).get("message_id")
    except Exception:
        pass
    return None

def edit_message(chat_id, message_id, text: str):
    try:
        requests.post(
            f"{TELEGRAM_API}/editMessageText",
            json={
                "chat_id": chat_id,
                "message_id": message_id,
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": False,
            },
            timeout=5,
        )
    except Exception:
        pass

def analyze_english_sentence(chat_id, text: str):
    """Phân tích câu tiếng Anh bằng Gemini"""
    if not GEMINI_API_KEY:
        # Fallback dịch nếu không có Gemini
        translated_to_vi = translate_text(text, "en", "vi")
        if translated_to_vi and translated_to_vi.lower() != text.lower():
            send_message(chat_id, f"🇬🇧 {text}\n🇻🇳 {translated_to_vi}")
        else:
            send_message(
                chat_id,
                "Không thể dịch được câu này 😢\nBạn kiểm tra lại chính tả giúp mình nhé."
            )
        return

    msg_id = send_message(chat_id, "⏳ <i>Đang phân tích câu của bạn...</i>")
    
    prompt = (
        f"Học sinh vừa viết câu tiếng Anh sau: '{text}'.\n"
        "Kiểm tra ngữ pháp và chính tả. Tuân thủ tuyệt đối các quy tắc sau, KHÔNG thêm lời chào hỏi dài dòng:\n"
        "1. Nếu đúng hoàn toàn: Khen ngợi ngắn gọn và dịch sang tiếng Việt.\n"
        "2. Nếu sai: Bắt đầu ngay bằng câu 'Câu này sai ở [chỉ ra chỗ sai]'. Sau đó viết lại câu đúng (phải IN ĐẬM câu đúng bằng thẻ HTML <b>câu đúng</b>), dịch câu đúng sang tiếng Việt, và giải thích ngắn gọn, súc tích lý do tại sao sai.\n"
        "Hãy xưng hô là 'mình' và 'bạn'. Tuyệt đối không dùng markdown, hãy dùng HTML (<b>, <i>, <code>)."
    )
    analysis = ask_gemini(prompt)
    
    reply_text = f"📖 <b>Phân tích câu của bạn:</b>\n\n{analysis}"
    if msg_id:
        edit_message(chat_id, msg_id, reply_text)
    else:
        send_message(chat_id, reply_text)

@app.route("/api/webhook", methods=["GET", "POST"])
def webhook():
    if request.method == "GET":
        return "Telegram Dictionary Bot is running on Vercel."
        
    # Check Webhook Secret (Nâng cao bảo mật)
    if WEBHOOK_SECRET and request.headers.get("X-Telegram-Bot-Api-Secret-Token") != WEBHOOK_SECRET:
         return jsonify({"error": "Unauthorized"}), 403

    update = request.get_json(silent=True) or {}
    
    message = update.get("message")
    if not message:
        return jsonify({"ok": True})

    chat_id = message.get("chat", {}).get("id")
    text = (message.get("text") or "").strip()
    if not chat_id or not text:
        return jsonify({"ok": True})

    if text.startswith("/start"):
        send_message(
            chat_id,
            "Chào bạn! 👋\nGửi mình một từ tiếng Anh để tra phiên âm + nghĩa,\n "
            "hoặc gửi một từ/câu tiếng Việt để dịch sang tiếng Anh."
        )
        return jsonify({"ok": True})

    if text.startswith("/debug"):
        debug_msg = "🔍 <b>DEBUG INFO:</b>\n"
        # 1. Test Dictionary API
        try:
            r = requests.get("https://api.dictionaryapi.dev/api/v2/entries/en/hello", timeout=5)
            debug_msg += f"1. Dictionary API: {r.status_code}\n"
        except Exception as e:
            debug_msg += f"1. Dictionary API Error: {type(e).__name__}\n"
        
        # 2. Test Google Translate
        try:
            r2 = translate_text("hello", "en", "vi")
            debug_msg += f"2. Google Translate: {'OK' if r2 else 'Failed'}\n"
        except Exception as e:
            debug_msg += f"2. Google Translate Error: {type(e).__name__}\n"

        # 3. Test Gemini
        if GEMINI_API_KEY:
            try:
                g = ask_gemini("Say 'OK' if you hear this.")
                debug_msg += f"3. Gemini: {'OK' if g else 'Failed'}\n"
            except Exception as e:
                debug_msg += f"3. Gemini Error: {type(e).__name__}\n"
        else:
            debug_msg += "3. Gemini: LỖI (CHƯA CẤU HÌNH API KEY!)\n"
            
        send_message(chat_id, debug_msg)
        return jsonify({"ok": True})

    if is_vietnamese(text):
        if GEMINI_API_KEY:
            msg_id = send_message(chat_id, "⏳ <i>Đang dịch...</i>")
            prompt = f"Hãy đóng vai một biên dịch viên xuất sắc. Dịch câu tiếng Việt sau sang tiếng Anh một cách tự nhiên, chuẩn giao tiếp bản xứ nhất (chỉ trả về kết quả dịch, không giải thích dài dòng, không dùng markdown, giữ nguyên text thuần): '{text}'"
            translated = ask_gemini(prompt)
            reply = f"🇻🇳 {text}\n🇬🇧 <b>{translated}</b>"
            if msg_id:
                edit_message(chat_id, msg_id, reply)
            else:
                send_message(chat_id, reply)
        else:
            translated = translate_text(text, "vi", "en")
            if translated:
                send_message(chat_id, f"🇻🇳 {text}\n🇬🇧 <b>{translated}</b>")
            else:
                send_message(chat_id, "Xin lỗi, mình không dịch được từ/câu này 😢")
    else:
        words_count = len(text.split())
        
        # Với cụm từ ngắn (<= 3 từ), ưu tiên tra từ điển trước
        if words_count <= 3:
            result = lookup_english_word(text.lower())
            if result and not result.get("error"):
                if result.get("is_gemini"):
                    reply = f"📖 <b>{text}</b>\n\n{result['text']}\n\n<a href='{result['audio']}'>▶️ Nghe phát âm</a>"
                    send_message(chat_id, reply)
                else:
                    # Dùng HTML Format
                    reply = f"📖 <b>{text}</b>\n"
                    if result["phonetic"]:
                        reply += f"🔊 <code>{result['phonetic']}</code>\n\n"
                    reply += "\n".join(result["meanings"])
                    if result.get("example"):
                        reply += f"\n\n{result['example']}"
                    if result["audio"]:
                        reply += f"\n\n<a href='{result['audio']}'>▶️ Nghe phát âm</a>"
                    send_message(chat_id, reply)
            else:
                # Không có trong từ điển, dùng Google Translate dịch nghĩa chay
                translated_to_vi = translate_text(text, "en", "vi")
                if not translated_to_vi or translated_to_vi.lower() == text.lower():
                    if GEMINI_API_KEY:
                        translated_to_vi = ask_gemini(f"Dịch ngắn gọn từ/cụm từ sau sang tiếng Việt: '{text}'. Trả lời trực tiếp bằng nghĩa tiếng Việt, không giải thích.")
                        if "lỗi" in translated_to_vi.lower() or not translated_to_vi:
                            translated_to_vi = None

                if translated_to_vi and translated_to_vi.lower() != text.lower():
                    send_message(chat_id, f"🇬🇧 {text}\n🇻🇳 <b>{translated_to_vi}</b>")
                elif words_count == 1:
                    # Nếu 1 từ mà không dịch được thì báo lỗi
                    send_message(
                        chat_id,
                        f"❌ Không tìm thấy từ '<b>{text}</b>'.\nCó thể bạn đã viết sai chính tả, bạn kiểm tra lại nhé!"
                    )
                else:
                    # Cụm 2-3 từ không có trong từ điển -> Phân tích câu
                    analyze_english_sentence(chat_id, text)
        else:
            # Xử lý cho câu dài (phân tích ngữ pháp)
            analyze_english_sentence(chat_id, text)

    return jsonify({"ok": True})
