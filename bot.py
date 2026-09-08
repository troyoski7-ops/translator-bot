import os
import asyncio
from datetime import datetime
from aiohttp import web
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
)
from google import genai

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8653764956:AAG1x3qHbG5WMouZ6GiWOtJ5jROMLAbs9tY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

client = genai.Client(api_key=GEMINI_API_KEY)

LANGUAGES = [
    ("Arabic", "🇸🇦"), ("Bengali", "🇧🇩"), ("Chinese", "🇨🇳"), ("Dutch", "🇳🇱"),
    ("English", "🇬🇧"), ("French", "🇫🇷"), ("German", "🇩🇪"), ("Greek", "🇬🇷"),
    ("Hebrew", "🇮🇱"), ("Hindi", "🇮🇳"), ("Indonesian", "🇮🇩"), ("Italian", "🇮🇹"),
    ("Japanese", "🇯🇵"), ("Korean", "🇰🇷"), ("Malayalam", "🇮🇳"), ("Persian", "🇮🇷"),
    ("Polish", "🇵🇱"), ("Portuguese", "🇵🇹"), ("Russian", "🇷🇺"), ("Spanish", "🇪🇸"),
    ("Swedish", "🇸🇪"), ("Tamil", "🇮🇳"), ("Telugu", "🇮🇳"), ("Thai", "🇹🇭"),
    ("Turkish", "🇹🇷"), ("Ukrainian", "🇺🇦"), ("Urdu", "🇵🇰"), ("Vietnamese", "🇻🇳")
]

user_settings = {}

def get_user_config(user_id):
    if user_id not in user_settings:
        user_settings[user_id] = {
            "from": "Malayalam",
            "to": "German",
            "active": True,
            "show_phonetics": True,
            "translations_count": 0
        }
    return user_settings[user_id]

async def handle_ping(request):
    return web.Response(text="Bot Core Online & Ready!")

async def start_web_server():
    app = web.Application()
    app.router.add_get('/', handle_ping)
    app.router.add_get('/healthz', handle_ping)
    port = int(os.environ.get("PORT", 10000))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()

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
    return f"⚠️ Engine Busy. Please retry. ({last_err[:50]})"

