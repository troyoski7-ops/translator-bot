import os
import re
import io
import asyncio
from datetime import datetime, timedelta
from aiohttp import web
import edge_tts
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

# 2. Render Keep-Alive
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

# 3. Themes: 4 Free + VIP Vault
STANDARD_THEMES = {
    "chibi": {"label": "🎀 Chibi Anime Girl Talking Fast", "url": "https://media.giphy.com/media/B2wxqJaigm4E0/giphy.gif", "vip": False},
    "doge": {"label": "🐕 Funny Confused / Breakthrough Doge", "url": "https://media.giphy.com/media/5Zesu5VPNGJlm/giphy.gif", "vip": False},
    "minion": {"label": "🍌 Excited Minion Polyglot", "url": "https://media.giphy.com/media/11sBLVxNs7v6WA/giphy.gif", "vip": False},
    "cat": {"label": "🐱 Dancing Happy Cat", "url": "https://media.giphy.com/media/JIX9t2j0ZTN9S/giphy.gif", "vip": False},
}

PREMIUM_THEMES = {
    "vip_gold": {"label": "👑 Royal Imperial Gold", "url": "https://media.giphy.com/media/l0ExhcMymdL6TrZ84/giphy.gif", "badge": "⚜️ 24K GOLD VIP ⚜️", "quote_prefix": "👑 ", "vip": True},
    "vip_cyber": {"label": "🐉 Cyber Tokyo Neon", "url": "https://media.giphy.com/media/3oKIPnAiaMCws8nOsE/giphy.gif", "badge": "⚡ CYBER MATRIX VIP ⚡", "quote_prefix": "🔮 ", "vip": True},
    "vip_matrix": {"label": "⚡ Quantum Matrix Core", "url": "https://media.giphy.com/media/l378c0402U49fs29O/giphy.gif", "badge": "✨ ASTRAL HORIZON ✨", "quote_prefix": "🪐 ", "vip": True},
    "vip_sound": {"label": "🎧 Hologram Soundwaves", "url": "https://media.giphy.com/media/26AHONQ79FdWZhAI0/giphy.gif", "badge": "💎 DIAMOND PRESTIGE 💎", "quote_prefix": "❄️ ", "vip": True}
}

ALL_THEMES = {**STANDARD_THEMES, **PREMIUM_THEMES}

# 4. Neural Voices Mapping (Guaranteed 100% Working Voices)
VOICE_MAP = {
    "persian": {"voice": "fa-IR-DilaraNeural", "flag": "🇮🇷", "loc": "Tehran"},
    "farsi": {"voice": "fa-IR-DilaraNeural", "flag": "🇮🇷", "loc": "Tehran"},
    "malayalam": {"voice": "ml-IN-SobhanaNeural", "flag": "🇮🇳", "loc": "Kerala"},
    "tajik": {"voice": "tg-TJ-GanjinaNeural", "flag": "🇹🇯", "loc": "Dushanbe"},
    "azerbaijani": {"voice": "az-AZ-BabekNeural", "flag": "🇦🇿", "loc": "Baku"},
    "turkish": {"voice": "tr-TR-AhmetNeural", "flag": "🇹🇷", "loc": "Istanbul"},
    "uzbek": {"voice": "uz-UZ-MadinaNeural", "flag": "🇺🇿", "loc": "Tashkent"},
    "kazakh": {"voice": "kk-KZ-AigulNeural", "flag": "🇰🇿", "loc": "Astana"},
    "russian": {"voice": "ru-RU-SvetlanaNeural", "flag": "🇷🇺", "loc": "Moscow"},
    "english": {"voice": "en-US-JennyNeural", "flag": "🇬🇧", "loc": "London"},
    "arabic": {"voice": "ar-AE-HamdanNeural", "flag": "🇦🇪", "loc": "Dubai"},
    "german": {"voice": "de-DE-KatjaNeural", "flag": "🇩🇪", "loc": "Berlin"},
    "hindi": {"voice": "hi-IN-SwaraNeural", "flag": "🇮🇳", "loc": "Delhi"},
}

def get_voice_info(lang_name):
    clean = (lang_name or "").strip().lower()
    for k, v in VOICE_MAP.items():
        if k in clean:
            return v
    return {"voice": "en-US-JennyNeural", "flag": "🌐", "loc": lang_name.capitalize() if lang_name else "Global"}

