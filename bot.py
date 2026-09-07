import os
import requests
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import telebot
from telebot import types
import yt_dlp

# خادم ويب وهمي لإبقاء البوت نشطاً عبر UptimeRobot
class SimpleServer(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot Server is Live & Active 24/7!")

def run_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), SimpleServer)
    server.serve_forever()

threading.Thread(target=run_server, daemon=True).start()

# إعداد البوت
BOT_TOKEN = "8945302717:AAHEAkn89ygLc5QtwhuWRKIG-v0ucebQfyY"
bot = telebot.TeleBot(BOT_TOKEN)
user_links = {}

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    bot.reply_to(message, "👋 أهلاً بك! أرسل رابط الفيديو من يوتيوب أو تيك توك وسأعرض لك خيارات الجودات المتوفرة.")

@bot.message_handler(func=lambda msg: msg.text and any(d in msg.text for d in ["tiktok.com", "youtube.com", "youtu.be"]))
def handle_link(message):
    user_id = message.from_user.id
    words = message.text.strip().split()
    url = next((w for w in words if any(d in w for d in ["tiktok.com", "youtube.com", "youtu.be"])), None)

    if not url:
        bot.reply_to(message, "يرجى إرسال رابط صحيح.")
        return

    # تنظيف الرابط من معاملات التتبع الإضافية
    url = url.split("?si=")[0]
    user_links[user_id] = url

    # لوحة مفاتيح الجودات والصيغ
    markup = types.InlineKeyboardMarkup(row_width=2)
    btn_360 = types.InlineKeyboardButton("🎬 360p", callback_data="res_360")
    btn_480 = types.InlineKeyboardButton("🎬 480p", callback_data="res_480")
    btn_720 = types.InlineKeyboardButton("🎬 720p", callback_data="res_720")
    btn_1080 = types.InlineKeyboardButton("🎬 1080p", callback_data="res_1080")
    btn_mp3 = types.InlineKeyboardButton("🎵 استخراج صوت MP3", callback_data="res_mp3")

    markup.add(btn_360, btn_480, btn_720, btn_1080)
    markup.add(btn_mp3)

    bot.reply_to(message, "اختر الجودة أو الصيغة المطلوبة:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('res_'))
def process_download(call):
    user_id = call.from_user.id
    choice = call.data.replace('res_', '')

    if user_id not in user_links:
        bot.answer_callback_query(call.id, "انتهت صلاحية الرابط، أعد إرساله.")
        return

    url = user_links[user_id]
    msg = bot.send_message(call.message.chat.id, "⏳ جاري استخراج أفضل رابط مناسب وتجهيزه...")

    # خيارات تجاوز فحص البوتات في يوتيوب وتيك توك
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'noplaylist': True,
        'extractor_args': {
            'youtube': {'player_client': ['android', 'ios']},
            'tiktok': {'app_version': ['latest']}
        },
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Mobile Safari/537.36',
        }
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            formats = info.get('formats', [])
            
            target_url = None

            if choice == 'mp3':
                # البحث عن مسار صوتي مباشر
                for f in reversed(formats):
                    if f.get('acodec') != 'none' and f.get('vcodec') == 'none' and f.get('url'):
                        target_url = f.get('url')
                        break
            else:
                max_h = int(choice)
                # البحث عن أفضل صيغة مدمجة (صوت وصورة معاً) أقل من أو تساوي الجودة المختارة
                for f in reversed(formats):
                    h = f.get('height') or 0
                    if f.get('acodec') != 'none' and f.get('vcodec') != 'none' and f.get('url'):
                        if h <= max_h:
                            target_url = f.get('url')
                            break

            # إذا لم يتم العثور على صيغة مطابقة تماماً، اختيار أول صيغة متوفرة مدمجة
            if not target_url:
                for f in reversed(formats):
                    if f.get('acodec') != 'none' and f.get('vcodec') != 'none' and f.get('url'):
                        target_url = f.get('url')
                        break

            if not target_url:
                target_url = info.get('url') or (formats[-1].get('url') if formats else None)

        if not target_url:
            raise Exception("لم يتوفر رابط تحميل مباشر.")

        bot.edit_message_text("⚡ جاري تنزيل الملف وإرساله إلى المحادثة...", call.message.chat.id, msg.message_id)

        ext = "mp3" if choice == 'mp3' else "mp4"
        local_filename = f"dl_{user_id}.{ext}"

        # تحميل الملف مباشرة كـ Stream لتفادي أخطاء المعالجة الداخلية
        headers = {'User-Agent': ydl_opts['http_headers']['User-Agent']}
        with requests.get(target_url, headers=headers, stream=True, timeout=60) as r:
            r.raise_for_status()
            with open(local_filename, 'wb') as f:
                for chunk in r.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        f.write(chunk)

        # التحقق من حد تيليجرام (50 ميغابايت)
        if os.path.exists(local_filename) and os.path.getsize(local_filename) > 49 * 1024 * 1024:
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("📥 تحميل المقطع عبر المتصفح", url=target_url))
            bot.edit_message_text("📦 حجم هذا المقطع أكبر من حد الرفع التلقائي في تيليجرام (50MB).\nيمكنك تنزيله بالكامل إلى جهازك عبر الزر التالي:", call.message.chat.id, msg.message_id, reply_markup=markup)
            if os.path.exists(local_filename):
                os.remove(local_filename)
            return

        bot.send_chat_action(call.message.chat.id, 'upload_video' if choice != 'mp3' else 'upload_document')
        with open(local_filename, 'rb') as f:
            if choice == 'mp3':
                bot.send_audio(call.message.chat.id, f, caption="تم استخراج الصوت بنجاح 🎵")
            else:
                bot.send_video(call.message.chat.id, f, caption=f"تم التحميل بجودة {choice}p 🎬", supports_streaming=True)

        if os.path.exists(local_filename):
            os.remove(local_filename)
        bot.delete_message(call.message.chat.id, msg.message_id)

    except Exception:
        # حل احتياطي فوري إذا واجه السيرفر أي تقييد إضافي
        try:
            with yt_dlp.YoutubeDL({'quiet': True, 'extractor_args': {'youtube': {'player_client': ['android']}}}) as fb:
                data = fb.extract_info(url, download=False)
                stream_link = data.get('url') or (data.get('formats', [{}])[-1].get('url'))
                if stream_link:
                    markup = types.InlineKeyboardMarkup()
                    markup.add(types.InlineKeyboardButton("📥 اضغط هنا للتحميل المباشر", url=stream_link))
                    bot.edit_message_text("⚠️ يوتيوب يفرض قيوداً على التحميل المباشر داخل التيليجرام لهذا المقطع. يمكنك تنزيله مباشرة من الرابط التالي:", call.message.chat.id, msg.message_id, reply_markup=markup)
                    return
        except Exception:
            pass

        bot.edit_message_text("تعذر تحميل المقطع. قد يكون خاصاً، أو مقيداً جغرافياً، أو يتطلب تسجيل دخول.", call.message.chat.id, msg.message_id)

bot.infinity_polling()
