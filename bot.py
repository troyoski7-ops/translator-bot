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

# 2. Render Keep-Alive Server
async def handle_ping(request):
    return web.Response(text="Translator Bridge Live!")

async def start_web_server():
    app = web.Application()
    app.router.add_get('/', handle_ping)
    app.router.add_get('/healthz', handle_ping)
    port = int(os.environ.get("PORT", 10000))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()

# 3. Themes: 4 Free + VIP Luxury Vault
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

# 4. Neural Voices Mapping (Edge-TTS)
VOICE_MAP = {
    "persian": {"voice": "fa-IR-DilaraNeural", "flag": "🇮🇷", "loc": "Tehran"},
    "farsi": {"voice": "fa-IR-DilaraNeural", "flag": "🇮🇷", "loc": "Tehran"},
    "malayalam": {"voice": "ml-IN-SobhanaNeural", "flag": "🇮🇳", "loc": "Kerala"},
    "german": {"voice": "de-DE-KatjaNeural", "flag": "🇩🇪", "loc": "Berlin"},
    "english": {"voice": "en-US-JennyNeural", "flag": "🇬🇧", "loc": "London"},
    "tajik": {"voice": "tg-TJ-GanjinaNeural", "flag": "🇹🇯", "loc": "Dushanbe"},
    "azerbaijani": {"voice": "az-AZ-BabekNeural", "flag": "🇦🇿", "loc": "Baku"},
    "azeri": {"voice": "az-AZ-BabekNeural", "flag": "🇦🇿", "loc": "Baku"},
    "turkish": {"voice": "tr-TR-AhmetNeural", "flag": "🇹🇷", "loc": "Istanbul"},
    "uzbek": {"voice": "uz-UZ-MadinaNeural", "flag": "🇺🇿", "loc": "Tashkent"},
    "kazakh": {"voice": "kk-KZ-AigulNeural", "flag": "🇰🇿", "loc": "Astana"},
    "russian": {"voice": "ru-RU-SvetlanaNeural", "flag": "🇷🇺", "loc": "Moscow"},
    "arabic": {"voice": "ar-AE-HamdanNeural", "flag": "🇦🇪", "loc": "Dubai"},
    "hindi": {"voice": "hi-IN-SwaraNeural", "flag": "🇮🇳", "loc": "Delhi"},
    "french": {"voice": "fr-FR-DeniseNeural", "flag": "🇫🇷", "loc": "Paris"},
    "spanish": {"voice": "es-ES-ElviraNeural", "flag": "🇪🇸", "loc": "Madrid"},
    "italian": {"voice": "it-IT-ElsaNeural", "flag": "🇮🇹", "loc": "Rome"},
}

def get_voice_info(lang_name):
    clean = (lang_name or "").strip().lower()
    for k, v in VOICE_MAP.items():
        if k in clean:
            return v
    return {"voice": "en-US-JennyNeural", "flag": "🌐", "loc": lang_name.capitalize() if lang_name else "Global"}

# 5. Universal Translation Engine (Automatic Language Bridge)
def execute_bridge_translation(text, target_hint=None):
    if not GROQ_API_KEY:
        return None

    system_instruction = (
        "You are an infallible bilingual chat interpreter bridging two people.\n"
        "1. Accurately detect the source language of the input text.\n"
        "2. If Target Language is provided and DIFFERENT from source, translate into that target language.\n"
        "   If no target is provided or target is identical to source, automatically cross-translate:\n"
        "   - Persian/Tajik -> Malayalam (or English)\n"
        "   - Malayalam -> Persian\n"
        "   - English -> Persian\n"
        "   - Other languages -> English\n"
        "3. Provide the English Meaning of the sentence.\n"
        "4. Provide two pronunciations for the translated text:\n"
        "   - TRG_NATIVE_PHONETIC: Native script or native phonetic writing helper.\n"
        "   - TRG_EN_PHONETIC: Transliteration in Latin English alphabet so any speaker can easily pronounce it.\n"
        "Strictly output in this 7-line format:\n"
        "SRC_LANG: [Detected Source Language Name]\n"
        "TRG_LANG: [Target Language Name]\n"
        "ENG_MEANING: [Clear English Meaning]\n"
        "TRG_NATIVE_PHONETIC: [Phonetic helper in native script/system]\n"
        "TRG_EN_PHONETIC: [Phonetic transliteration in English letters]\n"
        "RES: [Translated text only]"
    )

    user_prompt = f"Text: \"{text}\"\nTarget Hint: {target_hint or 'Auto-Detect'}"

    try:
        completion = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.1,
            max_tokens=450,
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
        "• Unlimited Automatic 2-Way Translations\n"
        "• Ultra-Clear Neural Voice Playback\n"
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

