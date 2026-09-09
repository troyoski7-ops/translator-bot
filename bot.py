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

ANIM_STORE_URL = "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExbnYydWhsazBqczJycHJmdTR5cWNvZGFoYm95am03MGl2aTFxZTN3ZSZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/3o7TKSjRrfIPjeiVyM/giphy.gif"
VIP_GIFT_STICKER = "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExYWZ0N25xZG82OXF0NWlhbnF6bWc2dHFob2ZlZmxmbnlucTNtc2xxeSZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/l0ExhcMymdL6TrZ84/giphy.gif"

# 2. Render Keep-Alive Server
async def handle_ping(request):
    return web.Response(text="Translator Engine Running Smoothly!")

async def start_web_server():
    app = web.Application()
    app.router.add_get('/', handle_ping)
    app.router.add_get('/healthz', handle_ping)
    port = int(os.environ.get("PORT", 10000))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()

# 3. Themes: 4 Free + VIP Vault
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
        "badge": "⚜️ 24K GOLD VIP ⚜️",
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

# 4. Universal LLM Processing Engine
def execute_groq_translation(prompt):
    if not GROQ_API_KEY:
        return "Error: GROQ_API_KEY Missing."

    system_instruction = (
        "You are an infallible world-class polyglot linguist and universal translator. "
        "Analyze the given input text accurately, detect its source language even if it's a single word, "
        "rare dialect, or written in complex/Cyrillic scripts (e.g., Tajik, Uzbek, Kazakh, Azerbaijani, Persian, Georgian, Malayalam). "
        "Translate it naturally to the target language. "
        "Generate natural phonetic English romanization for BOTH source and translated words (never write NONE, provide readable pronunciation). "
        "Find the country flag emoji, capital/major city, and standard 2-letter ISO voice code for both languages (e.g., Tajik=tg, Persian=fa, Uzbek=uz, Russian=ru, German=de, Malayalam=ml).\n"
        "Strictly return output in this exact 9-line format without backticks or other conversational filler:\n"
        "SRC_NAME: [Source Language Name]\n"
        "SRC_FLAG: [Source Country Flag Emoji]\n"
        "SRC_CITY: [Source Major City]\n"
        "SRC_CODE: [Source 2-Letter ISO Voice Code]\n"
        "SRC_PRON: [Phonetic pronunciation of the input]\n"
        "TRG_NAME: [Target Language Name]\n"
        "TRG_FLAG: [Target Country Flag Emoji]\n"
        "TRG_CITY: [Target Major City]\n"
        "TRG_CODE: [Target 2-Letter ISO Voice Code]\n"
        "TRG_PRON: [Phonetic pronunciation of the translated text]\n"
        "RES: [Accurate translated text only]"
    )

    try:
        completion = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
            max_tokens=500,
        )
        return completion.choices[0].message.content.strip()
    except Exception as e:
        return f"ERROR: {str(e)}"

# 5. User Quota & VIP Logic
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
        "Free translation limit reached!\n\n"
        "👑 <b>VIP Perks:</b>\n"
        "• Unlimited real-time translations\n"
        "• Dual Voice Audio with 0.75x Slow-Motion player\n"
        "• Secret VIP Luxury Themes (Gold, Cyber Neon, Matrix)\n"
        "• High-priority zero latency queue\n\n"
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

