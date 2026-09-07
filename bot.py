import os
import requests
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import telebot
from telebot import types

# سيرفر وهمي لإبقاء البوت نشطاً
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

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    bot.reply_to(message, "👋 أهلاً بك! أرسل رابط الفيديو من يوتيوب أو تيك توك وسأقوم بتحميله فوراً.")

@bot.message_handler(func=lambda msg: msg.text and any(d in msg.text for d in ["tiktok.com", "youtube.com", "youtu.be"]))
def handle_link(message):
    user_id = message.from_user.id
    words = message.text.strip().split()
    url = next((w for w in words if any(d in w for d in ["tiktok.com", "youtube.com", "youtu.be"])), None)

    if not url:
        bot.reply_to(message, "يرجى إرسال رابط صالح.")
        return

    user_links[user_id] = url

    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🎬 360p", callback_data="res_360"),
        types.InlineKeyboardButton("🎬 480p", callback_data="res_480"),
        types.InlineKeyboardButton("🎬 720p", callback_data="res_720"),
        types.InlineKeyboardButton("🎬 1080p", callback_data="res_1080"),
        types.InlineKeyboardButton("🎵 استخراج صوت MP3", callback_data="res_mp3")
    )
    bot.reply_to(message, "اختر الجودة أو الصيغة المطلوبة:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('res_'))
def process_download(call):
    user_id = call.from_user.id
    choice = call.data.replace('res_', '')

    if user_id not in user_links:
        bot.answer_callback_query(call.id, "انتهت صلاحية الرابط، أعد إرساله.")
        return

    url = user_links[user_id]
    msg = bot.send_message(call.message.chat.id, "⏳ جاري جلب المقطع عبر المخدمات المفتوحة...")

    # الاتصال بمحرك Cobalt لمعالجة الروابط بعيداً عن حظر IP السيرفر
    api_url = "https://api.cobalt.tools/api/json"
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
    
    payload = {
        "url": url,
        "videoQuality": choice if choice != 'mp3' else "720",
        "downloadMode": "audio" if choice == 'mp3' else "auto"
    }

    try:
        response = requests.post(api_url, json=payload, headers=headers, timeout=20)
        data = response.json()

        download_url = data.get("url")
        if not download_url:
            raise Exception("API did not return a valid download URL")

        bot.edit_message_text("⚡ جاري تنزيل الملف وإرساله إلى المحادثة...", call.message.chat.id, msg.message_id)

        ext = "mp3" if choice == 'mp3' else "mp4"
        local_filename = f"file_{user_id}.{ext}"

        with requests.get(download_url, stream=True, timeout=60) as r:
            r.raise_for_status()
            with open(local_filename, 'wb') as f:
                for chunk in r.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        f.write(chunk)

        # فحص الحجم المسموح به في تيليجرام
        if os.path.exists(local_filename) and os.path.getsize(local_filename) > 49 * 1024 * 1024:
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("📥 تنزيل الملف بالكامل", url=download_url))
            bot.edit_message_text("⚠️ حجم المقطع يتجاوز حد الرفع المباشر في تيليجرام (50MB).\nيمكنك تحميله مباشرة عبر الرابط أدناه:", call.message.chat.id, msg.message_id, reply_markup=markup)
            if os.path.exists(local_filename):
                os.remove(local_filename)
            return

        bot.send_chat_action(call.message.chat.id, 'upload_document' if choice == 'mp3' else 'upload_video')
        with open(local_filename, 'rb') as f:
            if choice == 'mp3':
                bot.send_audio(call.message.chat.id, f, caption="تم استخراج الصوت 🎵")
            else:
                bot.send_video(call.message.chat.id, f, caption=f"تم التحميل بجودة {choice}p 🎬")

        if os.path.exists(local_filename):
            os.remove(local_filename)
        bot.delete_message(call.message.chat.id, msg.message_id)

    except Exception:
        bot.edit_message_text("تعذر معالجة هذا المقطع؛ قد يكون مقيداً أو مؤمناً ضد التحميل الخارجي.", call.message.chat.id, msg.message_id)

bot.infinity_polling()
