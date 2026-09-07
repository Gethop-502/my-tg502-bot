import os
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import telebot
from telebot import types
import yt_dlp

# سيرفر وهمي لتشغيل المنصة
class SimpleServer(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is active!")

def run_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), SimpleServer)
    server.serve_forever()

threading.Thread(target=run_server, daemon=True).start()

# إعدادات البوت
BOT_TOKEN = "8945302717:AAHEAkn89ygLc5QtwhuWRKIG-v0ucebQfyY"
bot = telebot.TeleBot(BOT_TOKEN)
user_links = {}

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    welcome_text = "👋 أهلاً بك! أرسل لي رابط تيك توك أو يوتيوب وسأقوم بتحميله فوراً."
    bot.reply_to(message, welcome_text)

@bot.message_handler(func=lambda message: message.text and ("youtube.com" in message.text or "youtu.be" in message.text or "tiktok.com" in message.text))
def handle_link(message):
    user_id = message.from_user.id
    # تنظيف الرابط من أي نصوص مشاركة إضافية
    text = message.text.strip()
    words = text.split()
    url = ""
    for word in words:
        if "tiktok.com" in word or "youtube.com" in word or "youtu.be" in word:
            url = word
            break
            
    if not url:
        bot.reply_to(message, "لم يتم العثور على رابط صالح.")
        return

    user_links[user_id] = url

    markup = types.InlineKeyboardMarkup(row_width=2)
    btn_mp4 = types.InlineKeyboardButton("🎬 تحميل فيديو", callback_data="res_best")
    btn_mp3 = types.InlineKeyboardButton("🎵 تحويل صوت MP3", callback_data="res_mp3")
    markup.add(btn_mp4, btn_mp3)
    bot.reply_to(message, "اختر طريقة التحميل المطلوبة:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('res_'))
def process_download(call):
    user_id = call.from_user.id
    choice = call.data.replace('res_', '')

    if user_id not in user_links:
        bot.answer_callback_query(call.id, "انتهت صلاحية الرابط، أعد إرساله.")
        return

    url = user_links[user_id]
    msg = bot.send_message(call.message.chat.id, "⏳ جارٍ التحميل والمعالجة...")

    file_output = f"dl_{user_id}.%(ext)s"
    
    ydl_opts = {
        'outtmpl': file_output,
        'quiet': True,
        'no_warnings': True,
        'noplaylist': True,
        'extractor_args': {
            'tiktok': {'app_version': ['latest']}
        },
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        }
    }

    if choice == 'mp3':
        ydl_opts.update({
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
        })
    else:
        ydl_opts.update({
            'format': 'best[ext=mp4]/best',
        })

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            final_file = ydl.prepare_filename(info)
            if choice == 'mp3':
                final_file = os.path.splitext(final_file)[0] + ".mp3"

        bot.send_chat_action(call.message.chat.id, 'upload_document')
        with open(final_file, 'rb') as f:
            if choice == 'mp3':
                bot.send_audio(call.message.chat.id, f, caption="تم التحميل بنجاح 🎵")
            else:
                bot.send_video(call.message.chat.id, f, caption="تم التحميل بنجاح 🎬")

        if os.path.exists(final_file):
            os.remove(final_file)
        bot.delete_message(call.message.chat.id, msg.message_id)

    except Exception as e:
        bot.edit_message_text(f"تعذر التحميل: قد يكون المقطع خاصاً أو محظوراً من السيرفر.", call.message.chat.id, msg.message_id)

bot.infinity_polling()