# 5. Groq Translation
def process_groq_translation(text, target_hint=None):
    if not GROQ_API_KEY:
        return None

    system_instruction = (
        "You are an expert bilingual bridge interpreter between two chatting users.\n"
        "1. Identify the source language (e.g., Malayalam, Persian, Tajik, Turkish, Uzbek, English, etc.).\n"
        "2. If Target Language Hint is provided and DIFFERENT from source, translate into that target language. "
        "If no hint is provided or hint is the same as source, translate Malayalam to Persian, Persian to Malayalam, and other languages to English.\n"
        "3. Always generate phonetic romanized English pronunciation for BOTH the source input and translated output.\n"
        "Output strictly in this 6-line format:\n"
        "SRC_LANG: [Source Language Name]\n"
        "TRG_LANG: [Target Language Name]\n"
        "SRC_PRON: [Phonetic English pronunciation of the source input]\n"
        "TRG_PRON: [Phonetic English pronunciation of the translated text]\n"
        "RES: [Translated text only]"
    )

    user_prompt = f"Input Text: \"{text}\"\nTarget Language Hint: {target_hint or 'None'}"

    try:
        completion = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.1,
            max_tokens=400,
        )
        return completion.choices[0].message.content.strip()
    except Exception:
        return None

# 6. Quotas & Subscriptions
FREE_LIMIT = 100
PLANS = {
    "sub_1m": {"name": "1 Month VIP", "days": 30, "stars": 50, "badge": "⭐️ VIP"},
    "sub_3m": {"name": "3 Months VIP", "days": 90, "stars": 120, "badge": "💎 ELITE"},
    "sub_1y": {"name": "1 Year VIP Pass", "days": 365, "stars": 399, "badge": "👑 LEGEND"},
}

def is_user_active(context: ContextTypes.DEFAULT_TYPE, user_id: str):
    if "premium_expiry" not in context.chat_data: context.chat_data["premium_expiry"] = {}
    if "free_credits" not in context.chat_data: context.chat_data["free_credits"] = {}

    exp = context.chat_data["premium_expiry"].get(user_id)
    if exp and datetime.utcnow() < datetime.fromisoformat(exp):
        days = (datetime.fromisoformat(exp) - datetime.utcnow()).days
        badge = context.chat_data.get("vip_tier", {}).get(user_id, "👑 VIP")
        return True, f"{badge} ({days}d left)", True

    if user_id not in context.chat_data["free_credits"]:
        context.chat_data["free_credits"][user_id] = FREE_LIMIT

    rem = context.chat_data["free_credits"][user_id]
    return (True, f"{rem}/100", False) if rem > 0 else (False, "Expired", False)

async def send_store_menu(chat_id, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "⭐️ <b>STAR VIP STORE & VAULT</b> ⭐️\n\n"
        "Free translation quota exhausted!\n\n"
        "• Unlimited 2-Way Translations\n"
        "• Ultra-Clear Neural Voices (Persian, Malayalam, etc.)\n"
        "• 0.75x Slow-Motion Voice Player\n"
        "• Secret VIP Luxury Themes\n\n"
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
        await context.bot.send_animation(chat_id=chat_id, animation=ANIM_STORE_URL, caption=text, parse_mode="HTML", reply_markup=keyboard)
    except Exception:
        await context.bot.send_message(chat_id=chat_id, text=text, parse_mode="HTML", reply_markup=keyboard)

# 7. Handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.chat_data["paused"] = False
    user_id = str(update.effective_user.id)
    _, _, is_vip = is_user_active(context, user_id)

    selected_theme = context.chat_data.get("user_theme", {}).get(user_id, "chibi")
    active_theme = ALL_THEMES.get(selected_theme, STANDARD_THEMES["chibi"])
    vip_badge = "👑 <b>VIP PRIVILEGES ACTIVE</b>\n" if is_vip else ""

    welcome = (
        f"🌐 <b>SMART 2-WAY TRANSLATOR</b>\n"
        f"{vip_badge}\n"
        "• ⚡ Instant auto 2-way cross translation\n"
        "• 🗣 Dual Phonetics (Original & Translated)\n"
        "• 🔊 Crystal-Clear Neural Persian Voice Enabled!\n\n"
        "/theme • Change themes | /status • Check quota"
    )
    try:
        await update.message.reply_animation(animation=active_theme["url"], caption=welcome, parse_mode="HTML")
    except Exception:
        await update.message.reply_text(welcome, parse_mode="HTML")

async def theme_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    _, _, is_vip = is_user_active(context, user_id)
    keyboard = []
    for key, item in STANDARD_THEMES.items():
        keyboard.append([InlineKeyboardButton(item["label"], callback_data=f"settheme_{key}")])
    for key, item in PREMIUM_THEMES.items():
        label = f"✨ {item['label']}" if is_vip else f"🔒 {item['label']} [VIP]"
        keyboard.append([InlineKeyboardButton(label, callback_data=f"settheme_{key}")])
    await update.message.reply_text("🎨 <b>Select Welcome Animation:</b>", parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))

