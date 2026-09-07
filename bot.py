import os
import re
import glob
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import telebot
from telebot import types
import yt_dlp

# خادم ويب وهمي لمنع نوم السيرفر على Render
class SimpleServer(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot Server is Live!")

def run_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), SimpleServer)
    server.serve_forever()

threading.Thread(target=run_server, daemon=True).start()

BOT_TOKEN = "8945302717:AAHEAkn89ygLc5QtwhuWRKIG-v0ucebQfyY"
bot = telebot.TeleBot(BOT_TOKEN)
user_links = {}

def extract_url(text):
    match = re.search(r'(https?://[^\s]+)', text)
    return match.group(1).strip() if match else None

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    bot.reply_to(message, "👋 مرحباً بك! أرسل رابط الفيديو (يوتيوب أو تيك توك) وسأقوم بتحميله مباشرة.")

@bot.message_handler(func=lambda msg: msg.text and any(d in msg.text for d in ["tiktok.com", "youtube.com", "youtu.be"]))
def handle_link(message):
    user_id = message.from_user.id
    url = extract_url(message.text)

    if not url:
        bot.reply_to(message, "⚠️ يرجى إرسال رابط صالح.")
        return

    user_links[user_id] = url

    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🎬 تحميل الفيديو", callback_data="res_video"),
        types.InlineKeyboardButton("🎵 استخراج الصوت MP3", callback_data="res_audio")
    )
    bot.reply_to(message, "اختر المطلوب:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('res_'))
def process_download(call):
    user_id = call.from_user.id
    choice = call.data.replace('res_', '')

    if user_id not in user_links:
        bot.answer_callback_query(call.id, "انتهت صلاحية الرابط، يرجى إرساله مجدداً.")
        return

    url = user_links[user_id]
    msg = bot.send_message(call.message.chat.id, "⏳ جاري الفحص والتنزيل...")

    output_template = f"dl_{user_id}_%(id)s.%(ext)s"

    # إعدادات مخصصة لتجاوز حظر المنصات
    ydl_opts = {
        'outtmpl': output_template,
        'quiet': True,
        'no_warnings': True,
        'noplaylist': True,
        'max_filesize': 49 * 1024 * 1024,
        'extractor_args': {
            'youtube': {'player_client': ['android', 'ios']},
            'tiktok': {'app_version': ['latest']}
        },
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
        }
    }

    if choice == 'audio':
        ydl_opts['format'] = 'bestaudio/best'
    else:
        # جلب صيغة متكاملة مباشرة صوت وصورة دون اشتراط برامج دمج
        ydl_opts['format'] = 'best[ext=mp4]/best'

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        files = glob.glob(f"dl_{user_id}_*")
        if not files:
            raise Exception("لم يتم العثور على الملف بعد اكتمال التنزيل.")

        downloaded_file = files[0]

        bot.edit_message_text("⚡ تم التنزيل بنجاح، جاري الرفع للشات...", call.message.chat.id, msg.message_id)

        bot.send_chat_action(call.message.chat.id, 'upload_document' if choice == 'audio' else 'upload_video')
        with open(downloaded_file, 'rb') as f:
            if choice == 'audio':
                bot.send_audio(call.message.chat.id, f, caption="تم استخراج الصوت 🎵")
            else:
                bot.send_video(call.message.chat.id, f, caption="تم التحميل بنجاح 🎬")

        bot.delete_message(call.message.chat.id, msg.message_id)

    except Exception as e:
        err_msg = str(e)
        if "File is larger than max_filesize" in err_msg:
            bot.edit_message_text("⚠️ حجم المقطع أكبر من 50 ميغابايت (حد تيليجرام الأقصى).", call.message.chat.id, msg.message_id)
        else:
            bot.edit_message_text(f"⚠️ فشل التحميل بسبب:\n`{err_msg[:120]}`", parse_mode="Markdown", chat_id=call.message.chat.id, message_id=msg.message_id)

    finally:
        for f in glob.glob(f"dl_{user_id}_*"):
            try:
                os.remove(f)
            except Exception:
                pass

bot.infinity_polling()
