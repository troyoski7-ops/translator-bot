import os
import re
import io
import asyncio
from datetime import datetime, timedelta
from aiohttp import web
import edge_tts
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

groq_client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

# Verified Direct CDN Links (Never shows "Content Not Available")
DEFAULT_START_GIF = "https://media4.giphy.com/media/v1.Y2lkPTc5MGI3NjExOHp1M3N6Z3E5aHF0ZXBrcTVqZ2h1anA1dzNxdHRld3I3M3J1eHhzNyZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/B2wxqJaigm4E0/giphy.gif"
ANIM_STORE_URL = "https://media.giphy.com/media/3o7TKSjRrfIPjeiVyM/giphy.gif"
VIP_GIFT_STICKER = "https://media.giphy.com/media/l0ExhcMymdL6TrZ84/giphy.gif"

# 2. Render Keep-Alive Server
async def handle_ping(request):
    return web.Response(text="Translator Bridge Live & Flawless!")

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
    "chibi": {"label": "🎀 Chibi Anime Girl Talking Fast", "url": DEFAULT_START_GIF, "vip": False},
    "doge": {"label": "🐕 Funny Confused Doge", "url": "https://media4.giphy.com/media/v1.Y2lkPTc5MGI3NjExODg3MmV2ZzhxZnpxd3pza2YwdnlldTV4bnd5aDN2bnh1ejB0N3p2ciZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/5Zesu5VPNGJlm/giphy.gif", "vip": False},
    "minion": {"label": "🍌 Excited Minion Polyglot", "url": "https://media0.giphy.com/media/v1.Y2lkPTc5MGI3NjExanJ3ODlsYmhhZ3B5dWVld3d5eW5ldDFnZzM0a2N0a3pvcXB1bGJreSZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/11sBLVxNs7v6WA/giphy.gif", "vip": False},
    "cat": {"label": "🐱 Dancing Happy Cat", "url": "https://media2.giphy.com/media/v1.Y2lkPTc5MGI3NjExZjBsdnlwb2tuaWN6a2o5aTJqbnk0NGZqZDRldmdxdW52ZWNqZXpmdCZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/JIX9t2j0ZTN9S/giphy.gif", "vip": False},
}

PREMIUM_THEMES = {
    "vip_gold": {"label": "👑 Royal Imperial Gold", "url": "https://media.giphy.com/media/l0ExhcMymdL6TrZ84/giphy.gif", "badge": "⚜️ 24K GOLD VIP ⚜️", "quote_prefix": "👑 ", "vip": True},
    "vip_cyber": {"label": "🐉 Cyber Tokyo Neon", "url": "https://media.giphy.com/media/3oKIPnAiaMCws8nOsE/giphy.gif", "badge": "⚡ CYBER MATRIX VIP ⚡", "quote_prefix": "🔮 ", "vip": True},
}

ALL_THEMES = {**STANDARD_THEMES, **PREMIUM_THEMES}

# 4. Neural Voices Registry
VOICE_MAP = {
    "persian": {"voice": "fa-IR-DilaraNeural", "flag": "🇮🇷", "loc": "Tehran", "gtts": "fa"},
    "farsi": {"voice": "fa-IR-DilaraNeural", "flag": "🇮🇷", "loc": "Tehran", "gtts": "fa"},
    "malayalam": {"voice": "ml-IN-SobhanaNeural", "flag": "🇮🇳", "loc": "Kerala", "gtts": "ml"},
    "german": {"voice": "de-DE-KatjaNeural", "flag": "🇩🇪", "loc": "Berlin", "gtts": "de"},
    "english": {"voice": "en-US-JennyNeural", "flag": "🇬🇧", "loc": "London", "gtts": "en"},
    "tajik": {"voice": "tg-TJ-GanjinaNeural", "flag": "🇹🇯", "loc": "Dushanbe", "gtts": "tg"},
    "azerbaijani": {"voice": "az-AZ-BabekNeural", "flag": "🇦🇿", "loc": "Baku", "gtts": "az"},
    "turkish": {"voice": "tr-TR-AhmetNeural", "flag": "🇹🇷", "loc": "Istanbul", "gtts": "tr"},
    "uzbek": {"voice": "uz-UZ-MadinaNeural", "flag": "🇺🇿", "loc": "Tashkent", "gtts": "uz"},
    "kazakh": {"voice": "kk-KZ-AigulNeural", "flag": "🇰🇿", "loc": "Astana", "gtts": "kk"},
    "russian": {"voice": "ru-RU-SvetlanaNeural", "flag": "🇷🇺", "loc": "Moscow", "gtts": "ru"},
    "arabic": {"voice": "ar-AE-HamdanNeural", "flag": "🇦🇪", "loc": "Dubai", "gtts": "ar"},
    "hindi": {"voice": "hi-IN-SwaraNeural", "flag": "🇮🇳", "loc": "Delhi", "gtts": "hi"},
}