async def theme_selection_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    theme_key = query.data.replace("settheme_", "")
    user_id = str(update.effective_user.id)
    _, _, is_vip = is_user_active(context, user_id)

    selected = ALL_THEMES.get(theme_key)
    if not selected: return
    if selected.get("vip") and not is_vip:
        await query.answer("🔒 VIP Theme! Upgrade with Stars to unlock.", show_alert=True)
        return
    if "user_theme" not in context.chat_data: context.chat_data["user_theme"] = {}
    context.chat_data["user_theme"][user_id] = theme_key
    await query.edit_message_text(f"✅ Active screen theme set to:\n{selected['label']}")

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    _, status_val, _ = is_user_active(context, user_id)
    state = "⏸ Paused" if context.chat_data.get("paused", False) else "▶️ Active"
    await update.message.reply_text(f"📊 <b>STATUS</b>\n🏃 Quota: {status_val}\n🔄 State: {state}", parse_mode="HTML")

async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.chat_data["paused"] = True
    await update.message.reply_text("⏸ <b>Translations Paused!</b>", parse_mode="HTML")

async def resume_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.chat_data["paused"] = False
    await update.message.reply_text("▶️ <b>Translations Resumed!</b>", parse_mode="HTML")

async def premium_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_store_menu(update.effective_chat.id, context)

# 8. Core Text & Translation Logic
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.chat_data.get("paused", False): return

    user = update.effective_user
    user_id = str(user.id)
    user_name = user.first_name or "User"

    active, status_val, is_vip = is_user_active(context, user_id)
    if not active:
        await send_store_menu(update.effective_chat.id, context)
        return

    text = update.message.text.strip()
    placeholder = await update.message.reply_text("<i>Translating... 🏃</i>", parse_mode="HTML")

    if "chat_users" not in context.chat_data:
        context.chat_data["chat_users"] = {}

    chat_users = context.chat_data["chat_users"]
    other_user_ids = [uid for uid in chat_users if uid != user_id]
    target_hint = chat_users[other_user_ids[0]] if other_user_ids else None

    raw_response = process_groq_translation(text, target_hint)

    src_lang = "Original"
    trg_lang = target_hint or "Persian"
    src_pron = ""
    trg_pron = ""
    translation = text

    if raw_response:
        for line in raw_response.splitlines():
            line = line.strip()
            if line.startswith("SRC_LANG:"): src_lang = line.replace("SRC_LANG:", "").strip()
            elif line.startswith("TRG_LANG:"): trg_lang = line.replace("TRG_LANG:", "").strip()
            elif line.startswith("SRC_PRON:"): src_pron = line.replace("SRC_PRON:", "").strip()
            elif line.startswith("TRG_PRON:"): trg_pron = line.replace("TRG_PRON:", "").strip()
            elif line.startswith("RES:"): translation = line.replace("RES:", "").strip()

    # Lock this user's language
    if src_lang and "unknown" not in src_lang.lower():
        chat_users[user_id] = src_lang

    if not is_vip:
        context.chat_data["free_credits"][user_id] -= 1
        _, status_val, _ = is_user_active(context, user_id)

    src_info = get_voice_info(src_lang)
    trg_info = get_voice_info(trg_lang)

    user_theme_key = context.chat_data.get("user_theme", {}).get(user_id, "chibi")
    active_theme = ALL_THEMES.get(user_theme_key, STANDARD_THEMES["chibi"])

    if is_vip and active_theme.get("vip"):
        vip_header = f"<b>{active_theme.get('badge')}</b>\n"
        quote_symbol = active_theme.get("quote_prefix", "✨ ")
        status_line = f"👑 <b>VIP Priority</b> • {status_val}"
    else:
        vip_header = ""
        quote_symbol = ""
        status_line = f"🏃 Status: {status_val}"

    src_pron_str = f"🗣 <i>Original:</i> <code>{src_pron}</code>\n" if src_pron and src_pron.upper() != "NONE" else ""
    trg_pron_str = f"🗣 <i>Phonetic:</i> <tg-spoiler>{trg_pron}</tg-spoiler>\n" if trg_pron and trg_pron.upper() != "NONE" else ""

    card_text = (
        f"{vip_header}"
        f"👤 <b>{user_name}</b>\n"
        f"{src_info['flag']} <code>{src_lang.upper()}</code> ➔ {trg_info['flag']} <code>{trg_lang.upper()}</code>\n"
        f"📍 <i>{src_info['loc']} ⇄ {trg_info['loc']}</i>\n\n"
        f"{src_pron_str}"
        f"<blockquote>{quote_symbol}{translation}</blockquote>"
        f"{trg_pron_str}\n"
        f"{status_line}"
    )

    msg_id = placeholder.message_id
    context.bot_data[f"tts_trg_{msg_id}"] = {
        "text": translation,
        "voice": trg_info["voice"],
        "lang": trg_lang
    }

    keyboard = [
        [InlineKeyboardButton(f"🔊 Listen ({trg_info['flag']} {trg_lang})", callback_data=f"play_{msg_id}")]
    ]
    if is_vip:
        keyboard.append([InlineKeyboardButton("🐢 Slow-Mo (0.75x)", callback_data=f"slow_{msg_id}")])

    await placeholder.edit_text(card_text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))

