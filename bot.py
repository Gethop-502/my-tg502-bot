import os
import requests
import telebot
from telebot import types
import yt_dlp

BOT_TOKEN = "8945302717:AAHEAkn89ygLc5QtwhuWRKIG-v0ucebQfyY"

bot = telebot.TeleBot(BOT_TOKEN)

user_links = {}

def expand_url(url):
    try:
        response = requests.head(url, allow_redirects=True, timeout=10)
        return response.url
    except Exception:
        return url

FORMAT_OPTIONS = {
    '360p': 'bestvideo[height<=360]+bestaudio/best[height<=360]/best',
    '480p': 'bestvideo[height<=480]+bestaudio/best[height<=480]/best',
    '720p': 'bestvideo[height<=720]+bestaudio/best[height<=720]/best',
    '1080p': 'bestvideo[height<=1080]+bestaudio/best[height<=1080]/best',
    'mp3': 'bestaudio/best'
}

def get_ydl_opts(quality_key):
    is_audio = quality_key == 'mp3'
    os.makedirs('downloads', exist_ok=True)
    
    opts = {
        'format': FORMAT_OPTIONS.get(quality_key, 'best'),
        'outtmpl': 'downloads/%(id)s.%(ext)s',
        'quiet': True,
        'no_warnings': True,
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
            'Accept-Language': 'en-US,en;q=0.9',
        },
        'nocheckcertificate': True,
    }

    if is_audio:
        opts['postprocessors'] = [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }]
    else:
        opts['merge_output_format'] = 'mp4'

    return opts

@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, "مرحباً بك! أرسل رابط الفيديو من تيك توك أو يوتيوب للتحميل مباشرة.")

@bot.message_handler(func=lambda msg: msg.text and ("tiktok.com" in msg.text or "youtu" in msg.text))
def handle_link(message):
    chat_id = message.chat.id
    raw_url = message.text.strip()
    
    full_url = expand_url(raw_url)
    user_links[chat_id] = full_url

    markup = types.InlineKeyboardMarkup(row_width=2)
    btn_360 = types.InlineKeyboardButton("🎬 360p", callback_data="360p")
    btn_480 = types.InlineKeyboardButton("🎬 480p", callback_data="480p")
    btn_720 = types.InlineKeyboardButton("🎬 720p", callback_data="720p")
    btn_1080 = types.InlineKeyboardButton("🎬 1080p", callback_data="1080p")
    btn_mp3 = types.InlineKeyboardButton("🎵 استخراج صوت MP3", callback_data="mp3")
    
    markup.add(btn_360, btn_480, btn_720, btn_1080)
    markup.add(btn_mp3)

    bot.reply_to(message, "اختر الجودة أو الصيغة المطلوبة:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: True)
def process_download(call):
    chat_id = call.message.chat.id
    quality = call.data
    url = user_links.get(chat_id)

    if not url:
        bot.send_message(chat_id, "⚠️ انتهت صلاحية الطلب، يرجى إعادة إرسال الرابط من جديد.")
        return

    status_msg = bot.send_message(chat_id, "⏳ جاري التحميل والمعالجة، يرجى الانتظار...")

    try:
        ydl_opts = get_ydl_opts(quality)
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            file_path = ydl.prepare_filename(info)

            if quality == 'mp3':
                file_path = os.path.splitext(file_path)[0] + '.mp3'

        with open(file_path, 'rb') as media_file:
            if quality == 'mp3':
                bot.send_audio(chat_id, media_file)
            else:
                bot.send_video(chat_id, media_file)

        if os.path.exists(file_path):
            os.remove(file_path)

        bot.delete_message(chat_id, status_msg.message_id)

    except Exception:
        bot.edit_message_text("⚠️ تعذر استخراج أو تحميل المقطع. قد يكون المقطع مقيداً أو حجمه كبيراً جداً.", chat_id, status_msg.message_id)

if __name__ == "__main__":
    bot.infinity_polling()
