import os
import re
import io
import asyncio
from datetime import datetime, timedelta
from aiohttp import web
from gtts import gTTS
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
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

# 2. Render Keep-Alive Server
async def handle_ping(request):
    return web.Response(text="Translator Bridge Core Online & Functional!")

async def start_web_server():
    app = web.Application()
    app.router.add_get('/', handle_ping)
    app.router.add_get('/healthz', handle_ping)
    port = int(os.environ.get("PORT", 10000))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()

# 3. Themes: 4 Free + 4 Luxury VIP Vault
STANDARD_THEMES = {
    "chibi": {"label": "🎀 Anime Girl", "url": "https://media.giphy.com/media/B2wxqJaigm4E0/giphy.gif", "vip": False},
    "doge": {"label": "🐕 Smart Doge", "url": "https://media.giphy.com/media/5Zesu5VPNGJlm/giphy.gif", "vip": False},
    "minion": {"label": "🍌 Polyglot Minion", "url": "https://media.giphy.com/media/11sBLVxNs7v6WA/giphy.gif", "vip": False},
    "cat": {"label": "🐱 Dancing Cat", "url": "https://media.giphy.com/media/JIX9t2j0ZTN9S/giphy.gif", "vip": False},
}

PREMIUM_THEMES = {
    "vip_gold": {"label": "👑 Royal Imperial Gold", "url": "https://media.giphy.com/media/l0ExhcMymdL6TrZ84/giphy.gif", "badge": "⚜️ 24K GOLD VIP ⚜️", "quote_prefix": "👑 ", "vip": True},
    "vip_cyber": {"label": "🐉 Cyber Tokyo Neon", "url": "https://media.giphy.com/media/3oKIPnAiaMCws8nOsE/giphy.gif", "badge": "⚡ CYBER MATRIX VIP ⚡", "quote_prefix": "🔮 ", "vip": True},
    "vip_matrix": {"label": "⚡ Quantum Astral Core", "url": "https://media.giphy.com/media/l378c0402U49fs29O/giphy.gif", "badge": "✨ ASTRAL HORIZON ✨", "quote_prefix": "🪐 ", "vip": True},
    "vip_sound": {"label": "🎧 Hologram Soundwaves", "url": "https://media.giphy.com/media/26AHONQ79FdWZhAI0/giphy.gif", "badge": "💎 DIAMOND PRESTIGE 💎", "quote_prefix": "❄️ ", "vip": True}
}

ALL_THEMES = {**STANDARD_THEMES, **PREMIUM_THEMES}
ANIM_STORE_URL = "https://media.giphy.com/media/3o7TKSjRrfIPjeiVyM/giphy.gif"
VIP_GIFT_STICKER = "https://media.giphy.com/media/l0ExhcMymdL6TrZ84/giphy.gif"

# 4. Regional Voice Registry
VOICE_MAP = {
    "chinese": {"edge": "zh-CN-XiaoxiaoNeural", "gtts": "zh-CN", "flag": "🇨🇳", "loc": "Beijing"},
    "japanese": {"edge": "ja-JP-NanamiNeural", "gtts": "ja", "flag": "🇯🇵", "loc": "Tokyo"},
    "italian": {"edge": "it-IT-ElsaNeural", "gtts": "it", "flag": "🇮🇹", "loc": "Rome"},
    "german": {"edge": "de-DE-KatjaNeural", "gtts": "de", "flag": "🇩🇪", "loc": "Berlin"},
    "persian": {"edge": "fa-IR-DilaraNeural", "gtts": "fa", "flag": "🇮🇷", "loc": "Tehran"},
    "farsi": {"edge": "fa-IR-DilaraNeural", "gtts": "fa", "flag": "🇮🇷", "loc": "Tehran"},
    "malayalam": {"edge": "ml-IN-SobhanaNeural", "gtts": "ml", "flag": "🇮🇳", "loc": "Kerala"},
    "russian": {"edge": "ru-RU-SvetlanaNeural", "gtts": "ru", "flag": "🇷🇺", "loc": "Moscow"},
    "english": {"edge": "en-US-JennyNeural", "gtts": "en", "flag": "🇬🇧", "loc": "London"},
    "tajik": {"edge": "tg-TJ-GanjinaNeural", "gtts": "tg", "flag": "🇹🇯", "loc": "Dushanbe"},
    "azerbaijani": {"edge": "az-AZ-BabekNeural", "gtts": "az", "flag": "🇦🇿", "loc": "Baku"},
    "turkish": {"edge": "tr-TR-AhmetNeural", "gtts": "tr", "flag": "🇹🇷", "loc": "Istanbul"},
    "arabic": {"edge": "ar-AE-HamdanNeural", "gtts": "ar", "flag": "🇦🇪", "loc": "Dubai"},
    "hindi": {"edge": "hi-IN-SwaraNeural", "gtts": "hi", "flag": "🇮🇳", "loc": "Delhi"},
    "french": {"edge": "fr-FR-DeniseNeural", "gtts": "fr", "flag": "🇫🇷", "loc": "Paris"},
    "spanish": {"edge": "es-ES-ElviraNeural", "gtts": "es", "flag": "🇪🇸", "loc": "Madrid"},
    "korean": {"edge": "ko-KR-SunHiNeural", "gtts": "ko", "flag": "🇰🇷", "loc": "Seoul"},
}

