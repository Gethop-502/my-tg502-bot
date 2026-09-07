import os
import re
import requests
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import telebot
from telebot import types

# خادم وهمي لإبقاء البوت نشطاً على Render
class SimpleServer(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Server Live 24/7!")

def run_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), SimpleServer)
    server.serve_forever()

threading.Thread(target=run_server, daemon=True).start()

BOT_TOKEN = "8945302717:AAHEAkn89ygLc5QtwhuWRKIG-v0ucebQfyY"
bot = telebot.TeleBot(BOT_TOKEN)
user_links = {}

USER_AGENT = "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1"

def clean_and_resolve_url(raw_text):
    # استخراج الرابط بدقة وعزله عن أي نصوص أخرى
    match = re.search(r'(https?://[^\s]+)', raw_text)
    if not match:
        return None
    url = match.group(1).strip()

    # فك توجيه الروابط المختصرة (vm.tiktok / vt.tiktok / youtu.be)
    try:
        session = requests.Session()
        session.headers.update({"User-Agent": USER_AGENT})
        res = session.get(url, allow_redirects=True, timeout=12)
        url = res.url.split("?")[0]
    except Exception:
        url = url.split("?")[0]
        
    return url

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    bot.reply_to(message, "👋 مرحباً بك! أرسل رابط الفيديو (يوتيوب أو تيك توك) وسأقوم بتحميله فوراً.")

@bot.message_handler(func=lambda msg: msg.text and any(d in msg.text for d in ["tiktok.com", "youtube.com", "youtu.be"]))
def handle_link(message):
    user_id = message.from_user.id
    url = clean_and_resolve_url(message.text)

    if not url:
        bot.reply_to(message, "⚠️ الرابط غير صالح، تأكد من إرسال رابط صحيح.")
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
    msg = bot.send_message(call.message.chat.id, "⏳ جاري استخراج وتجهيز الملف...")

    download_url = None

    # --- معالجة تيك توك عبر واجهتين لضمان النجاح ---
    if "tiktok.com" in url:
        # المحاولة الأولى: tikwm
        try:
            r = requests.post("https://www.tikwm.com/api/", data={"url": url}, headers={"User-Agent": USER_AGENT}, timeout=15).json()
            if r.get("code") == 0:
                d = r.get("data", {})
                download_url = d.get("music") if choice == 'mp3' else (d.get("play") or d.get("wmplay"))
        except Exception:
            pass

        # المحاولة الثانية في حال فشل الأولى: lovetik API
        if not download_url:
            try:
                r2 = requests.post("https://lovetik.com/api/ajax/search", data={"query": url}, timeout=15).json()
                if choice == 'mp3':
                    download_url = r2.get("links", [])[-1].get("a")
                else:
                    download_url = r2.get("links", [])[0].get("a")
            except Exception:
                pass

    # --- معالجة يوتيوب أو الروابط العامة عبر cobalt API ---
    if not download_url:
        try:
            api_url = "https://co.wuk.sh/api/json"
            headers = {"Accept": "application/json", "Content-Type": "application/json", "User-Agent": USER_AGENT}
            payload = {
                "url": url,
                "videoQuality": choice if choice != 'mp3' else "720",
                "downloadMode": "audio" if choice == 'mp3' else "auto"
            }
            resp = requests.post(api_url, json=payload, headers=headers, timeout=20).json()
            download_url = resp.get("url")
        except Exception:
            pass

    if not download_url:
        bot.edit_message_text("⚠️ تعذر استخراج الرابط المباشر، قد يكون المقطع خاصاً أو مقيداً.", call.message.chat.id, msg.message_id)
        return

    bot.edit_message_text("⚡ تم العثور على المقطع! جاري تنزيله ورفعه إليك...", call.message.chat.id, msg.message_id)

    ext = "mp3" if choice == 'mp3' else "mp4"
    local_filename = f"file_{user_id}.{ext}"

    try:
        session = requests.Session()
        session.headers.update({"User-Agent": USER_AGENT})
        with session.get(download_url, stream=True, timeout=60) as r:
            r.raise_for_status()
            with open(local_filename, 'wb') as f:
                for chunk in r.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        f.write(chunk)

        # فحص الحجم المسموح به في تيليجرام
        if os.path.exists(local_filename) and os.path.getsize(local_filename) > 49 * 1024 * 1024:
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("📥 تنزيل المقطع كاملاً", url=download_url))
            bot.edit_message_text("⚠️ حجم المقطع يتجاوز 50 ميغابايت (حد التيليجرام)، اضغط أدناه للتنزيل المباشر:", call.message.chat.id, msg.message_id, reply_markup=markup)
            if os.path.exists(local_filename):
                os.remove(local_filename)
            return

        bot.send_chat_action(call.message.chat.id, 'upload_document' if choice == 'mp3' else 'upload_video')
        with open(local_filename, 'rb') as f:
            if choice == 'mp3':
                bot.send_audio(call.message.chat.id, f, caption="تم استخراج الصوت بنجاح 🎵")
            else:
                bot.send_video(call.message.chat.id, f, caption=f"تم التحميل بنجاح 🎬")

        if os.path.exists(local_filename):
            os.remove(local_filename)
        bot.delete_message(call.message.chat.id, msg.message_id)

    except Exception:
        bot.edit_message_text("حدث خطأ أثناء رفع الملف إلى التيليجرام.", call.message.chat.id, msg.message_id)
        if os.path.exists(local_filename):
            os.remove(local_filename)

bot.infinity_polling()
