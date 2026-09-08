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

# Animated Assets & VIP Gifts
ANIM_START_URL = "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExOHpqeGZhc3BuaXlndG5mNms2bmtuMjJ3bm1ocm44OXpsczF1eHZsZSZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/26tn33aiTi1jkl6H6/giphy.gif"
ANIM_STORE_URL = "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExbnYydWhsazBqczJycHJmdTR5cWNvZGFoYm95am03MGl2aTFxZTN3ZSZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/3o7TKSjRrfIPjeiVyM/giphy.gif"
VIP_GIFT_STICKER = "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExYWZ0N25xZG82OXF0NWlhbnF6bWc2dHFob2ZlZmxmbnlucTNtc2xxeSZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/l0ExhcMymdL6TrZ84/giphy.gif"

# 2. Render Keep-Alive Server
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

# 3. Dynamic Model Engine
def execute_groq_text(prompt):
    if not GROQ_API_KEY:
        return "Error: GROQ_API_KEY missing."

    try:
        model_list = groq_client.models.list()
        valid_models = [
            m.id for m in model_list.data
            if not any(x in m.id.lower() for x in ["whisper", "guard", "vision", "embed", "safeguard"])
        ]

        for model_id in valid_models:
            try:
                completion = groq_client.chat.completions.create(
                    model=model_id,
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "You are a bilingual real-time interpreter. "
                                "Follow the 4-line format strictly. "
                                "Never include commentary or <think> tags."
                            )
                        },
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.2,
                    max_tokens=350,
                )
                if completion and completion.choices:
                    res = completion.choices[0].message.content.strip()
                    res = re.sub(r'<think>.*?</think>', '', res, flags=re.DOTALL).strip()
                    return res
            except Exception:
                continue

        return "Translation unavailable."
    except Exception as e:
        return f"Groq Error: {str(e)[:80]}"

# 4. Quotas & Subscription Plans
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
        "⭐️ <b>STAR VIP STORE & GIFTS</b> ⭐️\n\n"
        "Your free trial limit has been reached!\n\n"
        "🎁 <b>VIP Perks & Unlocks:</b>\n"
        "• Exclusive animated VIP gift stickers\n"
        "• High-priority zero latency lane\n"
        "• Unlimited real-time audio pronunciation\n\n"
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

# 5. Handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.chat_data["paused"] = False
    welcome = (
        "🌐 <b>UNIVERSAL TRANSLATOR</b>\n\n"
        "• ⚡ Speak naturally in your native language\n"
        "• 🎁 <b>100 Free Translations</b> included\n"
        "• 🔊 Tap to listen to audio pronunciation\n\n"
        "<b>Commands:</b>\n"
        "📊 /status • Check quota / VIP status\n"
        "⏸ /stop • Pause translation\n"
        "▶️ /resume • Resume translation\n"
        "⭐️ /premium • Star VIP Store\n\n"
        "Send any message or voice memo to begin!"
    )
    try:
        await update.message.reply_animation(
            animation=ANIM_START_URL,
            caption=welcome,
            parse_mode="HTML"
        )
    except Exception:
        await update.message.reply_text(welcome, parse_mode="HTML")

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    _, status_val, is_vip = is_user_active(context, user_id)
    is_paused = context.chat_data.get("paused", False)
    state = "⏸ Paused" if is_paused else "▶️ Active"

    status_text = (
        f"📊 <b>STATUS</b>\n"
        f"🏃 Status: {status_val}\n"
        f"🔄 State: {state}\n\n"
        f"<i>Send /premium to unlock VIP gifts & unlimited translations!</i>"
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
    target_lang = user_langs[other_users[0]] if other_users else None

    prompt = (
        f"Input: \"{text}\"\n"
        f"Target language: {target_lang or 'English'}\n\n"
        "Instructions:\n"
        "1. Identify source language accurately.\n"
        "2. Translate directly into target language.\n"
        "3. Provide phonetic romanization if non-latin script (or NONE).\n"
        "4. Output strictly (4 lines):\n"
        "SRC: [Source Language]\n"
        "TRG: [Target Language]\n"
        "PRON: [Phonetic pronunciation or NONE]\n"
        "RES: [Final translation only]"
    )

    raw_response = execute_groq_text(prompt)

    src_lang = "Auto"
    trg_lang = target_lang or "English"
    pronunciation = "NONE"
    translation = raw_response

    for line in raw_response.splitlines():
        line = line.strip()
        if line.startswith("SRC:"):
            src_lang = line.replace("SRC:", "").strip()
        elif line.startswith("TRG:"):
            trg_lang = line.replace("TRG:", "").strip()
        elif line.startswith("PRON:"):
            pronunciation = line.replace("PRON:", "").strip()
        elif line.startswith("RES:"):
            translation = line.replace("RES:", "").strip()

    if src_lang and "unknown" not in src_lang.lower():
        user_langs[user_id] = src_lang

    if not is_vip:
        context.chat_data["free_credits"][user_id] -= 1
        _, status_val, _ = is_user_active(context, user_id)

    pron_line = f"\n🗣️ <i>Phonetic:</i> <tg-spoiler>{pronunciation}</tg-spoiler>" if pronunciation and pronunciation != "NONE" else ""

    # Concise layout with only "Status: 🏃"
    card_text = (
        f"⚡ <code>{src_lang.upper()}</code> ➔ <code>{trg_lang.upper()}</code>\n\n"
        f"<blockquote>{translation}</blockquote>"
        f"{pron_line}\n\n"
        f"🏃 Status: {status_val}"
    )

    msg_key = f"tts_{placeholder.message_id}"
    context.bot_data[msg_key] = {"text": translation, "lang": trg_lang}

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(f"🔊 Listen ({trg_lang})", callback_data=f"play_{placeholder.message_id}")]
    ])

    await placeholder.edit_text(card_text, parse_mode="HTML", reply_markup=keyboard)