def get_voice_info(lang_name):
    clean = (lang_name or "").strip().lower()
    for k, v in VOICE_MAP.items():
        if k in clean:
            return v
    return {"edge": "en-US-JennyNeural", "gtts": "en", "flag": "🌐", "loc": lang_name.capitalize() if lang_name else "Global"}

# 5. Dynamic Groq AI Engine
def _sync_groq_call(text, partner_lang=None, is_group=False):
    if not GROQ_API_KEY:
        return {"error": "GROQ_API_KEY is not configured in Render!"}

    client = Groq(api_key=GROQ_API_KEY)

    if is_group:
        system_instruction = (
            "You are an active live 2-way conversation interpreter inside a Telegram Group.\n"
            "Rules:\n"
            "1. Accurately detect the source language.\n"
            "2. If Partner Language is provided and different, translate directly into Partner Language.\n"
            "3. If Partner Language is not known, translate foreign text to English and English to partner's alternate language.\n"
            "4. NEVER output raw template placeholders.\n"
            "5. Output must strictly contain these 6 lines only:\n"
            "SRC: Source Language Name\n"
            "TRG: Target Language Name\n"
            "TRANS: Translation text\n"
            "MEANING: English meaning\n"
            "NATIVE_P: Native script phonetic pronunciation helper\n"
            "LATIN_P: Latin English alphabet pronunciation helper"
        )
        user_prompt = f"Message: \"{text}\"\nPartner Language: {partner_lang or 'None'}"
    else:
        system_instruction = (
            "You are a dedicated Personal Language Assistant and Tutor for a direct message chat.\n"
            "Rules:\n"
            "1. Accurately detect the source language.\n"
            "2. If input is English, translate to Malayalam (or alternate language).\n"
            "3. If input is foreign or regional (Malayalam, German, Russian, etc.), translate to English.\n"
            "4. Output must strictly contain these 6 lines only:\n"
            "SRC: Source Language Name\n"
            "TRG: Target Language Name\n"
            "TRANS: Translation text\n"
            "MEANING: English meaning\n"
            "NATIVE_P: Native script phonetic pronunciation helper\n"
            "LATIN_P: Latin English alphabet pronunciation helper"
        )
        user_prompt = f"Message: \"{text}\""

    models_to_try = []
    try:
        m_list = client.models.list()
        for m in m_list.data:
            mid = m.id.lower()
            if not any(bad in mid for bad in ["whisper", "guard", "vision", "embed", "safeguard", "distil"]):
                models_to_try.append(m.id)
    except Exception:
        pass

    standard_fallbacks = ["llama-3.3-70b-versatile", "llama-3.1-8b-instant", "llama3-70b-8192"]
    for fb in standard_fallbacks:
        if fb not in models_to_try:
            models_to_try.append(fb)

    last_error_msg = ""
    for model_id in models_to_try:
        try:
            completion = client.chat.completions.create(
                model=model_id,
                messages=[
                    {"role": "system", "content": system_instruction},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.1,
                max_tokens=400,
            )
            raw = completion.choices[0].message.content.strip()
            parsed = {}
            for line in raw.splitlines():
                line = line.strip()
                if line.startswith("SRC:"): parsed["src"] = line.replace("SRC:", "").strip()
                elif line.startswith("TRG:"): parsed["trg"] = line.replace("TRG:", "").strip()
                elif line.startswith("TRANS:"): parsed["trans"] = line.replace("TRANS:", "").strip()
                elif line.startswith("MEANING:"): parsed["meaning"] = line.replace("MEANING:", "").strip()
                elif line.startswith("NATIVE_P:"): parsed["native_p"] = line.replace("NATIVE_P:", "").strip()
                elif line.startswith("LATIN_P:"): parsed["latin_p"] = line.replace("LATIN_P:", "").strip()

            if parsed.get("trans") and "[" not in parsed.get("trans", ""):
                return parsed
        except Exception as e:
            last_error_msg = str(e)
            continue

    return {"error": f"Groq Error: {last_error_msg}"}

async def execute_translation(text, partner_lang=None, is_group=False):
    return await asyncio.to_thread(_sync_groq_call, text, partner_lang, is_group)

# 6. Quota & VIP Logic
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
        "⚡ <b>HOLOGRAPHIC VIP VAULT</b> ⚡\n\n"
        "Free translation quota exhausted!\n\n"
        "• Unlimited Text Translations (Group & Solo)\n"
        "• High-Definition Audio Pronunciations with 0.75x Slow-Motion\n"
        "• Secret VIP Luxury Themes & Custom Backgrounds\n\n"
        "• <b>1 Month VIP:</b> 50 Stars\n"
        "• <b>3 Months ELITE:</b> 120 Stars <i>(20% Off)</i>\n"
        "• <b>1 Year LEGEND:</b> 399 Stars <i>(Best Value!)</i>"
    )
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔥 1 Month (50 Stars)", callback_data="buy_sub_1m")],
        [InlineKeyboardButton("💎 3 Months (120 Stars)", callback_data="buy_sub_3m")],
        [InlineKeyboardButton("👑 1 Year LEGEND (399 Stars)", callback_data="buy_sub_1y")],
    ])
    try:
        await context.bot.send_animation(chat_id=chat_id, animation=ANIM_STORE_URL, caption=text, parse_mode="HTML", reply_markup=keyboard)
    except Exception:
        await context.bot.send_message(chat_id=chat_id, text=text, parse_mode="HTML", reply_markup=keyboard)

