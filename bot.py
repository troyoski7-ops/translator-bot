import os
import re
import io
import time
import asyncio
import subprocess
import sys

try:
    from groq import Groq
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "groq"])
    from groq import Groq

from datetime import datetime, timedelta
from aiohttp import web
from gtts import gTTS
import edge_tts
from deep_translator import GoogleTranslator
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

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
GROQ_API_KEY = "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"

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
    "vip_gold": {"label": "👑 Royal Imperial Gold", "url": "https://media.giphy.com/media/l0ExhcMymdL6TrZ84/giphy.gif", "badge": "⚜️ 24K GOLD VIP ⚜️", "quote_prefix": "👑 ", "vip": True},
    "vip_cyber": {"label": "🐉 Cyber Tokyo Neon", "url": "https://media.giphy.com/media/3oKIPnAiaMCws8nOsE/giphy.gif", "badge": "⚡ CYBER MATRIX VIP ⚡", "quote_prefix": "🔮 ", "vip": True},
    "vip_matrix": {"label": "⚡ Quantum Astral Core", "url": "https://media.giphy.com/media/l378c0402U49fs29O/giphy.gif", "badge": "✨ ASTRAL HORIZON ✨", "quote_prefix": "🪐 ", "vip": True},
    "vip_sound": {"label": "🎧 Hologram Soundwaves", "url": "https://media.giphy.com/media/26AHONQ79FdWZhAI0/giphy.gif", "badge": "💎 DIAMOND PRESTIGE 💎", "quote_prefix": "❄️ ", "vip": True}
}

ALL_THEMES = {**STANDARD_THEMES, **PREMIUM_THEMES}
ANIM_STORE_URL = "https://media.giphy.com/media/3o7TKSjRrfIPjeiVyM/giphy.gif"
VIP_GIFT_STICKER = "https://media.giphy.com/media/l0ExhcMymdL6TrZ84/giphy.gif"

VOICE_MAP = {
    "malayalam": {"edge": "ml-IN-SobhanaNeural", "gtts": "ml", "flag": "🇮🇳", "loc": "Kerala"},
    "persian": {"edge": "fa-IR-DilaraNeural", "gtts": "fa", "flag": "🇮🇷", "loc": "Tehran"},
    "farsi": {"edge": "fa-IR-DilaraNeural", "gtts": "fa", "flag": "🇮🇷", "loc": "Tehran"},
    "azerbaijani": {"edge": "az-AZ-BabekNeural", "gtts": "az", "flag": "🇦🇿", "loc": "Baku"},
    "uzbek": {"edge": "uz-UZ-MadinaNeural", "gtts": "uz", "flag": "🇺🇿", "loc": "Tashkent"},
    "kazakh": {"edge": "kk-KZ-AigulNeural", "gtts": "kk", "flag": "🇰🇿", "loc": "Astana"},
    "tajik": {"edge": "tg-TJ-GanjinaNeural", "gtts": "tg", "flag": "🇹🇯", "loc": "Dushanbe"},
    "turkish": {"edge": "tr-TR-AhmetNeural", "gtts": "tr", "flag": "🇹🇷", "loc": "Istanbul"},
    "german": {"edge": "de-DE-KatjaNeural", "gtts": "de", "flag": "🇩🇪", "loc": "Berlin"},
    "chinese": {"edge": "zh-CN-XiaoxiaoNeural", "gtts": "zh-CN", "flag": "🇨🇳", "loc": "Beijing"},
    "japanese": {"edge": "ja-JP-NanamiNeural", "gtts": "ja", "flag": "🇯🇵", "loc": "Tokyo"},
    "italian": {"edge": "it-IT-ElsaNeural", "gtts": "it", "flag": "🇮🇹", "loc": "Rome"},
    "russian": {"edge": "ru-RU-SvetlanaNeural", "gtts": "ru", "flag": "🇷🇺", "loc": "Moscow"},
    "english": {"edge": "en-US-JennyNeural", "gtts": "en", "flag": "🇬🇧", "loc": "London"},
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

def _sync_translation_logic(text):
    if GROQ_API_KEY:
        try:
            client = Groq(api_key=GROQ_API_KEY)
            system_instruction = (
                "You are an expert multi-lingual translation bridge and cultural language tutor.\n"
                "Rules:\n"
                "1. Accurately and strictly detect the true source language of the input text (e.g., if input is Malayalam like 'സുഖമാണോ', source must be 'Malayalam'. If Persian, 'Persian', etc.).\n"
                "2. Translate text accurately.\n"
                "3. In LATIN_P, provide strict English phonetic romanized spelling using English alphabet so someone can read it naturally (e.g. 'sukamano' for സുഖമാണോ, 'Abgoosht' for آب گوشت).\n"
                "4. In CULTURAL_INSIGHT, generate a unique, specific, and fresh cultural fact, historical background, or linguistic idiom directly related to THIS exact word or phrase. Avoid generic sentences.\n"
                "5. Output MUST strictly contain these 6 lines with exact prefixes and nothing else:\n"
                "SRC: [True Source Language Name, e.g. Malayalam or Persian]\n"
                "TRG: [Target Language Name, e.g. English]\n"
                "TRANS: [Translated Text in Target Language]\n"
                "MEANING: [English meaning of the text]\n"
                "NATIVE_P: [Original native text/script]\n"
                "LATIN_P: [English readable phonetic spelling like sukamano or Abgoosht]\n"
                "CULTURAL_INSIGHT: [Unique and specific cultural context or fact about this exact word]"
            )
            completion = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": system_instruction},
                    {"role": "user", "content": f"Message: \"{text}\""}
                ],
                temperature=0.4,
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
                elif line.startswith("CULTURAL_INSIGHT:"): parsed["cultural_insight"] = line.replace("CULTURAL_INSIGHT:", "").strip()

            if parsed.get("trans"):
                parsed["native_text"] = text
                return parsed
        except Exception:
            pass

    try:
        is_eng = all(ord(c) < 128 for c in text)
        target = "ml" if is_eng else "en"
        translated = GoogleTranslator(source='auto', target=target).translate(text)
        if translated:
            return {
                "src": "Malayalam" if any(ord(c) > 3000 for c in text) else ("Persian" if any(ord(c) > 1500 for c in text) else "English"),
                "trg": "English",
                "trans": translated,
                "meaning": translated,
                "native_p": text,
                "latin_p": text,
                "cultural_insight": "A common linguistic expression used in daily communication.",
                "native_text": text
            }
    except Exception as e:
        return {"error": f"Error: {str(e)[:40]}"}

    return {"error": "Translation service busy."}

