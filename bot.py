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
    return web.Response(text="Omnilingual Dynamic Engine Online")

async def start_web_server():
    app = web.Application()
    app.router.add_get('/', handle_ping)
    app.router.add_get('/healthz', handle_ping)
    port = int(os.environ.get("PORT", 10000))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()

# Multimodal Engine Cascade
MODELS = ["gemini-2.5-flash", "gemini-1.5-flash"]

async def execute_gemini(contents):
    last_err = ""
    for model in MODELS:
        try:
            res = client.models.generate_content(
                model=model,
                contents=contents
            )
            if res and res.text:
                return res.text.strip()
        except Exception as e:
            last_err = str(e)
            await asyncio.sleep(1)
            continue
    return f"വിവർത്തനം ചെയ്യാൻ സാധിച്ചില്ല. ({last_err[:50]})"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome = (
        "🌐 **Universal Dynamic Two-Way Translator**\n\n"
        "ഇവിടെ ഒരു സെറ്റിങ്സും ആവശ്യമില്ല!\n"
        "• നിങ്ങൾ സംസാരിക്കുന്ന ആളുടെ ഭാഷയും നിങ്ങളുടെ ഭാഷയും ബോട്ട് തനിയെ മനസ്സിലാക്കും.\n"
        "• ഉദാഹരണത്തിന്: നിങ്ങൾ മലയാളത്തിൽ 'സുഖം' എന്ന് അയക്കുകയും, സുഹൃത്ത് പേർഷ്യനിൽ (Persian/Farsi) മറുപടി അയക്കുകയും ചെയ്താൽ ബോട്ട് ഓട്ടോമാറ്റിക് ആയി രണ്ട് ഭാഷകളും പരസ്പരം വിവർത്തനം ചെയ്യും.\n\n"
        "ടെക്സ്റ്റോ വോയ്‌സോ നേരിട്ട് അയക്കൂ!"
    )
    await update.message.reply_text(welcome, parse_mode="Markdown")

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    chat_id = update.effective_chat.id

    # ചാറ്റിലെ സംഭാഷണത്തിന്റെ ഭാഷകൾ ട്രാക്ക് ചെയ്യാൻ ഹിസ്റ്ററി സൂക്ഷിക്കുന്നു
    if "lang_a" not in context.chat_data:
        context.chat_data["lang_a"] = None
    if "lang_b" not in context.chat_data:
        context.chat_data["lang_b"] = None

    await context.bot.send_chat_action(chat_id=chat_id, action="typing")

    l_a = context.chat_data.get("lang_a", "None")
    l_b = context.chat_data.get("lang_b", "None")

    prompt = (
        "You are an omnilingual, adaptive two-way conversational interpreter for any two people chatting.\n"
        f"Active chat memory: [Language A: {l_a}, Language B: {l_b}]\n\n"
        "Tasks:\n"
        "1. Detect the language of the incoming message.\n"
        "2. If Language A is not set, set it to the incoming language.\n"
        "3. If the incoming message is in a DIFFERENT language than Language A, lock that as Language B.\n"
        "4. Seamless Two-Way Translation Rule:\n"
        "   - If input is in Language A, translate to Language B (if Language B isn't known yet, translate to Persian/English contextual partner).\n"
        "   - If input is in Language B, translate directly into Language A.\n"
        "5. Return strictly in this 2-line format (NO asterisks or explanations):\n"
        "DETECTED: [Language Name]\n"
        "TRANSLATION: [Only the translated sentence]"
        f"\n\nInput message:\n{text}"
    )

    response = await execute_gemini(prompt)

    # ഔട്ട്പുട്ടിൽ നിന്ന് ട്രാൻസ്ലേഷൻ മാത്രം വേർതിരിക്കുന്നു
    lines = response.splitlines()
    detected_lang = None
    final_translation = response

    for line in lines:
        if line.startswith("DETECTED:"):
            detected_lang = line.replace("DETECTED:", "").strip()
        elif line.startswith("TRANSLATION:"):
            final_translation = line.replace("TRANSLATION:", "").strip()

    # ചാറ്റ് മെമ്മറി അപ്ഡേറ്റ് ചെയ്യുന്നു
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

    chat_id = update.effective_chat.id
    l_a = context.chat_data.get("lang_a", "None")
    l_b = context.chat_data.get("lang_b", "None")

    await context.bot.send_chat_action(chat_id=chat_id, action="record_voice")

    file = await context.bot.get_file(voice.file_id)
    temp_path = f"temp_{voice.file_id}.ogg"
    await file.download_to_drive(temp_path)

    try:
        uploaded_audio = client.files.upload(file=temp_path)
        prompt = [
            uploaded_audio,
            "You are a universal speech interpreter for two people talking in different languages.\n"
            f"Active languages in memory: [Language A: {l_a}, Language B: {l_b}]\n"
            "Tasks:\n"
            "1. Accurately transcribe the spoken voice in its original language.\n"
            "2. Detect the spoken language.\n"
            "3. If spoken in Language A, translate to Language B (e.g. Persian). If spoken in Language B (or foreign), translate into Language A.\n"
            "Output strictly formatted as (no markdown symbols):\n"
            "🗣 സംസാരം: [Transcribed words]\n"
            "🌐 വിവർത്തനം: [Translated words]"
        ]
        result = await execute_gemini(prompt)
        await update.message.reply_text(result)
    except Exception as e:
        await update.message.reply_text("വോയ്‌സ് മനസ്സിലാക്കാൻ സാധിച്ചില്ല, ദയവായി ഒന്നുകൂടി അയക്കൂ.")
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
