import os
import re
import io
import asyncio
from datetime import datetime, timedelta
from aiohttp import web
from gtts import gTTS
from telegram import (
    Update,
    LabeledPrice,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    PreCheckoutQueryHandler,
    filters,
    ContextTypes,
)
from groq import Groq

# 1. Credentials
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8653764956:AAGE8ol1gvfUg9naFkMPD7wGqoDqw-0IFZY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

groq_client = Groq(api_key=GROQ_API_KEY)

# Animated Assets
ANIM_STORE_URL = "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExbnYydWhsazBqczJycHJmdTR5cWNvZGFoYm95am03MGl2aTFxZTN3ZSZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/3o7TKSjRrfIPjeiVyM/giphy.gif"
VIP_GIFT_STICKER = "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExYWZ0N25xZG82OXF0NWlhbnF6bWc2dHFob2ZlZmxmbnlucTNtc2xxeSZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/l0ExhcMymdL6TrZ84/giphy.gif"

# 2. Render Keep-Alive Server
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

# 3. Theme Registry (4 Free Dedicated Themes + VIP Vault)
STANDARD_THEMES = {
    "chibi": {
        "label": "🎀 Chibi Anime Girl Talking Fast",
        "url": "https://media.giphy.com/media/B2wxqJaigm4E0/giphy.gif",
        "vip": False
    },
    "doge": {
        "label": "🐕 Funny Confused / Breakthrough Doge",
        "url": "https://media.giphy.com/media/5Zesu5VPNGJlm/giphy.gif",
        "vip": False
    },
    "minion": {
        "label": "🍌 Excited Minion Polyglot",
        "url": "https://media.giphy.com/media/11sBLVxNs7v6WA/giphy.gif",
        "vip": False
    },
    "cat": {
        "label": "🐱 Dancing Happy Cat",
        "url": "https://media.giphy.com/media/JIX9t2j0ZTN9S/giphy.gif",
        "vip": False
    },
}

PREMIUM_THEMES = {
    "vip_gold": {
        "label": "👑 Royal Imperial Gold",
        "url": "https://media.giphy.com/media/l0ExhcMymdL6TrZ84/giphy.gif",
        "badge": "⚜️ 24K GOLD EDITION ⚜️",
        "quote_prefix": "👑 ",
        "vip": True
    },
    "vip_cyber": {
        "label": "🐉 Cyber Tokyo Neon",
        "url": "https://media.giphy.com/media/3oKIPnAiaMCws8nOsE/giphy.gif",
        "badge": "⚡ CYBER MATRIX VIP ⚡",
        "quote_prefix": "🔮 ",
        "vip": True
    },
    "vip_matrix": {
        "label": "⚡ Quantum Matrix Core",
        "url": "https://media.giphy.com/media/l378c0402U49fs29O/giphy.gif",
        "badge": "✨ ASTRAL HORIZON ✨",
        "quote_prefix": "🪐 ",
        "vip": True
    },
    "vip_sound": {
        "label": "🎧 Hologram Soundwaves",
        "url": "https://media.giphy.com/media/26AHONQ79FdWZhAI0/giphy.gif",
        "badge": "💎 DIAMOND PRESTIGE 💎",
        "quote_prefix": "❄️ ",
        "vip": True
    }
}

ALL_THEMES = {**STANDARD_THEMES, **PREMIUM_THEMES}

