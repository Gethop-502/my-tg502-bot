import os
import re
import requests
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import telebot
from telebot import types

# خادم ويب وهمي لمنع توقف الاستضافة على Render
class SimpleServer(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is fully active 24/7!")

def run_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), SimpleServer)
    server.serve_forever()

threading.Thread(target=run_server, daemon=True).start()

BOT_TOKEN = "8945302717:AAHEAkn89ygLc5QtwhuWRKIG-v0ucebQfyY"
bot = telebot.TeleBot(BOT_TOKEN)
user_links = {}

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"

def clean_input_url(text):
    match = re.search(r'(https?://[^\s]+)', text)
    if not match:
        return None
    url = match.group(1).strip()
    return url.split("?si=")[0]

def extract_youtube_id(url):
    pattern = r'(?:v=|\/|youtu\.be\/|shorts\/)([0-9A-Za-z_-]{11})'
    match = re.search(pattern, url)
    return match.group(1) if match else None

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    bot.reply_to(message, "👋 أهلاً بك! أرسل أي رابط من تيك توك أو يوتيوب لبدء التحميل فوراً.")

@bot.message_handler(func=lambda msg: msg.text and any(d in msg.text for d in ["tiktok.com", "youtube.com", "youtu.be"]))
def handle_link(message):
    user_id = message.from_user.id
    clean_url = clean_input_url(message.text)

    if not clean_url:
        bot.reply_to(message, "⚠️ يرجى إرسال رابط صالح.")
        return

    user_links[user_id] = clean_url

    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🎬 تحميل الفيديو (MP4)", callback_data="res_video"),
        types.InlineKeyboardButton("🎵 استخراج الصوت (MP3)", callback_data="res_audio")
    )
    bot.reply_to(message, "اختر ما ترغب بتحميله:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('res_'))
def process_download(call):
    user_id = call.from_user.id
    choice = call.data.replace('res_', '')

    if user_id not in user_links:
        bot.answer_callback_query(call.id, "انتهت صلاحية الرابط، أعد إرساله.")
        return

    url = user_links[user_id]
    msg = bot.send_message(call.message.chat.id, "⏳ جاري استخراج المقطع وتجهيزه...")

    stream_url = None

    # --------------------------------------------------
    # 1. مسار تيك توك عبر محرك TikWM لتجاوز حظر Render
    # --------------------------------------------------
    if "tiktok.com" in url:
        try:
            req_url = f"https://www.tikwm.com/api/?url={url}&hd=1"
            res = requests.get(req_url, headers={"User-Agent": USER_AGENT}, timeout=15).json()
            if res.get("code") == 0:
                data = res.get("data", {})
                stream_url = data.get("music") if choice == "audio" else (data.get("play") or data.get("wmplay"))
        except Exception:
            pass

    # --------------------------------------------------
    # 2. مسار يوتيوب عبر خوادم Invidious النشطة
    # --------------------------------------------------
    elif any(d in url for d in ["youtube.com", "youtu.be"]):
        video_id = extract_youtube_id(url)
        if not video_id:
            bot.edit_message_text("⚠️ تعذر استخراج معرّف فيديو يوتيوب من الرابط.", call.message.chat.id, msg.message_id)
            return

        invidious_hosts = [
            "https://inv.nadeko.net",
            "https://invidious.nerdvpn.de",
            "https://invidious.jing.rocks",
            "https://yt.artemislena.eu"
        ]

        for host in invidious_hosts:
            try:
                # استخدام صيغ البث المباشرة (itag 18 للفيديو و itag 140 للصوت)
                itag = "140" if choice == "audio" else "18"
                test_url = f"{host}/latest_version?id={video_id}&itag={itag}"
                check = requests.head(test_url, headers={"User-Agent": USER_AGENT}, allow_redirects=True, timeout=8)
                if check.status_code in [200, 302]:
                    stream_url = check.url
                    break
            except Exception:
                continue

    if not stream_url:
        bot.edit_message_text("⚠️ تعذر جلب رابط التحميل، قد يكون المقطع خاصاً أو مقيداً جغرافياً.", call.message.chat.id, msg.message_id)
        return

    # --------------------------------------------------
    # 3. سحب الملف ورفعه إلى تيليجرام
    # --------------------------------------------------
    bot.edit_message_text("⚡ تم جلب الرابط، جاري الرفع إلى تيليجرام...", call.message.chat.id, msg.message_id)

    ext = "mp3" if choice == "audio" else "mp4"
    local_file = f"media_{user_id}.{ext}"

    try:
        with requests.get(stream_url, headers={"User-Agent": USER_AGENT}, stream=True, timeout=60) as r:
            r.raise_for_status()
            with open(local_file, "wb") as f:
                for chunk in r.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        f.write(chunk)

        # فحص سقف التيليجرام (50 ميغابايت)
        if os.path.exists(local_file) and os.path.getsize(local_file) > 49 * 1024 * 1024:
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("📥 تنزيل المقطع مباشرة", url=stream_url))
            bot.edit_message_text("⚠️ حجم المقطع يتجاوز 50 ميغا، اضغط الزر لتحميله مباشرة لجهازك:", call.message.chat.id, msg.message_id, reply_markup=markup)
            os.remove(local_file)
            return

        bot.send_chat_action(call.message.chat.id, "upload_document" if choice == "audio" else "upload_video")
        with open(local_file, "rb") as f:
            if choice == "audio":
                bot.send_audio(call.message.chat.id, f, caption="تم استخراج الصوت بنجاح 🎵")
            else:
                bot.send_video(call.message.chat.id, f, caption="تم التحميل بنجاح 🎬", supports_streaming=True)

        bot.delete_message(call.message.chat.id, msg.message_id)

    except Exception as e:
        bot.edit_message_text("⚠️ حدث خطأ أثناء إرسال الملف، حاول مجدداً.", call.message.chat.id, msg.message_id)

    finally:
        if os.path.exists(local_file):
            try:
                os.remove(local_file)
            except Exception:
                pass

bot.infinity_polling()
