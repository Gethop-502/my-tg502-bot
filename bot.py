import yt_dlp

# خريطة الجودات لليوتيوب وتيك توك
# نستخدم دمج الفيديو والصوت تلقائياً مع السماح بالهبوط لأفضل جودة متاحة إذا لم يتطابق الارتفاع بالضبط
FORMAT_OPTIONS = {
    '360p': 'bestvideo[height<=360]+bestaudio/best[height<=360]/best',
    '480p': 'bestvideo[height<=480]+bestaudio/best[height<=480]/best',
    '720p': 'bestvideo[height<=720]+bestaudio/best[height<=720]/best',
    '1080p': 'bestvideo[height<=1080]+bestaudio/best[height<=1080]/best',
    'mp3': 'bestaudio/best'
}

def get_ydl_opts(quality_key):
    is_audio = quality_key == 'mp3'
    
    opts = {
        'format': FORMAT_OPTIONS.get(quality_key, 'best'),
        'outtmpl': 'downloads/%(id)s.%(ext)s',
        'quiet': True,
        'no_warnings': True,
        # تجاوز حظر User-Agent ورؤوس التشفير
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
            'Accept-Language': 'en-US,en;q=0.9',
        },
        # منع التوقف في حال وجود مشاكل ببروتوكول HTTPS
        'nocheckcertificate': True,
    }

    if is_audio:
        opts['postprocessors'] = [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }]
    else:
        # دمج المقاطع في صيغة mp4 متوافقة مع تليجرام
        opts['merge_output_format'] = 'mp4'

    return opts
    
