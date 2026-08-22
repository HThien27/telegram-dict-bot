"""
Telegram Dictionary Bot
- Nếu input là tiếng Việt -> dịch sang tiếng Anh
- Nếu input là tiếng Anh -> trả về phiên âm + audio + nghĩa tiếng Việt

Chạy trên Vercel Python Serverless Function (webhook mode).
"""

import os
import re
import requests
import unicodedata
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


def translate_batch(texts: list, source: str, target: str):
    if not texts:
        return []
    try:
        return GoogleTranslator(source=source, target=target).translate_batch(texts)
    except Exception:
        return texts  # Fallback: trả về nguyên bản nếu lỗi


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
                
                # Map part of speech to abbreviations
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
                
                # Viết hoa chữ cái đầu tiên của từng nghĩa
                capitalized_words = []
                for w in words:
                    w = w.strip()
                    if w:
                        capitalized_words.append(w[0].upper() + w[1:])
                
                words_str = ", ".join(capitalized_words).replace("*", "").replace("_", "").replace("`", "")
                words_str = unicodedata.normalize("NFC", words_str)
                alternatives.append(f"• ({pos_mapped}) {words_str}")
                
        if alternatives:
            return alternatives
        else:
            if primary.lower() == word.lower():
                return []
            safe_vi = primary.strip()
            if safe_vi: safe_vi = safe_vi[0].upper() + safe_vi[1:]
            safe_vi = safe_vi.replace("*", "").replace("_", "").replace("`", "")
            safe_vi = unicodedata.normalize("NFC", safe_vi)
            return [f"• Nghĩa: {safe_vi}"]
    except Exception:
        short = translate_text(word, "en", "vi")
        if short and short.lower() != word.lower():
            safe_vi = short.strip()
            if safe_vi: safe_vi = safe_vi[0].upper() + safe_vi[1:]
            safe_vi = safe_vi.replace("*", "").replace("_", "").replace("`", "")
            safe_vi = unicodedata.normalize("NFC", safe_vi)
            return [f"• Nghĩa: {safe_vi}"]
        return []


def lookup_english_word(word: str):
    """Gọi Free Dictionary API lấy phiên âm + audio, lấy nghĩa từ Google Translate."""
    phonetic = ""
    audio_url = ""
    english_example = ""
    is_valid = False
    try:
        resp = requests.get(
            f"https://api.dictionaryapi.dev/api/v2/entries/en/{word}", timeout=8
        )
        if resp.status_code == 200:
            is_valid = True
            entry = resp.json()[0]
            phonetic = entry.get("phonetic", "")
            for p in entry.get("phonetics", []):
                if not phonetic and p.get("text"):
                    phonetic = p["text"]
                if not audio_url and p.get("audio"):
                    audio_url = p["audio"]
            
            for m in entry.get("meanings", []):
                for d in m.get("definitions", []):
                    if d.get("example"):
                        english_example = d["example"]
                        break
                if english_example:
                    break
    except Exception:
        pass

    if not is_valid:
        return {"error": "not_found"}

    if not audio_url:
        import urllib.parse
        safe_word = urllib.parse.quote(word)
        audio_url = f"https://translate.google.com/translate_tts?ie=UTF-8&q={safe_word}&tl=en&client=tw-ob"

    meanings = get_vietnamese_meanings(word)
    
    if not meanings:
        return None

    example_text = ""
    if english_example:
        example_vi = translate_text(english_example, "en", "vi")
        if example_vi:
            example_text = f"💡 *Ví dụ:* _{english_example}_\n({example_vi})"

    return {"phonetic": phonetic, "audio": audio_url, "meanings": meanings, "example": example_text}


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


@app.route("/api/webhook", methods=["GET", "POST"])
def webhook():
    if request.method == "GET":
        return "Telegram Dictionary Bot is running on Vercel."
        
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
        # Giả định ban đầu là tiếng Anh
        words_count = len(text.split())
        
        if words_count == 1:
            result = lookup_english_word(text.lower())
            if result and not result.get("error"):
                reply = f"📖 *{text}*\n"
                if result["phonetic"]:
                    reply += f"🔊 `{result['phonetic']}`\n\n"
                reply += "\n".join(result["meanings"])
                if result.get("example"):
                    reply += f"\n\n{result['example']}"
                if result["audio"]:
                    reply += f"\n\n[▶️ Nghe phát âm]({result['audio']})"
                send_message(chat_id, reply)
            else:
                send_message(
                    chat_id,
                    f"❌ Không tìm thấy từ '{text}' trong từ điển.\nCó thể bạn đã viết sai chính tả, bạn kiểm tra lại nhé!"
                )
        else:
            # Fallback: Nếu là một câu dài
            # -> Dịch thẳng câu tiếng Anh đó sang tiếng Việt
            translated_to_vi = translate_text(text, "en", "vi")
            if translated_to_vi and translated_to_vi.lower() != text.lower():
                send_message(chat_id, f"🇬🇧 {text}\n🇻🇳 {translated_to_vi}")
            else:
                send_message(
                    chat_id,
                    "Không thể dịch được câu này 😢\n"
                    "Bạn kiểm tra lại chính tả giúp mình nhé.",
                )

    return jsonify({"ok": True})
