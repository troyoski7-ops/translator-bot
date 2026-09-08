import os
import asyncio
from aiohttp import web
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
)
from google import genai

# Credentials
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8653764956:AAG1x3qHbG5WMouZ6GiWOtJ5jROMLAbs9tY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

client = genai.Client(api_key=GEMINI_API_KEY)

# Global comprehensive language list
LANGUAGES = [
    ("Arabic", "🇸🇦"), ("Bengali", "🇧🇩"), ("Chinese", "🇨🇳"), ("Dutch", "🇳🇱"),
    ("English", "🇬🇧"), ("French", "🇫🇷"), ("German", "🇩🇪"), ("Greek", "🇬🇷"),
    ("Hebrew", "🇮🇱"), ("Hindi", "🇮🇳"), ("Indonesian", "🇮🇩"), ("Italian", "🇮🇹"),
    ("Japanese", "🇯🇵"), ("Korean", "🇰🇷"), ("Malayalam", "🇮🇳"), ("Persian", "🇮🇷"),
    ("Polish", "🇵🇱"), ("Portuguese", "🇵🇹"), ("Russian", "🇷🇺"), ("Spanish", "🇪🇸"),
    ("Swedish", "🇸🇪"), ("Tamil", "🇮🇳"), ("Telugu", "🇮🇳"), ("Thai", "🇹🇭"),
    ("Turkish", "🇹🇷"), ("Ukrainian", "🇺🇦"), ("Urdu", "🇵🇰"), ("Vietnamese", "🇻🇳")
]

# User preference storage: user_id -> {"from": "English", "to": "German", "nuance": True}
user_settings = {}

def get_user_config(user_id):
    if user_id not in user_settings:
        user_settings[user_id] = {"from": "English", "to": "German", "show_phonetics": True}
    return user_settings[user_id]

# Dummy Web Server for Render Keep-Alive
async def handle_ping(request):
    return web.Response(text="Bot is operational!")

async def start_web_server():
    app = web.Application()
    app.router.add_get('/', handle_ping)
    app.router.add_get('/healthz', handle_ping)
    port = int(os.environ.get("PORT", 10000))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()

# Resilient Multi-Model Failover
MODELS_TO_TRY = ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"]

async def run_gemini(contents):
    last_err = ""
    for model_name in MODELS_TO_TRY:
        for attempt in range(2):
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=contents
                )
                if response and response.text:
                    return response.text.strip()
            except Exception as e:
                last_err = str(e)
                await asyncio.sleep(1)
                continue
    return f"Service busy. Please try again in a moment. ({last_err[:60]})"

# Paginated Inline Keyboard Generator
def build_language_keyboard(mode, page=0):
    items_per_page = 8
    total_pages = (len(LANGUAGES) + items_per_page - 1) // items_per_page
    start_idx = page * items_per_page
    page_langs = LANGUAGES[start_idx:start_idx + items_per_page]

    keyboard = []
    for i in range(0, len(page_langs), 2):
        row = [InlineKeyboardButton(f"{page_langs[i][1]} {page_langs[i][0]}", callback_data=f"set_{mode}_{page_langs[i][0]}")]
        if i + 1 < len(page_langs):
            row.append(InlineKeyboardButton(f"{page_langs[i+1][1]} {page_langs[i+1][0]}", callback_data=f"set_{mode}_{page_langs[i+1][0]}"))
        keyboard.append(row)

    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"nav_{mode}_{page-1}"))
    if page < total_pages - 1:
        nav_row.append(InlineKeyboardButton("Next ➡️", callback_data=f"nav_{mode}_{page+1}"))
    if nav_row:
        keyboard.append(nav_row)

    keyboard.append([InlineKeyboardButton("🔙 Back to Settings", callback_data="back_to_menu")])
    return InlineKeyboardMarkup(keyboard)

def build_main_menu(cfg):
    toggle_icon = "✅" if cfg.get("show_phonetics", True) else "❌"
    keyboard = [
        [InlineKeyboardButton(f"🗣 My Language: {cfg['from']}", callback_data="open_from_0")],
        [InlineKeyboardButton(f"🎯 Target Language: {cfg['to']}", callback_data="open_to_0")],
        [InlineKeyboardButton("🔄 Swap Direction", callback_data="swap_langs")],
        [InlineKeyboardButton(f"{toggle_icon} Phonetics & Nuance Tips", callback_data="toggle_phonetics")]
    ]
    return InlineKeyboardMarkup(keyboard)

