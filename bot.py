import os
import re
import requests
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import telebot
from telebot import types

# خادم وهمي لإبقاء البوت نشطاً
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

def extract_clean_url(text):
    # استخراج أي رابط يبدأ بـ http أو https بدقة متناهية وفصله عن الكلام العربي
    match = re.search(r'(https?://[^\s]+)', text)
    if not match:
        return None
    url = match.group(1).strip()
    # تنظيف أي علامات أو مسافات قد تلتصق بنهاية الرابط
    url = url.split("?")[0]
    return url

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    bot.reply_to(message, "👋 مرحباً بك! أرسل رابط الفيديو وسأقوم بتحميله فوراً وبدون أي أخطاء.")

@bot.message_handler(func=lambda msg: msg.text and any(d in msg.text for d in ["tiktok.com", "youtube.com", "youtu.be"]))
def handle_link(message):
    user_id = message.from_user.id
    raw_url = extract_clean_url(message.text)

    if not raw_url:
        bot.reply_to(message, "⚠️ لم يتم العثور على رابط صحيح، أعد إرساله بمفرده.")
        return

    # فك توجيه الروابط المختصرة مثل vm.tiktok.com
    try:
        if "vm.tiktok.com" in raw_url or "vt.tiktok.com" in raw_url or "youtu.be" in raw_url:
            resp = requests.head(raw_url, allow_redirects=True, timeout=10)
            raw_url = resp.url.split("?")[0]
    except Exception:
        pass

    user_links[user_id] = raw_url

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
    msg = bot.send_message(call.message.chat.id, "⏳ جاري جلب المقطع وفك التشفير...")

    download_url = None

    # مسار تنزيل تيك توك المباشر والسريع
    if "tiktok.com" in url:
        try:
            # استخدام API مباشر ومجاني لتيك توك بدون علامة مائية
            tt_api = f"https://www.tikwm.com/api/?url={url}"
            r = requests.get(tt_api, timeout=15).json()
            if r.get("code") == 0:
                data = r.get("data", {})
                if choice == 'mp3':
                    download_url = data.get("music")
                else:
                    download_url = data.get("play") or data.get("wmplay")
        except Exception:
            pass

    # مسار يوتيوب أو المحاولات العامة عبر محرك Cobalt
    if not download_url:
        try:
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
            resp = requests.post(api_url, json=payload, headers=headers, timeout=20)
            res_data = resp.json()
            download_url = res_data.get("url")
        except Exception:
            pass

    if not download_url:
        bot.edit_message_text("⚠️ تعذر استخراج هذا الفيديو، تأكد أن الحساب ليس خاصاً (Private).", call.message.chat.id, msg.message_id)
        return

    bot.edit_message_text("⚡ جاري تنزيل الملف وإرساله لك الآن...", call.message.chat.id, msg.message_id)

    ext = "mp3" if choice == 'mp3' else "mp4"
    local_filename = f"dl_{user_id}.{ext}"

    try:
        with requests.get(download_url, stream=True, timeout=60) as r:
            r.raise_for_status()
            with open(local_filename, 'wb') as f:
                for chunk in r.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        f.write(chunk)

        if os.path.exists(local_filename) and os.path.getsize(local_filename) > 49 * 1024 * 1024:
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("📥 تنزيل المقطع مباشرة", url=download_url))
            bot.edit_message_text("⚠️ حجم المقطع يتجاوز 50 ميغابايت، اضغط الزر للتحميل المباشر:", call.message.chat.id, msg.message_id, reply_markup=markup)
            if os.path.exists(local_filename):
                os.remove(local_filename)
            return

        bot.send_chat_action(call.message.chat.id, 'upload_document' if choice == 'mp3' else 'upload_video')
        with open(local_filename, 'rb') as f:
            if choice == 'mp3':
                bot.send_audio(call.message.chat.id, f, caption="تم استخراج الصوت 🎵")
            else:
                bot.send_video(call.message.chat.id, f, caption=f"تم التحميل بنجاح 🎬")

        if os.path.exists(local_filename):
            os.remove(local_filename)
        bot.delete_message(call.message.chat.id, msg.message_id)

    except Exception:
        bot.edit_message_text("حدث خطأ أثناء رفع المقطع إلى التيليجرام.", call.message.chat.id, msg.message_id)
        if os.path.exists(local_filename):
            os.remove(local_filename)

bot.infinity_polling()
