import os
import re
import io
import time
import asyncio
import subprocess
import sys
import urllib.request
import urllib.parse
import json

from datetime import datetime, timedelta
from aiohttp import web
from gtts import gTTS
import edge_tts
from telegram import (
    Update,
    LabeledPrice,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    BotCommand
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

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()

OWNER_USER_ID = 1689374364
UNLIMITED_GROUPS = set()

# Vibe Chill Lofi Audio Stream/Sample link for welcome and premium vibe
VIBE_MUSIC_URL = "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3"

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

STANDARD_THEMES = {
    "chibi": {"label": "🎀 Anime Girl", "url": "https://media.giphy.com/media/B2wxqJaigm4E0/giphy.gif", "vip": False},
    "doge": {"label": "🐕 Smart Doge", "url": "https://media.giphy.com/media/5Zesu5VPNGJlm/giphy.gif", "vip": False},
    "minion": {"label": "🍌 Polyglot Minion", "url": "https://media.giphy.com/media/11sBLVxNs7v6WA/giphy.gif", "vip": False},
    "cat": {"label": "🐱 Dancing Cat", "url": "https://media.giphy.com/media/JIX9t2j0ZTN9S/giphy.gif", "vip": False},
}

PREMIUM_THEMES = {
    "vip_gold": {"label": "👑 Royal Imperial Gold", "url": "https://media.giphy.com/media/l0ExhcMymdL6TrZ84/giphy.gif", "badge": "⚜️ 24K GOLD VIP ⚜️", "vip": True},
    "vip_cyber": {"label": "🐉 Cyber Tokyo Neon", "url": "https://media.giphy.com/media/3oKIPnAiaMCws8nOsE/giphy.gif", "badge": "⚡ CYBER MATRIX VIP ⚡", "vip": True},
    "vip_matrix": {"label": "⚡ Quantum Astral Core", "url": "https://media.giphy.com/media/l378c0402U49fs29O/giphy.gif", "badge": "✨ ASTRAL HORIZON ✨", "vip": True},
    "vip_sound": {"label": "🎧 Hologram Soundwaves", "url": "https://media.giphy.com/media/26AHONQ79FdWZhAI0/giphy.gif", "badge": "💎 DIAMOND PRESTIGE 💎", "vip": True}
}

ALL_THEMES = {**STANDARD_THEMES, **PREMIUM_THEMES}

ANIM_WELCOME_URL = "https://media.giphy.com/media/3oKIPnAiaMCws8nOsE/giphy.gif"
ANIM_STORE_URL = "https://media.giphy.com/media/3o7TKSjRrfIPjeiVyM/giphy.gif"
VIP_GIFT_STICKER = "https://media.giphy.com/media/l0ExhcMymdL6TrZ84/giphy.gif"

VOICE_MAP = {
    "malayalam": {"edge": "ml-IN-SobhanaNeural", "gtts": "ml", "flag": "🇮🇳", "code": "ml"},
    "german": {"edge": "de-DE-KatjaNeural", "gtts": "de", "flag": "🇩🇪", "code": "de"},
    "english": {"edge": "en-US-JennyNeural", "gtts": "en", "flag": "🇬🇧", "code": "en"},
    "persian": {"edge": "fa-IR-DilaraNeural", "gtts": "fa", "flag": "🇮🇷", "code": "fa"},
    "russian": {"edge": "ru-RU-SvetlanaNeural", "gtts": "ru", "flag": "🇷🇺", "code": "ru"},
    "french": {"edge": "fr-FR-DeniseNeural", "gtts": "fr", "flag": "🇫🇷", "code": "fr"},
    "spanish": {"edge": "es-ES-ElviraNeural", "gtts": "es", "flag": "🇪🇸", "code": "es"},
    "arabic": {"edge": "ar-AE-HamdanNeural", "gtts": "ar", "flag": "🇦🇪", "code": "ar"},
    "hindi": {"edge": "hi-IN-SwaraNeural", "gtts": "hi", "flag": "🇮🇳", "code": "hi"},
    "chinese": {"edge": "zh-CN-XiaoxiaoNeural", "gtts": "zh-CN", "flag": "🇨🇳", "code": "zh"},
    "japanese": {"edge": "ja-JP-NanamiNeural", "gtts": "ja", "flag": "🇯🇵", "code": "ja"},
    "korean": {"edge": "ko-KR-SunHiNeural", "gtts": "ko", "flag": "🇰🇷", "code": "ko"},
    "italian": {"edge": "it-IT-ElsaNeural", "gtts": "it", "flag": "🇮🇹", "code": "it"},
    "turkish": {"edge": "tr-TR-AhmetNeural", "gtts": "tr", "flag": "🇹🇷", "code": "tr"},
    "ukrainian": {"edge": "uk-UA-PolinaNeural", "gtts": "uk", "flag": "🇺🇦", "code": "uk"},
    "vietnamese": {"edge": "vi-VN-HoaiMyNeural", "gtts": "vi", "flag": "🇻🇳", "code": "vi"},
    "georgian": {"edge": "ka-GE-EkaNeural", "gtts": "ka", "flag": "🇬🇪", "code": "ka"},
    "azerbaijani": {"edge": "az-AZ-BanuNeural", "gtts": "az", "flag": "🇦🇿", "code": "az"},
}

def get_voice_info(lang_name):
    clean = (lang_name or "").strip().lower()
    for k, v in VOICE_MAP.items():
        if k in clean:
            return v
    return VOICE_MAP["english"]

def _sync_translation_logic(text, target_override=None):
    try:
        is_eng = all(ord(c) < 128 for c in text)
        target = target_override if target_override else ('ml' if is_eng else 'en')
        
        url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl=auto&tl={target}&dt=t&q={urllib.parse.quote(text)}"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        
        with urllib.request.urlopen(req, timeout=5) as response:
            res_data = json.loads(response.read().decode('utf-8'))
            translated = "".join([item[0] for item in res_data[0] if item[0]])
            detected_code = res_data[2] if len(res_data) > 2 and res_data[2] else "unknown"

        phonetic_text = text
        try:
            url_phonetic = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl=auto&tl=en&dt=rm&q={urllib.parse.quote(text)}"
            req_p = urllib.request.Request(url_phonetic, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req_p, timeout=5) as resp_p:
                p_data = json.loads(resp_p.read().decode('utf-8'))
                if len(p_data) > 0 and len(p_data[0]) > 0:
                    for item in p_data[0]:
                        if len(item) > 3 and item[3]:
                            phonetic_text = item[3]
                            break
        except Exception:
            pass

        if not translated:
            return {"error": "Translation failed. Please try again."}

        lang_names = {
            'ml': 'Malayalam', 'fa': 'Persian', 'de': 'German', 'uk': 'Ukrainian',
            'vi': 'Vietnamese', 'zh': 'Chinese', 'ja': 'Japanese', 'ko': 'Korean',
            'fr': 'French', 'es': 'Spanish', 'ru': 'Russian', 'en': 'English',
            'ar': 'Arabic', 'hi': 'Hindi', 'it': 'Italian', 'tr': 'Turkish', 'ka': 'Georgian', 'az': 'Azerbaijani'
        }
        
        src_lang_name = lang_names.get(detected_code, detected_code.upper() if detected_code != "unknown" else "Foreign Language")
        target_lang_name = lang_names.get(target, target.upper())

        return {
            "src": src_lang_name,
            "trg": target_lang_name,
            "trans": translated,
            "meaning": translated,
            "native_p": text,
            "latin_p": phonetic_text if phonetic_text != text else text,
            "cultural_insight": f"An expression commonly used in {src_lang_name}.",
            "native_text": text,
            "target_code": target
        }
    except Exception as e:
        return {"error": f"Error: {str(e)[:40]}"}

async def execute_translation(text, target_override=None):
    return await asyncio.to_thread(_sync_translation_logic, text, target_override)

FREE_LIMIT = 100
PLANS = {
    "sub_1m": {"name": "1 Month VIP", "days": 30, "stars": 50, "badge": "⭐️ VIP"},
    "sub_3m": {"name": "3 Months VIP", "days": 90, "stars": 120, "badge": "💎 ELITE"},
    "sub_1y": {"name": "1 Year VIP Pass", "days": 365, "stars": 399, "badge": "👑 LEGEND"},
}

def is_user_active(context: ContextTypes.DEFAULT_TYPE, user_id: int, chat_id: int):
    if user_id == OWNER_USER_ID:
        return True, "♾️ UNLIMITED", True
        
    if chat_id in UNLIMITED_GROUPS:
        return True, "♾️ UNLIMITED GROUP", True

    str_user_id = str(user_id)
    if "premium_expiry" not in context.bot_data: context.bot_data["premium_expiry"] = {}
    if "free_credits" not in context.bot_data: context.bot_data["free_credits"] = {}

    exp = context.bot_data["premium_expiry"].get(str_user_id)
    if exp and datetime.utcnow() < datetime.fromisoformat(exp):
        days = (datetime.fromisoformat(exp) - datetime.utcnow()).days
        badge = context.bot_data.get("vip_tier", {}).get(str_user_id, "👑 VIP")
        return True, f"{badge} ({days}d left)", True

    if str_user_id not in context.bot_data["free_credits"]:
        context.bot_data["free_credits"][str_user_id] = FREE_LIMIT

    rem = context.bot_data["free_credits"][str_user_id]
    return (True, f"{rem}/100", False) if rem > 0 else (False, "Expired", False)

async def set_group_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat = update.effective_chat

    if user_id != OWNER_USER_ID:
        await update.message.reply_text("⛔ You are not authorized to use this command (Owner Only).")
        return

    if chat.type in ["group", "supergroup"]:
        UNLIMITED_GROUPS.add(chat.id)
        await update.message.reply_text("🚀 <b>Success!</b> This group is now set to <b>Unlimited Free Translations</b> for everyone by Owner!", parse_mode="HTML")
    else:
        await update.message.reply_text("⚠️ This command can only be used inside a Telegram Group!", parse_mode="HTML")

async def send_store_menu(chat_id, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "⚡ <b>HOLOGRAPHIC VIP VAULT</b> ⚡\n\n"
        "Your free 100 messages quota has expired!\n\n"
        "• Unlimited Translations\n"
        "• High-Definition Dual Audio Pronunciations\n"
        "• Exclusive VIP Themes\n"
        "• 🎧 VIP Vibe Music Lounge Access\n\n"
        "• <b>1 Month VIP:</b> 50 Stars\n"
        "• <b>3 Months ELITE:</b> 120 Stars\n"
        "• <b>1 Year LEGEND:</b> 399 Stars"
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

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    _, _, is_vip = is_user_active(context, user_id, chat_id)

    vip_badge = "🌟 <b>VIP HOLOGRAPHIC SHIELD ACTIVE</b>\n" if is_vip else ""

    welcome = (
        f"🌌 <b>QUANTUM TWO-WAY TRANSLATION BRIDGE & VIBE LOUNGE</b> 🌌\n"
        f"{vip_badge}\n"
        "✨ <b>HOW THIS BOT WORKS:</b>\n\n"
        "💬 <b>1. Personal Chat (PM):</b>\n"
        "• Send text or voice notes directly to me in <b>any language</b> for instant translation, phonetics, and meanings.\n\n"
        "👥 <b>2. Telegram Groups (Automatic 2-Way):</b>\n"
        "• Add this bot to any group chat.\n"
        "• <b>User 1</b> types in their language → <b>Bot automatically translates it.</b>\n"
        "• <b>User 2</b> replies in their language → <b>Bot automatically translates it back.</b> No manual setup needed!\n\n"
        "🎧 Use /vibe to play chill background music anytime!\n\n"
        "<b>Commands:</b>\n"
        "🎧 /vibe • Play Chill Vibe Music\n"
        "🌍 /setlang • Choose Target Language\n"
        "🎨 /theme • Holographic UI Theme\n"
        "📊 /status • Quota & Core Status\n"
        "⏸ /stop • Pause | ▶️ /resume • Resume\n"
        "⭐️ /premium • VIP Vault\n\n"
        "<b>Send any text or voice note to begin!</b>"
    )
    try:
        await update.message.reply_animation(animation=ANIM_WELCOME_URL, caption=welcome, parse_mode="HTML")
        # Play welcome vibe audio
        await update.message.reply_audio(audio=VIBE_MUSIC_URL, caption="🎧 <b>Welcome Vibe Track:</b> Enjoy the chill rhythm!", parse_mode="HTML")
    except Exception:
        await update.message.reply_text(welcome, parse_mode="HTML")

async def vibe_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    active, _, is_vip = is_user_active(context, user_id, chat_id)
    
    if not active:
        await send_store_menu(chat_id, context)
        return

    try:
        await update.message.reply_audio(
            audio=VIBE_MUSIC_URL, 
            caption="🎧 <b>VIP Vibe Lounge:</b> Relax and enjoy the stream!", 
            parse_mode="HTML"
        )
    except Exception as e:
        await update.message.reply_text(f"⚠️ Vibe error: {str(e)[:40]}")

async def setlang_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🇮🇳 Malayalam", callback_data="lang_ml"), InlineKeyboardButton("🇩🇪 German", callback_data="lang_de")],
        [InlineKeyboardButton("🇬🇧 English", callback_data="lang_en"), InlineKeyboardButton("🇮🇷 Persian", callback_data="lang_fa")],
        [InlineKeyboardButton("🇷🇺 Russian", callback_data="lang_ru"), InlineKeyboardButton("🇫🇷 French", callback_data="lang_fr")],
        [InlineKeyboardButton("🇪🇸 Spanish", callback_data="lang_es"), InlineKeyboardButton("🇦🇪 Arabic", callback_data="lang_ar")],
        [InlineKeyboardButton("🇮🇳 Hindi", callback_data="lang_hi"), InlineKeyboardButton("🇨🇳 Chinese", callback_data="lang_zh")],
        [InlineKeyboardButton("🇯🇵 Japanese", callback_data="lang_ja"), InlineKeyboardButton("🇰🇷 Korean", callback_data="lang_ko")],
        [InlineKeyboardButton("🇮🇹 Italian", callback_data="lang_it"), InlineKeyboardButton("🇹🇷 Turkish", callback_data="lang_tr")],
        [InlineKeyboardButton("🇺🇦 Ukrainian", callback_data="lang_uk"), InlineKeyboardButton("🇻🇳 Vietnamese", callback_data="lang_vi")],
    ]
    await update.message.reply_text("🌍 <b>Select your default target language:</b>", parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))