# 7. Handlers & Commands
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.chat_data["paused"] = False
    user_id = str(update.effective_user.id)
    _, _, is_vip = is_user_active(context, user_id)

    selected_theme = context.chat_data.get("user_theme", {}).get(user_id, "chibi")
    active_theme = ALL_THEMES.get(selected_theme, STANDARD_THEMES["chibi"])
    vip_badge = "👑 <b>VIP PRIVILEGES ACTIVE</b>\n" if is_vip else ""

    welcome = (
        f"🌐 <b>SMART 2-WAY DIALOGUE INTERPRETER</b>\n"
        f"{vip_badge}\n"
        "• ⚡ <b>100% ഓട്ടോമാറ്റിക്</b>: രണ്ട് പേരുടെ ഭാഷയും തനിയെ ലോക്ക് ചെയ്യുന്നു!\n"
        "• 🔄 സംസാരിക്കുന്നതിനനുസരിച്ച് തനിയെ അങ്ങോട്ടും ഇങ്ങോട്ടും ട്രാൻസ്ലേറ്റ് ചെയ്യും.\n"
        "• 🗣 <b>Dual Phonetics</b>: തനത് ഉച്ചാരണവും ഇംഗ്ലീഷ് Transliteration-ഉം!\n"
        "• 🔊 <b>Single Target Voice</b>: കേൾക്കേണ്ട ഭാഷയുടെ വോയ്‌സ് മാത്രം താഴെ പ്ലേ ചെയ്യാം.\n\n"
        "<b>Commands:</b>\n"
        "🎨 /theme • Change start screen theme\n"
        "📊 /status • Check quota / VIP status\n"
        "⏸ /stop • Pause | ▶️ /resume • Resume\n"
        "⭐️ /premium • VIP Star Store"
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
    await update.message.reply_text(
        f"📊 <b>STATUS</b>\n\n"
        f"🏃 Usage Quota: {status_val}\n"
        f"🔄 State: {state}\n\n"
        f"<i>Unlock unlimited usage & VIP themes with /premium</i>",
        parse_mode="HTML"
    )

async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.chat_data["paused"] = True
    await update.message.reply_text("⏸ <b>Translations Paused!</b> Send /resume to start again.", parse_mode="HTML")

async def resume_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.chat_data["paused"] = False
    await update.message.reply_text("▶️ <b>Translations Resumed!</b> Listening 🏃💨", parse_mode="HTML")

async def premium_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_store_menu(update.effective_chat.id, context)

# 8. 100% Automatic 2-Way Language Bridge Logic
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.chat_data.get("paused", False): 
        return

    user = update.effective_user
    user_id = str(user.id)
    user_name = user.first_name or "User"

    active, status_val, is_vip = is_user_active(context, user_id)
    if not active:
        await send_store_menu(update.effective_chat.id, context)
        return

    text = update.message.text.strip()
    placeholder = await update.message.reply_text("<i>Translating... 🏃</i>", parse_mode="HTML")

    # ഓരോ യൂസറുടെയും ഏറ്റവും പുതിയ ഭാഷ ഓട്ടോമാറ്റിക് ആയി സേവ് ചെയ്യുന്നു
    if "user_languages" not in context.chat_data:
        context.chat_data["user_languages"] = {}

    user_languages = context.chat_data["user_languages"]

    # ചാറ്റിലെ രണ്ടാമത്തെ ആളിന്റെ ലേറ്റസ്റ്റ് ഭാഷ കണ്ടെത്തുന്നു
    partner_ids = [uid for uid in user_languages if uid != user_id]
    partner_target_lang = user_languages[partner_ids[0]] if partner_ids else None

    # AI വഴി ട്രാൻസ്ലേറ്റ് ചെയ്യുന്നു
    raw_response = execute_bridge_translation(text, partner_target_lang)

    src_lang = "Detected"
    trg_lang = partner_target_lang or "Persian"
    eng_meaning = ""
    trg_native_pron = ""
    trg_en_pron = ""
    translation = text

    if raw_response:
        for line in raw_response.splitlines():
            line = line.strip()
            if line.startswith("SRC_LANG:"): src_lang = line.replace("SRC_LANG:", "").strip()
            elif line.startswith("TRG_LANG:"): trg_lang = line.replace("TRG_LANG:", "").strip()
            elif line.startswith("ENG_MEANING:"): eng_meaning = line.replace("ENG_MEANING:", "").strip()
            elif line.startswith("TRG_NATIVE_PHONETIC:"): trg_native_pron = line.replace("TRG_NATIVE_PHONETIC:", "").strip()
            elif line.startswith("TRG_EN_PHONETIC:"): trg_en_pron = line.replace("TRG_EN_PHONETIC:", "").strip()
            elif line.startswith("RES:"): translation = line.replace("RES:", "").strip()

    # അയച്ച ആളുടെ ഭാഷ ഓട്ടോമാറ്റിക് ആയി അപ്‌ഡേറ്റ് ചെയ്യുന്നു
    if src_lang and "unknown" not in src_lang.lower():
        user_languages[user_id] = src_lang

    # ഒരേ ഭാഷ തന്നെ വരാതിരിക്കാനുള്ള സ്മാർട്ട് ചെക്ക് (Persian -> Persian ഒഴിവാക്കുന്നു)
    if src_lang.strip().lower() == trg_lang.strip().lower():
        if "persian" in src_lang.lower() or "farsi" in src_lang.lower():
            trg_lang = "Malayalam" if partner_target_lang == "Malayalam" else "English"
        elif "malayalam" in src_lang.lower():
            trg_lang = "Persian"
        else:
            trg_lang = "English"

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

    # തനത് ലിപിയിലെയും ഇംഗ്ലീഷ് ലാറ്റിൻ ലിപിയിലെയും ഉച്ചാരണം
    native_pron_block = f"🗣 <i>Phonetic Script ({trg_lang}):</i> <code>{trg_native_pron}</code>\n" if trg_native_pron and trg_native_pron.upper() != "NONE" else ""
    en_pron_block = f"🔤 <i>English Phonetics:</i> <tg-spoiler>{trg_en_pron}</tg-spoiler>\n" if trg_en_pron and trg_en_pron.upper() != "NONE" else ""
    meaning_block = f"📖 <i>Meaning (EN):</i> {eng_meaning}\n" if eng_meaning and eng_meaning.upper() != "NONE" else ""

    card_text = (
        f"{vip_header}"
        f"👤 <b>{user_name}</b>\n"
        f"{src_info['flag']} <code>{src_lang.upper()}</code> ➔ {trg_info['flag']} <code>{trg_lang.upper()}</code>\n"
        f"📍 <i>{src_info['loc']} ⇄ {trg_info['loc']}</i>\n\n"
        f"<blockquote>{quote_symbol}{translation}</blockquote>"
        f"{native_pron_block}"
        f"{en_pron_block}"
        f"{meaning_block}\n"
        f"{status_line}"
    )

    msg_id = placeholder.message_id
    context.bot_data[f"tts_trg_{msg_id}"] = {
        "text": translation,
        "voice": trg_info["voice"],
        "lang": trg_lang
    }

    # ഒരൊറ്റ ഓഡിയോ ബട്ടൺ (Target Voice Only)
    keyboard = [
        [InlineKeyboardButton(f"🔊 Listen ({trg_info['flag']} {trg_lang})", callback_data=f"play_{msg_id}")]
    ]
    if is_vip:
        keyboard.append([InlineKeyboardButton("🐢 Slow-Mo (0.75x)", callback_data=f"slow_{msg_id}")])

    await placeholder.edit_text(card_text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))

# 9. Crystal-Clear Edge-TTS Voice Generator
async def handle_tts_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("🎙️ Generating native voice...")
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
        except Exception as e:
            if "Conflict" in str(e):
                try: await app.updater.stop()
                except Exception: pass
                await asyncio.sleep(10)
            else:
                await asyncio.sleep(5)

def main():
    try: asyncio.run(run_bot())
    except (KeyboardInterrupt, SystemExit): pass

if __name__ == "__main__":
    main()
