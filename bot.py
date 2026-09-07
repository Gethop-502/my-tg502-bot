import os
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import telebot
from telebot import types
import yt_dlp

# سيرفر ويب وهمي لمنع توقف الخدمة على Render
class SimpleServer(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is online and active!")

def run_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), SimpleServer)
    server.serve_forever()

threading.Thread(target=run_server, daemon=True).start()

# إعداد البوت
BOT_TOKEN = "8945302717:AAHEAkn89ygLc5QtwhuWRKIG-v0ucebQfyY"
bot = telebot.TeleBot(BOT_TOKEN)
user_links = {}

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    welcome_text = "👋 أهلاً بك في بوت التحميل!\n\nأرسل لي أي رابط من **تيك توك** أو **يوتيوب** وسأعرض لك خيارات التحميل بالجودات المختلفة أو تحويله لصوت."
    bot.reply_to(message, welcome_text, parse_mode="Markdown")

@bot.message_handler(func=lambda message: message.text and any(domain in message.text for domain in ["tiktok.com", "youtube.com", "youtu.be"]))
def handle_link(message):
    user_id = message.from_user.id
    text = message.text.strip()
    words = text.split()
    url = ""
    for word in words:
        if any(d in word for d in ["tiktok.com", "youtube.com", "youtu.be"]):
            url = word
            break

    if not url:
        bot.reply_to(message, "يرجى التأكد من إرسال رابط صحيح.")
        return

    user_links[user_id] = url

    # لوحة أزرار اختيار الجودات والصوت
    markup = types.InlineKeyboardMarkup(row_width=2)
    btn_360 = types.InlineKeyboardButton("🎬 360p", callback_data="res_360")
    btn_480 = types.InlineKeyboardButton("🎬 480p", callback_data="res_480")
    btn_720 = types.InlineKeyboardButton("🎬 720p", callback_data="res_720")
    btn_1080 = types.InlineKeyboardButton("🎬 1080p", callback_data="res_1080")
    btn_mp3 = types.InlineKeyboardButton("🎵 تحويل إلى MP3", callback_data="res_mp3")
    
    markup.add(btn_360, btn_480, btn_720, btn_1080)
    markup.add(btn_mp3)

    bot.reply_to(message, "اختر الجودة أو الصيغة المطلوبة:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('res_'))
def process_download(call):
    user_id = call.from_user.id
    choice = call.data.replace('res_', '')

    if user_id not in user_links:
        bot.answer_callback_query(call.id, "انتهت مهلة الرابط، يرجى إرساله مرة أخرى.")
        return

    url = user_links[user_id]
    msg = bot.send_message(call.message.chat.id, "⏳ جارٍ التجهيز والتحميل، يرجى الانتظار...")

    file_output = f"dl_{user_id}_%(id)s.%(ext)s"

    # ضبط خيارات الجودة
    if choice == 'mp3':
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': file_output,
            'quiet': True,
            'noplaylist': True,
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
        }
    else:
        # جلب الجودة المحددة أو أقرب جودة مناسبة لها
        ydl_opts = {
            'format': f'bestvideo[height<={choice}][ext=mp4]+bestaudio[ext=m4a]/best[height<={choice}][ext=mp4]/best',
            'outtmpl': file_output,
            'quiet': True,
            'noplaylist': True,
        }

    # خيارات مشتركة لتفادي الحظر في تيك توك ويوتيوب
    ydl_opts.update({
        'extractor_args': {'tiktok': {'app_version': ['latest']}},
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        }
    })

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            if choice == 'mp3':
                filename = os.path.splitext(filename)[0] + ".mp3"

        bot.send_chat_action(call.message.chat.id, 'upload_document')
        with open(filename, 'rb') as f:
            if choice == 'mp3':
                bot.send_audio(call.message.chat.id, f, caption="تم استخراج الصوت بنجاح 🎵")
            else:
                bot.send_video(call.message.chat.id, f, caption=f"تم التحميل بنجاح بجودة {choice}p 🎬")

        if os.path.exists(filename):
            os.remove(filename)
        bot.delete_message(call.message.chat.id, msg.message_id)

    except Exception:
        bot.edit_message_text("تعذر تحميل الفيديو. تأكد من صحة الرابط أو أن حجمه لا يتجاوز حد تيليجرام (50MB).", call.message.chat.id, msg.message_id)

bot.infinity_polling()
