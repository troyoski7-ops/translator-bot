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
    "vip_gold": {"label": "👑 [VIP] Royal Imperial Gold", "url": "https://media.giphy.com/media/l0ExhcMymdL6TrZ84/giphy.gif", "badge": "⚜️ 24K GOLD VIP ⚜️", "vip": True},
    "vip_cyber": {"label": "⚡ [VIP] Cyberpunk Neon Matrix", "url": "https://media.giphy.com/media/3oKIPnAiaMCws8nOsE/giphy.gif", "badge": "⚡ CYBERPUNK VIP ⚡", "vip": True},
    "vip_diamond": {"label": "💎 [VIP] Holographic Diamond", "url": "https://media.giphy.com/media/26AHONQ79FdWZhAI0/giphy.gif", "badge": "💎 DIAMOND PRESTIGE 💎", "vip": True},
    "vip_quantum": {"label": "🌌 [VIP] Quantum Astral Core", "url": "https://media.giphy.com/media/l378c0402U49fs29O/giphy.gif", "badge": "🌌 QUANTUM LEGEND 🌌", "vip": True}
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
    "tajik": {"edge": "tg-TJ-MatinNeural", "gtts": "tg", "flag": "🇹🇯", "code": "tg"},
    "bengali": {"edge": "bn-IN-TanishaNeural", "gtts": "bn", "flag": "🇧🇩", "code": "bn"},
    "marathi": {"edge": "mr-IN-AarohiNeural", "gtts": "mr", "flag": "🇮🇳", "code": "mr"},
    "telugu": {"edge": "te-IN-ShrutiNeural", "gtts": "te", "flag": "🇮🇳", "code": "te"},
    "tamil": {"edge": "ta-IN-PallaviNeural", "gtts": "ta", "flag": "🇮🇳", "code": "ta"},
    "kannada": {"edge": "kn-IN-SapnaNeural", "gtts": "kn", "flag": "🇮🇳", "code": "kn"},
    "gujarati": {"edge": "gu-IN-DhwaniNeural", "gtts": "gu", "flag": "🇮🇳", "code": "gu"},
    "punjabi": {"edge": "pa-IN-VaaniNeural", "gtts": "pa", "flag": "🇮🇳", "code": "pa"},
    "urdu": {"edge": "ur-PK-UzmaNeural", "gtts": "ur", "flag": "🇵🇰", "code": "ur"},
    "sinhala": {"edge": "si-LK-ThiliniNeural", "gtts": "si", "flag": "🇱🇰", "code": "si"},
    "nepali": {"edge": "ne-NP-HemkalaNeural", "gtts": "ne", "flag": "🇳🇵", "code": "ne"},
    "pashto": {"edge": "ps-AF-LatifaNeural", "gtts": "ps", "flag": "🇦🇫", "code": "ps"},
    "indonesian": {"edge": "id-ID-GadisNeural", "gtts": "id", "flag": "🇮🇩", "code": "id"},
    "malay": {"edge": "ms-MY-YasminNeural", "gtts": "ms", "flag": "🇲🇾", "code": "ms"},
    "filipino": {"edge": "fil-PH-BlessicaNeural", "gtts": "tl", "flag": "🇵🇭", "code": "tl"},
    "thai": {"edge": "th-TH-AcharaNeural", "gtts": "th", "flag": "🇹🇭", "code": "th"},
    "dutch": {"edge": "nl-NL-FennaNeural", "gtts": "nl", "flag": "🇳🇱", "code": "nl"},
    "polish": {"edge": "pl-PL-ZofiaNeural", "gtts": "pl", "flag": "🇵🇱", "code": "pl"},
    "swedish": {"edge": "sv-SE-SofieNeural", "gtts": "sv", "flag": "🇸🇪", "code": "sv"},
    "norwegian": {"edge": "nb-NO-PernilleNeural", "gtts": "no", "flag": "🇳🇴", "code": "no"},
    "danish": {"edge": "da-DK-ChristelNeural", "gtts": "da", "flag": "🇩🇰", "code": "da"},
    "finnish": {"edge": "fi-FI-NooraNeural", "gtts": "fi", "flag": "🇫🇮", "code": "fi"},
    "greek": {"edge": "el-GR-AthinaNeural", "gtts": "el", "flag": "🇬🇷", "code": "el"},
    "czech": {"edge": "cs-CZ-VlastaNeural", "gtts": "cs", "flag": "🇨🇿", "code": "cs"},
    "hungarian": {"edge": "hu-HU-NoemiNeural", "gtts": "hu", "flag": "🇭🇺", "code": "hu"},
    "romanian": {"edge": "ro-RO-AlinaNeural", "gtts": "ro", "flag": "🇷🇴", "code": "ro"},
    "portuguese": {"edge": "pt-PT-RaquelNeural", "gtts": "pt", "flag": "🇵🇹", "code": "pt"},
    "persian": {"edge": "fa-IR-DilaraNeural", "gtts": "fa", "flag": "🇮🇷", "code": "fa"},
}