# 4. Regional Cultural Registry
LANGUAGE_THEMES = {
    # Central & South Asian Languages
    "persian": {"flag": "🇮🇷", "loc": "Tehran", "accent": "🕌", "code": "fa"},
    "farsi": {"flag": "🇮🇷", "loc": "Tehran", "accent": "🕌", "code": "fa"},
    "azerbaijani": {"flag": "🇦🇿", "loc": "Baku", "accent": "🔥", "code": "az"},
    "azeri": {"flag": "🇦🇿", "loc": "Baku", "accent": "🔥", "code": "az"},
    "uzbek": {"flag": "🇺🇿", "loc": "Tashkent", "accent": "🏛️", "code": "uz"},
    "tajik": {"flag": "🇹🇯", "loc": "Dushanbe", "accent": "🏔️", "code": "tg"},
    "malayalam": {"flag": "🇮🇳", "loc": "Kerala", "accent": "🌴", "code": "ml"},
    "tamil": {"flag": "🇮🇳", "loc": "Chennai", "accent": "🛕", "code": "ta"},
    "hindi": {"flag": "🇮🇳", "loc": "Delhi", "accent": "🦚", "code": "hi"},
    "bengali": {"flag": "🇧🇩", "loc": "Dhaka", "accent": "🐅", "code": "bn"},

    # Hard Complex Scripts & Dialects
    "mandarin": {"flag": "🇨🇳", "loc": "Beijing", "accent": "🐉", "code": "zh-cn"},
    "chinese": {"flag": "🇨🇳", "loc": "Beijing", "accent": "🐉", "code": "zh-cn"},
    "japanese": {"flag": "🇯🇵", "loc": "Tokyo", "accent": "⛩️", "code": "ja"},
    "korean": {"flag": "🇰🇷", "loc": "Seoul", "accent": "🇰🇷", "code": "ko"},
    "arabic": {"flag": "🇦🇪", "loc": "Dubai", "accent": "🕌", "code": "ar"},
    "hungarian": {"flag": "🇭🇺", "loc": "Budapest", "accent": "🏰", "code": "hu"},
    "finnish": {"flag": "🇫🇮", "loc": "Helsinki", "accent": "❄️", "code": "fi"},
    "icelandic": {"flag": "🇮🇸", "loc": "Reykjavik", "accent": "🌋", "code": "is"},
    "polish": {"flag": "🇵🇱", "loc": "Warsaw", "accent": "🦅", "code": "pl"},
    "russian": {"flag": "🇷🇺", "loc": "Moscow", "accent": "🪆", "code": "ru"},
    "georgian": {"flag": "🇬🇪", "loc": "Tbilisi", "accent": "🍇", "code": "ka"},
    "armenian": {"flag": "🇦🇲", "loc": "Yerevan", "accent": "🏔️", "code": "hy"},
    "vietnamese": {"flag": "🇻🇳", "loc": "Hanoi", "accent": "🏮", "code": "vi"},
    "thai": {"flag": "🇹🇭", "loc": "Bangkok", "accent": "🛕", "code": "th"},
    "greek": {"flag": "🇬🇷", "loc": "Athens", "accent": "🏛️", "code": "el"},
    "hebrew": {"flag": "🇮🇱", "loc": "Jerusalem", "accent": "📜", "code": "iw"},
    "basque": {"flag": "🇪🇸", "loc": "Bilbao", "accent": "🌲", "code": "eu"},
    "turkish": {"flag": "🇹🇷", "loc": "Istanbul", "accent": "☕", "code": "tr"},
    "ukrainian": {"flag": "🇺🇦", "loc": "Kyiv", "accent": "🌻", "code": "uk"},
    "czech": {"flag": "🇨🇿", "loc": "Prague", "accent": "🏰", "code": "cs"},

    # Global Standards
    "german": {"flag": "🇩🇪", "loc": "Berlin", "accent": "🏰", "code": "de"},
    "italian": {"flag": "🇮🇹", "loc": "Rome", "accent": "🏛️", "code": "it"},
    "french": {"flag": "🇫🇷", "loc": "Paris", "accent": "🥐", "code": "fr"},
    "spanish": {"flag": "🇪🇸", "loc": "Madrid", "accent": "💃", "code": "es"},
    "english": {"flag": "🇬🇧", "loc": "London", "accent": "🎡", "code": "en"},
}

def get_theme(lang_name):
    lang_key = (lang_name or "").lower()
    for key, theme in LANGUAGE_THEMES.items():
        if key in lang_key:
            return theme
    return {"flag": "🌐", "loc": "Global", "accent": "⚡", "code": "en"}