# 9. Crystal-Clear Edge-TTS Voice Audio Generator
async def handle_tts_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("🎙️ Generating Persian/Native Voice...")
    data = query.data

    is_slow = data.startswith("slow_")
    msg_id = data.replace("slow_", "").replace("play_", "")

    cache = context.bot_data.get(f"tts_trg_{msg_id}")
    if not cache:
        await query.answer("Session expired. Please send message again!", show_alert=True)
        return

    text_to_speak = cache["text"]
    voice = cache.get("voice", "fa-IR-DilaraNeural")

    rate_str = "-25%" if is_slow else "+0%"

    try:
        communicate = edge_tts.Communicate(text_to_speak, voice, rate=rate_str)
        audio_buffer = io.BytesIO()
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_buffer.write(chunk["data"])

        audio_buffer.seek(0)
        audio_buffer.name = "voice.ogg"

        caption = f"🔊 <i>Spoken ({cache['lang']}): \"{text_to_speak[:45]}...\"</i>"
        await context.bot.send_voice(chat_id=query.message.chat_id, voice=audio_buffer, caption=caption, parse_mode="HTML")
    except Exception as e:
        await query.answer(f"Voice Error: {str(e)[:45]}", show_alert=True)

# 10. Star Payments
async def plan_selection_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    plan_key = query.data.replace("buy_", "")
    if plan_key not in PLANS: return
    plan = PLANS[plan_key]

    await context.bot.send_invoice(
        chat_id=query.message.chat_id,
        title=f"⭐️ {plan['name']}",
        description=f"Unlock VIP features for {plan['days']} days.",
        payload=plan_key,
        provider_token="",
        currency="XTR",
        prices=[LabeledPrice(label=plan["name"], amount=plan["stars"])],
    )

async def precheckout_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.pre_checkout_query.answer(ok=True)

async def successful_payment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    plan_key = update.message.successful_payment.invoice_payload
    plan = PLANS.get(plan_key, PLANS["sub_1m"])

    if "premium_expiry" not in context.chat_data: context.chat_data["premium_expiry"] = {}
    if "vip_tier" not in context.chat_data: context.chat_data["vip_tier"] = {}

    current_expiry_str = context.chat_data["premium_expiry"].get(user_id)
    now = datetime.utcnow()
    base_time = datetime.fromisoformat(current_expiry_str) if current_expiry_str and datetime.fromisoformat(current_expiry_str) > now else now

    new_expiry = base_time + timedelta(days=plan["days"])
    context.chat_data["premium_expiry"][user_id] = new_expiry.isoformat()
    context.chat_data["vip_tier"][user_id] = plan["badge"]

    gift_text = f"🎁 <b>VIP UNLOCKED!</b> ⭐️\n\n👑 <b>Tier:</b> {plan['name']}\n💎 <b>Badge:</b> {plan['badge']}"
    try:
        await update.message.reply_animation(animation=VIP_GIFT_STICKER, caption=gift_text, parse_mode="HTML")
    except Exception:
        await update.message.reply_text(gift_text, parse_mode="HTML")

# 11. Run Engine
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
    app.add_handler(CallbackQueryHandler(handle_tts_button, pattern="^(play_|slow_)"))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(PreCheckoutQueryHandler(precheckout_callback))
    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment_callback))

    await app.initialize()
    try: await app.bot.delete_webhook(drop_pending_updates=True)
    except Exception: pass
    await app.start()

    while True:
        try:
            await app.updater.start_polling(drop_pending_updates=True)
            while True: await asyncio.sleep(3600)
        except Exception:
            await asyncio.sleep(5)

def main():
    try: asyncio.run(run_bot())
    except (KeyboardInterrupt, SystemExit): pass

if __name__ == "__main__":
    main()
