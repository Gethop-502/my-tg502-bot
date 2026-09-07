import os
import re
import requests
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import telebot
from telebot import types

# خادم وهمي لإبقاء الخدمة نشطة على Render
class SimpleServer(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is running smoothly!")

def run_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), SimpleServer)
    server.serve_forever()

threading.Thread(target=run_server, daemon=True).start()

BOT_TOKEN = os.environ.get("BOT_TOKEN", "8945302717:AAHEAkn89ygLc5QtwhuWRKIG-v0ucebQfyY")
bot = telebot.TeleBot(BOT_TOKEN)
user_links = {}

def extract_url(text):
    match = re.search(r'(https?://[^\s]+)', text)
    return match.group(1).strip() if match else None

def fetch_media_link(url, is_audio=False):
    # خادم وسيط مجاني لتجاوز الحظر
    api_endpoint = "https://co.wuk.sh/api/json"
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
    payload = {
        "url": url,
        "isAudioOnly": is_audio,
        "aFormat": "mp3" if is_audio else "best",
        "vQuality": "720"
    }
    
    response = requests.post(api_endpoint, json=payload, headers=headers, timeout=20)
    data = response.json()
    
    if "url" in data:
        return data["url"]
    return None

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    bot.reply_to(message, "مرحباً بك! أرسل رابط يوتيوب أو تيك توك وسأقوم بتجهيزه فوراً.")

@bot.message_handler(func=lambda msg: msg.text and any(d in msg.text for d in ["tiktok.com", "youtube.com", "youtu.be"]))
def handle_link(message):
    user_id = message.from_user.id
    url = extract_url(message.text)

    if not url:
        bot.reply_to(message, "يرجى إرسال رابط صالح.")
        return

    user_links[user_id] = url

    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🎬 تحميل الفيديو", callback_data="res_video"),
        types.InlineKeyboardButton("🎵 استخراج الصوت MP3", callback_data="res_audio")
    )
    bot.reply_to(message, "اختر الصيغة المطلوبة:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('res_'))
def process_download(call):
    user_id = call.from_user.id
    choice = call.data.replace('res_', '')

    if user_id not in user_links:
        bot.answer_callback_query(call.id, "انتهت صلاحية الرابط، أعد إرساله مجدداً.")
        return

    url = user_links[user_id]
    status_msg = bot.send_message(call.message.chat.id, "جاري استخراج الرابط المباشر وتخطي الحظر...")

    try:
        is_audio = (choice == "audio")
        download_url = fetch_media_link(url, is_audio=is_audio)

        if not download_url:
            bot.edit_message_text("تعذر جلب رابط التحميل، تأكد من صحة الرابط وحاول مجدداً.", call.message.chat.id, status_msg.message_id)
            return

        # إرسال زر تحميل مباشر لتفادي حدود مساحة تيليجرام وسيرفر Render
        download_markup = types.InlineKeyboardMarkup()
        download_markup.add(types.InlineKeyboardButton("📥 اضغط هنا للتحميل المباشر", url=download_url))

        caption = "تم تجهيز المقطع الصوتي بنجاح:" if is_audio else "تم تجهيز رابط الفيديو بنجاح:"
        bot.edit_message_text(caption, call.message.chat.id, status_msg.message_id, reply_markup=download_markup)

    except Exception as e:
        bot.edit_message_text("حدث خطأ أثناء معالجة الطلب، حاول مرة أخرى لاحقاً.", call.message.chat.id, status_msg.message_id)

if __name__ == "__main__":
    bot.infinity_polling()