# 5. Groq Translation Engine
def execute_groq_text(prompt):
    if not GROQ_API_KEY:
        return "Error: GROQ_API_KEY missing."

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
                                "You are an expert polyglot interpreter fluent in all scripts and dialects. "
                                "Translate accurately with natural regional phrasing. "
                                "Follow the 4-line format strictly without extra remarks or <think> tags."
                            )
                        },
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.2,
                    max_tokens=400,
                )
                if completion and completion.choices:
                    res = completion.choices[0].message.content.strip()
                    res = re.sub(r'<think>.*?</think>', '', res, flags=re.DOTALL).strip()
                    return res
            except Exception:
                continue

        return "Translation unavailable."
    except Exception as e:
        return f"Groq Error: {str(e)[:80]}"

# 6. Quotas & Subscriptions
FREE_LIMIT = 100

PLANS = {
    "sub_1m": {"name": "1 Month VIP", "days": 30, "stars": 50, "badge": "⭐️ VIP"},
    "sub_3m": {"name": "3 Months VIP", "days": 90, "stars": 120, "badge": "💎 ELITE"},
    "sub_1y": {"name": "1 Year VIP Pass", "days": 365, "stars": 399, "badge": "👑 LEGEND"},
}

def is_user_active(context: ContextTypes.DEFAULT_TYPE, user_id: str) -> tuple[bool, str, bool]:
    if "premium_expiry" not in context.chat_data:
        context.chat_data["premium_expiry"] = {}
    if "free_credits" not in context.chat_data:
        context.chat_data["free_credits"] = {}

    expiry_str = context.chat_data["premium_expiry"].get(user_id)
    if expiry_str:
        expiry = datetime.fromisoformat(expiry_str)
        if datetime.utcnow() < expiry:
            days_left = (expiry - datetime.utcnow()).days
            badge = context.chat_data.get("vip_tier", {}).get(user_id, "👑 VIP")
            return True, f"{badge} ({days_left}d left)", True

    if user_id not in context.chat_data["free_credits"]:
        context.chat_data["free_credits"][user_id] = FREE_LIMIT

    remaining = context.chat_data["free_credits"][user_id]
    if remaining > 0:
        return True, f"{remaining}/100", False

    return False, "Expired", False

async def send_store_menu(chat_id, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "⭐️ <b>STAR VIP STORE & VAULT</b> ⭐️\n\n"
        "Your free trial limit has been reached!\n\n"
        "🎁 <b>VIP Elite Perks:</b>\n"
        "• Secret VIP Themes (Gold, Cyber Neon, Matrix, Soundwaves)\n"
        "• High-priority zero latency queue\n"
        "• Unlimited real-time audio pronunciation\n"
        "• Slow-motion (0.75x) dialect study player\n"
        "• Exclusive VIP status badges on cards\n\n"
        "• <b>1 Month VIP:</b> 50 Stars\n"
        "• <b>3 Months ELITE:</b> 120 Stars <i>(20% Off)</i>\n"
        "• <b>1 Year LEGEND:</b> 399 Stars <i>(Best Value!)</i>"
    )
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("⭐️ 1 Month (50 Stars)", callback_data="buy_sub_1m")],
        [InlineKeyboardButton("💎 3 Months (120 Stars)", callback_data="buy_sub_3m")],
        [InlineKeyboardButton("👑 1 Year LEGEND (399 Stars)", callback_data="buy_sub_1y")],
    ])
    try:
        await context.bot.send_animation(
            chat_id=chat_id,
            animation=ANIM_STORE_URL,
            caption=text,
            parse_mode="HTML",
            reply_markup=keyboard,
        )
    except Exception:
        await context.bot.send_message(chat_id=chat_id, text=text, parse_mode="HTML", reply_markup=keyboard)