# 6. Handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.chat_data["paused"] = False
    user_id = str(update.effective_user.id)
    _, _, is_vip = is_user_active(context, user_id)

    user_themes = context.chat_data.get("user_theme", {})
    selected_theme = user_themes.get(user_id, "chibi")
    active_theme = ALL_THEMES.get(selected_theme, STANDARD_THEMES["chibi"])

    vip_badge = "👑 <b>VIP PRIVILEGES ACTIVE</b>\n" if is_vip else ""

    welcome = (
        f"🌐 <b>UNIVERSAL OMNILINGUAL INTERPRETER</b>\n"
        f"{vip_badge}\n"
        "• ⚡ Type or speak in any language\n"
        "• 🗣 Dual Phonetics (Original & Translation)\n"
        "• 🔊 Dual Voice Playback for all 100+ global languages\n"
        "• 🎁 <b>100 Free Translations</b> included\n\n"
        "<b>Commands:</b>\n"
        "🎨 /theme • Customize welcome screen\n"
        "📊 /status • Check quota & VIP status\n"
        "⏸ /stop • Pause translation\n"
        "▶️ /resume • Resume translation\n"
        "⭐️ /premium • Star VIP Store\n\n"
        "Send any message or voice note to begin!"
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
    # 4 Free Standard Themes
    for key, item in STANDARD_THEMES.items():
        keyboard.append([InlineKeyboardButton(item["label"], callback_data=f"settheme_{key}")])

    # VIP Themes
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
        "👑 <b>VIP Vault:</b> Royal Gold, Cyberpunk Neon, Matrix, and Soundwave animations!"
    )
    await update.message.reply_text(menu_text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))

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
        f"✅ <b>Welcome screen updated to:</b>\n{selected['label']}\n\n"
        "Send /start anytime to see it in action!",
        parse_mode="HTML"
    )

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    _, status_val, _ = is_user_active(context, user_id)
    state = "⏸ Paused" if context.chat_data.get("paused", False) else "▶️ Active"

    status_text = (
        f"📊 <b>TRANSLATOR CORE STATUS</b>\n\n"
        f"🏃 Usage Quota: {status_val}\n"
        f"🔄 State: {state}\n\n"
        f"<i>Unlock unlimited usage & VIP styles with /premium</i>"
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
    target_lang = user_langs[other_users[0]] if other_users else "English"

    prompt = f"Input Text: \"{text}\"\nTarget Language Request: {target_lang}"
    raw_response = execute_groq_translation(prompt)

    # Defaults
    src_name, src_flag, src_city, src_code, src_pron = "Original", "🌐", "Global", "en", ""
    trg_name, trg_flag, trg_city, trg_code, trg_pron = "Target", "🌐", "Global", "en", ""
    translation = text

    for line in raw_response.splitlines():
        line = line.strip()
        if line.startswith("SRC_NAME:"): src_name = line.replace("SRC_NAME:", "").strip()
        elif line.startswith("SRC_FLAG:"): src_flag = line.replace("SRC_FLAG:", "").strip()
        elif line.startswith("SRC_CITY:"): src_city = line.replace("SRC_CITY:", "").strip()
        elif line.startswith("SRC_CODE:"): src_code = line.replace("SRC_CODE:", "").strip().lower()
        elif line.startswith("SRC_PRON:"): src_pron = line.replace("SRC_PRON:", "").strip()
        elif line.startswith("TRG_NAME:"): trg_name = line.replace("TRG_NAME:", "").strip()
        elif line.startswith("TRG_FLAG:"): trg_flag = line.replace("TRG_FLAG:", "").strip()
        elif line.startswith("TRG_CITY:"): trg_city = line.replace("TRG_CITY:", "").strip()
        elif line.startswith("TRG_CODE:"): trg_code = line.replace("TRG_CODE:", "").strip().lower()
        elif line.startswith("TRG_PRON:"): trg_pron = line.replace("TRG_PRON:", "").strip()
        elif line.startswith("RES:"): translation = line.replace("RES:", "").strip()

    if src_name and "unknown" not in src_name.lower():
        user_langs[user_id] = src_name

    if not is_vip:
        context.chat_data["free_credits"][user_id] -= 1
        _, status_val, _ = is_user_active(context, user_id)

    # VIP Styling
    user_theme_key = context.chat_data.get("user_theme", {}).get(user_id, "chibi")
    active_theme = ALL_THEMES.get(user_theme_key, STANDARD_THEMES["chibi"])

    if is_vip and active_theme.get("vip"):
        vip_header = f"<b>{active_theme.get('badge')}</b>\n"
        quote_prefix = active_theme.get("quote_prefix", "✨ ")
        status_line = f"👑 <b>VIP Priority Lane</b> • {status_val}"
    else:
        vip_header = ""
        quote_prefix = ""
        status_line = f"🏃 Status: {status_val}"

    # Phonetics Lines
    src_pron_block = f"🗣 <i>Original:</i> <code>{src_pron}</code>\n" if src_pron and src_pron.upper() != "NONE" else ""
    trg_pron_block = f"🗣 <i>Phonetic:</i> <tg-spoiler>{trg_pron}</tg-spoiler>\n" if trg_pron and trg_pron.upper() != "NONE" else ""

    card_text = (
        f"{vip_header}"
        f"{src_flag} <code>{src_name.upper()}</code> ➔ {trg_flag} <code>{trg_name.upper()}</code>\n"
        f"📍 <i>{src_city} ⇄ {trg_city}</i>\n\n"
        f"{src_pron_block}"
        f"<blockquote>{quote_prefix}{translation}</blockquote>"
        f"{trg_pron_block}\n"
        f"{status_line}"
    )

    msg_id = placeholder.message_id
    context.bot_data[f"aud_src_{msg_id}"] = {"text": text, "code": src_code, "name": src_name}
    context.bot_data[f"aud_trg_{msg_id}"] = {"text": translation, "code": trg_code, "name": trg_name}

    # Dual Listen Buttons
    buttons = [
        InlineKeyboardButton(f"🔊 Listen ({src_flag} {src_name})", callback_data=f"play_src_{msg_id}"),
        InlineKeyboardButton(f"🔊 Listen ({trg_flag} {trg_name})", callback_data=f"play_trg_{msg_id}")
    ]
    keyboard = [buttons]

    # VIP Slow-Mo Button
    if is_vip:
        keyboard.append([InlineKeyboardButton(f"🐢 Slow-Mo (0.75x {trg_flag})", callback_data=f"slow_trg_{msg_id}")])

    await placeholder.edit_text(card_text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))