# 7. Start Command (Updated: Text-Only Architecture Focus)
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.chat_data["paused"] = False
    user_id = str(update.effective_user.id)
    _, _, is_vip = is_user_active(context, user_id)

    custom_bg = context.chat_data.get("user_custom_bg", {}).get(user_id)
    selected_theme = context.chat_data.get("user_theme", {}).get(user_id, "chibi")
    active_theme = ALL_THEMES.get(selected_theme, STANDARD_THEMES["chibi"])
    
    bg_url = custom_bg if (custom_bg and is_vip) else active_theme["url"]
    vip_badge = "🌟 <b>VIP HOLOGRAPHIC SHIELD ACTIVE</b>\n" if is_vip else ""

    welcome = (
        f"🌌 <b>QUANTUM POLYGLOT NEURAL BRIDGE</b> 🌌\n"
        f"{vip_badge}\n"
        "✨ <b>HOW THIS BOT WORKS:</b>\n\n"
        "👤 <b>1. Personal Chat (Solo Tutor & Translator):</b>\n"
        "• Send any text, word, or sentence in any language.\n"
        "• Get instant meanings, dynamic card UI, dual phonetics, and native HD audio (`🔊 Listen`).\n\n"
        "👥 <b>2. Group Chat (Automatic Live Neural Bridge):</b>\n"
        "• Add this bot to any group chat!\n"
        "• Cross-translates multi-lingual text conversations on the fly.\n\n"
        "<b>Commands:</b>\n"
        "🎨 /theme • Holographic UI Theme\n"
        "🖼 /custombg [URL] • Set Custom VIP Background GIF\n"
        "📊 /status • Quota & Core Status\n"
        "⏸ /stop • Pause | ▶️ /resume • Resume\n"
        "⭐️ /premium • VIP Vault\n\n"
        "Send any text to begin your quantum session!"
    )
    try:
        await update.message.reply_animation(animation=bg_url, caption=welcome, parse_mode="HTML")
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
    await update.message.reply_text("🎨 <b>Select Holographic Theme:</b>", parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))

async def theme_selection_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    theme_key = query.data.replace("settheme_", "")
    user_id = str(update.effective_user.id)
    _, _, is_vip = is_user_active(context, user_id)

    selected = ALL_THEMES.get(theme_key)
    if not selected: return
    if selected.get("vip") and not is_vip:
        await query.answer("🔒 VIP Locked! Upgrade with Telegram Stars.", show_alert=True)
        return
    if "user_theme" not in context.chat_data: context.chat_data["user_theme"] = {}
    context.chat_data["user_theme"][user_id] = theme_key
    await query.edit_message_text(f"✨ Holographic theme updated to:\n<b>{selected['label']}</b>", parse_mode="HTML")

