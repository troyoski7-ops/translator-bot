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
import PyPDF2

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

VIBE_MUSIC_URL = "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3"

async def handle_ping(request):
    return web.Response(text="Translator Core Online & Functional!")

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
    "kazakh": {"edge": "kk-KZ-AigulNeural", "gtts": "kk", "flag": "🇰🇿", "code": "kk"},
    "uzbek": {"edge": "uz-UZ-MadinaNeural", "gtts": "uz", "flag": "🇺🇿", "code": "uz"},
    "tajik": {"edge": "ru-RU-SvetlanaNeural", "gtts": "ru", "flag": "🇹🇯", "code": "tg"},
}

def get_voice_info(lang_name):
    clean = (lang_name or "").strip().lower()
    for k, v in VOICE_MAP.items():
        if k in clean:
            return v
    return VOICE_MAP["english"]

def _translate_chunk(chunk, target):
    url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl=auto&tl={target}&dt=t&q={urllib.parse.quote(chunk)}"
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=10) as response:
        res_data = json.loads(response.read().decode('utf-8'))
        translated = "".join([item[0] for item in res_data[0] if item[0]])
        detected_code = res_data[2] if len(res_data) > 2 and res_data[2] else "unknown"
        return translated, detected_code

def _sync_translation_logic(text, chat_id=None, context_data=None):
    try:
        is_malayalam = bool(re.search(r'[\u0d00-\u0d7f]', text))
        
        if chat_id and context_data and "chat_target_lang" in context_data:
            target = context_data["chat_target_lang"].get(str(chat_id), 'ru')
        else:
            target = 'ru'
        
        if is_malayalam:
            target = chat_id and context_data and context_data.get("chat_target_lang", {}).get(str(chat_id), 'ru') or 'ru'
        else:
            target = 'ml'

        max_chunk = 1500
        chunks = [text[i:i+max_chunk] for i in range(0, len(text), max_chunk)]
        
        translated_full = ""
        detected_code = "unknown"
        for chunk in chunks:
            t_part, d_code = _translate_chunk(chunk, target)
            translated_full += t_part + " "
            if detected_code == "unknown":
                detected_code = d_code

        translated = translated_full.strip()

        if target == 'ml':
            translated = re.sub(r'\s+([അ-ഹ])', r'\1', translated)

        phonetic_text = text[:300]
        try:
            url_phonetic = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl=auto&tl=en&dt=rm&q={urllib.parse.quote(text[:300])}"
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
            'ar': 'Arabic', 'hi': 'Hindi', 'it': 'Italian', 'tr': 'Turkish', 'ka': 'Georgian',
            'az': 'Azerbaijani', 'kk': 'Kazakh', 'uz': 'Uzbek', 'tg': 'Tajik'
        }
        
        src_lang_name = lang_names.get(detected_code, detected_code.upper() if detected_code != "unknown" else detected_code.capitalize())
        target_lang_name = lang_names.get(target, target.upper())

        import random
        detected_mood = random.choice(["✨ Cosmic & Positive", "💫 Deep & Philosophical", "🔥 High Energy Vibe", "💎 Pure Elite Class"])

        return {
            "src": src_lang_name,
            "trg": target_lang_name,
            "trans": translated,
            "meaning": translated,
            "native_p": text[:300],
            "latin_p": phonetic_text if phonetic_text != text[:300] else text[:300],
            "cultural_insight": f"Expression used in {src_lang_name} | Aura: {detected_mood}",
            "native_text": text,
            "target_code": target
        }
    except Exception as e:
        return {"error": f"Error: {str(e)[:40]}"}

async def execute_translation(text, chat_id=None, context_data=None):
    return await asyncio.to_thread(_sync_translation_logic, text, chat_id, context_data)

MAX_FREE_USERS = 500

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
    if "registered_users" not in context.bot_data: context.bot_data["registered_users"] = []

    exp = context.bot_data["premium_expiry"].get(str_user_id)
    if exp and datetime.utcnow() < datetime.fromisoformat(exp):
        days = (datetime.fromisoformat(exp) - datetime.utcnow()).days
        badge = context.bot_data.get("vip_tier", {}).get(str_user_id, "👑 VIP")
        return True, f"{badge} ({days}d left)", True

    reg_list = context.bot_data["registered_users"]
    if str_user_id not in reg_list:
        reg_list.append(str_user_id)

    user_index = reg_list.index(str_user_id)
    if user_index < MAX_FREE_USERS:
        return True, "♾️ FREE PASS", False
    else:
        return (False, "Free Access Closed. Get VIP!", False)

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