async def handle_audio_playback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("🎙️ Generating native speech...")
    data = query.data

    is_slow = data.startswith("slow_")
    key_prefix = "aud_trg_" if "trg" in data else "aud_src_"
    msg_id = data.split("_")[-1]

    cache = context.bot_data.get(f"{key_prefix}{msg_id}")
    if not cache:
        await query.answer("Session expired. Please send a new text!", show_alert=True)
        return

    text_to_speak = cache["text"]
    lang_code = cache.get("code", "en")

    try:
        try:
            tts = gTTS(text=text_to_speak, lang=lang_code, slow=is_slow)
        except Exception:
            # Fallback to English voice safely if code is unsupported by gTTS
            tts = gTTS(text=text_to_speak, lang='en', slow=is_slow)

        audio_buffer = io.BytesIO()
        tts.write_to_fp(audio_buffer)
        audio_buffer.seek(0)
        audio_buffer.name = "voice.mp3"

        speed_label = "Slowed" if is_slow else "Native"
        caption = f"🔊 <i>{speed_label} Pronunciation: \"{text_to_speak[:45]}...\"</i>"
        await context.bot.send_voice(chat_id=query.message.chat_id, voice=audio_buffer, caption=caption, parse_mode="HTML")
    except Exception as e:
        await query.answer(f"Audio Error: {str(e)[:45]}", show_alert=True)

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

        prompt = f"Voice Transcript: \"{spoken_text}\"\nTarget Language: {target_lang}"
        raw_response = execute_groq_translation(prompt)

        src_name, src_flag, trg_name, trg_flag = "Audio", "🎙️", "Target", "🌐"
        translation = spoken_text

        for line in raw_response.splitlines():
            line = line.strip()
            if line.startswith("SRC_NAME:"): src_name = line.replace("SRC_NAME:", "").strip()
            elif line.startswith("SRC_FLAG:"): src_flag = line.replace("SRC_FLAG:", "").strip()
            elif line.startswith("TRG_NAME:"): trg_name = line.replace("TRG_NAME:", "").strip()
            elif line.startswith("TRG_FLAG:"): trg_flag = line.replace("TRG_FLAG:", "").strip()
            elif line.startswith("RES:"): translation = line.replace("RES:", "").strip()

        if not is_vip:
            context.chat_data["free_credits"][user_id] -= 1
            _, status_val, _ = is_user_active(context, user_id)

        card_text = (
            f"🎙️ <code>{src_name.upper()}</code> {src_flag} ➔ {trg_flag} <code>{trg_name.upper()}</code>\n\n"
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

# 7. Telegram Star Payments
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
        description=f"Unlock VIP luxury themes, dual voice slow-mo, and unlimited translations for {plan['days']} days.",
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
        await query.answer(ok=False, error_message="Invalid plan selection.")

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

    if "user_theme" not in context.chat_data:
        context.chat_data["user_theme"] = {}
    context.chat_data["user_theme"][user_id] = "vip_gold"

    gift_celebration_text = (
        f"🎁 <b>VIP VAULT & MEMBERSHIP UNLOCKED!</b> ⭐️\n\n"
        f"👑 <b>Tier:</b> {plan['name']}\n"
        f"💎 <b>Badge:</b> {plan['badge']}\n"
        f"⏳ <b>Valid Until:</b> <code>{new_expiry.strftime('%Y-%m-%d')}</code>\n\n"
        f"✨ <i>All limits removed: Unlimited dual translations & VIP Vault active!</i>"
    )

    try:
        await update.message.reply_animation(
            animation=VIP_GIFT_STICKER,
            caption=gift_celebration_text,
            parse_mode="HTML"
        )
    except Exception:
        await update.message.reply_text(gift_celebration_text, parse_mode="HTML")

# 8. Main Safe Application Loop
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
    app.add_handler(CallbackQueryHandler(handle_audio_playback, pattern="^(play_|slow_)"))

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
