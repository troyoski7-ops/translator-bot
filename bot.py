import os
import asyncio
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

# Credentials
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8653764956:AAGE8ol1gvfUg9naFkMPD7wGqoDqw-0IFZY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

client = genai.Client(api_key=GEMINI_API_KEY)

# Global Language Matrix
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
            "count": 0
        }
    return user_settings[user_id]

# Keep-Alive Server for Render
async def handle_ping(request):
    return web.Response(text="Bot Status: Online")

async def start_web_server():
    app = web.Application()
    app.router.add_get('/', handle_ping)
    app.router.add_get('/healthz', handle_ping)
    port = int(os.environ.get("PORT", 10000))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()

# Model Fallback Cascade (gemini-2.5-flash -> 2.0 -> 1.5)
MODELS = ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"]

async def execute_gemini(contents):
    last_err = ""
    for model in MODELS:
        for attempt in range(2):
            try:
                res = client.models.generate_content(model=model, contents=contents)
                if res and res.text:
                    return res.text.strip()
            except Exception as e:
                last_err = str(e)
                if "503" in str(e) or "UNAVAILABLE" in str(e):
                    await asyncio.sleep(1)
                    continue
                break
    return "Translation service momentarily busy. Please try again."

# UI Generators
def get_dashboard_markup(cfg):
    status_text = "🟢 Active" if cfg["active"] else "🔴 Paused"
    phonetic_text = "🔊 Phonetics: ON" if cfg["show_phonetics"] else "🔇 Phonetics: OFF"
    keyboard = [
        [
            InlineKeyboardButton(f"🗣 {cfg['from']}", callback_data="open_from_0"),
            InlineKeyboardButton("⇄ Swap", callback_data="swap_langs"),
            InlineKeyboardButton(f"🎯 {cfg['to']}", callback_data="open_to_0")
        ],
        [
            InlineKeyboardButton(f"⚡ {status_text}", callback_data="toggle_power"),
            InlineKeyboardButton(phonetic_text, callback_data="toggle_phonetics")
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

    keyboard.append([InlineKeyboardButton("🔙 Back to Console", callback_data="back_dashboard")])
    return InlineKeyboardMarkup(keyboard)

def get_hud_text(cfg, user_name):
    state = "ACTIVE / LISTENING" if cfg["active"] else "STANDBY / PAUSED"
    return (
        "╔═══════════════════════════╗\n"
        "   ✦ UNIVERSAL TRANSLATOR HUD ✦   \n"
        "╚═══════════════════════════╝\n\n"
        f"👤 User: {user_name}\n"
        f"⚡ Status: [{state}]\n"
        "─────────────────────────────\n"
        f"🎙 Channel A : {cfg['from']}\n"
        f"🎧 Channel B : {cfg['to']}\n"
        f"🔊 Pronunciation & Nuance : {'ENABLED' if cfg['show_phonetics'] else 'DISABLED'}\n"
        "─────────────────────────────\n"
        "• Send any Text or Voice message directly to translate.\n"
        "• Tap [⇄ Swap] or any language button to switch."
    )

# Handlers
async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    cfg = get_user_config(user.id)
    await update.message.reply_text(get_hud_text(cfg, user.first_name), reply_markup=get_dashboard_markup(cfg))

async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    cfg = get_user_config(user.id)
    status_card = (
        "┌───────────────────────────┐\n"
        "        ❖ DIAGNOSTICS ❖       \n"
        "└───────────────────────────┘\n\n"
        f"• Status      : {'🟢 Live' if cfg['active'] else '🔴 Paused'}\n"
        f"• Route       : {cfg['from']} ⟷ {cfg['to']}\n"
        f"• Phonetics   : {'Enabled' if cfg['show_phonetics'] else 'Disabled'}\n"
        f"• Processed   : {cfg['count']} requests\n"
        "─────────────────────────────\n"
        "Quick controls: /stop to pause, /resume to start."
    )
    await update.message.reply_text(status_card, reply_markup=get_dashboard_markup(cfg))

async def stop_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    cfg = get_user_config(user.id)
    cfg["active"] = False
    await update.message.reply_text("🛑 Translator Paused. Use /resume or tap below to restart.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("▶️ Resume", callback_data="resume_bot")]]))

async def resume_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    cfg = get_user_config(user.id)
    cfg["active"] = True
    await update.message.reply_text("⚡ Translator Active. Send any text or audio message.", reply_markup=get_dashboard_markup(cfg))

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = update.effective_user
    cfg = get_user_config(user.id)
    data = query.data

    if data.startswith("open_") or data.startswith("nav_"):
        _, mode, page = data.split("_")
        label = "Input (Channel A)" if mode == "from" else "Target (Channel B)"
        await query.edit_message_text(f"Select {label}:", reply_markup=build_language_keyboard(mode, int(page)))

    elif data.startswith("set_"):
        _, mode, lang = data.split("_")
        cfg[mode] = lang
        await query.edit_message_text(get_hud_text(cfg, user.first_name), reply_markup=get_dashboard_markup(cfg))

    elif data == "swap_langs":
        cfg["from"], cfg["to"] = cfg["to"], cfg["from"]
        await query.edit_message_text(get_hud_text(cfg, user.first_name), reply_markup=get_dashboard_markup(cfg))

    elif data == "toggle_power":
        cfg["active"] = not cfg["active"]
        await query.edit_message_text(get_hud_text(cfg, user.first_name), reply_markup=get_dashboard_markup(cfg))

    elif data == "resume_bot":
        cfg["active"] = True
        await query.edit_message_text(get_hud_text(cfg, user.first_name), reply_markup=get_dashboard_markup(cfg))

    elif data == "toggle_phonetics":
        cfg["show_phonetics"] = not cfg["show_phonetics"]
        await query.edit_message_text(get_hud_text(cfg, user.first_name), reply_markup=get_dashboard_markup(cfg))

    elif data == "back_dashboard":
        await query.edit_message_text(get_hud_text(cfg, user.first_name), reply_markup=get_dashboard_markup(cfg))

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    cfg = get_user_config(user.id)
    if not cfg["active"]:
        return

    text = update.message.text
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

    phonetics_rule = (
        "Provide a 2nd line with simplified phonetic pronunciation, and a 3rd line with a 1-sentence formality note if helpful."
        if cfg["show_phonetics"] else "Provide only the direct translation."
    )

    prompt = (
        f"You are a bilingual translator between {cfg['from']} and {cfg['to']}.\n"
        f"1. Detect whether the input is in {cfg['from']} or {cfg['to']} (or other).\n"
        f"2. If in {cfg['from']}, translate to natural {cfg['to']}. If in {cfg['to']}, translate to {cfg['from']}.\n"
        f"3. {phonetics_rule}\n"
        f"Do not use markdown stars (*), underscores, or hashes. Format cleanly:\n"
        f"Translation: [Translation]\n"
        f"Pronunciation: [Phonetics]\n"
        f"Note: [Brief nuance if applicable]\n\n"
        f"Input:\n{text}"
    )

    result = await execute_gemini(prompt)
    cfg["count"] += 1
    card = f"╭───────────────────────────\n│ 🌐 ROUTE: {cfg['from']} ⇄ {cfg['to']}\n├───────────────────────────\n{result}\n╰───────────────────────────"
    await update.message.reply_text(card)

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
            f"1. Transcribe the audio accurately.\n"
            f"2. Translate to opposite language.\n"
            f"3. Provide phonetic guide.\n"
            f"Do not use markdown formatting symbols:\n"
            f"Transcript: [Original speech]\n"
            f"Translation: [Translated text]\n"
            f"Pronunciation: [Phonetic guide]"
        ]
        result = await execute_gemini(contents)
        cfg["count"] += 1
        card = f"╭─── 🎙 VOICE DECODER ──────\n│ 🌐 ROUTE: {cfg['from']} ⇄ {cfg['to']}\n├───────────────────────────\n{result}\n╰───────────────────────────"
        await update.message.reply_text(card)
    except Exception as e:
        await update.message.reply_text(f"Voice processing error: {e}")
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)

async def main():
    await start_web_server()

    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("status", status_cmd))
    app.add_handler(CommandHandler("stop", stop_cmd))
    app.add_handler(CommandHandler("resume", resume_cmd))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, handle_voice))

    await app.initialize()
    commands = [
        BotCommand("start", "Open Interface HUD"),
        BotCommand("status", "System Health & Diagnostics"),
        BotCommand("stop", "Pause Translator"),
        BotCommand("resume", "Reactivate Translator"),
    ]
    await app.bot.set_my_commands(commands)
    
    # Safe cleanup to eliminate leftover webhook states
    try:
        await app.bot.delete_webhook(drop_pending_updates=True)
    except Exception:
        pass

    await app.start()

    # Resilient polling loop to prevent 409 Conflict shutdown
    print("Initiating resilient polling...")
    while True:
        try:
            await app.updater.start_polling(drop_pending_updates=True)
            while True:
                await asyncio.sleep(3600)
        except Exception as e:
            if "Conflict" in str(e):
                print("Old container still shutting down. Waiting 10 seconds before retrying...")
                await asyncio.sleep(10)
            else:
                print(f"Polling warning: {e}. Retrying in 5 seconds...")
                await asyncio.sleep(5)

if __name__ == "__main__":
    asyncio.run(main())
