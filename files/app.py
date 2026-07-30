"""
Telegram Dictionary Bot
- Nếu input là tiếng Việt -> dịch sang tiếng Anh
- Nếu input là tiếng Anh -> trả về phiên âm + audio + nghĩa tiếng Việt

Chạy trên Vercel Python Serverless Function (webhook mode).
"""

import os
import re
import requests
from flask import Flask, request, jsonify
from deep_translator import GoogleTranslator

app = Flask(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

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


def lookup_english_word(word: str):
    """Gọi Free Dictionary API lấy phiên âm + audio + nghĩa, rồi dịch nghĩa sang tiếng Việt."""
    try:
        resp = requests.get(
            f"https://api.dictionaryapi.dev/api/v2/entries/en/{word}", timeout=8
        )
    except requests.RequestException:
        return None

    if resp.status_code != 200:
        return None

    try:
        entry = resp.json()[0]
    except (ValueError, IndexError, KeyError):
        return None

    # Lấy phiên âm (ưu tiên field "phonetic", fallback qua danh sách "phonetics")
    phonetic = entry.get("phonetic", "")
    audio_url = ""
    for p in entry.get("phonetics", []):
        if not phonetic and p.get("text"):
            phonetic = p["text"]
        if not audio_url and p.get("audio"):
            audio_url = p["audio"]

    # Lấy tối đa 3 nghĩa, dịch từng nghĩa sang tiếng Việt
    meanings = []
    for meaning in entry.get("meanings", [])[:3]:
        pos = meaning.get("partOfSpeech", "")
        definitions = meaning.get("definitions", [])
        if not definitions:
            continue
        definition_en = definitions[0].get("definition", "")
        if not definition_en:
            continue
        definition_vi = translate_text(definition_en, "en", "vi") or definition_en
        meanings.append(f"• ({pos}) {definition_vi}")

    if not meanings:
        return None

    return {"phonetic": phonetic, "audio": audio_url, "meanings": meanings}


def send_message(chat_id, text: str):
    requests.post(
        f"{TELEGRAM_API}/sendMessage",
        json={
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "Markdown",
            "disable_web_page_preview": False,
        },
        timeout=8,
    )


@app.route("/", methods=["GET"])
def home():
    return "Telegram Dictionary Bot is running."


@app.route("/api/webhook", methods=["POST"])
def webhook():
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
            "Chào bạn! 👋\nGửi mình một từ tiếng Anh để tra phiên âm + nghĩa, "
            "hoặc gửi một từ/câu tiếng Việt để dịch sang tiếng Anh.",
        )
        return jsonify({"ok": True})

    if is_vietnamese(text):
        translated = translate_text(text, "vi", "en")
        if translated:
            send_message(chat_id, f"🇻🇳 {text}\n🇬🇧 {translated}")
        else:
            send_message(chat_id, "Xin lỗi, mình không dịch được từ/câu này 😢")
    else:
        result = lookup_english_word(text.lower())
        if result:
            reply = f"📖 *{text}*\n"
            if result["phonetic"]:
                reply += f"🔊 `{result['phonetic']}`\n\n"
            reply += "\n".join(result["meanings"])
            if result["audio"]:
                reply += f"\n\n[▶️ Nghe phát âm]({result['audio']})"
            send_message(chat_id, reply)
        else:
            send_message(
                chat_id,
                "Không tìm thấy từ này trong từ điển 😢\n"
                "Bạn kiểm tra lại chính tả giúp mình nhé.",
            )

    return jsonify({"ok": True})
