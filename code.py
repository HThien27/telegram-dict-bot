import telebot
from config import BOT_TOKEN

# Khởi tạo bot với token
bot = telebot.TeleBot(BOT_TOKEN)

# Xử lý khi user gõ lệnh /start
@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, "Chào bạn! Mình là bot demo, cứ gõ gì đó để test nhé.")

# Xử lý tất cả tin nhắn text còn lại (echo lại nguyên văn)
@bot.message_handler(func=lambda message: True)
def echo_all(message):
    bot.reply_to(message, f"Bạn vừa gõ: {message.text}")

# Chạy bot liên tục, lắng nghe tin nhắn (polling)
print("Bot đang chạy...")
bot.infinity_polling()