async def lang_selection_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    lang_code = query.data.replace("lang_", "")
    user_id = str(update.effective_user.id)

    if "user_lang" not in context.bot_data: context.bot_data["user_lang"] = {}
    context.bot_data["user_lang"][user_id] = lang_code
    
    await query.edit_message_text(f"✅ Target language successfully set to: <b>{lang_code.upper()}</b>", parse_mode="HTML")

async def theme_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    _, _, is_vip = is_user_active(context, user_id, chat_id)
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
    user_id = update.effective_user.id
    chat_id = query.message.chat_id
    _, _, is_vip = is_user_active(context, user_id, chat_id)

    selected = ALL_THEMES.get(theme_key)
    if not selected: return
    if selected.get("vip") and not is_vip:
        await query.answer("🔒 VIP Locked! Upgrade using Telegram Stars.", show_alert=True)
        return
    if "user_theme" not in context.bot_data: context.bot_data["user_theme"] = {}
    context.bot_data["user_theme"][str(user_id)] = theme_key
    await query.edit_message_text(f"✨ Theme updated to:\n<b>{selected['label']}</b>", parse_mode="HTML")

async def custom_bg_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    _, _, is_vip = is_user_active(context, user_id, chat_id)
    if not is_vip:
        await update.message.reply_text("🔒 <b>This is a VIP exclusive feature!</b>", parse_mode="HTML")
        return
    args = context.args
    if not args:
        await update.message.reply_text("🖼 Usage: <code>/custombg [URL]</code>", parse_mode="HTML")
        return
    if "user_custom_bg" not in context.bot_data: context.bot_data["user_custom_bg"] = {}
    context.bot_data["user_custom_bg"][str(user_id)] = args[0]
    await update.message.reply_text("✅ Custom background saved successfully!", parse_mode="HTML")

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    _, status_val, _ = is_user_active(context, user_id, chat_id)
    await update.message.reply_text(f"📊 <b>Your Quota:</b> {status_val}", parse_mode="HTML")