async def execute_translation(text):
    return await asyncio.to_thread(_sync_translation_logic, text)

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
        "• Unlimited Universal Group & Solo Translations\n"
        "• High-Definition Dual Audio Pronunciations\n"
        "• Secret VIP Luxury Themes\n\n"
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
        "🌐 <b>Universal Multi-User & Group Support:</b>\n"
        "• Send text or voice notes in any language (Malayalam, Persian, Turkish, Uzbek, etc.).\n"
        "• 🔊 <b>HD Audio Synthesis:</b> Get instant dual audio buttons with language flags!\n\n"
        "<b>Commands:</b>\n"
        "🎨 /theme • Holographic UI Theme\n"
        "🖼 /custombg [URL] • Set Custom VIP Background GIF\n"
        "📊 /status • Quota & Core Status\n"
        "⏸ /stop • Pause | ▶️ /resume • Resume\n"
        "⭐️ /premium • VIP Vault\n\n"
        "Send any text or voice note to begin!"
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
        await update.message.reply_text("🔒 <b>VIP Exclusive Feature!</b>", parse_mode="HTML")
        return
    args = context.args
    if not args:
        await update.message.reply_text("🖼 Usage: <code>/custombg [URL]</code>", parse_mode="HTML")
        return
    if "user_custom_bg" not in context.chat_data: context.chat_data["user_custom_bg"] = {}
    context.chat_data["user_custom_bg"][user_id] = args[0]
    await update.message.reply_text("✅ Custom background saved!", parse_mode="HTML")

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    _, status_val, _ = is_user_active(context, user_id)
    await update.message.reply_text(f"📊 <b>Quota:</b> {status_val}", parse_mode="HTML")

async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.chat_data["paused"] = True
    await update.message.reply_text("⏸ Paused.", parse_mode="HTML")

async def resume_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.chat_data["paused"] = False
    await update.message.reply_text("▶️ Resumed.", parse_mode="HTML")

async def premium_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_store_menu(update.effective_chat.id, context)

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.chat_data.get("paused", False): return
    if not update.message or not update.message.text: return
    await process_and_reply(update, context, update.message.text.strip())