# 7. Bot Handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.chat_data["paused"] = False
    user_id = str(update.effective_user.id)
    _, _, is_vip = is_user_active(context, user_id)

    user_themes = context.chat_data.get("user_theme", {})
    selected_theme = user_themes.get(user_id, "chibi")
    active_theme = ALL_THEMES.get(selected_theme, STANDARD_THEMES["chibi"])

    vip_badge = "👑 <b>VIP PRIVILEGES ACTIVE</b>\n" if is_vip else ""

    welcome = (
        f"🌐 <b>UNIVERSAL OMNILINGUAL TRANSLATOR</b>\n"
        f"{vip_badge}\n"
        "• ⚡ Speak naturally in your native language\n"
        "• 🎁 <b>100 Free Translations</b> included\n"
        "• 🔊 Tap to listen to native pronunciation\n"
        "• 🌍 Supports Persian, Uzbek, Tajik, Azerbaijani & 100+ global languages\n\n"
        "<b>Commands:</b>\n"
        "🎨 /theme • Pick your welcome animation\n"
        "📊 /status • Check quota / VIP status\n"
        "⏸ /stop • Pause translation\n"
        "▶️ /resume • Resume translation\n"
        "⭐️ /premium • Star VIP Store\n\n"
        "Send any text or voice note to begin!"
    )
    try:
        await update.message.reply_animation(
            animation=active_theme["url"],
            caption=welcome,
            parse_mode="HTML"
        )
    except Exception:
        await update.message.reply_text(welcome, parse_mode="HTML")

