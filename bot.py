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
from groq import Groq

# 1. Credentials from Render Environment
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8653764956:AAGE8ol1gvfUg9naFkMPD7wGqoDqw-0IFZY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

groq_client = Groq(api_key=GROQ_API_KEY)

# 2. Keep-Alive Web Server for Render
async def handle_ping(request):
    return web.Response(text="Translator Service Online!")

async def start_web_server():
    app = web.Application()
    app.router.add_get('/', handle_ping)
    app.router.add_get('/healthz', handle_ping)
    port = int(os.environ.get("PORT", 10000))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()

# 3. Dynamic Model Discovery (No hardcoded decommissioned names)
def execute_groq_text(prompt):
    if not GROQ_API_KEY:
        return "Error: GROQ_API_KEY is not configured in Render Environment."

    try:
        # Fetch the live list of models enabled on this API key
        model_list = groq_client.models.list()
        valid_models = [
            m.id for m in model_list.data
            if not any(x in m.id.lower() for x in ["whisper", "guard", "vision", "embed", "safeguard"])
        ]

        if not valid_models:
            return f"No chat models available on this key. Found: {[m.id for m in model_list.data]}"

        # Query the first available working chat model
        last_error = ""
        for model_id in valid_models:
            try:
                completion = groq_client.chat.completions.create(
                    model=model_id,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.3,
                    max_tokens=400,
                )
                if completion and completion.choices:
                    return completion.choices[0].message.content.strip()
            except Exception as inner_e:
                last_error = str(inner_e)
                continue

        return f"Model error: {last_error[:120]}"

    except Exception as e:
        return f"Groq Connection Error: {str(e)[:120]}"

# 4. Message Handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome = (
        "🌐 **Universal Real-Time Translator**\n\n"
        "Send any text or voice note. The bot will automatically detect the language "
        "and translate seamlessly back and forth!"
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
        "Instructions:\n"
        "1. Identify the input language accurately.\n"
        "2. If Primary is unset, register input language as Primary.\n"
        "3. If input is in a different language, register that as Partner.\n"
        "4. Translation rule:\n"
        "   - If input is Primary, translate directly to Partner (default to Persian or English if partner language is unknown).\n"
        "   - If input is Partner or foreign, translate directly into Primary.\n"
        "5. Output format (strictly 2 lines, no markdown symbols like *, _, or #):\n"
        "DETECTED: [Language Name]\n"
        "TRANSLATION: [Translated sentence only]\n\n"
        f"Input message:\n{text}"
    )

    response = execute_groq_text(prompt)

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
        with open(temp_path, "rb") as audio_file:
            transcription = groq_client.audio.transcriptions.create(
                file=(temp_path, audio_file.read()),
                model="whisper-large-v3-turbo"
            )
        spoken_text = transcription.text.strip()

        prompt = (
            f"You are a voice translator. Memory: [Lang A: {l_a}, Lang B: {l_b}].\n"
            "If the text is in Lang A (or Malayalam), translate to Lang B (e.g., Persian/English). "
            "If it is in Lang B (or foreign), translate to Lang A (Malayalam).\n"
            "Output strictly the translated sentence only, without markdown symbols.\n\n"
            f"Text: {spoken_text}"
        )
        translation = execute_groq_text(prompt)

        result_card = (
            f"🗣 Spoken: {spoken_text}\n"
            f"🌐 Translation: {translation}"
        )
        await update.message.reply_text(result_card)
    except Exception as e:
        await update.message.reply_text(f"Voice error: {str(e)[:100]}")
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)

# 5. Polling Loop with Crash Guard
async def run_bot():
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
            print("Starting polling listener...")
            await app.updater.start_polling(drop_pending_updates=True)
            while True:
                await asyncio.sleep(3600)
        except Exception as e:
            if "Conflict" in str(e):
                print("Old container closing down. Waiting 10s for takeover...")
                try:
                    await app.updater.stop()
                except Exception:
                    pass
                await asyncio.sleep(10)
            else:
                print(f"Network warning: {e}. Retrying in 5s...")
                await asyncio.sleep(5)

def main():
    try:
        asyncio.run(run_bot())
    except (KeyboardInterrupt, SystemExit):
        pass

if __name__ == "__main__":
    main()