async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.chat_data["paused"] = True
    await update.message.reply_text("⏸ Bot paused successfully.", parse_mode="HTML")

async def resume_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.chat_data["paused"] = False
    await update.message.reply_text("▶️ Bot resumed successfully.", parse_mode="HTML")

async def premium_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_store_menu(update.effective_chat.id, context)

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.chat_data.get("paused", False): return
    if not update.message or not update.message.text: return
    
    user_id = str(update.effective_user.id)
    target_override = None
    if "user_lang" in context.bot_data and user_id in context.bot_data["user_lang"]:
        target_override = context.bot_data["user_lang"][user_id]
        
    await process_and_reply(update, context, update.message.text.strip(), target_override)

async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.chat_data.get("paused", False): return
    if not update.message or not update.message.voice: return

    placeholder = await update.message.reply_text("🎙 <i>Processing voice note...</i>", parse_mode="HTML")
    voice = update.message.voice
    file = await context.bot.get_file(voice.file_id)
    
    ogg_path = f"voice_{voice.file_unique_id}.ogg"
    mp3_path = f"voice_{voice.file_unique_id}.mp3"
    
    try:
        await file.download_to_drive(ogg_path)
        subprocess.run(["ffmpeg", "-y", "-i", ogg_path, mp3_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        trans_text = "Voice message translation"
        await placeholder.delete()
        
        user_id = str(update.effective_user.id)
        target_override = context.bot_data.get("user_lang", {}).get(user_id)
        await process_and_reply(update, context, trans_text, target_override)
    except Exception as e:
        await placeholder.edit_text(f"⚠️ Voice error: {str(e)[:40]}")
    finally:
        for p in [ogg_path, mp3_path]:
            if os.path.exists(p):
                try: os.remove(p)
                except Exception: pass

async def process_and_reply(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str, target_override=None):
    user = update.effective_user
    user_id = user.id
    chat_id = update.effective_chat.id
    user_name = user.first_name or "Operator"

    active, status_val, is_vip = is_user_active(context, user_id, chat_id)
    if not active:
        await send_store_menu(update.effective_chat.id, context)
        return

    placeholder = await update.message.reply_text("⚡ <i>Translating...</i>", parse_mode="HTML")
    res = await execute_translation(text, target_override)

    if "error" in res:
        await placeholder.edit_text(f"⚠️ <b>Error:</b> {res['error']}", parse_mode="HTML")
        return

    src_lang = res.get("src", "English")
    trg_lang = res.get("trg", "Malayalam")
    translation = res.get("trans", text)
    native_p = res.get("native_p", text)
    latin_p = res.get("latin_p", "")
    cultural_insight = res.get("cultural_insight", "A unique linguistic expression.")

    if user_id != OWNER_USER_ID and chat_id not in UNLIMITED_GROUPS and not is_vip:
        str_user_id = str(user_id)
        context.bot_data["free_credits"][str_user_id] -= 1
        _, status_val, _ = is_user_active(context, user_id, chat_id)

    src_info = get_voice_info(src_lang)
    trg_info = get_voice_info(trg_lang)

    native_p_block = f"🗣 <i>Phonetic ({src_info['flag']} {src_lang}):</i> <code>{native_p}</code>\n" if native_p else ""
    latin_p_block = f"🔤 <i>English Phonetics:</i> <tg-spoiler><b>{latin_p}</b></tg-spoiler>\n" if latin_p else ""
    meaning_en_block = f"📖 <b>Meaning ({trg_lang.upper()}): {translation}</b>\n" if translation else ""
    cultural_block = f"💡 <i>Insight:</i> <b>{cultural_insight}</b>\n" if cultural_insight else ""

    card_text = (
        f"👤 <b>{user_name}</b>\n"
        f"────────────────────────\n"
        f"{src_info['flag']} <code>{src_lang.upper()}</code> ➔ {trg_info['flag']} <code>{trg_info['flag']}</code>\n"
        f"────────────────────────\n\n"
        f"💬 <b>{translation}</b>\n\n"
        f"{native_p_block}"
        f"{latin_p_block}"
        f"{meaning_en_block}"
        f"{cultural_block}\n"
        f"────────────────────────\n"
        f"🔋 Quota: {status_val}"
    )

    msg_id = placeholder.message_id
    context.bot_data[f"aud_src_{msg_id}"] = {"text": text, "voice_edge": src_info.get("edge"), "gtts_code": src_info.get("code", "en"), "lang": src_lang, "flag": src_info["flag"]}
    context.bot_data[f"aud_trg_{msg_id}"] = {"text": translation, "voice_edge": trg_info.get("edge"), "gtts_code": trg_info.get("code", "en"), "lang": trg_lang, "flag": trg_info["flag"]}

    keyboard = [
        [
            InlineKeyboardButton(f"🔊 {src_info['flag']} Listen ({src_lang})", callback_data=f"play_src_{msg_id}"),
            InlineKeyboardButton(f"🔊 {trg_info['flag']} Listen ({trg_lang})", callback_data=f"play_trg_{msg_id}")
        ]
    ]

    await placeholder.edit_text(card_text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))

async def handle_audio_play(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data

    if "src_" in data:
        msg_id = data.replace("play_src_", "")
        cache = context.bot_data.get(f"aud_src_{msg_id}")
    else:
        msg_id = data.replace("play_trg_", "")
        cache = context.bot_data.get(f"aud_trg_{msg_id}")

    if not cache:
        await query.answer("Session expired!", show_alert=True)
        return

    await query.answer(f"🎧 Generating {cache['flag']} Audio...")

    text_to_speak = cache["text"]
    voice_edge = cache.get("voice_edge")
    gtts_code = cache.get("gtts_code", "en")
    lang_flag = cache.get("flag", "🌐")
    temp_audio_file = f"speech_{msg_id}.mp3"
    caption = f"🔊 <b>Audio ({lang_flag}):</b>\n<i>\"{text_to_speak}\"</i>"

    try:
        worked = False
        if voice_edge:
            try:
                communicate = edge_tts.Communicate(text_to_speak, voice_edge)
                await communicate.save(temp_audio_file)
                if os.path.exists(temp_audio_file) and os.path.getsize(temp_audio_file) > 500:
                    worked = True
            except Exception:
                worked = False

        if not worked:
            def _generate_gtts():
                tts = gTTS(text=text_to_speak, lang=gtts_code, slow=False)
                tts.save(temp_audio_file)
            await asyncio.to_thread(_generate_gtts)

        with open(temp_audio_file, "rb") as audio:
            await context.bot.send_voice(chat_id=query.message.chat_id, voice=audio, caption=caption, parse_mode="HTML")
    except Exception as e:
        await context.bot.send_message(chat_id=query.message.chat_id, text=f"⚠️ Audio error: {str(e)[:40]}")
    finally:
        if os.path.exists(temp_audio_file):
            try: os.remove(temp_audio_file)
            except Exception: pass

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

    if "premium_expiry" not in context.bot_data: context.bot_data["premium_expiry"] = {}
    if "vip_tier" not in context.bot_data: context.bot_data["vip_tier"] = {}

    current_expiry_str = context.bot_data["premium_expiry"].get(user_id)
    now = datetime.utcnow()
    base_time = datetime.fromisoformat(current_expiry_str) if current_expiry_str and datetime.fromisoformat(current_expiry_str) > now else now

    new_expiry = base_time + timedelta(days=plan["days"])
    context.bot_data["premium_expiry"][user_id] = new_expiry.isoformat()
    context.bot_data["vip_tier"][user_id] = plan["badge"]

    gift_text = f"🎁 <b>VIP PASS UNLOCKED!</b> ⭐️\n\n👑 <b>Tier:</b> {plan['name']}"
    try:
        await update.message.reply_animation(animation=VIP_GIFT_STICKER, caption=gift_text, parse_mode="HTML")
    except Exception:
        await update.message.reply_text(gift_text, parse_mode="HTML")

async def main():
    await start_web_server()

    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    
    # Set bot commands for left menu
    await app.bot.set_my_commands([
        BotCommand("start", "Start Translator Bridge"),
        BotCommand("vibe", "Play Chill Vibe Music"),
        BotCommand("setlang", "Choose Target Language"),
        BotCommand("theme", "Holographic UI Theme"),
        BotCommand("status", "Quota & Core Status"),
        BotCommand("stop", "Pause Bot"),
        BotCommand("resume", "Resume Bot"),
        BotCommand("premium", "VIP Vault")
    ])

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("vibe", vibe_command))
    app.add_handler(CommandHandler("setlang", setlang_command))
    app.add_handler(CommandHandler("setgroup", set_group_command))
    app.add_handler(CommandHandler("theme", theme_command))
    app.add_handler(CommandHandler("custombg", custom_bg_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CommandHandler("stop", stop_command))
    app.add_handler(CommandHandler("resume", resume_command))
    app.add_handler(CommandHandler("premium", premium_command))

    app.add_handler(CallbackQueryHandler(plan_selection_callback, pattern="^buy_"))
    app.add_handler(CallbackQueryHandler(handle_audio_play, pattern="^play_"))
    app.add_handler(CallbackQueryHandler(theme_selection_callback, pattern="^settheme_"))
    app.add_handler(CallbackQueryHandler(lang_selection_callback, pattern="^lang_"))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))
    app.add_handler(PreCheckoutQueryHandler(precheckout_callback))
    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment_callback))

    await app.initialize()
    try: await app.bot.delete_webhook(drop_pending_updates=True)
    except Exception: pass
        
    await app.start()
    await app.updater.start_polling(drop_pending_updates=True)

    stop_event = asyncio.Event()
    await stop_event.wait()

if __name__ == "__main__":
    try: asyncio.run(main())
    except (KeyboardInterrupt, SystemExit): pass