def get_dashboard_markup(cfg):
    status_icon = "🟢 ACTIVE" if cfg["active"] else "🔴 PAUSED"
    toggle_icon = "🔔 Phonetics: ON" if cfg.get("show_phonetics", True) else "🔕 Phonetics: OFF"
    
    keyboard = [
        [
            InlineKeyboardButton(f"🗣 {cfg['from']}", callback_data="open_from_0"),
            InlineKeyboardButton("⇄ SWAP", callback_data="swap_langs"),
            InlineKeyboardButton(f"🎯 {cfg['to']}", callback_data="open_to_0")
        ],
        [
            InlineKeyboardButton(f"⚡ {status_icon}", callback_data="toggle_power"),
            InlineKeyboardButton(toggle_icon, callback_data="toggle_phonetics")
        ],
        [
            InlineKeyboardButton("📊 System Status", callback_data="view_status")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

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
        nav_row.append(InlineKeyboardButton("◀ Prev", callback_data=f"nav_{mode}_{page-1}"))
    if page < total_pages - 1:
        nav_row.append(InlineKeyboardButton("Next ▶", callback_data=f"nav_{mode}_{page+1}"))
    if nav_row:
        keyboard.append(nav_row)

    keyboard.append([InlineKeyboardButton("🔙 Return to Console", callback_data="back_dashboard")])
    return InlineKeyboardMarkup(keyboard)

def render_dashboard_text(cfg, user_name="User"):
    power_label = "ONLINE & LISTENING" if cfg["active"] else "PAUSED / STANDBY"
    return (
        "╔═══════════════════════════╗\n"
        "   ✦ POLY-WAVE TRANSLATION HUD ✦   \n"
        "╚═══════════════════════════╝\n\n"
        f"👤 Operator: {user_name}\n"
        f"⚡ Core Status: [{power_label}]\n"
        "─────────────────────────────\n"
        f"🎙 Channel A : ❮ {cfg['from']} ❯\n"
        f"🎧 Channel B : ❮ {cfg['to']} ❯\n"
        f"🔊 Pronunciation & Nuance : {'ACTIVE' if cfg['show_phonetics'] else 'MUTED'}\n"
        "─────────────────────────────\n"
        "💡 Commands:\n"
        "• Direct text/voice sends will auto-translate.\n"
        "• Use left menu (/status, /stop, /start) anytime."
    )

async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    cfg = get_user_config(user.id)
    text = render_dashboard_text(cfg, user.first_name)
    await update.message.reply_text(text, reply_markup=get_dashboard_markup(cfg))

async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    cfg = get_user_config(user.id)
    power_str = "🟢 LIVE (Active)" if cfg["active"] else "🔴 STANDBY (Paused)"
    status_card = (
        "┌───────────────────────────┐\n"
        "        ❖ SYSTEM DIAGNOSTICS ❖       \n"
        "└───────────────────────────┘\n\n"
        f"• Bot State      : {power_str}\n"
        f"• Active Route   : {cfg['from']} ⟷ {cfg['to']}\n"
        f"• Phonetic Guide : {'Enabled' if cfg['show_phonetics'] else 'Disabled'}\n"
        f"• Handled Total  : {cfg['translations_count']} translations\n"
        "─────────────────────────────\n"
        "Control via /stop or /resume"
    )
    await update.message.reply_text(status_card, reply_markup=get_dashboard_markup(cfg))

async def stop_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    cfg = get_user_config(user.id)
    cfg["active"] = False
    stop_msg = (
        "🛑 TRANSLATOR SUSPENDED\n\n"
        "The bot will ignore incoming messages while on pause.\n"
        "Tap below or type /resume to reactivate."
    )
    markup = InlineKeyboardMarkup([[InlineKeyboardButton("▶️ RESUME BOT", callback_data="resume_bot")]])
    await update.message.reply_text(stop_msg, reply_markup=markup)

async def resume_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    cfg = get_user_config(user.id)
    cfg["active"] = True
    await update.message.reply_text(
        "⚡ TRANSLATOR RESUMED\nReady to accept Voice and Text messages!",
        reply_markup=get_dashboard_markup(cfg)
    )

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user = update.effective_user
    cfg = get_user_config(user.id)

    if data.startswith("open_") or data.startswith("nav_"):
        _, mode, page = data.split("_")
        mode_title = "Input Language (Channel A)" if mode == "from" else "Target Language (Channel B)"
        await query.edit_message_text(
            f"Select {mode_title}:",
            reply_markup=build_language_keyboard(mode, int(page))
        )

    elif data.startswith("set_"):
        _, mode, lang = data.split("_")
        cfg[mode] = lang
        await query.edit_message_text(
            render_dashboard_text(cfg, user.first_name),
            reply_markup=get_dashboard_markup(cfg)
        )

    elif data == "swap_langs":
        cfg["from"], cfg["to"] = cfg["to"], cfg["from"]
        await query.edit_message_text(
            render_dashboard_text(cfg, user.first_name),
            reply_markup=get_dashboard_markup(cfg)
        )

    elif data == "toggle_power":
        cfg["active"] = not cfg["active"]
        await query.edit_message_text(
            render_dashboard_text(cfg, user.first_name),
            reply_markup=get_dashboard_markup(cfg)
        )

    elif data == "resume_bot":
        cfg["active"] = True
        await query.edit_message_text(
            render_dashboard_text(cfg, user.first_name),
            reply_markup=get_dashboard_markup(cfg)
        )

    elif data == "toggle_phonetics":
        cfg["show_phonetics"] = not cfg.get("show_phonetics", True)
        await query.edit_message_text(
            render_dashboard_text(cfg, user.first_name),
            reply_markup=get_dashboard_markup(cfg)
        )

    elif data == "view_status":
        await status_cmd(update, context)

    elif data == "back_dashboard":
        await query.edit_message_text(
            render_dashboard_text(cfg, user.first_name),
            reply_markup=get_dashboard_markup(cfg)
        )

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    cfg = get_user_config(user.id)

    if not cfg["active"]:
        return

    text = update.message.text
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

    phonetic_clause = (
        "Provide a 2nd line with readable simplified phonetics, and a 3rd line with a 1-sentence nuance note if applicable."
        if cfg.get("show_phonetics", True) else "Provide only the direct translation."
    )

    prompt = (
        f"You are a bilingual translation core between {cfg['from']} and {cfg['to']}.\n"
        f"1. Detect whether input is {cfg['from']} or {cfg['to']} (or other).\n"
        f"2. If {cfg['from']}, translate to {cfg['to']}. If {cfg['to']}, translate to {cfg['from']}.\n"
        f"3. {phonetic_clause}\n"
        f"Do NOT use markdown asterisks (*), hashes (#), or backticks. Strict format:\n"
        f"Translation: [Translated text]\n"
        f"Pronunciation: [Phonetics if enabled]\n"
        f"Nuance: [Tone/grammar tip if relevant]\n\n"
        f"Input:\n{text}"
    )

    result = await run_gemini(prompt)
    cfg["translations_count"] += 1

    formatted_card = (
        "╭───────────────────────────\n"
        f"│ 🌐 ROUTE: {cfg['from']} ⇄ {cfg['to']}\n"
        "├───────────────────────────\n"
        f"{result}\n"
        "╰───────────────────────────"
    )
    await update.message.reply_text(formatted_card)

async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    cfg = get_user_config(user.id)

    if not cfg["active"]:
        return

    voice = update.message.voice or update.message.audio
    if not voice:
        return

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="record_voice")

    file = await context.bot.get_file(voice.file_id)
    temp_path = f"temp_{voice.file_id}.ogg"
    await file.download_to_drive(temp_path)

    try:
        uploaded_audio = client.files.upload(file=temp_path)
        contents = [
            uploaded_audio,
            f"Bilingual voice translator between {cfg['from']} and {cfg['to']}.\n"
            f"1. Transcribe the audio.\n"
            f"2. Translate to opposite language.\n"
            f"3. Phonetic pronunciation guide.\n"
            f"Do not use markdown symbols:\n"
            f"Transcript: [Original speech]\n"
            f"Translation: [Target translation]\n"
            f"Pronunciation: [Phonetics]"
        ]
        result = await run_gemini(contents)
        cfg["translations_count"] += 1

        voice_card = (
            "╭─── 🎙 VOICE DECODER ──────\n"
            f"│ 🌐 ROUTE: {cfg['from']} ⇄ {cfg['to']}\n"
            "├───────────────────────────\n"
            f"{result}\n"
            "╰───────────────────────────"
        )
        await update.message.reply_text(voice_card)
    except Exception as e:
        await update.message.reply_text(f"Voice error: {e}")
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)

async def setup_commands(app):
    commands = [
        BotCommand("start", "Launch Interactive Console"),
        BotCommand("status", "System Diagnostics"),
        BotCommand("stop", "Pause Translation"),
        BotCommand("resume", "Resume Translation"),
    ]
    try:
        await app.bot.set_my_commands(commands)
    except Exception as e:
        print(f"Commands setup warning: {e}")

async def main():
    await start_web_server()

    application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start_cmd))
    application.add_handler(CommandHandler("status", status_cmd))
    application.add_handler(CommandHandler("stop", stop_cmd))
    application.add_handler(CommandHandler("resume", resume_cmd))
    application.add_handler(CallbackQueryHandler(handle_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    application.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, handle_voice))

    async with application:
        await application.start()
        await setup_commands(application)
        await application.updater.start_polling(drop_pending_updates=True)
        while True:
            await asyncio.sleep(3600)

if __name__ == "__main__":
    asyncio.run(main())