# Telegram Command & Callback Handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    cfg = get_user_config(user_id)
    text = (
        "🌐 **Universal Smart Translator**\n\n"
        f"• **Your Language:** {cfg['from']}\n"
        f"• **Target Language:** {cfg['to']}\n"
        f"• **Phonetics & Tips:** {'Enabled' if cfg['show_phonetics'] else 'Disabled'}\n\n"
        "Tap below to customize your languages, then send any **Text** or **Voice message**."
    )
    await update.message.reply_text(text, reply_markup=build_main_menu(cfg), parse_mode="Markdown")

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = update.effective_user.id
    cfg = get_user_config(user_id)

    if data.startswith("open_") or data.startswith("nav_"):
        _, mode, page = data.split("_")
        title = "Your Language (Input)" if mode == "from" else "Target Language (Output)"
        await query.edit_message_text(
            f"Select **{title}**:",
            reply_markup=build_language_keyboard(mode, int(page)),
            parse_mode="Markdown"
        )

    elif data.startswith("set_"):
        _, mode, lang = data.split("_")
        cfg[mode] = lang
        await query.edit_message_text(
            f"✅ **Preferences Saved!**\n\n• **Your Language:** {cfg['from']}\n• **Target Language:** {cfg['to']}",
            reply_markup=build_main_menu(cfg),
            parse_mode="Markdown"
        )

    elif data == "swap_langs":
        cfg["from"], cfg["to"] = cfg["to"], cfg["from"]
        await query.edit_message_text(
            f"🔄 **Direction Swapped!**\n\n• **Your Language:** {cfg['from']}\n• **Target Language:** {cfg['to']}",
            reply_markup=build_main_menu(cfg),
            parse_mode="Markdown"
        )

    elif data == "toggle_phonetics":
        cfg["show_phonetics"] = not cfg.get("show_phonetics", True)
        status = "enabled" if cfg["show_phonetics"] else "disabled"
        await query.edit_message_text(
            f"ℹ️ Phonetic pronunciation & tone tips **{status}**.",
            reply_markup=build_main_menu(cfg),
            parse_mode="Markdown"
        )

    elif data == "back_to_menu":
        await query.edit_message_text(
            "⚙️ **Translation Configuration:**",
            reply_markup=build_main_menu(cfg),
            parse_mode="Markdown"
        )

# Content Processing
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    cfg = get_user_config(user_id)
    text = update.message.text

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

    phonetic_instruction = (
        "Include a line with simple pronunciation/phonetics if the target script is non-Latin or tricky, "
        "and append a brief cultural tone nuance if relevant (e.g., formal vs informal address)."
        if cfg.get("show_phonetics", True) else "Return ONLY the translated text."
    )

    prompt = (
        f"You are an expert bilingual interpreter between {cfg['from']} and {cfg['to']}.\n"
        f"Task:\n"
        f"1. Detect whether the input is primarily in {cfg['from']} or {cfg['to']}.\n"
        f"2. If in {cfg['from']}, translate to {cfg['to']}. If in {cfg['to']} or another language, translate to {cfg['from']}.\n"
        f"3. {phonetic_instruction}\n"
        f"Format the output cleanly as:\n"
        f"🌐 **Translation:** [Translated text]\n"
        f"🗣 **Pronunciation:** [Phonetic transcription if applicable]\n"
        f"💡 **Note:** [1 short tone/nuance note if applicable]\n\n"
        f"Input:\n{text}"
    )

    result = await run_gemini(prompt)
    await update.message.reply_text(result, parse_mode="Markdown")

async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    voice = update.message.voice or update.message.audio
    if not voice:
        return

    user_id = update.effective_user.id
    cfg = get_user_config(user_id)

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="record_voice")

    file = await context.bot.get_file(voice.file_id)
    temp_path = f"temp_{voice.file_id}.ogg"
    await file.download_to_drive(temp_path)

    try:
        uploaded_audio = client.files.upload(file=temp_path)
        contents = [
            uploaded_audio,
            f"You are a native interpreter between {cfg['from']} and {cfg['to']}.\n"
            f"1. Transcribe the spoken audio accurately in its native language.\n"
            f"2. Translate it into the opposite language ({cfg['to']} if spoken in {cfg['from']}, or {cfg['from']} if spoken in foreign language).\n"
            f"3. Provide simple phonetic guide for pronunciation.\n"
            f"Format:\n"
            f"🎙 **Transcript:** [Original speech]\n"
            f"🌐 **Translation:** [Translated text]\n"
            f"🗣 **Pronunciation:** [Phonetics]"
        ]
        result = await run_gemini(contents)
        await update.message.reply_text(result, parse_mode="Markdown")
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)

async def main():
    await start_web_server()

    application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(handle_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    application.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, handle_voice))

    async with application:
        await application.start()
        await application.updater.start_polling(drop_pending_updates=True)
        while True:
            await asyncio.sleep(3600)

if __name__ == "__main__":
    asyncio.run(main())