async def theme_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    _, _, is_vip = is_user_active(context, user_id)

    keyboard = []

    # Free Users Theme Section
    for key, item in STANDARD_THEMES.items():
        keyboard.append([InlineKeyboardButton(item["label"], callback_data=f"settheme_{key}")])

    # VIP Vault Theme Section
    for key, item in PREMIUM_THEMES.items():
        label = f"✨ {item['label']}" if is_vip else f"🔒 {item['label']} [VIP]"
        keyboard.append([InlineKeyboardButton(label, callback_data=f"settheme_{key}")])

    menu_text = (
        "🎨 <b>SELECT WELCOME ANIMATION</b>\n\n"
        "<b>Free Themes:</b>\n"
        "• 🎀 Chibi Anime Girl Talking Fast\n"
        "• 🐕 Funny Confused / Breakthrough Doge\n"
        "• 🍌 Excited Minion Polyglot\n"
        "• 🐱 Dancing Happy Cat\n\n"
        "👑 <b>VIP Vault:</b> Gold, Cyber Neon, and Matrix themes (Unlocked with Telegram Stars)!"
    )
    await update.message.reply_text(
        menu_text,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def theme_selection_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    theme_key = query.data.replace("settheme_", "")
    user_id = str(update.effective_user.id)
    _, _, is_vip = is_user_active(context, user_id)

    selected = ALL_THEMES.get(theme_key)
    if not selected:
        return

    if selected.get("vip") and not is_vip:
        await query.answer("🔒 VIP Theme! Upgrade with Telegram Stars to unlock.", show_alert=True)
        await send_store_menu(query.message.chat_id, context)
        return

    if "user_theme" not in context.chat_data:
        context.chat_data["user_theme"] = {}

    context.chat_data["user_theme"][user_id] = theme_key

    await query.edit_message_text(
        f"✅ <b>Active screen theme set to:</b>\n{selected['label']}\n\n"
        "Send /start to view your new animation!",
        parse_mode="HTML"
    )

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    _, status_val, is_vip = is_user_active(context, user_id)
    is_paused = context.chat_data.get("paused", False)
    state = "⏸ Paused" if is_paused else "▶️ Active"

    status_text = (
        f"📊 <b>STATUS</b>\n"
        f"🏃 Status: {status_val}\n"
        f"🔄 State: {state}\n\n"
        f"<i>Send /premium to unlock the VIP Vault & unlimited translations!</i>"
    )
    await update.message.reply_text(status_text, parse_mode="HTML")

async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.chat_data["paused"] = True
    await update.message.reply_text("⏸ <b>Translations Paused!</b> Send /resume to restart.", parse_mode="HTML")

async def resume_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.chat_data["paused"] = False
    await update.message.reply_text("▶️ <b>Translations Resumed!</b> Listening 🏃💨", parse_mode="HTML")

async def premium_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_store_menu(update.effective_chat.id, context)

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.chat_data.get("paused", False):
        return

    user_id = str(update.effective_user.id)
    active, status_val, is_vip = is_user_active(context, user_id)

    if not active:
        await send_store_menu(update.effective_chat.id, context)
        return

    text = update.message.text.strip()
    placeholder = await update.message.reply_text("<i>Translating... 🏃</i>", parse_mode="HTML")

    if "user_langs" not in context.chat_data:
        context.chat_data["user_langs"] = {}

    user_langs = context.chat_data["user_langs"]
    other_users = [uid for uid in user_langs if uid != user_id]
    target_lang = user_langs[other_users[0]] if other_users else None

    prompt = (
        f"Input: \"{text}\"\n"
        f"Target language: {target_lang or 'English'}\n\n"
        "Instructions:\n"
        "1. Identify the source language accurately.\n"
        "2. Translate naturally into the target language.\n"
        "3. Provide phonetic romanization if non-latin script (or NONE).\n"
        "4. Output strictly in this 4-line format:\n"
        "SRC: [Source Language]\n"
        "TRG: [Target Language]\n"
        "PRON: [Phonetic pronunciation or NONE]\n"
        "RES: [Final translation only]"
    )

    raw_response = execute_groq_text(prompt)

    src_lang = "Auto"
    trg_lang = target_lang or "English"
    pronunciation = "NONE"
    translation = raw_response

    for line in raw_response.splitlines():
        line = line.strip()
        if line.startswith("SRC:"):
            src_lang = line.replace("SRC:", "").strip()
        elif line.startswith("TRG:"):
            trg_lang = line.replace("TRG:", "").strip()
        elif line.startswith("PRON:"):
            pronunciation = line.replace("PRON:", "").strip()
        elif line.startswith("RES:"):
            translation = line.replace("RES:", "").strip()

    if src_lang and "unknown" not in src_lang.lower():
        user_langs[user_id] = src_lang

    if not is_vip:
        context.chat_data["free_credits"][user_id] -= 1
        _, status_val, _ = is_user_active(context, user_id)

    src_th = get_theme(src_lang)
    trg_th = get_theme(trg_lang)

    pron_line = f"\n🗣️ <i>Phonetic:</i> <tg-spoiler>{pronunciation}</tg-spoiler>" if pronunciation and pronunciation != "NONE" else ""

    # VIP Styling Checks
    user_theme_key = context.chat_data.get("user_theme", {}).get(user_id, "chibi")
    active_theme = ALL_THEMES.get(user_theme_key, STANDARD_THEMES["chibi"])

    if is_vip and active_theme.get("vip"):
        vip_header = f"<b>{active_theme.get('badge')}</b>\n"
        quote_symbol = active_theme.get("quote_prefix", "✨ ")
        status_line = f"👑 <b>VIP Priority Lane</b> • {status_val}"
    else:
        vip_header = ""
        quote_symbol = ""
        status_line = f"🏃 Status: {status_val}"

    card_text = (
        f"{vip_header}"
        f"{src_th['flag']} <code>{src_lang.upper()}</code> ➔ {trg_th['flag']} <code>{trg_lang.upper()}</code>\n"
        f"📍 <i>{src_th['loc']} ⇄ {trg_th['loc']}</i>\n\n"
        f"<blockquote>{quote_symbol}{translation}</blockquote>"
        f"{pron_line}\n\n"
        f"{status_line}"
    )

    msg_key = f"tts_{placeholder.message_id}"
    context.bot_data[msg_key] = {
        "text": translation,
        "lang": trg_lang,
        "lang_code": trg_th["code"]
    }

    # Action Buttons (Standard Voice + VIP Slow-Mo Button)
    buttons = [InlineKeyboardButton(f"🔊 Listen ({trg_th['flag']})", callback_data=f"play_{placeholder.message_id}")]
    if is_vip:
        buttons.append(InlineKeyboardButton("🐢 Slow-Mo (0.75x)", callback_data=f"slow_{placeholder.message_id}"))

    await placeholder.edit_text(card_text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup([buttons]))

async def handle_tts_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("🎙️ Generating native audio...")

    msg_id = query.data.replace("play_", "")
    cache = context.bot_data.get(f"tts_{msg_id}")

    if not cache:
        await query.answer("Session expired. Send a new message!", show_alert=True)
        return

    text_to_speak = cache["text"]
    lang_code = cache.get("lang_code", "en")

    try:
        try:
            tts = gTTS(text=text_to_speak, lang=lang_code)
        except Exception:
            tts = gTTS(text=text_to_speak, lang='en')

        audio_buffer = io.BytesIO()
        tts.write_to_fp(audio_buffer)
        audio_buffer.seek(0)
        audio_buffer.name = "pronunciation.mp3"

        await context.bot.send_voice(
            chat_id=query.message.chat_id,
            voice=audio_buffer,
            caption=f"🔊 <i>Native Spoken: \"{text_to_speak[:40]}...\"</i>",
            parse_mode="HTML"
        )
    except Exception as e:
        await query.answer(f"Audio error: {str(e)[:50]}", show_alert=True)

async def handle_slow_tts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    msg_id = query.data.replace("slow_", "")
    cache = context.bot_data.get(f"tts_{msg_id}")

    if not cache:
        await query.answer("Session expired!", show_alert=True)
        return

    await query.answer("🎙️ Generating slow pronunciation...")
    text_to_speak = cache["text"]
    lang_code = cache.get("lang_code", "en")

    try:
        try:
            tts = gTTS(text=text_to_speak, lang=lang_code, slow=True)
        except Exception:
            tts = gTTS(text=text_to_speak, lang='en', slow=True)

        audio_buffer = io.BytesIO()
        tts.write_to_fp(audio_buffer)
        audio_buffer.seek(0)
        audio_buffer.name = "slow_pronunciation.mp3"

        await context.bot.send_voice(
            chat_id=query.message.chat_id,
            voice=audio_buffer,
            caption=f"🐢 <i>Slowed native pronunciation for learning</i>",
            parse_mode="HTML"
        )
    except Exception as e:
        await query.answer(f"Audio error: {str(e)[:50]}", show_alert=True)

async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.chat_data.get("paused", False):
        return

    user_id = str(update.effective_user.id)
    active, status_val, is_vip = is_user_active(context, user_id)

    if not active:
        await send_store_menu(update.effective_chat.id, context)
        return

    voice = update.message.voice or update.message.audio
    if not voice:
        return

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="record_voice")

    file = await context.bot.get_file(voice.file_id)
    temp_path = f"temp_{voice.file_id}.ogg"
    await file.download_to_drive(temp_path)

    if "user_langs" not in context.chat_data:
        context.chat_data["user_langs"] = {}

    user_langs = context.chat_data["user_langs"]
    other_users = [uid for uid in user_langs if uid != user_id]
    target_lang = user_langs[other_users[0]] if other_users else "English"

    try:
        with open(temp_path, "rb") as audio_file:
            transcription = groq_client.audio.transcriptions.create(
                file=(temp_path, audio_file.read()),
                model="whisper-large-v3-turbo"
            )
        spoken_text = transcription.text.strip()

        prompt = (
            f"Voice transcript: \"{spoken_text}\"\n"
            f"Target language: {target_lang}\n\n"
            "Translate accurately into target language. Output strictly:\n"
            "SRC: [Source Language]\n"
            "RES: [Translated text only]"
        )

        raw_response = execute_groq_text(prompt)
        src_lang = "Audio"
        translation = raw_response

        for line in raw_response.splitlines():
            line = line.strip()
            if line.startswith("SRC:"):
                src_lang = line.replace("SRC:", "").strip()
            elif line.startswith("RES:"):
                translation = line.replace("RES:", "").strip()

        if not is_vip:
            context.chat_data["free_credits"][user_id] -= 1
            _, status_val, _ = is_user_active(context, user_id)

        trg_th = get_theme(target_lang)

        card_text = (
            f"🎙️ <code>{src_lang.upper()}</code> ➔ {trg_th['flag']} <code>{target_lang.upper()}</code> {trg_th['accent']}\n\n"
            f"🗣 <i>\"{spoken_text}\"</i>\n\n"
            f"<blockquote>✨ {translation}</blockquote>\n\n"
            f"🏃 Status: {status_val}"
        )
        await update.message.reply_text(card_text, parse_mode="HTML")

    except Exception as e:
        await update.message.reply_text(f"Voice Error: {str(e)[:80]}")
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)

