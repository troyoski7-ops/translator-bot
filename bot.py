import os
import asyncio
from aiohttp import web
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from openai import OpenAI

# 1. Credentials
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8653764956:AAG1x3qHbG5WMouZ6GiWOtJ5jROMLAbs9tY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

client = OpenAI(api_key=OPENAI_API_KEY)

# 2. Render Dummy Web Server (Port Scan Fix)
async def handle_ping(request):
    return web.Response(text="Bot is running!")

async def start_web_server():
    app = web.Application()
    app.router.add_get('/', handle_ping)
    app.router.add_get('/healthz', handle_ping)
    
    port = int(os.environ.get("PORT", 10000))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    print(f"Web server started on port {port}")

# 3. Telegram Handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Hello! Send me text or a voice message to translate.")

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a helpful translator. Translate text accurately."},
                {"role": "user", "content": f"Translate this: {user_text}"}
            ]
        )
        translated_text = response.choices[0].message.content
        await update.message.reply_text(translated_text)
    except Exception as e:
        await update.message.reply_text(f"Error processing translation: {str(e)}")

async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    voice = update.message.voice or update.message.audio
    if not voice:
        return
    
    try:
        file = await context.bot.get_file(voice.file_id)
        voice_file_path = "temp_voice.ogg"
        await file.download_to_drive(voice_file_path)

        with open(voice_file_path, "rb") as audio:
            transcript = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio
            )
        
        user_text = transcript.text
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a helpful translator. Translate voice transcript accurately."},
                {"role": "user", "content": f"Translate this: {user_text}"}
            ]
        )
        translated_text = response.choices[0].message.content
        await update.message.reply_text(f"🗣 Recognized: {user_text}\n\n🌐 Translation: {translated_text}")

        if os.path.exists(voice_file_path):
            os.remove(voice_file_path)

    except Exception as e:
        await update.message.reply_text(f"Error processing voice: {str(e)}")

# 4. Main Runner
async def main():
    await start_web_server()

    application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    application.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, handle_voice))

    print("Bot is starting polling...")
    async with application:
        await application.start()
        await application.updater.start_polling(drop_pending_updates=True)
        while True:
            await asyncio.sleep(3600)

if __name__ == "__main__":
    asyncio.run(main())
