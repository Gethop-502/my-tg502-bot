import os
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import telebot
from telebot import types
import yt_dlp

# --- سيرفر وهمي لإبقاء الخدمة نشطة على ريندر مجاناً ---
class SimpleServer(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is running successfully!")

def run_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), SimpleServer)
    server.serve_forever()

threading.Thread(target=run_server, daemon=True).start()
# ----------------------------------------------------

# توكن البوت
BOT_TOKEN = "8945302717:AAHEAkn89ygLc5QtwhuWRKIG-v0ucebQfyY"
bot = telebot.TeleBot(BOT_TOKEN)

user_links = {}

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    welcome_text = (
        "👋 أهلاً بك في بوت التحميل!\n\n"
        "أرسل لي أي رابط من **تيك توك** أو **يوتيوب**، "
        "وسأعرض لك خيارات التحميل بالجودات المختلفة أو تحويله لصوت."
    )
    bot.reply_to(message, welcome_text)

@bot.message_handler(func=lambda message: message.text and ("youtube.com" in message.text or "youtu.be" in message.text or "tiktok.com" in message.text))
def handle_link(message):
    user_id = message.from_user.id
    url = message.text.strip()
    user_links[user_id] = url

    markup = types.InlineKeyboardMarkup(row_width=2)
    btn_360 = types.InlineKeyboardButton("📹 360p", callback_data="res_360")
    btn_480 = types.InlineKeyboardButton("📹 480p", callback_data="res_480")
    btn_720 = types.InlineKeyboardButton("📹 720p", callback_data="res_720")
    btn_1080 = types.InlineKeyboardButton("📹 1080p", callback_data="res_1080")
    btn_mp3 = types.InlineKeyboardButton("🎵 تحويل إلى MP3", callback_data="res_mp3")

    markup.add(btn_360, btn_480, btn_720, btn_1080, btn_mp3)
    bot.reply_to(message, "اختر الجودة أو الصيغة المطلوبة:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('res_'))
def process_download(call):
    user_id = call.from_user.id
    choice = call.data.replace('res_', '')

    if user_id not in user_links:
        bot.answer_callback_query(call.id, "انتهت صلاحية الرابط، أعد إرساله مجدداً.")
        return

    url = user_links[user_id]
    bot.edit_message_text("⏳ جارٍ تجهيز وتحميل الملف، يرجى الانتظار...", call.message.chat.id, call.message.message_id)

    file_output = f"download_{user_id}.%(ext)s"
    final_filename = ""

    ydl_opts = {
        'outtmpl': file_output,
        'quiet': True,
        'no_warnings': True,
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
            'format': f'bestvideo[height<={choice}]+bestaudio/best[height<={choice}]/best',
        })

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            final_filename = ydl.prepare_filename(info)
            if choice == 'mp3':
                final_filename = os.path.splitext(final_filename)[0] + ".mp3"

        bot.send_chat_action(call.message.chat.id, 'upload_document')
        
        with open(final_filename, 'rb') as f:
            if choice == 'mp3':
                bot.send_audio(call.message.chat.id, f, caption="تم التحميل بنجاح 🎵")
            else:
                bot.send_video(call.message.chat.id, f, caption=f"تم التحميل بجودة {choice}p 🎬")

        if os.path.exists(final_filename):
            os.remove(final_filename)

        bot.delete_message(call.message.chat.id, call.message.message_id)

    except Exception as e:
        bot.send_message(call.message.chat.id, "تعذر تحميل الفيديو، تأكد من صحة الرابط أو أن حجمه مناسب.")
        if final_filename and os.path.exists(final_filename):
            os.remove(final_filename)

bot.infinity_polling()
    