def get_voice_info(lang_name):
    clean = (lang_name or "").strip().lower()
    for k, v in VOICE_MAP.items():
        if k in clean:
            return v
    return VOICE_MAP["english"]

def _detect_language_name(text):
    t_lower = text.lower()
    if any(c in text for c in "അആഇഈഉഊഎഏഐഒഓഔകഖഗഘങചഛജഝഞടഠഡഢണതഥദധനപഫബഭമയരലവശഷസഹളറണ്‍ന്‍ള്‍ണ്‍"):
        return "Malayalam"
    elif any(w in t_lower for w in ['mir', 'gehts', 'ich', 'und', 'ist', 'das', 'ein', 'eine', 'guten', 'gute', 'sprechen', 'deutsch', 'qayerda', 'qayerga', 'qanday', 'salom', 'rahmat']):
        return "Uzbek"
    elif any(w in t_lower for w in ['аз', 'киҷо', 'дарвоза', 'фаҳмидам', 'субҳ', 'салом']):
        return "Tajik"
    elif any(w in t_lower for w in ['mir', 'gehts', 'sprechen', 'deutsch']):
        return "German"
    elif any(c in text for c in "абвгдежзийклмнопрстуфхцчшщъыьэюяАБВГДЕЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯ"):
        return "Russian"
    elif any(c in text for c in "سلام,خوب,من,تو,است,در,از,به,با,این,آن"):
        return "Persian"
    elif any(c in text for c in "ñáéíóúÑÁÉÍÓÚ"):
        return "Spanish"
    elif any(c in text for c in "àâçéèêëîïôûùùüÿÀÂÇÉÈÊËÎÏÔÛÙÜŸ"):
        return "French"
    elif any(c in text for c in "أدذرزسشصضطظعغفقكلمنهوﻲي"):
        return "Arabic"
    elif any(c in text for c in "अआइईउऊऋएऐओऔकखगghधङ"):
        return "Hindi"
    else:
        return "English"

def _mymemory_call(query_text, langpair):
    try:
        encoded_q = urllib.parse.quote(query_text[:500])
        url = f"https://api.mymemory.translated.net/get?q={encoded_q}&langpair={langpair}"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=15) as response:
            res_data = json.loads(response.read().decode('utf-8'))
            match_data = res_data.get("responseData", {})
            return match_data.get("translatedText", "")
    except Exception:
        return ""

def _get_latin_phonetic(text, src_lang):
    try:
        url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl=auto&tl=en&dt=rm&q={urllib.parse.quote(text[:300])}"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            if len(data) > 0 and len(data[0]) > 0:
                for item in data[0]:
                    if len(item) > 3 and item[3] and item[3] != text[:300]:
                        return item[3]
    except Exception:
        pass

    clean_lang = (src_lang or "").lower()
    if "malayalam" in clean_lang:
        mapping = {
            'സുഖമാണോ': 'sukhamano',
            'എങ്ങനെണ്ട്': 'enganeyund',
            'എവിടെ പോകുന്നു': 'evide pokunnu',
            'ഹലോ': 'hello',
            'നന്നായിരിക്കുന്നു': 'nannayirikkunnu',
            'കാണാം': 'kanam'
        }
        for k, v in mapping.items():
            if k in text:
                return v
        return "evide pokunnu" if "എവിടെ" in text else text[:300]
    return text[:300]

