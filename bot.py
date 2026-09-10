import os
import io
import time
import asyncio
import requests
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

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()

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

def _sync_translate(text):
    try:
        target = "ml" if is_text_english(text) else "en"
        url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl=auto&tl={target}&dt=t&q={requests.utils.quote(text)}"
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=5)
        if response.status_code == 200:
            data = response.json()
            translated = "".join([item[0] for item in data[0] if item[0]])
            src_lang = data[2] if len(data) > 2 else "auto"
            return {
                "src": src_lang.upper(),
                "trg": "Malayalam" if target == "ml" else "English",
                "trans": translated,
                "meaning": translated,
                "native_p": translated,
                "latin_p": text
            }
        return {"error": "Translation service busy."}
    except Exception as e:
        return {"error": f"Error: {str(e)[:40]}"}

async def execute_translation(text, recent_languages=None, is_group=False):
    return await asyncio.to_thread(_sync_translate, text)

def is_text_english(text):
    try:
        text.encode(encoding='utf-8').decode('ascii')
    except UnicodeDecodeError:
        return False
    else:
        return True

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
        "• Unlimited Text Translations\n"
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
    active_theme = STANDARD_THEMES["chibi"]
    bg_url = active_theme["url"]
    
    welcome = (
        f"🌌 <b>QUANTUM POLYGLOT NEURAL BRIDGE</b> 🌌\n\n"
        "✨ Send any text to translate instantly!\n"
        "🔊 Dual Audio buttons included for pronunciation.\n\n"
        "Send any text to begin!"
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

    user = update.effective_user
    user_id = str(user.id)
    user_name = user.first_name or "Operator"

    active, status_val, is_vip = is_user_active(context, user_id)
    if not active:
        await send_store_menu(update.effective_chat.id, context)
        return

    text = update.message.text.strip()
    placeholder = await update.message.reply_text("⚡ <i>Translating...</i>", parse_mode="HTML")

    res = await execute_translation(text)

    if "error" in res:
        await placeholder.edit_text(f"⚠️ <b>Error:</b> {res['error']}", parse_mode="HTML")
        return

    src_lang = res.get("src", "AUTO")
    trg_lang = res.get("trg", "English")
    translation = res.get("trans", text)

    if not is_vip:
        context.chat_data["free_credits"][user_id] -= 1
        _, status_val, _ = is_user_active(context, user_id)

    src_info = get_voice_info(src_lang)
    trg_info = get_voice_info(trg_lang)

    card_text = (
        f"👤 <b>{user_name}</b>\n"
        f"────────────────────────\n"
        f"{src_info['flag']} <code>{src_lang}</code> ➔ {trg_info['flag']} <code>{trg_lang.upper()}</code>\n"
        f"────────────────────────\n\n"
        f"💬 <b>{translation}</b>\n\n"
        f"────────────────────────\n"
        f"🔋 Quota: {status_val}"
    )

    msg_id = placeholder.message_id
    context.bot_data[f"aud_src_{msg_id}"] = {"text": text, "voice_edge": src_info.get("edge"), "gtts_code": "en", "lang": src_lang}
    context.bot_data[f"aud_trg_{msg_id}"] = {"text": translation, "voice_edge": trg_info.get("edge"), "gtts_code": "ml" if trg_lang == "Malayalam" else "en", "lang": trg_lang}

    keyboard = [
        [
            InlineKeyboardButton(f"🔊 Listen (Source)", callback_data=f"play_src_{msg_id}"),
            InlineKeyboardButton(f"🔊 Listen (Target)", callback_data=f"play_trg_{msg_id}")
        ]
    ]

    await placeholder.edit_text(card_text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))

async def handle_audio_play(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("🎧 Generating Audio...")
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

    text_to_speak = cache["text"]
    voice_edge = cache.get("voice_edge")
    gtts_code = cache.get("gtts_code", "en")
    temp_audio_file = f"speech_{msg_id}.mp3"

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
            await context.bot.send_voice(chat_id=query.message.chat_id, voice=audio)
    except Exception as e:
        await context.bot.send_message(chat_id=query.message.chat_id, text=f"⚠️ Audio error")
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
