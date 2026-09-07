import os
import re
import glob
import requests
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import telebot
from telebot import types
import yt_dlp

# سيرفر وهمي لإبقاء البوت متصلاً
class SimpleServer(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is Running 24/7!")

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

def extract_youtube_id(url):
    pattern = r'(?:v=|\/|youtu\.be\/|shorts\/)([0-9A-Za-z_-]{11})'
    match = re.search(pattern, url)
    return match.group(1) if match else None

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    bot.reply_to(message, "👋 مرحباً بك! أرسل رابط تيك توك أو يوتيوب وسأقوم بتحميله فوراً وبدون قيود.")

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
        types.InlineKeyboardButton("🎬 تحميل الفيديو (MP4)", callback_data="res_video"),
        types.InlineKeyboardButton("🎵 استخراج الصوت (Audio)", callback_data="res_audio")
    )
    bot.reply_to(message, "اختر طريقة التنزيل:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('res_'))
def process_download(call):
    user_id = call.from_user.id
    choice = call.data.replace('res_', '')

    if user_id not in user_links:
        bot.answer_callback_query(call.id, "انتهت صلاحية الرابط، أعد إرساله.")
        return

    url = user_links[user_id]
    msg = bot.send_message(call.message.chat.id, "⏳ جاري فحص الرابط واستخراج المقطع...")

    # ==========================================
    # 1. مسار يوتيوب (تجاوز حظر خوادم Render)
    # ==========================================
    if "youtube.com" in url or "youtu.be" in url:
        video_id = extract_youtube_id(url)
        if not video_id:
            bot.edit_message_text("⚠️ تعذر استخراج معرف فيديو يوتيوب.", call.message.chat.id, msg.message_id)
            return

        # قائمة خوادم Invidious مفتوحة المصدر لتخطي حظر IP السيرفر
        invidious_instances = [
            "https://inv.tux.pizza",
            "https://invidious.nerdvpn.de",
            "https://invidious.private.coffee"
        ]

        stream_url = None
        for base_api in invidious_instances:
            try:
                api_req = f"{base_api}/api/v1/videos/{video_id}"
                resp = requests.get(api_req, timeout=10).json()

                if choice == 'audio':
                    audio_streams = resp.get("adaptiveFormats", [])
                    for a in audio_streams:
                        if "audio" in a.get("type", "") and a.get("url"):
                            stream_url = a.get("url")
                            break
                else:
                    # اختيار أعلى صيغة فيديو مدمجة بالصوت
                    video_streams = resp.get("formatStreams", [])
                    if video_streams:
                        stream_url = video_streams[-1].get("url")

                if stream_url:
                    break
            except Exception:
                continue

        if not stream_url:
            bot.edit_message_text("⚠️ مقطع يوتيوب هذا محمي أو مقيد بشكل يمنع سحبه عبر الخوادم.", call.message.chat.id, msg.message_id)
            return

        # تنزيل ورفع المقطع
        bot.edit_message_text("⚡ تم تجاوز الحظر! جاري سحب المقطع ورفعه إليك...", call.message.chat.id, msg.message_id)
        ext = "mp3" if choice == 'audio' else "mp4"
        local_file = f"yt_{user_id}.{ext}"

        try:
            with requests.get(stream_url, stream=True, timeout=60) as r:
                r.raise_for_status()
                with open(local_file, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=1024 * 1024):
                        if chunk:
                            f.write(chunk)

            if os.path.exists(local_file) and os.path.getsize(local_file) > 49 * 1024 * 1024:
                markup = types.InlineKeyboardMarkup()
                markup.add(types.InlineKeyboardButton("📥 تنزيل المقطع مباشرة", url=stream_url))
                bot.edit_message_text("⚠️ حجم الفيديو يتجاوز 50 ميغا، يمكنك تحميله مباشرة عبر هذا الرابط:", call.message.chat.id, msg.message_id, reply_markup=markup)
                os.remove(local_file)
                return

            bot.send_chat_action(call.message.chat.id, 'upload_document' if choice == 'audio' else 'upload_video')
            with open(local_file, 'rb') as f:
                if choice == 'audio':
                    bot.send_audio(call.message.chat.id, f, caption="تم استخراج الصوت 🎵")
                else:
                    bot.send_video(call.message.chat.id, f, caption="تم التحميل بنجاح 🎬")

            if os.path.exists(local_file):
                os.remove(local_file)
            bot.delete_message(call.message.chat.id, msg.message_id)
            return

        except Exception as e:
            bot.edit_message_text("⚠️ حدث خطأ أثناء تنزيل ملف يوتيوب.", call.message.chat.id, msg.message_id)
            if os.path.exists(local_file):
                os.remove(local_file)
            return

    # ==========================================
    # 2. مسار تيك توك (يعمل بنجاح ومباشرة)
    # ==========================================
    output_template = f"dl_{user_id}_%(id)s.%(ext)s"
    ydl_opts = {
        'outtmpl': output_template,
        'quiet': True,
        'no_warnings': True,
        'noplaylist': True,
        'max_filesize': 49 * 1024 * 1024,
        'extractor_args': {'tiktok': {'app_version': ['latest']}},
        'format': 'bestaudio/best' if choice == 'audio' else 'best[ext=mp4]/best'
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        files = glob.glob(f"dl_{user_id}_*")
        if not files:
            raise Exception("لم يتم العثور على ملف تيك توك.")

        downloaded_file = files[0]
        bot.send_chat_action(call.message.chat.id, 'upload_document' if choice == 'audio' else 'upload_video')
        with open(downloaded_file, 'rb') as f:
            if choice == 'audio':
                bot.send_audio(call.message.chat.id, f, caption="تم استخراج الصوت 🎵")
            else:
                bot.send_video(call.message.chat.id, f, caption="تم التحميل بنجاح 🎬")

        bot.delete_message(call.message.chat.id, msg.message_id)

    except Exception as e:
        bot.edit_message_text(f"⚠️ فشل تنزيل تيك توك: {str(e)[:100]}", call.message.chat.id, msg.message_id)

    finally:
        for f in glob.glob(f"dl_{user_id}_*"):
            try:
                os.remove(f)
            except Exception:
                pass

bot.infinity_polling()
