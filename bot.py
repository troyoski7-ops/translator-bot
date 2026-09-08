import os
import re
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

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8653764956:AAGE8ol1gvfUg9naFkMPD7wGqoDqw-0IFZY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

groq_client = Groq(api_key=GROQ_API_KEY)

# Render Keep-Alive Port Bind
async def handle_ping(request):
    return web.Response(text="Translator Active!")

async def start_web_server():
    app = web.Application()
    app.router.add_get('/', handle_ping)
    app.router.add_get('/healthz', handle_ping)
    port = int(os.environ.get("PORT", 10000))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()

def execute_translation(prompt):
    if not GROQ_API_KEY:
        return "Error: GROQ_API_KEY is missing."

    try:
        model_list = groq_client.models.list()
        valid_models = [
            m.id for m in model_list.data
            if not any(x in m.id.lower() for x in ["whisper", "guard", "vision", "embed", "safeguard"])
        ]

        for model_id in valid_models:
            try:
                completion = groq_client.chat.completions.create(
                    model=model_id,
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "You are an invisible real-time translator between two chat partners. "
                                "Translate the given input directly into the other partner's language. "
                                "Return ONLY the translated sentence. Never explain, never greet, "
                                "and never include <think> tags or reasoning."
                            )
                        },
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.2,
                    max_tokens=350,
                )
                if completion and completion.choices:
                    res = completion.choices[0].message.content.strip()
                    res = re.sub(r'<think>.*?</think>', '', res, flags=re.DOTALL).strip()
                    return res
            except Exception:
                continue

        return "Translation failed. Please try again."
    except Exception as e:
        return f"Error: {str(e)[:80]}"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🌐 Send any message or voice note. It will translate automatically!")

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

    recent_pair = context.chat_data.get("pair", [])

    prompt = (
        f"Known conversation context: {recent_pair}\n"
        f"Input: \"{text}\"\n\n"
        "Task:\n"
        "1. Identify the language of the input.\n"
        "2. If input matches the first language of this conversation, translate to the second language.\n"
        "3. If input matches the second language (or a new foreign language), translate to the first language.\n"
        "4. If this is the start and only one language is seen, translate it into English by default so it can be understood.\n"
        "Output ONLY the final translation."
    )

    translation = execute_translation(prompt)
    await update.message.reply_text(translation)

async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    voice = update.message.voice or update.message.audio
    if not voice:
        return

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="record_voice")

    file = await context.bot.get_file(voice.file_id)
    temp_path = f"temp_{voice.file_id}.ogg"
    await file.download_to_drive(temp_path)

    try:
        with open(temp_path, "rb") as audio_file:
            transcription = groq_client.audio.transcriptions.create(
                file=(temp_path, audio_file.read()),
                model="whisper-large-v3-turbo"
            )
        spoken_text = transcription.text.strip()

        prompt = (
            f"Input text from voice note: \"{spoken_text}\"\n"
            "Translate this directly to the alternate language of this chat. "
            "Output ONLY the translated sentence."
        )
        translation = execute_translation(prompt)

        await update.message.reply_text(f"🗣 {spoken_text}\n\n🌐 {translation}")
    except Exception as e:
        await update.message.reply_text(f"Voice error: {str(e)[:80]}")
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)

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
            await app.updater.start_polling(drop_pending_updates=True)
            while True:
                await asyncio.sleep(3600)
        except Exception as e:
            if "Conflict" in str(e):
                try:
                    await app.updater.stop()
                except Exception:
                    pass
                await asyncio.sleep(10)
            else:
                await asyncio.sleep(5)

def main():
    try:
        asyncio.run(run_bot())
    except (KeyboardInterrupt, SystemExit):
        pass

if __name__ == "__main__":
    main()