async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.chat_data.get("paused", False): return
    if not update.message or not update.message.voice: return

    placeholder = await update.message.reply_text("🎙 <i>Transcribing Voice Note via Whisper...</i>", parse_mode="HTML")
    voice = update.message.voice
    file = await context.bot.get_file(voice.file_id)
    
    ogg_path = f"voice_{voice.file_unique_id}.ogg"
    mp3_path = f"voice_{voice.file_unique_id}.mp3"
    
    try:
        await file.download_to_drive(ogg_path)
        subprocess.run(["ffmpeg", "-y", "-i", ogg_path, mp3_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        client = Groq(api_key=GROQ_API_KEY)
        with open(mp3_path, "rb") as audio_file:
            transcript = client.audio.transcriptions.create(
                model="whisper-large-v3",
                file=audio_file,
                response_format="text"
            )
        
        trans_text = transcript.strip() if isinstance(transcript, str) else transcript.get("text", "").strip()
        if not trans_text:
            await placeholder.edit_text("⚠️ Could not recognize voice audio.")
            return

        await placeholder.delete()
        await process_and_reply(update, context, trans_text)
    except Exception as e:
        await placeholder.edit_text(f"⚠️ Voice transcription error: {str(e)[:40]}")
    finally:
        for p in [ogg_path, mp3_path]:
            if os.path.exists(p):
                try: os.remove(p)
                except Exception: pass

async def process_and_reply(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
    user = update.effective_user
    user_id = str(user.id)
    user_name = user.first_name or "Operator"

    active, status_val, is_vip = is_user_active(context, user_id)
    if not active:
        await send_store_menu(update.effective_chat.id, context)
        return

    placeholder = await update.message.reply_text("⚡ <i>Translating...</i>", parse_mode="HTML")
    res = await execute_translation(text)

    if "error" in res:
        await placeholder.edit_text(f"⚠️ <b>Error:</b> {res['error']}", parse_mode="HTML")
        return

    src_lang = res.get("src", "Malayalam" if any(ord(c) > 3000 for c in text) else "English")
    trg_lang = res.get("trg", "English")
    translation = res.get("trans", text)
    native_p = res.get("native_p", text)
    latin_p = res.get("latin_p", "")
    cultural_insight = res.get("cultural_insight", "A rich linguistic expression.")

    if not is_vip:
        context.chat_data["free_credits"][user_id] -= 1
        _, status_val, _ = is_user_active(context, user_id)

    src_info = get_voice_info(src_lang)
    trg_info = get_voice_info(trg_lang)

    native_p_block = f"🗣 <i>Phonetic ({src_info['flag']} {src_lang}):</i> <code>{native_p}</code>\n" if native_p else ""
    latin_p_block = f"🔤 <i>English Phonetics:</i> <tg-spoiler><b>{latin_p}</b></tg-spoiler>\n" if latin_p else ""
    meaning_en_block = f"📖 <b>Meaning (EN): {translation}</b>\n" if translation else ""
    cultural_block = f"💡 <i>Cultural Insight:</i> <b>{cultural_insight}</b>\n" if cultural_insight else ""

    card_text = (
        f"👤 <b>{user_name}</b>\n"
        f"────────────────────────\n"
        f"{src_info['flag']} <code>{src_lang.upper()}</code> ➔ {trg_info['flag']} <code>{trg_lang.upper()}</code>\n"
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
    context.bot_data[f"aud_src_{msg_id}"] = {"text": text, "voice_edge": src_info.get("edge"), "gtts_code": src_info.get("gtts", "en"), "lang": src_lang, "flag": src_info["flag"]}
    context.bot_data[f"aud_trg_{msg_id}"] = {"text": translation, "voice_edge": trg_info.get("edge"), "gtts_code": trg_info.get("gtts", "en"), "lang": trg_lang, "flag": trg_info["flag"]}

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

    if "premium_expiry" not in context.chat_data: context.chat_data["premium_expiry"] = {}
    if "vip_tier" not in context.chat_data: context.chat_data["vip_tier"] = {}

    current_expiry_str = context.chat_data["premium_expiry"].get(user_id)
    now = datetime.utcnow()
    base_time = datetime.fromisoformat(current_expiry_str) if current_expiry_str and datetime.fromisoformat(current_expiry_str) > now else now

    new_expiry = base_time + timedelta(days=plan["days"])
    context.chat_data["premium_expiry"][user_id] = new_expiry.isoformat()
    context.chat_data["vip_tier"][user_id] = plan["badge"]

    gift_text = f"🎁 <b>VIP PASS UNLOCKED!</b> ⭐️\n\n👑 <b>Tier:</b> {plan['name']}"
    try:
        await update.message.reply_animation(animation=VIP_GIFT_STICKER, caption=gift_text, parse_mode="HTML")
    except Exception:
        await update.message.reply_text(gift_text, parse_mode="HTML")

async def main():
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
    app.add_handler(CallbackQueryHandler(handle_audio_play, pattern="^play_"))
    app.add_handler(CallbackQueryHandler(theme_selection_callback, pattern="^settheme_"))

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
