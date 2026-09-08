import os
import asyncio
from aiohttp import web
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)
from google import genai

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8653764956:AAGE8ol1gvfUg9naFkMPD7wGqoDqw-0IFZY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

client = genai.Client(api_key=GEMINI_API_KEY)

# Render Keep-Alive Port Bind
async def handle_ping(request):
    return web.Response(text="Translator Core Online!")

async def start_web_server():
    app = web.Application()
    app.router.add_get('/', handle_ping)
    app.router.add_get('/healthz', handle_ping)
    port = int(os.environ.get("PORT", 10000))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()

# Production Model Fallback
MODELS = ["gemini-2.0-flash", "gemini-1.5-flash"]

async def execute_gemini(contents):
    last_err = ""
    for model_name in MODELS:
        try:
            res = client.models.generate_content(
                model=model_name,
                contents=contents
            )
            if res and res.text:
                return res.text.strip()
        except Exception as e:
            last_err = str(e)
            await asyncio.sleep(1)
            continue
    return f"Translation error: ({last_err[:60]})"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome = (
        "🌐 **Universal Real-Time Translator**\n\n"
        "Communicate seamlessly in any language across the world!\n\n"
        "• **Zero Setup:** No need to configure or select languages manually.\n"
        "• **Smart Pairing:** The bot detects your language and your friend's language automatically.\n"
        "• **Two-Way Translation:** If you write or speak in Malayalam, it translates to your partner's language (e.g., Persian, German, French). When they reply in their language, it instantly translates back for you.\n\n"
        "Simply send any **Text** or **Voice note** to get started!"
    )
    await update.message.reply_text(welcome, parse_mode="Markdown")

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()

    if "lang_a" not in context.chat_data:
        context.chat_data["lang_a"] = None
    if "lang_b" not in context.chat_data:
        context.chat_data["lang_b"] = None

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

    l_a = context.chat_data.get("lang_a")
    l_b = context.chat_data.get("lang_b")

    prompt = (
        "You are an omnilingual, adaptive two-way interpreter for any two people chatting in different languages.\n"
        f"Chat Memory: [Primary Language: {l_a}, Partner Language: {l_b}]\n\n"
        "Tasks:\n"
        "1. Detect the language of the incoming message accurately.\n"
        "2. If Primary Language is unset, set it as the incoming language.\n"
        "3. If incoming message is in a DIFFERENT language, recognize that as Partner Language.\n"
        "4. Seamless Translation:\n"
        "   - If input is in Primary Language, translate it into Partner Language (if Partner Language is not yet known, translate into Persian or English by default).\n"
        "   - If input is in Partner Language (or any other foreign language), translate directly into Primary Language.\n"
        "5. Output STRICTLY in this two-line format with NO markdown symbols (*, _, #):\n"
        "DETECTED: [Language Name]\n"
        "TRANSLATION: [Only the translated sentence]"
        f"\n\nMessage:\n{text}"
    )

    response = await execute_gemini(prompt)

    lines = response.splitlines()
    detected_lang = None
    final_translation = response

    for line in lines:
        if line.startswith("DETECTED:"):
            detected_lang = line.replace("DETECTED:", "").strip()
        elif line.startswith("TRANSLATION:"):
            final_translation = line.replace("TRANSLATION:", "").strip()

    if detected_lang:
        if not context.chat_data["lang_a"]:
            context.chat_data["lang_a"] = detected_lang
        elif detected_lang.lower() != context.chat_data["lang_a"].lower() and not context.chat_data["lang_b"]:
            context.chat_data["lang_b"] = detected_lang

    await update.message.reply_text(final_translation)

async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    voice = update.message.voice or update.message.audio
    if not voice:
        return

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="record_voice")

    file = await context.bot.get_file(voice.file_id)
    temp_path = f"temp_{voice.file_id}.ogg"
    await file.download_to_drive(temp_path)

    l_a = context.chat_data.get("lang_a")
    l_b = context.chat_data.get("lang_b")

    try:
        uploaded_audio = client.files.upload(file=temp_path)
        prompt = [
            uploaded_audio,
            f"Universal voice translator. Memory: [Lang A: {l_a}, Lang B: {l_b}].\n"
            "1. Transcribe the audio accurately.\n"
            "2. Detect the spoken language.\n"
            "3. If spoken in Lang A, translate to Lang B (e.g., Persian). If spoken in Lang B or any foreign language, translate to Lang A.\n"
            "Format strictly without asterisks:\n"
            "🗣 Spoken: [Transcribed speech]\n"
            "🌐 Translation: [Translated sentence]"
        ]
        result = await execute_gemini(prompt)
        await update.message.reply_text(result)
    except Exception as e:
        await update.message.reply_text("Could not recognize speech. Please speak clearly and try again.")
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)

async def main():
    await start_web_server()

    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, handle_voice))

    await app.initialize()
    try:
        await app.bot.delete_webhook(drop_pending_updates=True)
    except Exception:
        pass

    await app.start()

    while True:
        try:
            await app.updater.start_polling(drop_pending_updates=True)
            while True:
                await asyncio.sleep(3600)
        except Exception as e:
            if "Conflict" in str(e):
                await asyncio.sleep(10)
            else:
                await asyncio.sleep(5)

if __name__ == "__main__":
    asyncio.run(main())