async def handle_tts_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("🎙️ Generating audio...")

    msg_id = query.data.replace("play_", "")
    cache = context.bot_data.get(f"tts_{msg_id}")

    if not cache:
        await query.answer("Session expired. Send a new message!", show_alert=True)
        return

    text_to_speak = cache["text"]

    try:
        tts = gTTS(text=text_to_speak, lang='en')
        audio_buffer = io.BytesIO()
        tts.write_to_fp(audio_buffer)
        audio_buffer.seek(0)
        audio_buffer.name = "pronunciation.mp3"

        await context.bot.send_voice(
            chat_id=query.message.chat_id,
            voice=audio_buffer,
            caption=f"🔊 <i>\"{text_to_speak[:40]}...\"</i>",
            parse_mode="HTML"
        )
    except Exception as e:
        await query.answer(f"Audio error: {str(e)[:50]}", show_alert=True)

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

        prompt = (
            f"Voice transcript: \"{spoken_text}\"\n"
            f"Target language: {target_lang}\n\n"
            "Translate accurately into target language. Output strictly:\n"
            "SRC: [Source Language]\n"
            "RES: [Translated text only]"
        )

        raw_response = execute_groq_text(prompt)
        src_lang = "Audio"
        translation = raw_response

        for line in raw_response.splitlines():
            line = line.strip()
            if line.startswith("SRC:"):
                src_lang = line.replace("SRC:", "").strip()
            elif line.startswith("RES:"):
                translation = line.replace("RES:", "").strip()

        if not is_vip:
            context.chat_data["free_credits"][user_id] -= 1
            _, status_val, _ = is_user_active(context, user_id)

        card_text = (
            f"🎙️ <code>{src_lang.upper()}</code> ➔ <code>{target_lang.upper()}</code>\n\n"
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

# 6. Telegram Star Payments & VIP Gifts Activation
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
        description=f"Unlock VIP animated stickers and unlimited translations for {plan['days']} days.",
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
        await query.answer(ok=False, error_message="Invalid plan selected.")

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

    gift_celebration_text = (
        f"🎁 <b>VIP GIFTS & MEMBERSHIP UNLOCKED!</b> ⭐️\n\n"
        f"👑 <b>Tier:</b> {plan['name']}\n"
        f"💎 <b>Badge:</b> {plan['badge']}\n"
        f"⏳ <b>Valid Until:</b> <code>{new_expiry.strftime('%Y-%m-%d')}</code>\n\n"
        f"✨ <i>All restrictions lifted: Unlimited real-time translations activated!</i>"
    )

    try:
        await update.message.reply_animation(
            animation=VIP_GIFT_STICKER,
            caption=gift_celebration_text,
            parse_mode="HTML"
        )
    except Exception:
        await update.message.reply_text(gift_celebration_text, parse_mode="HTML")

# 7. Safe Runner Loop
async def run_bot():
    await start_web_server()

    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CommandHandler("stop", stop_command))
    app.add_handler(CommandHandler("resume", resume_command))
    app.add_handler(CommandHandler("premium", premium_command))
    app.add_handler(CallbackQueryHandler(plan_selection_callback, pattern="^buy_"))
    app.add_handler(CallbackQueryHandler(handle_tts_button, pattern="^play_"))
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