# 8. Telegram Star Payments & VIP Gifts Activation
async def plan_selection_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    plan_key = query.data.replace("buy_", "")
    if plan_key not in PLANS:
        return

    plan = PLANS[plan_key]
    prices = [LabeledPrice(label=plan["name"], amount=plan["stars"])]

    await context.bot.send_invoice(
        chat_id=query.message.chat_id,
        title=f"⭐️ {plan['name']}",
        description=f"Unlock VIP Vault themes, stickers, and unlimited translations for {plan['days']} days.",
        payload=plan_key,
        provider_token="",
        currency="XTR",
        prices=prices,
    )

async def precheckout_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.pre_checkout_query
    if query.invoice_payload in PLANS:
        await query.answer(ok=True)
    else:
        await query.answer(ok=False, error_message="Invalid plan selected.")

async def successful_payment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    plan_key = update.message.successful_payment.invoice_payload
    plan = PLANS.get(plan_key, PLANS["sub_1m"])

    if "premium_expiry" not in context.chat_data:
        context.chat_data["premium_expiry"] = {}
    if "vip_tier" not in context.chat_data:
        context.chat_data["vip_tier"] = {}

    current_expiry_str = context.chat_data["premium_expiry"].get(user_id)
    now = datetime.utcnow()

    if current_expiry_str and datetime.fromisoformat(current_expiry_str) > now:
        base_time = datetime.fromisoformat(current_expiry_str)
    else:
        base_time = now

    new_expiry = base_time + timedelta(days=plan["days"])
    context.chat_data["premium_expiry"][user_id] = new_expiry.isoformat()
    context.chat_data["vip_tier"][user_id] = plan["badge"]

    # Assign default luxury VIP theme
    if "user_theme" not in context.chat_data:
        context.chat_data["user_theme"] = {}
    context.chat_data["user_theme"][user_id] = "vip_gold"

    gift_celebration_text = (
        f"🎁 <b>VIP GIFTS & VAULT UNLOCKED!</b> ⭐️\n\n"
        f"👑 <b>Tier:</b> {plan['name']}\n"
        f"💎 <b>Badge:</b> {plan['badge']}\n"
        f"⏳ <b>Valid Until:</b> <code>{new_expiry.strftime('%Y-%m-%d')}</code>\n\n"
        f"✨ <i>VIP Vault themes unlocked! Type /theme to pick your luxury animation.</i>"
    )

    try:
        await update.message.reply_animation(
            animation=VIP_GIFT_STICKER,
            caption=gift_celebration_text,
            parse_mode="HTML"
        )
    except Exception:
        await update.message.reply_text(gift_celebration_text, parse_mode="HTML")

# 9. Polling Loop
async def run_bot():
    await start_web_server()

    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("theme", theme_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CommandHandler("stop", stop_command))
    app.add_handler(CommandHandler("resume", resume_command))
    app.add_handler(CommandHandler("premium", premium_command))
    app.add_handler(CallbackQueryHandler(plan_selection_callback, pattern="^buy_"))
    app.add_handler(CallbackQueryHandler(theme_selection_callback, pattern="^settheme_"))
    app.add_handler(CallbackQueryHandler(handle_tts_button, pattern="^play_"))
    app.add_handler(CallbackQueryHandler(handle_slow_tts, pattern="^slow_"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, handle_voice))
    app.add_handler(PreCheckoutQueryHandler(precheckout_callback))
    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment_callback))

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
