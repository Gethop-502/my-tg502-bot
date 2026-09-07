import os
import re
import requests
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import telebot
from telebot import types

# خادم وهمي لمنع توقف البوت على Render
class SimpleServer(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot 24/7 Active!")

def run_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), SimpleServer)
    server.serve_forever()

threading.Thread(target=run_server, daemon=True).start()

BOT_TOKEN = "8945302717:AAHEAkn89ygLc5QtwhuWRKIG-v0ucebQfyY"
bot = telebot.TeleBot(BOT_TOKEN)
user_links = {}

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"

def clean_url(text):
    match = re.search(r'(https?://[^\s]+)', text)
    if not match:
        return None
    return match.group(1).strip().split("?si=")[0]

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    bot.reply_to(message, "👋 أهلاً بك! أرسل رابط المقطع (يوتيوب أو تيك توك) وسأقوم بتحميله فوراً.")

@bot.message_handler(func=lambda msg: msg.text and any(d in msg.text for d in ["tiktok.com", "youtube.com", "youtu.be"]))
def handle_link(message):
    user_id = message.from_user.id
    url = clean_url(message.text)

    if not url:
        bot.reply_to(message, "⚠️ يرجى إرسال رابط صالح.")
        return

    user_links[user_id] = url

    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🎬 تحميل الفيديو (MP4)", callback_data="res_video"),
        types.InlineKeyboardButton("🎵 استخراج الصوت (MP3)", callback_data="res_audio")
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
    msg = bot.send_message(call.message.chat.id, "⏳ جاري استخراج الرابط المباشر وفك التشفير...")

    download_url = None

    # --- 1. مسار تيك توك (TikTok) ---
    if "tiktok.com" in url:
        try:
            # محاولة عبر TikWM API
            res = requests.post("https://www.tikwm.com/api/", data={"url": url}, headers={"User-Agent": USER_AGENT}, timeout=15).json()
            if res.get("code") == 0:
                data = res.get("data", {})
                download_url = data.get("music") if choice == "audio" else (data.get("play") or data.get("wmplay"))
        except Exception:
            pass

        if not download_url:
            try:
                # محاولة احتياطية عبر lovetik
                r = requests.post("https://lovetik.com/api/ajax/search", data={"query": url}, timeout=15).json()
                links = r.get("links", [])
                if choice == "audio":
                    download_url = links[-1].get("a")
                else:
                    download_url = links[0].get("a")
            except Exception:
                pass

    # --- 2. مسار يوتيوب (YouTube) عبر واجهات تفريغ وسيطة خارجية ---
    elif any(d in url for d in ["youtube.com", "youtu.be"]):
        # المحاولة الأولى: cobalt instances النشطة
        cobalt_nodes = [
            "https://api.cobalt.tools/api/json",
            "https://cobalt-api.kwiatekm.tokyo/api/json",
            "https://api.wuk.sh/api/json"
        ]
        
        for node in cobalt_nodes:
            try:
                payload = {
                    "url": url,
                    "videoQuality": "720",
                    "downloadMode": "audio" if choice == "audio" else "auto"
                }
                headers = {
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                    "User-Agent": USER_AGENT
                }
                resp = requests.post(node, json=payload, headers=headers, timeout=12)
                if resp.status_code == 200:
                    data = resp.json()
                    download_url = data.get("url")
                    if download_url:
                        break
            except Exception:
                continue

        # المحاولة الثانية: yt-downloaders API بديل
        if not download_url:
            try:
                api_req = f"https://api.siputzx.my.id/api/d/ytmp4?url={url}" if choice != "audio" else f"https://api.siputzx.my.id/api/d/ytmp3?url={url}"
                res = requests.get(api_req, timeout=15).json()
                download_url = res.get("data", {}).get("dl") or res.get("data", {}).get("url")
            except Exception:
                pass

    if not download_url:
        bot.edit_message_text("⚠️ تعذر فك تشفير هذا الرابط حالياً من المصدر، يرجى تجربة رابط آخر.", call.message.chat.id, msg.message_id)
        return

    # --- تنزيل الملف ورفعه للمحادثة ---
    bot.edit_message_text("⚡ تم الحصول على المقطع، جاري التنزيل والرفع للشات...", call.message.chat.id, msg.message_id)
    ext = "mp3" if choice == "audio" else "mp4"
    local_file = f"media_{user_id}.{ext}"

    try:
        with requests.get(download_url, headers={"User-Agent": USER_AGENT}, stream=True, timeout=60) as r:
            r.raise_for_status()
            with open(local_file, "wb") as f:
                for chunk in r.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        f.write(chunk)

        file_size = os.path.getsize(local_file)
        if file_size > 49 * 1024 * 1024:
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("📥 اضغط هنا للتحميل المباشر", url=download_url))
            bot.edit_message_text("⚠️ حجم المقطع يتجاوز 50 ميغا، يمكنك تحميله لجهازك مباشرة عبر الرابط أدناه:", call.message.chat.id, msg.message_id, reply_markup=markup)
            os.remove(local_file)
            return

        bot.send_chat_action(call.message.chat.id, "upload_document" if choice == "audio" else "upload_video")
        with open(local_file, "rb") as f:
            if choice == "audio":
                bot.send_audio(call.message.chat.id, f, caption="تم استخراج الصوت 🎵")
            else:
                bot.send_video(call.message.chat.id, f, caption="تم التحميل بنجاح 🎬", supports_streaming=True)

        bot.delete_message(call.message.chat.id, msg.message_id)

    except Exception:
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("📥 فتح رابط التنزيل المباشر", url=download_url))
        bot.edit_message_text("تعذر إرسال الملف مباشرة للشات، يمكنك تنزيله عبر الرابط المباشر:", call.message.chat.id, msg.message_id, reply_markup=markup)

    finally:
        if os.path.exists(local_file):
            try:
                os.remove(local_file)
            except Exception:
                pass

bot.infinity_polling()