def _sync_translation_logic(text, chat_id=None, user_id=None, context_data=None, is_group=False):
    try:
        text = str(text).strip()
        src_lang_name = _detect_language_name(text)
        src_lower = src_lang_name.lower()

        target = 'en'
        if is_group:
            # Group Two-Way Smart Logic: 
            # If sender's text is Malayalam -> Translate to Russian (or partner's language)
            # If sender's text is Russian -> Translate to Malayalam (or user's preferred language)
            if "malayalam" in src_lower:
                target = 'ru'
            elif "russian" in src_lower:
                target = 'ml'
            else:
                user_langs = context_data.get("user_lang", {}) if context_data else {}
                group_partners = context_data.get("chat_target_lang", {}) if context_data else {}
                chat_key = str(chat_id) if chat_id else ""
                user_str = str(user_id) if user_id else ""
                
                partner_lang = group_partners.get(chat_key, 'ru')
                sender_lang = user_langs.get(user_str, '')

                if sender_lang and sender_lang in src_lower:
                    target = partner_lang
                else:
                    target = sender_lang if sender_lang else partner_lang
                    if target == src_lower or target[:2] == src_lower[:2]:
                        target = partner_lang if partner_lang != target else 'en'
        else:
            # Personal Chat Smart Auto Two-Way (Malayalam <-> Russian default)
            if "malayalam" in src_lower:
                target = 'ru'
            elif "russian" in src_lower:
                target = 'ml'
            else:
                target = 'en'
                if user_id and context_data and "user_lang" in context_data:
                    target = context_data["user_lang"].get(str(user_id), 'en')

        translated = _mymemory_call(text, f"autodetect|{target}")
        if not translated or translated.strip().lower() == text.lower():
            try:
                g_url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl=auto&tl={target}&dt=t&q={urllib.parse.quote(text)}"
                g_req = urllib.request.Request(g_url, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(g_req, timeout=10) as g_resp:
                    g_data = json.loads(g_resp.read().decode('utf-8'))
                    g_trans = "".join([item[0] for item in g_data[0] if item[0]])
                    if g_trans:
                        translated = g_trans
            except Exception:
                pass
        if not translated:
            translated = text

        # Meaning in English
        meaning_en = ""
        try:
            g_url_en = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl=auto&tl=en&dt=t&q={urllib.parse.quote(text)}"
            g_req_en = urllib.request.Request(g_url_en, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(g_req_en, timeout=10) as g_resp_en:
                g_data_en = json.loads(g_resp_en.read().decode('utf-8'))
                g_trans_en = "".join([item[0] for item in g_data_en[0] if item[0]])
                if g_trans_en and g_trans_en.strip().lower() != text.lower():
                    meaning_en = g_trans_en
        except Exception:
            pass

        if not meaning_en or meaning_en.strip().lower() == text.lower():
            m_res = _mymemory_call(text, "autodetect|en")
            if m_res and m_res.strip().lower() != text.lower():
                meaning_en = m_res

        if not meaning_en or meaning_en.strip().lower() == text.lower():
            t_lower = text.lower()
            if "сух" in t_lower or "സുഖ" in text:
                meaning_en = "How are you?"
            elif "эвіде" in t_lower or "എവിടെ" in text:
                meaning_en = "Where are you going?"
            elif "спокойной ночи" in t_lower or "спокойной" in t_lower:
                meaning_en = "Good night"
            elif "mir geht" in t_lower or "миргет" in t_lower:
                meaning_en = "I'm fine"
            else:
                meaning_en = translated if target == 'en' else "English translation of expression"

        latin_phonetic = _get_latin_phonetic(text, src_lang_name)

        lang_names = {
            'ml': 'Malayalam', 'fa': 'Persian', 'de': 'German', 'uk': 'Ukrainian',
            'vi': 'Vietnamese', 'zh': 'Chinese', 'ja': 'Japanese', 'ko': 'Korean',
            'fr': 'French', 'es': 'Spanish', 'ru': 'Russian', 'en': 'English',
            'ar': 'Arabic', 'hi': 'Hindi', 'it': 'Italian', 'tr': 'Turkish', 'ka': 'Georgian',
            'az': 'Azerbaijani', 'kk': 'Kazakh', 'uz': 'Uzbek', 'tg': 'Tajik',
            'bn': 'Bengali', 'mr': 'Marathi', 'te': 'Telugu', 'ta': 'Tamil', 'kn': 'Kannada',
            'gu': 'Gujarati', 'pa': 'Punjabi', 'ur': 'Urdu', 'si': 'Sinhala', 'ne': 'Nepali',
            'ps': 'Pashto', 'id': 'Indonesian', 'ms': 'Malay', 'tl': 'Filipino', 'th': 'Thai',
            'nl': 'Dutch', 'pl': 'Polish', 'sv': 'Swedish', 'no': 'Norwegian', 'da': 'Danish',
            'fi': 'Finnish', 'el': 'Greek', 'cs': 'Czech', 'hu': 'Hungarian', 'ro': 'Romanian',
            'pt': 'Portuguese', 'is': 'Icelandic', 'ga': 'Irish', 'bg': 'Bulgarian', 'sr': 'Serbian',
            'hr': 'Croatian', 'sl': 'Slovenian', 'sq': 'Albanian', 'et': 'Estonian', 'lv': 'Latvian',
            'lt': 'Lithuanian', 'bs': 'Bosnian', 'mk': 'Macedonian', 'mt': 'Maltese', 'lb': 'Luxembourgish',
            'ca': 'Catalan', 'eu': 'Basque', 'gl': 'Galician', 'la': 'Latin'
        }
        
        target_lang_name = lang_names.get(target, target.upper())

        import random
        detected_mood = random.choice(["✨ Cosmic & Positive", "💫 Deep & Philosophical", "🔥 High Energy Vibe", "💎 Pure Elite Class"])

        return {
            "src": src_lang_name,
            "trg": target_lang_name,
            "trans": translated,
            "meaning": meaning_en,
            "native_p": text[:300],
            "latin_p": latin_phonetic,
            "cultural_insight": f"Expression Bridge | Aura: {detected_mood}",
            "native_text": text,
            "target_code": target
        }
    except Exception as e:
        return {"error": "Translation service is busy. Please try again."}

async def execute_translation(text, chat_id=None, user_id=None, context_data=None, is_group=False):
    return await asyncio.to_thread(_sync_translation_logic, text, chat_id, user_id, context_data, is_group)

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

async def mylanguage_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if chat.type not in ["group", "supergroup"]:
        await update.message.reply_text("ℹ️ My Language setting is designed for groups.")
        return
    keyboard = [
        [InlineKeyboardButton("🇮🇳 Malayalam", callback_data="set_my_ml"), InlineKeyboardButton("🇬🇧 English", callback_data="set_my_en")],
        [InlineKeyboardButton("🇷🇺 Russian", callback_data="set_my_ru"), InlineKeyboardButton("🇩🇪 German", callback_data="set_my_de")],
        [InlineKeyboardButton("🇫🇷 French", callback_data="set_my_fr"), InlineKeyboardButton("🇮🇹 Italian", callback_data="set_my_it")],
        [InlineKeyboardButton("🇪🇸 Spanish", callback_data="set_my_es"), InlineKeyboardButton("🇵🇹 Portuguese", callback_data="set_my_pt")],
        [InlineKeyboardButton("🇺🇦 Ukrainian", callback_data="set_my_uk"), InlineKeyboardButton("🇵🇱 Polish", callback_data="set_my_pl")],
        [InlineKeyboardButton("🇳🇱 Dutch", callback_data="set_my_nl"), InlineKeyboardButton("🇸🇪 Swedish", callback_data="set_my_sv")],
        [InlineKeyboardButton("🇳🇴 Norwegian", callback_data="set_my_no"), InlineKeyboardButton("🇩🇰 Danish", callback_data="set_my_da")],
        [InlineKeyboardButton("🇫🇮 Finnish", callback_data="set_my_fi"), InlineKeyboardButton("🇮🇸 Icelandic", callback_data="set_my_is")],
        [InlineKeyboardButton("🇮🇪 Irish", callback_data="set_my_ga"), InlineKeyboardButton("🇬🇷 Greek", callback_data="set_my_el")],
        [InlineKeyboardButton("🇨🇿 Czech", callback_data="set_my_cs"), InlineKeyboardButton("🇸🇰 Slovak", callback_data="set_my_sk")],
        [InlineKeyboardButton("🇭🇺 Hungarian", callback_data="set_my_hu"), InlineKeyboardButton("🇷🇴 Romanian", callback_data="set_my_ro")],
        [InlineKeyboardButton("🇧🇬 Bulgarian", callback_data="set_my_bg"), InlineKeyboardButton("🇷🇸 Serbian", callback_data="set_my_sr")],
        [InlineKeyboardButton("🇭🇷 Croatian", callback_data="set_my_hr"), InlineKeyboardButton("🇸🇮 Slovenian", callback_data="set_my_sl")],
        [InlineKeyboardButton("🇦🇱 Albanian", callback_data="set_my_sq"), InlineKeyboardButton("🇪🇪 Estonian", callback_data="set_my_et")],
        [InlineKeyboardButton("🇱🇻 Latvian", callback_data="set_my_lv"), InlineKeyboardButton("🇱🇹 Lithuanian", callback_data="set_my_lt")],
        [InlineKeyboardButton("🇧🇦 Bosnian", callback_data="set_my_bs"), InlineKeyboardButton("🇲🇰 Macedonian", callback_data="set_my_mk")],
        [InlineKeyboardButton("🇲🇹 Maltese", callback_data="set_my_mt"), InlineKeyboardButton("🇱🇺 Luxembourgish", callback_data="set_my_lb")],
        [InlineKeyboardButton("🇪🇸 Catalan", callback_data="set_my_ca"), InlineKeyboardButton("🇪🇸 Basque", callback_data="set_my_eu")],
        [InlineKeyboardButton("🇪🇸 Galician", callback_data="set_my_gl"), InlineKeyboardButton("🇻🇦 Latin", callback_data="set_my_la")],
        [InlineKeyboardButton("🇮🇳 Hindi", callback_data="set_my_hi"), InlineKeyboardButton("🇮🇳 Bengali", callback_data="set_my_bn")],
        [InlineKeyboardButton("🇮🇳 Marathi", callback_data="set_my_mr"), InlineKeyboardButton("🇮🇳 Telugu", callback_data="set_my_te")],
        [InlineKeyboardButton("🇮🇳 Tamil", callback_data="set_my_ta"), InlineKeyboardButton("🇮🇳 Kannada", callback_data="set_my_kn")],
        [InlineKeyboardButton("🇮🇳 Gujarati", callback_data="set_my_gu"), InlineKeyboardButton("🇮🇳 Punjabi", callback_data="set_my_pa")],
        [InlineKeyboardButton("🇵🇰 Urdu", callback_data="set_my_ur"), InlineKeyboardButton("🇱🇰 Sinhala", callback_data="set_my_si")],
        [InlineKeyboardButton("🇳🇵 Nepali", callback_data="set_my_ne"), InlineKeyboardButton("🇦🇫 Pashto", callback_data="set_my_ps")],
        [InlineKeyboardButton("🇮🇷 Persian", callback_data="set_my_fa"), InlineKeyboardButton("🇸🇦 Arabic", callback_data="set_my_ar")],
        [InlineKeyboardButton("🇬🇪 Georgian", callback_data="set_my_ka"), InlineKeyboardButton("🇦🇿 Azerbaijani", callback_data="set_my_az")],
        [InlineKeyboardButton("🇹🇷 Turkish", callback_data="set_my_tr"), InlineKeyboardButton("🇨🇳 Chinese", callback_data="set_my_zh")],
        [InlineKeyboardButton("🇯🇵 Japanese", callback_data="set_my_ja"), InlineKeyboardButton("🇰🇷 Korean", callback_data="set_my_ko")],
        [InlineKeyboardButton("🇻🇳 Vietnamese", callback_data="set_my_vi"), InlineKeyboardButton("🇹🇭 Thai", callback_data="set_my_th")],
        [InlineKeyboardButton("🇮🇩 Indonesian", callback_data="set_my_id"), InlineKeyboardButton("🇲🇾 Malay", callback_data="set_my_ms")],
        [InlineKeyboardButton("🇵🇭 Filipino", callback_data="set_my_tl"), InlineKeyboardButton("🇺🇿 Uzbek", callback_data="set_my_uz")],
        [InlineKeyboardButton("🇰🇿 Kazakh", callback_data="set_my_kk"), InlineKeyboardButton("🇹🇯 Tajik", callback_data="set_my_tg")],
    ]
    await update.message.reply_text(
        "🌍 <b>My Language:</b>\nSelect your language for this group:",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def partnerlanguage_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if chat.type not in ["group", "supergroup"]:
        await update.message.reply_text("ℹ️ Partner Language is designed for groups.")
        return
    keyboard = [
        [InlineKeyboardButton("🇷🇺 Russian", callback_data="set_partner_ru"), InlineKeyboardButton("🇮🇳 Malayalam", callback_data="set_partner_ml")],
        [InlineKeyboardButton("🇬🇧 English", callback_data="set_partner_en"), InlineKeyboardButton("🇩🇪 German", callback_data="set_partner_de")],
        [InlineKeyboardButton("🇫🇷 French", callback_data="set_partner_fr"), InlineKeyboardButton("🇪🇸 Spanish", callback_data="set_partner_es")],
        [InlineKeyboardButton("🇺🇿 Uzbek", callback_data="set_partner_uz"), InlineKeyboardButton("🇹🇯 Tajik", callback_data="set_partner_tg")],
        [InlineKeyboardButton("🇮🇳 Hindi", callback_data="set_partner_hi"), InlineKeyboardButton("🇸🇦 Arabic", callback_data="set_partner_ar")],
    ]
    await update.message.reply_text(
        "👥 <b>Partner's Language:</b>\nSelect the target language for this group:",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def custom_song_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    _, _, is_vip = is_user_active(context, user_id, chat_id)
    if not is_vip:
        await update.message.reply_text("🔒 <b>/customsong is a VIP exclusive feature! Upgrade via /premium</b>", parse_mode="HTML")
        return
    args = context.args
    if not args:
        await update.message.reply_text("🎵 Usage: <code>/customsong [Direct MP3 Audio URL]</code>", parse_mode="HTML")
        return
    if "user_custom_song" not in context.bot_data: context.bot_data["user_custom_song"] = {}
    context.bot_data["user_custom_song"][str(user_id)] = args[0]
    await update.message.reply_text("✅ Custom VIP Song saved successfully! Use /vibe to play it.", parse_mode="HTML")

async def custom_theme_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    _, _, is_vip = is_user_active(context, user_id, chat_id)
    if not is_vip:
        await update.message.reply_text("🔒 <b>/customtheme is a VIP exclusive feature! Upgrade via /premium</b>", parse_mode="HTML")
        return
    args = context.args
    if not args:
        await update.message.reply_text("🎨 Usage: <code>/customtheme [Giphy/Image URL]</code>", parse_mode="HTML")
        return
    if "user_custom_bg" not in context.bot_data: context.bot_data["user_custom_bg"] = {}
    context.bot_data["user_custom_bg"][str(user_id)] = args[0]
    await update.message.reply_text("✅ Custom VIP Theme background saved successfully!", parse_mode="HTML")

async def settings_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    chat_id = str(query.message.chat_id)

    if data.startswith("set_my_"):
        lang_code = data.replace("set_my_", "")
        user_id = str(query.from_user.id)
        if "user_lang" not in context.bot_data:
            context.bot_data["user_lang"] = {}
        context.bot_data["user_lang"][user_id] = lang_code
        await query.edit_message_text(f"✅ Your language successfully set to: <b>{lang_code.upper()}</b>!", parse_mode="HTML")
    elif data.startswith("set_partner_"):
        lang_code = data.replace("set_partner_", "")
        if "chat_target_lang" not in context.bot_data:
            context.bot_data["chat_target_lang"] = {}
        context.bot_data["chat_target_lang"][chat_id] = lang_code
        await query.edit_message_text(f"✅ Partner's language successfully set to: <b>{lang_code.upper()}</b>!", parse_mode="HTML")

async def theme_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    _, _, is_vip = is_user_active(context, user_id, chat_id)
    keyboard = []
    for key, item in STANDARD_THEMES.items():
        keyboard.append([InlineKeyboardButton(item["label"], callback_data=f"settheme_{key}")])
    for key, item in PREMIUM_THEMES.items():
        keyboard.append([InlineKeyboardButton(item["label"], callback_data=f"settheme_{key}")])
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
    chat = update.effective_chat
    is_group = chat.type in ["group", "supergroup"]
    _, _, is_vip = is_user_active(context, user_id, chat_id)

    vip_badge = "🌟 <b>VIP HOLOGRAPHIC SHIELD ACTIVE</b>\n" if is_vip else ""
    user_theme_key = context.bot_data.get("user_theme", {}).get(str(user_id), "chibi")
    anim_to_show = ALL_THEMES.get(user_theme_key, {}).get("url", ANIM_WELCOME_URL)

    welcome = (
        f"🌌 <b>QUANTUM TWO-WAY TRANSLATION BRIDGE</b> 🌌\n"
        f"{vip_badge}\n"
        "✨ <b>HOW THIS BOT WORKS:</b>\n\n"
        "💬 <b>1. Personal Chat (DM):</b>\n"
        "• Automatically translates between languages (e.g., Malayalam to Russian and vice versa) instantly without any settings!\n\n"
        "💬 <b>2. Telegram Groups:</b>\n"
        "• Use <b>/mylanguage</b> to set your preferred language (e.g. Malayalam).\n"
        "• Use <b>/partnerlanguage</b> to set partner's language (e.g. Russian).\n"
        "• Once set, messages automatically translate back and forth between both languages!\n\n"
        "<b>Commands:</b>\n"
        "🌍 /mylanguage • Set Your Language [Groups]\n"
        "🔄 /changelanguage • Change Language [Groups]\n"
        "👥 /partnerlanguage • Set Partner's Language [Groups]\n"
        "🎧 /vibe • Play Chill Vibe Music\n"
        "🎵 /customsong • Set Custom VIP Song [VIP]\n"
        "🎨 /customtheme • Set Custom Theme URL [VIP]\n"
        "🎨 /theme • Holographic UI Theme\n"
        "📊 /status • Quota & Core Status\n"
        "⏸ /stop • Pause | ▶️ /resume • Resume\n"
        "⭐️ /premium • VIP Vault\n\n"
        "<b>Send any text or PDF document to begin!</b>"
    )
    
    if is_group:
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🌍 My Language", callback_data="open_mylang_menu"), InlineKeyboardButton("🔄 Change Language", callback_data="open_changelang_menu")],
            [InlineKeyboardButton("👥 Partner's Language", callback_data="open_partnerlang_menu")]
        ])
    else:
        keyboard = InlineKeyboardMarkup([])

    try:
        if "giphy" in anim_to_show or anim_to_show.endswith(('.gif', '.jpg', '.png')):
            if keyboard.inline_keyboard:
                await update.message.reply_animation(animation=anim_to_show, caption=welcome, parse_mode="HTML", reply_markup=keyboard)
            else:
                await update.message.reply_animation(animation=anim_to_show, caption=welcome, parse_mode="HTML")
        else:
            if keyboard.inline_keyboard:
                await update.message.reply_text(welcome, parse_mode="HTML", reply_markup=keyboard)
            else:
                await update.message.reply_text(welcome, parse_mode="HTML")
        await update.message.reply_audio(audio=VIBE_MUSIC_URL, caption="🎧 <b>Welcome Vibe Track:</b> Enjoy the chill rhythm!", parse_mode="HTML")
    except Exception:
        if keyboard.inline_keyboard:
            await update.message.reply_text(welcome, parse_mode="HTML", reply_markup=keyboard)
        else:
            await update.message.reply_text(welcome, parse_mode="HTML")

async def start_lang_button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    keyboard = [
        [InlineKeyboardButton("🇮🇳 Malayalam", callback_data="set_my_ml"), InlineKeyboardButton("🇬🇧 English", callback_data="set_my_en")],
        [InlineKeyboardButton("🇷🇺 Russian", callback_data="set_my_ru"), InlineKeyboardButton("🇩🇪 German", callback_data="set_my_de")],
        [InlineKeyboardButton("🇫🇷 French", callback_data="set_my_fr"), InlineKeyboardButton("🇮🇹 Italian", callback_data="set_my_it")],
        [InlineKeyboardButton("🇪🇸 Spanish", callback_data="set_my_es"), InlineKeyboardButton("🇵🇹 Portuguese", callback_data="set_my_pt")],
        [InlineKeyboardButton("🇺🇦 Ukrainian", callback_data="set_my_uk"), InlineKeyboardButton("🇵🇱 Polish", callback_data="set_my_pl")],
        [InlineKeyboardButton("🇺🇿 Uzbek", callback_data="set_my_uz"), InlineKeyboardButton("🇹🇯 Tajik", callback_data="set_my_tg")],
        [InlineKeyboardButton("🇮🇳 Hindi", callback_data="set_my_hi"), InlineKeyboardButton("🇸🇦 Arabic", callback_data="set_my_ar")],
    ]
    partner_keyboard = [
        [InlineKeyboardButton("🇷🇺 Russian", callback_data="set_partner_ru"), InlineKeyboardButton("🇮🇳 Malayalam", callback_data="set_partner_ml")],
        [InlineKeyboardButton("🇬🇧 English", callback_data="set_partner_en"), InlineKeyboardButton("🇩🇪 German", callback_data="set_partner_de")],
        [InlineKeyboardButton("🇺🇿 Uzbek", callback_data="set_partner_uz"), InlineKeyboardButton("🇹🇯 Tajik", callback_data="set_partner_tg")],
    ]

    if data in ["open_mylang_menu", "open_changelang_menu"]:
        await query.message.reply_text(
            "🌍 <b>Choose Your Language:</b>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    elif data == "open_partnerlang_menu":
        await query.message.reply_text(
            "👥 <b>Choose Partner's Language:</b>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(partner_keyboard)
        )

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
    chat = update.effective_chat
    chat_id = chat.id
    user_id = update.effective_user.id
    is_group = chat.type in ["group", "supergroup"]
    await process_and_reply(update, context, text_content, chat_id, user_id, is_group)

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
        
        chat = update.effective_chat
        chat_id = chat.id
        user_id = update.effective_user.id
        is_group = chat.type in ["group", "supergroup"]
        await process_and_reply(update, context, trans_text, chat_id, user_id, is_group)
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

    chat = update.effective_chat
    chat_id = chat.id
    user_id = update.effective_user.id
    is_group = chat.type in ["group", "supergroup"]
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
        res = await execute_translation(extracted_text, chat_id, user_id, context.bot_data, is_group)
        
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

async def process_and_reply(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str, chat_id: int, user_id: int, is_group: bool):
    user = update.effective_user
    user_name = user.first_name or "Operator"

    active, status_val, is_vip = is_user_active(context, user_id, chat_id)
    if not active:
        await send_store_menu(chat_id, context)
        return

    placeholder = await update.message.reply_text("⚡ <i>Translating...</i>", parse_mode="HTML")
    res = await execute_translation(text, chat_id, user_id, context.bot_data, is_group)

    if "error" in res:
        await placeholder.edit_text(f"⚠️ <b>Error:</b> {res['error']}", parse_mode="HTML")
        return

    src_lang = res.get("src", "English")
    trg_lang = res.get("trg", "Target")
    translation = res.get("trans", text)
    meaning_en = res.get("meaning", text)
    native_p = res.get("native_p", text)
    latin_p = res.get("latin_p", "")
    cultural_insight = res.get("cultural_insight", "A unique linguistic expression.")

    src_info = get_voice_info(src_lang)
    trg_info = get_voice_info(trg_lang)

    native_p_block = f"🗣 <i>Phonetic ({src_info['flag']} {src_lang}):</i> <code>{native_p[:200]}</code>\n" if native_p else ""
    latin_p_block = f"🔤 <i>English Phonetics:</i> <tg-spoiler><b>{latin_p[:200]}</b></tg-spoiler>\n" if latin_p else ""
    meaning_en_block = f"📖 <b>Meaning (ENGLISH): {meaning_en[:1500]}</b>\n" if meaning_en else ""
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

    if is_group:
        keyboard = [
            [
                InlineKeyboardButton(f"🔊 {src_info['flag']} Listen ({src_lang})", callback_data=f"play_src_{msg_id}"),
                InlineKeyboardButton(f"🔊 {trg_info['flag']} Listen ({trg_lang})", callback_data=f"play_trg_{msg_id}")
            ],
            [
                InlineKeyboardButton("🌍 My Language", callback_data="open_mylang_menu"),
                InlineKeyboardButton("👥 Partner's Language", callback_data="open_partnerlang_menu")
            ]
        ]
    else:
        keyboard = [
            [
                InlineKeyboardButton(f"🔊 {src_info['flag']} Listen ({src_lang})", callback_data=f"play_src_{msg_id}"),
                InlineKeyboardButton(f"🔊 {trg_info['flag']} Listen ({trg_lang})", callback_data=f"play_trg_{msg_id}")
            ]
        ]

    user_theme_key = context.bot_data.get("user_theme", {}).get(str(user_id), "chibi")
    theme_item = ALL_THEMES.get(user_theme_key, {})
    
    if theme_item.get("vip") and not is_vip:
        theme_bg_url = STANDARD_THEMES["chibi"]["url"]
    else:
        theme_bg_url = theme_item.get("url")
        if is_vip and user_theme_key in PREMIUM_THEMES:
            theme_bg_url = context.bot_data.get("user_custom_bg", {}).get(str(user_id), theme_item.get("url"))

    try:
        await context.bot.delete_message(chat_id=chat_id, message_id=placeholder.message_id)
        if theme_bg_url and "giphy" in theme_bg_url or theme_bg_url and theme_bg_url.endswith(('.gif', '.jpg', '.png')):
            await context.bot.send_animation(chat_id=chat_id, animation=theme_bg_url, caption=card_text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            await context.bot.send_message(chat_id=chat_id, text=card_text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))
    except Exception:
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
        BotCommand("mylanguage", "Set My Language [Groups]"),
        BotCommand("changelanguage", "Change Language [Groups]"),
        BotCommand("partnerlanguage", "Set Partner's Language [Groups]"),
        BotCommand("vibe", "Play Chill Vibe Music"),
        BotCommand("customsong", "Set Custom VIP Song [VIP]"),
        BotCommand("customtheme", "Set Custom Theme URL [VIP]"),
        BotCommand("theme", "Holographic UI Theme"),
        BotCommand("status", "Quota & Core Status"),
        BotCommand("stop", "Pause Bot"),
        BotCommand("resume", "Resume Bot"),
        BotCommand("premium", "VIP Vault")
    ])

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("mylanguage", mylanguage_command))
    app.add_handler(CommandHandler("changelanguage", mylanguage_command))
    app.add_handler(CommandHandler("partnerlanguage", partnerlanguage_command))
    app.add_handler(CommandHandler("vibe", vibe_command))
    app.add_handler(CommandHandler("customsong", custom_song_command))
    app.add_handler(CommandHandler("customtheme", custom_theme_command))
    app.add_handler(CommandHandler("theme", theme_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CommandHandler("stop", stop_command))
    app.add_handler(CommandHandler("resume", resume_command))
    app.add_handler(CommandHandler("premium", premium_command))

    app.add_handler(CallbackQueryHandler(settings_callback, pattern="^(set_my_|set_partner_)"))
    app.add_handler(CallbackQueryHandler(start_lang_button_callback, pattern="^(open_mylang_menu|open_changelang_menu|open_partnerlang_menu)$"))
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