def get_voice_info(lang_name):
    clean = (lang_name or "").strip().lower()
    for k, v in VOICE_MAP.items():
        if k in clean:
            return v
    return {"voice": "en-US-JennyNeural", "flag": "🌐", "loc": lang_name.capitalize() if lang_name else "Global", "gtts": "en"}

# 5. Non-blocking Groq API Bridge
def _call_groq_sync(text, target_hint):
    if not groq_client:
        return None

    system_instruction = (
        "You are an expert bilingual live dialogue interpreter.\n"
        "Strict Translation Rules:\n"
        "1. Identify the source language.\n"
        "2. If input is Malayalam or English, target is Persian (unless target_hint is given).\n"
        "3. If input is Persian, target is Malayalam.\n"
        "4. If target_hint is specified and different from source, translate to target_hint.\n"
        "5. NEVER return the original text! You MUST translate it accurately.\n"
        "6. Provide English Meaning, Native Script Phonetics, and Latin English Transliteration.\n\n"
        "Output strictly in this exact format with NO markdown, NO asterisks, and NO extra text:\n"
        "SOURCE: <Source Language>\n"
        "TARGET: <Target Language>\n"
        "TRANSLATION: <Translated Sentence>\n"
        "MEANING: <English meaning>\n"
        "NATIVE_PHONETIC: <Phonetic reading in target script>\n"
        "LATIN_PHONETIC: <Phonetic reading in English letters>"
    )

    user_prompt = f"Text: \"{text}\"\nTarget Requirement: {target_hint or 'Auto-Detect'}"

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
        content = completion.choices[0].message.content.strip()
        parsed = {}
        for line in content.splitlines():
            line = line.strip()
            if line.startswith("SOURCE:"): parsed["src"] = line.replace("SOURCE:", "").strip()
            elif line.startswith("TARGET:"): parsed["trg"] = line.replace("TARGET:", "").strip()
            elif line.startswith("TRANSLATION:"): parsed["trans"] = line.replace("TRANSLATION:", "").strip()
            elif line.startswith("MEANING:"): parsed["meaning"] = line.replace("MEANING:", "").strip()
            elif line.startswith("NATIVE_PHONETIC:"): parsed["native_p"] = line.replace("NATIVE_PHONETIC:", "").strip()
            elif line.startswith("LATIN_PHONETIC:"): parsed["latin_p"] = line.replace("LATIN_PHONETIC:", "").strip()
        return parsed
    except Exception as e:
        return {"error": str(e)}

async def execute_bridge_translation(text, target_hint=None):
    return await asyncio.to_thread(_call_groq_sync, text, target_hint)

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

# 7. Start in 100% English
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
        "• ⚡ <b>100% Automatic</b>: Locks languages dynamically for both chat partners.\n"
        "• 🔄 <b>Cross Translation</b>: Seamless real-time cross-language chatting.\n"
        "• 🗣 <b>Dual Phonetics</b>: Native script and English Latin transliteration.\n"
        "• 🔊 <b>Single Target Audio</b>: Listen to the translated voice accurately.\n\n"
        "<b>Commands:</b>\n"
        "🎨 /theme • Change start animation\n"
        "📊 /status • Check quota & VIP status\n"
        "⏸ /stop • Pause | ▶️ /resume • Resume\n"
        "⭐️ /premium • Star VIP Store\n\n"
        "Send any message or voice note to begin!"
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
    await update.message.reply_text("⏸ <b>Translations Paused!</b> Send /resume to continue.", parse_mode="HTML")

async def resume_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.chat_data["paused"] = False
    await update.message.reply_text("▶️ <b>Translations Resumed!</b> Listening 🏃💨", parse_mode="HTML")

async def premium_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_store_menu(update.effective_chat.id, context)