async def custom_bg_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    _, _, is_vip = is_user_active(context, user_id)
    
    if not is_vip:
        await update.message.reply_text("🔒 <b>VIP Exclusive Feature!</b>\n\nCustom background GIFs are unlocked only for VIP/Legend subscribers. Use /premium to upgrade!", parse_mode="HTML")
        return

    args = context.args
    if not args:
        await update.message.reply_text(
            "🖼 <b>Custom Background Setup (VIP)</b>\n\n"
            "Usage: <code>/custombg [GIF / Animation URL]</code>\n"
            "Example: <code>/custombg https://media.giphy.com/media/...</code>",
            parse_mode="HTML"
        )
        return
    
    custom_url = args[0]
    if "user_custom_bg" not in context.chat_data:
        context.chat_data["user_custom_bg"] = {}
        
    context.chat_data["user_custom_bg"][user_id] = custom_url
    await update.message.reply_text("✅ <b>Custom VIP Background GIF successfully saved!</b> Use /start to see your new welcome animation.", parse_mode="HTML")

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    _, status_val, _ = is_user_active(context, user_id)
    state = "⏸ Paused" if context.chat_data.get("paused", False) else "🟢 Online & Syncing"
    await update.message.reply_text(
        f"📊 <b>CORE STATUS</b>\n\n"
        f"🔋 Neural Quota: {status_val}\n"
        f"⚡ Bridge State: {state}\n\n"
        f"<i>Unlock unlimited bandwidth & custom themes via /premium</i>",
        parse_mode="HTML"
    )

async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.chat_data["paused"] = True
    await update.message.reply_text("⏸ <b>Neural Bridge Paused!</b> Send /resume to reactivate.", parse_mode="HTML")

async def resume_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.chat_data["paused"] = False
    await update.message.reply_text("▶️ <b>Neural Bridge Resumed!</b> Synchronizing ⚡", parse_mode="HTML")

async def premium_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_store_menu(update.effective_chat.id, context)

# 8. Animated Visual Card Engine (Text Input Only)
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.chat_data.get("paused", False): 
        return

    user = update.effective_user
    user_id = str(user.id)
    user_name = user.first_name or "Operator"

    active, status_val, is_vip = is_user_active(context, user_id)
    if not active:
        await send_store_menu(update.effective_chat.id, context)
        return

    text = update.message.text.strip()
    placeholder = await update.message.reply_text("⚡ <i>Synthesizing Neural Translation...</i>", parse_mode="HTML")

    chat_type = update.effective_chat.type
    is_group = chat_type in ["group", "supergroup"]

    if "user_langs" not in context.chat_data:
        context.chat_data["user_langs"] = {}

    user_langs = context.chat_data["user_langs"]

    if is_group:
        other_users = [uid for uid in user_langs if uid != user_id]
        partner_target = user_langs[other_users[-1]] if other_users else None
    else:
        partner_target = None

    res = await execute_translation(text, partner_target, is_group=is_group)

    if "error" in res:
        await placeholder.edit_text(f"⚠️ <b>Neural Error:</b> {res['error']}", parse_mode="HTML")
        return

    src_lang = res.get("src", "Detected")
    trg_lang = res.get("trg", "Target")
    translation = res.get("trans", text)
    meaning_en = res.get("meaning", text)
    native_p = res.get("native_p", "")
    latin_p = res.get("latin_p", "")

    user_langs[user_id] = src_lang

    if not is_vip:
        context.chat_data["free_credits"][user_id] -= 1
        _, status_val, _ = is_user_active(context, user_id)

    src_info = get_voice_info(src_lang)
    trg_info = get_voice_info(trg_lang)

    user_theme_key = context.chat_data.get("user_theme", {}).get(user_id, "chibi")
    active_theme = ALL_THEMES.get(user_theme_key, STANDARD_THEMES["chibi"])

    if is_vip and active_theme.get("vip"):
        vip_header = f"🔮 <b>{active_theme.get('badge')}</b>\n"
        quote_symbol = active_theme.get("quote_prefix", "✨ ")
        status_line = f"💎 <b>Quantum Priority</b> • {status_val}"
    else:
        vip_header = ""
        quote_symbol = "💬 "
        status_line = f"🔋 Quota: {status_val}"

    native_block = f"🗣 <i>Phonetic Script ({trg_lang}):</i>\n<code>{native_p}</code>\n" if native_p else ""
    latin_block = f"🔤 <i>Phonetic Alphabet:</i> <tg-spoiler>{latin_p}</tg-spoiler>\n" if latin_p else ""
    meaning_block = f"📖 <i>Contextual Meaning:</i> <b>{meaning_en}</b>\n" if meaning_en else ""

    mode_label = "🌐 Group Live Neural Bridge" if is_group else "💠 Personal Neural Tutor"

    card_text = (
        f"{vip_header}"
        f"👤 <b>{user_name}</b> ➔ <i>{mode_label}</i>\n"
        f"────────────────────────\n"
        f"{src_info['flag']} <code>{src_lang.upper()}</code>  <b>⚡ SYNC ⚡</b>  {trg_info['flag']} <code>{trg_info['loc']} ({trg_lang.upper()})</code>\n"
        f"📍 <i>{src_info['loc']}</i> ⟷ <i>{trg_info['loc']}</i>\n"
        f"────────────────────────\n\n"
        f"<blockquote>{quote_symbol}<b>{translation}</b></blockquote>\n\n"
        f"{native_block}"
        f"{latin_block}"
        f"{meaning_block}\n"
        f"────────────────────────\n"
        f"⚡ {status_line}"
    )

    msg_id = placeholder.message_id
    context.bot_data[f"aud_{msg_id}"] = {
        "text": translation,
        "voice_edge": trg_info.get("edge"),
        "gtts_code": trg_info["gtts"],
        "lang": trg_lang
    }

    keyboard = [
        [InlineKeyboardButton(f"🔊 Listen ({trg_info['flag']} {trg_lang})", callback_data=f"play_{msg_id}")]
    ]
    if is_vip:
        keyboard.append([InlineKeyboardButton("🐢 Slow-Mo Matrix (0.75x)", callback_data=f"slow_{msg_id}")])

    await placeholder.edit_text(card_text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))

