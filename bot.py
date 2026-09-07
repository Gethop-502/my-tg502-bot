import os
import glob
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import telebot
from telebot import types
import yt_dlp

# تشغيل خادم ويب داخلي لإبقاء الخدمة نشطة عبر UptimeRobot
class SimpleServer(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Server is Healthy & Running 24/7!")

def run_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), SimpleServer)
    server.serve_forever()

threading.Thread(target=run_server, daemon=True).start()

# إعداد توكن البوت
BOT_TOKEN = "8945302717:AAHEAkn89ygLc5QtwhuWRKIG-v0ucebQfyY"
bot = telebot.TeleBot(BOT_TOKEN)
user_links = {}

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    bot.reply_to(message, "👋 مرحباً بك! أرسل رابط المقطع (يوتيوب أو تيك توك) وسأقوم بتحميله وإرساله فوراً.")

@bot.message_handler(func=lambda msg: msg.text and any(d in msg.text for d in ["tiktok.com", "youtube.com", "youtu.be"]))
def handle_link(message):
    user_id = message.from_user.id
    words = message.text.strip().split()
    url = next((w for w in words if any(d in w for d in ["tiktok.com", "youtube.com", "youtu.be"])), None)

    if not url:
        bot.reply_to(message, "⚠️ الرابط غير صالح، تأكد من إرسال رابط صحيح.")
        return

    # تنظيف الرابط من وسوم التتبع
    url = url.split("?si=")[0]
    user_links[user_id] = url

    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🎬 تحميل الفيديو (MP4)", callback_data="res_video"),
        types.InlineKeyboardButton("🎵 استخراج الصوت (Audio)", callback_data="res_audio")
    )
    bot.reply_to(message, "اختر ما ترغب بتحميله:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('res_'))
def process_download(call):
    user_id = call.from_user.id
    choice = call.data.replace('res_', '')

    if user_id not in user_links:
        bot.answer_callback_query(call.id, "انتهت مهلة الرابط، يرجى إرساله مجدداً.")
        return

    url = user_links[user_id]
    msg = bot.send_message(call.message.chat.id, "⏳ جاري فحص الرابط وتجهيز الملف...")

    file_prefix = f"dl_{user_id}"
    file_tmpl = f"{file_prefix}.%(ext)s"

    # خيارات التجاوز الآمن لحظر السيرفرات السحابية
    ydl_opts = {
        'outtmpl': file_tmpl,
        'quiet': True,
        'no_warnings': True,
        'noplaylist': True,
        'max_filesize': 49 * 1024 * 1024,  # رفض أي ملف أكبر من 49 ميغا تلقائياً
        'extractor_args': {
            'youtube': {'player_client': ['ios', 'android']},
            'tiktok': {'app_version': ['latest']}
        },
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15',
        }
    }

    if choice == 'audio':
        # جلب صيغة الصوت المتوفرة مباشرة بدون اشتراط برامج تحويل
        ydl_opts['format'] = 'ba/b'
    else:
        # البحث عن فيديو يحتوي الصوت والصورة معاً مباشرة لتفادي مشاكل الدمج
        ydl_opts['format'] = 'best[vcodec!=none][acodec!=none][ext=mp4]/best[vcodec!=none][acodec!=none]/best'

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        # العثور على الملف الذي تم تنزيله
        downloaded_files = glob.glob(f"{file_prefix}.*")
        if not downloaded_files:
            bot.edit_message_text("⚠️ تعذر العثور على الملف المحمل، تأكد من صحة الرابط.", call.message.chat.id, msg.message_id)
            return

        target_file = downloaded_files[0]
        bot.edit_message_text("🚀 تم التحميل من المصدر، جاري رفعه إليك الآن...", call.message.chat.id, msg.message_id)

        with open(target_file, 'rb') as f:
            if choice == 'audio':
                bot.send_audio(call.message.chat.id, f, caption="تم استخراج الملف الصوتي بنجاح 🎵")
            else:
                bot.send_video(call.message.chat.id, f, caption="تم التحميل بنجاح 🎬", supports_streaming=True)

        bot.delete_message(call.message.chat.id, msg.message_id)

    except yt_dlp.utils.MaxDownloadsReached:
        bot.edit_message_text("⚠️ حجم المقطع يتجاوز 49 ميغابايت (الحد الأقصى المسموح به للبوتات في تيليجرام).", call.message.chat.id, msg.message_id)
    except Exception as e:
        err = str(e)
        if "File is larger than max_filesize" in err:
            bot.edit_message_text("⚠️ حجم الفيديو أكبر من 49 ميغابايت، يرجى اختيار مقطع أقصر.", call.message.chat.id, msg.message_id)
        else:
            bot.edit_message_text("تعذر التحميل حالياً. قد يكون الفيديو خاصاً أو مقيداً من المصدر.", call.message.chat.id, msg.message_id)

    finally:
        # حذف الملفات المؤقتة لتوفير مساحة السيرفر
        for f in glob.glob(f"{file_prefix}.*"):
            try:
                os.remove(f)
            except Exception:
                pass

bot.infinity_polling()
