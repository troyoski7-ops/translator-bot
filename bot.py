import os
import asyncio
from aiohttp import web
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from google import genai

# Credentials
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8653764956:AAG1x3qHbG5WMouZ6GiWOtJ5jROMLAbs9tY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

client = genai.Client(api_key=GEMINI_API_KEY)

# Render Dummy Web Server
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

# Helper: Auto retry on temporary 503 high demand
async def generate_with_retry(contents, is_audio=False):
    for attempt in range(3):
        try:
            response = client.models.generate_content(
                model="gemini-3.6-flash",
                contents=contents
            )
            return response.text
        except Exception as e:
            if "503" in str(e) and attempt < 2:
                await asyncio.sleep(2)  # 2 സെക്കൻഡ് കാത്തിരുന്ന് വീണ്ടും ശ്രമിക്കും
                continue
            raise e

# Telegram Handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("ഹലോ! എനിക്ക് ടെക്സ്റ്റ് മെസ്സേജോ വോയ്സ് മെസ്സേജോ അയച്ചു തരൂ, ഞാൻ വിവർത്തനം ചെയ്തു തരാം.")

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    try:
        prompt = f"You are a professional translator. If the following text is in Malayalam, translate it accurately to English. If it is in any other language, translate it to Malayalam. Return ONLY the translated text without extra explanation:\n\n{user_text}"
        translated_text = await generate_with_retry(prompt)
        await update.message.reply_text(translated_text)
    except Exception as e:
        await update.message.reply_text("സെർവറിൽ ചെറിയ തിരക്കുണ്ട്, ദയവായി ഒരു നിമിഷത്തിന് ശേഷം വീണ്ടും അയക്കൂ.")

async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    voice = update.message.voice or update.message.audio
    if not voice:
        return
    
    try:
        file = await context.bot.get_file(voice.file_id)
        voice_file_path = "temp_voice.ogg"
        await file.download_to_drive(voice_file_path)

        uploaded_audio = client.files.upload(file=voice_file_path)

        contents = [
            uploaded_audio,
            "Transcribe this audio accurately. Then translate it: If the spoken language is Malayalam, translate to English. If it is any other language, translate to Malayalam. Output format:\n🗣 Transcript: [Transcribed text]\n🌐 Translation: [Translated text]"
        ]
        
        result_text = await generate_with_retry(contents, is_audio=True)
        await update.message.reply_text(result_text)

        if os.path.exists(voice_file_path):
            os.remove(voice_file_path)

    except Exception as e:
        await update.message.reply_text("വോയ്സ് പ്രോസസ്സ് ചെയ്യുന്നതിൽ തടസ്സം നേരിട്ടു, വീണ്ടും ശ്രമിക്കുക.")

# Main Runner
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