# 9. HD Audio Synthesis Engine
async def handle_audio_play(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("🎧 Synthesizing HD Audio Stream...")
    data = query.data

    is_slow = data.startswith("slow_")
    msg_id = data.replace("slow_", "").replace("play_", "")

    cache = context.bot_data.get(f"aud_{msg_id}")
    if not cache:
        await query.answer("Audio session expired. Send a new message!", show_alert=True)
        return

    text_to_speak = cache["text"]
    voice_edge = cache.get("voice_edge")
    gtts_code = cache.get("gtts_code", "en")
    rate_str = "-25%" if is_slow else "+0%"

    temp_audio_file = f"speech_{msg_id}.mp3"
    speed_label = "Slow-Mo Matrix" if is_slow else "HD Native"
    caption = f"🔊 <b>{speed_label} Audio Stream ({cache['lang']}):</b>\n<i>\"{text_to_speak}\"</i>"

    try:
        worked = False
        if voice_edge:
            try:
                communicate = edge_tts.Communicate(text_to_speak, voice_edge, rate=rate_str)
                await communicate.save(temp_audio_file)
                if os.path.exists(temp_audio_file) and os.path.getsize(temp_audio_file) > 500:
                    worked = True
            except Exception:
                worked = False

        if not worked:
            def _generate_gtts():
                tts = gTTS(text=text_to_speak, lang=gtts_code, slow=is_slow)
                tts.save(temp_audio_file)
            await asyncio.to_thread(_generate_gtts)

        with open(temp_audio_file, "rb") as audio:
            await context.bot.send_audio(
                chat_id=query.message.chat_id,
                audio=audio,
                title=f"{cache['lang']} Pronunciation",
                performer="Quantum Neural Bridge",
                caption=caption,
                parse_mode="HTML"
            )

    except Exception as e:
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text=f"⚠️ Audio error: {str(e)[:60]}"
        )
    finally:
        if os.path.exists(temp_audio_file):
            try: os.remove(temp_audio_file)
            except Exception: pass

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

    gift_text = f"🎁 <b>VIP HOLOGRAPHIC PASS UNLOCKED!</b> ⭐️\n\n👑 <b>Tier:</b> {plan['name']}\n💎 <b>Badge:</b> {plan['badge']}"
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
    app.add_handler(CommandHandler("custombg", custom_bg_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CommandHandler("stop", stop_command))
    app.add_handler(CommandHandler("resume", resume_command))
    app.add_handler(CommandHandler("premium", premium_command))

    app.add_handler(CallbackQueryHandler(plan_selection_callback, pattern="^buy_"))
    app.add_handler(CallbackQueryHandler(theme_selection_callback, pattern="^settheme_"))
    app.add_handler(CallbackQueryHandler(handle_audio_play, pattern="^(play_|slow_)"))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(PreCheckoutQueryHandler(precheckout_callback))
    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment_callback))

    await app.initialize()
    try: await app.bot.delete_webhook(drop_pending_updates=True)
    except Exception: pass
    app.start()

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