async def settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🇷🇺 Russian (RU)", callback_data="set_target_ru"), InlineKeyboardButton("🇩🇪 German (DE)", callback_data="set_target_de")],
        [InlineKeyboardButton("🇹🇷 Turkish (TR)", callback_data="set_target_tr"), InlineKeyboardButton("🇰🇿 Kazakh (KK)", callback_data="set_target_kk")],
        [InlineKeyboardButton("🇺🇿 Uzbek (UZ)", callback_data="set_target_uz"), InlineKeyboardButton("🇬🇧 English (EN)", callback_data="set_target_en")],
    ]
    await update.message.reply_text(
        "⚙️ <b>Two-Way Translation Settings:</b>\nChoose the partner language for automatic translation in this chat/group:",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def settings_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    lang_code = query.data.replace("set_target_", "")
    chat_id = str(query.message.chat_id)

    if "chat_target_lang" not in context.bot_data:
        context.bot_data["chat_target_lang"] = {}
    
    context.bot_data["chat_target_lang"][chat_id] = lang_code
    await query.edit_message_text(f"✅ Partner language successfully set to: <b>{lang_code.upper()}</b> for this chat!", parse_mode="HTML")

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

async def send_store_menu(chat_id, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "⚡ <b>HOLOGRAPHIC VIP VAULT</b> ⚡\n\n"
        "The first 500 free user slots have been filled! Upgrade to VIP for full access.\n\n"
        "• Unlimited Translations\n"
        "• High-Definition Dual Audio Pronunciations\n"
        "• Exclusive VIP Themes & /customtheme\n"
        "• Custom Vibe Song Lounge /customsong\n\n"
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
        f"🌌 <b>QUANTUM TWO-WAY TRANSLATION BRIDGE</b> 🌌\n"
        f"{vip_badge}\n"
        "✨ <b>HOW THIS BOT WORKS:</b>\n\n"
        "💬 <b>1. Personal & Group Chat (Automatic Two-Way):</b>\n"
        "• You type in Malayalam ➔ Partner gets Russian/Target language automatically.\n"
        "• Partner types in Target language ➔ You get Malayalam automatically.\n"
        "• Use <b>/settings</b> to change partner language anytime!\n\n"
        "<b>Commands:</b>\n"
        "⚙️ /settings • Two-Way Language Settings\n"
        "🎧 /vibe • Play Chill Vibe Music\n"
        "📊 /status • Quota & Core Status\n"
        "⏸ /stop • Pause | ▶️ /resume • Resume\n"
        "⭐️ /premium • VIP Vault\n\n"
        "<b>Send any text or PDF document to begin!</b>"
    )
    try:
        await update.message.reply_animation(animation=ANIM_WELCOME_URL, caption=welcome, parse_mode="HTML")
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

    user_str = str(user_id)
    stream_url = context.bot_data.get("user_custom_song", {}).get(user_str, VIBE_MUSIC_URL)

    try:
        await update.message.reply_audio(
            audio=stream_url, 
            caption="🎧 <b>Vibe Lounge:</b> Relax and enjoy your stream!", 
            parse_mode="HTML"
        )
    except Exception as e:
        await update.message.reply_text(f"⚠️ Vibe error: {str(e)[:40]}")

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    _, status_val, _ = is_user_active(context, user_id, chat_id)
    await update.message.reply_text(f"📊 <b>Your Quota Status:</b> {status_val}", parse_mode="HTML")

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
    
    text_content = update.message.text.strip()
    chat_id = update.effective_chat.id
    await process_and_reply(update, context, text_content, chat_id)

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
        
        chat_id = update.effective_chat.id
        await process_and_reply(update, context, trans_text, chat_id)
    except Exception as e:
        await placeholder.edit_text(f"⚠️ Voice error: {str(e)[:40]}")
    finally:
        for p in [ogg_path, mp3_path]:
            if os.path.exists(p):
                try: os.remove(p)
                except Exception: pass

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.chat_data.get("paused", False): return
    await update.message.reply_text("⚠️ Photo translation is disabled. Please send text directly or upload a PDF document!", parse_mode="HTML")

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.chat_data.get("paused", False): return
    doc = update.message.document
    if not doc.file_name.lower().endswith(('.pdf', '.txt', '.docx')):
        await update.message.reply_text("⚠️ Please send a valid PDF, TXT or DOCX document!")
        return

    chat_id = update.effective_chat.id
    placeholder = await context.bot.send_message(chat_id=chat_id, text="⚡ <i>Reading document & translating large passage...</i>", parse_mode="HTML")
    extracted_text = ""

    try:
        file = await context.bot.get_file(doc.file_id)
        doc_path = f"doc_{chat_id}_{int(time.time())}.file"
        await file.download_to_drive(doc_path)
        with open(doc_path, 'rb') as f:
            reader = PyPDF2.PdfReader(f)
            for page in reader.pages:
                txt = page.extract_text()
                if txt: extracted_text += txt + "\n"
        if os.path.exists(doc_path): os.remove(doc_path)

        extracted_text = extracted_text.strip()
        if not extracted_text:
            extracted_text = "Document contents successfully extracted."

        extracted_text = extracted_text[:10000]
        await placeholder.delete()

        user = update.effective_user
        res = await execute_translation(extracted_text, chat_id, context.bot_data)
        
        translation = res.get("trans", extracted_text)
        src_lang = res.get("src", "English")
        trg_lang = res.get("trg", "Target Language")
        
        if len(translation) > 3500:
            chunks = [translation[i:i+3500] for i in range(0, len(translation), 3500)]
            for idx, chunk in enumerate(chunks):
                card_text = (
                    f"👤 <b>{user.first_name or 'Operator'}</b> (Part {idx+1})\n"
                    f"────────────────────────\n"
                    f"🌐 <code>{src_lang.upper()}</code> ➔ 🌐 <code>{trg_lang.upper()}</code>\n"
                    f"────────────────────────\n\n"
                    f"💬 <b>{chunk}</b>"
                )
                await context.bot.send_message(chat_id=chat_id, text=card_text, parse_mode="HTML")
        else:
            card_text = (
                f"👤 <b>{user.first_name or 'Operator'}</b>\n"
                f"────────────────────────\n"
                f"🌐 <code>{src_lang.upper()}</code> ➔ 🌐 <code>{trg_lang.upper()}</code>\n"
                f"────────────────────────\n\n"
                f"💬 <b>{translation}</b>"
            )
            await context.bot.send_message(chat_id=chat_id, text=card_text, parse_mode="HTML")

    except Exception as e:
        await placeholder.edit_text(f"⚠️ Error processing file: {str(e)[:40]}")

async def process_and_reply(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str, chat_id: int):
    user = update.effective_user
    user_id = user.id
    user_name = user.first_name or "Operator"

    active, status_val, is_vip = is_user_active(context, user_id, chat_id)
    if not active:
        await send_store_menu(chat_id, context)
        return

    placeholder = await update.message.reply_text("⚡ <i>Translating...</i>", parse_mode="HTML")
    res = await execute_translation(text, chat_id, context.bot_data)

    if "error" in res:
        await placeholder.edit_text(f"⚠️ <b>Error:</b> {res['error']}", parse_mode="HTML")
        return

    src_lang = res.get("src", "English")
    trg_lang = res.get("trg", "Target")
    translation = res.get("trans", text)
    native_p = res.get("native_p", text)
    latin_p = res.get("latin_p", "")
    cultural_insight = res.get("cultural_insight", "A unique linguistic expression.")

    src_info = get_voice_info(src_lang)
    trg_info = get_voice_info(trg_lang)

    native_p_block = f"🗣 <i>Phonetic ({src_info['flag']} {src_lang}):</i> <code>{native_p[:200]}</code>\n" if native_p else ""
    latin_p_block = f"🔤 <i>English Phonetics:</i> <tg-spoiler><b>{latin_p[:200]}</b></tg-spoiler>\n" if latin_p else ""
    meaning_en_block = f"📖 <b>Meaning ({trg_lang.upper()}): {translation[:1500]}</b>\n" if translation else ""
    cultural_block = f"💡 <i>Insight:</i> <b>{cultural_insight}</b>\n" if cultural_insight else ""

    card_text = (
        f"👤 <b>{user_name}</b>\n"
        f"────────────────────────\n"
        f"{src_info['flag']} <code>{src_lang.upper()}</code> ➔ {trg_info['flag']} <code>{trg_lang.upper()}</code>\n"
        f"────────────────────────\n\n"
        f"💬 <b>{translation[:1500]}</b>\n\n"
        f"{native_p_block}"
        f"{latin_p_block}"
        f"{meaning_en_block}"
        f"{cultural_block}\n"
        f"────────────────────────\n"
        f"🔋 Quota: {status_val}"
    )

    msg_id = placeholder.message_id
    context.bot_data[f"aud_src_{msg_id}"] = {"text": text[:500], "voice_edge": src_info.get("edge"), "gtts_code": src_info.get("code", "en"), "lang": src_lang, "flag": src_info["flag"]}
    context.bot_data[f"aud_trg_{msg_id}"] = {"text": translation[:500], "voice_edge": trg_info.get("edge"), "gtts_code": trg_info.get("code", "en"), "lang": trg_lang, "flag": trg_info["flag"]}

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
    caption = f"🔊 <b>Audio ({lang_flag}):</b>\n<i>\"{text_to_speak[:100]}\"</i>"

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
    
    await app.bot.set_my_commands([
        BotCommand("start", "Start Translator Bridge"),
        BotCommand("settings", "Configure Two-Way Partner Language"),
        BotCommand("vibe", "Play Chill Vibe Music"),
        BotCommand("status", "Quota & Core Status"),
        BotCommand("stop", "Pause Bot"),
        BotCommand("resume", "Resume Bot"),
        BotCommand("premium", "VIP Vault")
    ])

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("settings", settings_command))
    app.add_handler(CommandHandler("vibe", vibe_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CommandHandler("stop", stop_command))
    app.add_handler(CommandHandler("resume", resume_command))
    app.add_handler(CommandHandler("premium", premium_command))

    app.add_handler(CallbackQueryHandler(settings_callback, pattern="^set_target_"))
    app.add_handler(CallbackQueryHandler(theme_selection_callback, pattern="^settheme_"))
    app.add_handler(CallbackQueryHandler(plan_selection_callback, pattern="^buy_"))
    app.add_handler(CallbackQueryHandler(handle_audio_play, pattern="^play_"))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
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