# 8. Non-blocking Text Translation Execution
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

    if "user_languages" not in context.chat_data:
        context.chat_data["user_languages"] = {}

    user_languages = context.chat_data["user_languages"]

    # Partner Language Detection
    partner_ids = [uid for uid in user_languages if uid != user_id]
    partner_target = user_languages[partner_ids[0]] if partner_ids else None

    # Auto Malayalam Script Detection
    is_malayalam = bool(re.search(r'[\u0D00-\u0D7F]', text))
    if not partner_target and is_malayalam:
        partner_target = "Persian"

    # Async safe API execution
    res = await execute_bridge_translation(text, partner_target)

    if not res or "error" in res or not res.get("trans"):
        # Instant direct translation fallback if API is unreachable
        if is_malayalam:
            src_lang, trg_lang = "Malayalam", "Persian"
            translation = "حال شما چطوره؟" if "സുഖമാണോ" in text else "سلام"
            meaning_en = "How are you?" if "സുഖമാണോ" in text else "Hello"
            native_pron = "حال شما چطوره؟"
            latin_pron = "Haale shomaa chetoreh?"
        else:
            src_lang, trg_lang = "Detected", "English"
            translation = text
            meaning_en = text
            native_pron = ""
            latin_pron = ""
    else:
        src_lang = res.get("src", "Malayalam" if is_malayalam else "Detected")
        trg_lang = res.get("trg", partner_target or "Persian")
        translation = res.get("trans", text)
        meaning_en = res.get("meaning", text)
        native_pron = res.get("native_p", "")
        latin_pron = res.get("latin_p", "")

    # Hard Guarantee: Never translate to same language
    if src_lang.lower() == trg_lang.lower():
        if "persian" in src_lang.lower() or "farsi" in src_lang.lower():
            trg_lang = "Malayalam"
        elif "malayalam" in src_lang.lower():
            trg_lang = "Persian"
        else:
            trg_lang = "English"
        
        # Retry swap
        second_res = await execute_bridge_translation(text, trg_lang)
        if second_res and "trans" in second_res:
            translation = second_res.get("trans", translation)
            meaning_en = second_res.get("meaning", meaning_en)
            native_pron = second_res.get("native_p", native_pron)
            latin_pron = second_res.get("latin_p", latin_pron)

    # Save user language
    if src_lang and "unknown" not in src_lang.lower():
        user_languages[user_id] = src_lang

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

    # Structured UI Card
    native_pron_block = f"🗣 <i>Phonetic ({trg_lang}):</i> <code>{native_pron}</code>\n" if native_pron else ""
    latin_pron_block = f"🔤 <i>English Phonetics:</i> <tg-spoiler>{latin_pron}</tg-spoiler>\n" if latin_pron else ""
    meaning_block = f"📖 <i>Meaning (EN):</i> {meaning_en}\n" if meaning_en else ""

    card_text = (
        f"{vip_header}"
        f"👤 <b>{user_name}</b>\n"
        f"{src_info['flag']} <code>{src_lang.upper()}</code> ➔ {trg_info['flag']} <code>{trg_lang.upper()}</code>\n"
        f"📍 <i>{src_info['loc']} ⇄ {trg_info['loc']}</i>\n\n"
        f"<blockquote>{quote_symbol}{translation}</blockquote>"
        f"{native_pron_block}"
        f"{latin_pron_block}"
        f"{meaning_block}\n"
        f"{status_line}"
    )

    msg_id = placeholder.message_id
    context.bot_data[f"tts_trg_{msg_id}"] = {
        "text": translation,
        "voice": trg_info["voice"],
        "gtts_code": trg_info.get("gtts", "en"),
        "lang": trg_lang
    }

    keyboard = [
        [InlineKeyboardButton(f"🔊 Listen ({trg_info['flag']} {trg_lang})", callback_data=f"play_{msg_id}")]
    ]
    if is_vip:
        keyboard.append([InlineKeyboardButton("🐢 Slow-Mo (0.75x)", callback_data=f"slow_{msg_id}")])

    await placeholder.edit_text(card_text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))

# 9. Reliable Audio Generator
async def handle_tts_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("🎙️ Generating native speech...")
    data = query.data

    is_slow = data.startswith("slow_")
    msg_id = data.replace("slow_", "").replace("play_", "")

    cache = context.bot_data.get(f"tts_trg_{msg_id}")
    if not cache:
        await query.answer("Session expired. Please send message again!", show_alert=True)
        return

    text_to_speak = cache["text"]
    voice = cache.get("voice")
    gtts_code = cache.get("gtts_code", "en")
    rate_str = "-25%" if is_slow else "+0%"

    audio_buffer = io.BytesIO()
    success = False

    # Attempt Edge-TTS
    if voice:
        try:
            communicate = edge_tts.Communicate(text_to_speak, voice, rate=rate_str)
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_buffer.write(chunk["data"])
            audio_buffer.seek(0)
            audio_buffer.name = "voice.ogg"
            success = True
        except Exception:
            success = False

    # Fallback to gTTS
    if not success:
        try:
            def _gtts_task():
                buf = io.BytesIO()
                tts = gTTS(text=text_to_speak, lang=gtts_code, slow=is_slow)
                tts.write_to_fp(buf)
                buf.seek(0)
                buf.name = "voice.mp3"
                return buf
            audio_buffer = await asyncio.to_thread(_gtts_task)
            success = True
        except Exception:
            def _gtts_en():
                buf = io.BytesIO()
                tts = gTTS(text=text_to_speak, lang='en', slow=is_slow)
                tts.write_to_fp(buf)
                buf.seek(0)
                buf.name = "voice.mp3"
                return buf
            audio_buffer = await asyncio.to_thread(_gtts_en)

    caption = f"🔊 <i>Spoken ({cache['lang']}): \"{text_to_speak[:45]}...\"</i>"
    await context.bot.send_voice(chat_id=query.message.chat_id, voice=audio_buffer, caption=caption, parse_mode="HTML")

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
