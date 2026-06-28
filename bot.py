import os
import asyncio
import yt_dlp
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, filters, ContextTypes
)

BOT_TOKEN = os.environ.get("BOT_TOKEN")

# نگه داشتن لینک هر کاربر
user_links = {}

# ==================== START ====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎬 *ربات دانلودر یوتیوب*\n\n"
        "لینک ویدیو یوتیوب رو بفرست تا دانلودش کنم 👇\n\n"
        "✅ پشتیبانی از ویدیو و صدا\n"
        "⚡ کیفیت‌های مختلف",
        parse_mode="Markdown"
    )

# ==================== دریافت لینک ====================
async def handle_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()

    if "youtube.com" not in url and "youtu.be" not in url:
        await update.message.reply_text(
            "❌ این لینک یوتیوب نیست!\n"
            "یه لینک مثل این بفرست:\n"
            "https://youtube.com/watch?v=..."
        )
        return

    user_id = update.effective_user.id
    user_links[user_id] = url

    msg = await update.message.reply_text("⏳ در حال بررسی ویدیو...")

    try:
        ydl_opts = {"quiet": True, "skip_download": True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

        title = info.get("title", "ویدیو")[:60]
        duration = info.get("duration", 0)
        mins = duration // 60
        secs = duration % 60
        uploader = info.get("uploader", "نامشخص")

        keyboard = [
            [
                InlineKeyboardButton("🎬 360p", callback_data="video_360"),
                InlineKeyboardButton("🎬 720p", callback_data="video_720"),
            ],
            [
                InlineKeyboardButton("🎵 فقط صدا (MP3)", callback_data="audio_mp3"),
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await msg.edit_text(
            f"✅ *ویدیو پیدا شد!*\n\n"
            f"📌 *عنوان:* {title}\n"
            f"👤 *کانال:* {uploader}\n"
            f"⏱ *مدت:* {mins}:{secs:02d}\n\n"
            f"کیفیت دانلود رو انتخاب کن 👇",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )

    except Exception as e:
        await msg.edit_text(
            "❌ خطا در بررسی ویدیو!\n"
            "لینک رو چک کن یا دوباره امتحان کن."
        )

# ==================== دانلود ====================
async def handle_quality(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    url = user_links.get(user_id)

    if not url:
        await query.edit_message_text("❌ لینک پیدا نشد. دوباره لینک بفرست.")
        return

    choice = query.data
    await query.edit_message_text("⏳ در حال دانلود... لطفاً صبر کن 🙏")

    try:
        output_path = f"/tmp/{user_id}"

        if choice == "audio_mp3":
            ydl_opts = {
                "format": "bestaudio/best",
                "outtmpl": f"{output_path}.%(ext)s",
                "postprocessors": [{
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "192",
                }],
                "quiet": True,
            }
        elif choice == "video_360":
            ydl_opts = {
                "format": "best[height<=360][ext=mp4]/best[height<=360]/best",
                "outtmpl": f"{output_path}.%(ext)s",
                "quiet": True,
            }
        else:  # 720p
            ydl_opts = {
                "format": "best[height<=720][ext=mp4]/best[height<=720]/best",
                "outtmpl": f"{output_path}.%(ext)s",
                "quiet": True,
            }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            title = info.get("title", "فایل")[:50]

        # پیدا کردن فایل دانلود شده
        import glob
        files = glob.glob(f"{output_path}.*")
        if not files:
            raise Exception("فایل پیدا نشد")
        filepath = files[0]

        await query.edit_message_text("📤 در حال ارسال فایل...")

        with open(filepath, "rb") as f:
            if choice == "audio_mp3":
                await context.bot.send_audio(
                    chat_id=query.message.chat_id,
                    audio=f,
                    title=title,
                    caption=f"🎵 {title}\n\n@YourBotUsername"
                )
            else:
                quality = "360p" if choice == "video_360" else "720p"
                await context.bot.send_video(
                    chat_id=query.message.chat_id,
                    video=f,
                    caption=f"🎬 {title} | {quality}\n\n@YourBotUsername",
                    supports_streaming=True
                )

        os.remove(filepath)
        await query.edit_message_text(
            "✅ *دانلود موفق!*\n\nلینک بعدی رو بفرست 👇",
            parse_mode="Markdown"
        )

    except Exception as e:
        error_msg = str(e)
        if "filesize" in error_msg or "too large" in error_msg.lower():
            msg = "❌ فایل خیلی بزرگه! تلگرام حداکثر 50MB قبول میکنه."
        elif "Private" in error_msg:
            msg = "❌ این ویدیو خصوصیه و قابل دانلود نیست."
        else:
            msg = f"❌ خطا در دانلود!\nدوباره امتحان کن."
        await query.edit_message_text(msg)

# ==================== MAIN ====================
def main():
    if not BOT_TOKEN:
        print("❌ BOT_TOKEN تنظیم نشده!")
        return

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_link))
    app.add_handler(CallbackQueryHandler(handle_quality))

    print("✅ ربات دانلودر یوتیوب روشنه!")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
