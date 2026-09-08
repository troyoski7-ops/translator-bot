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
import google.generativeai as genai

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8653764956:AAGE8ol1gvfUg9naFkMPD7wGqoDqw-0IFZY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

if not GEMINI_API_KEY:
    print("WARNING: GEMINI_API_KEY is not set in Render Environment Variables!")

genai.configure(api_key=GEMINI_API_KEY)

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

# API കീയിൽ ലഭ്യമായ ആദ്യത്തെ വർക്കിംഗ് മോഡൽ എടുക്കുന്നു
def get_working_model():
    try:
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                if '1.5-flash' in m.name or 'gemini-pro' in m.name:
                    return genai.GenerativeModel(m.name)
        return genai.GenerativeModel('gemini-1.5-flash')
    except Exception:
        return genai.GenerativeModel('gemini-1.5-flash')

async def execute_gemini(contents):
    if not GEMINI_API_KEY:
        return "Error: GEMINI_API_KEY is missing in Render Environment settings!"
    
    try:
        model = get_working_model()
        res = model.generate_content(contents)
        if res and res.text:
            return res.text.strip()
    except Exception as e:
        return f"API Error: {str(e)[:100]}"
    return "No response received."

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome = (
        "🌐 **Universal Real-Time Translator**\n\n"
        "Communicate seamlessly in any language across the world!\n\n"
        "• **Zero Setup:** No need to configure or select languages manually.\n"
        "• **Smart Pairing:** The bot detects your language and your friend's language automatically.\n"
        "• **Two-Way Translation:** Send text or voice in any language and it translates instantly.\n\n"
        "Send any message to test!"
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
        "You are an omnilingual, adaptive two-way interpreter for two people chatting.\n"
        f"Chat Memory: [Primary: {l_a}, Partner: {l_b}]\n\n"
        "Tasks:\n"
        "1. Identify the input language accurately.\n"
        "2. If Primary is unset, register the input language as Primary.\n"
        "3. If input is in a different language, register that as Partner.\n"
        "4. Translation rule:\n"
        "   - If input is Primary, translate directly to Partner (default to Persian/English if partner language is not yet known).\n"
        "   - If input is Partner or foreign, translate directly into Primary.\n"
        "5. Output format (strictly 2 lines, no markdown symbols like *, _, or #):\n"
        "DETECTED: [Language Name]\n"
        "TRANSLATION: [Translated sentence only]"
        f"\n\nInput message:\n{text}"
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
        uploaded_audio = genai.upload_file(path=temp_path)
        prompt = [
            uploaded_audio,
            f"Universal voice interpreter. Memory: [Lang A: {l_a}, Lang B: {l_b}].\n"
            "1. Transcribe the audio accurately.\n"
            "2. Detect the spoken language.\n"
            "3. If spoken in Lang A, translate to Lang B. If spoken in Lang B or any foreign language, translate to Lang A.\n"
            "Strict clean format without asterisks:\n"
            "🗣 Spoken: [Transcribed words]\n"
            "🌐 Translation: [Translated sentence]"
        ]
        result = await execute_gemini(prompt)
        await update.message.reply_text(result)
    except Exception as e:
        await update.message.reply_text(f"Voice error: {e}")
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
 
