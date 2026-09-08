import os
import re
import asyncio
from datetime import datetime, timedelta
from aiohttp import web
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

# Looping Animated Banners (Direct assets)
ANIM_TRANSLATE_URL = "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExOHpqeGZhc3BuaXlndG5mNms2bmtuMjJ3bm1ocm44OXpsczF1eHZsZSZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/26tn33aiTi1jkl6H6/giphy.gif"
ANIM_VOICE_URL = "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExM3ZkZjJmNmYwdjMxdmpobDFidGNrcWpzaDVpZXd3cThldGlsNHNpayZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/l41lI4bYmcsPJX9Go/giphy.gif"
ANIM_STORE_URL = "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExbnYydWhsazBqczJycHJmdTR5cWNvZGFoYm95am03MGl2aTFxZTN3ZSZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/3o7TKSjRrfIPjeiVyM/giphy.gif"
ANIM_CELEBRATE_URL = "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExMjRzNm1lYjhxZXlhZjB4MnJ3OXJ2djlueTR2YjA2aWhlbmx4ZXBhaCZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/artj92V8o75VPL7AeQ/giphy.gif"

# 2. Render Keep-Alive Port Binding
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
        return "Error: GROQ_API_KEY is missing."

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
                            "content": "You are a bilingual real-time interpreter. Output only the translation without explanations or <think> tags."
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

        return "Translation service is currently unavailable."
    except Exception as e:
        return f"Groq Error: {str(e)[:80]}"

# 4. Quota and Subscription Tiers
FREE_LIMIT = 100

PLANS = {
    "sub_1m": {"name": "1 Month VIP", "days": 30, "stars": 50},
    "sub_3m": {"name": "3 Months VIP", "days": 90, "stars": 120},
    "sub_1y": {"name": "1 Year VIP Pass", "days": 365, "stars": 399},
}

def is_user_active(context: ContextTypes.DEFAULT_TYPE, user_id: str) -> tuple[bool, str]:
    if "premium_expiry" not in context.chat_data:
        context.chat_data["premium_expiry"] = {}
    if "free_credits" not in context.chat_data:
        context.chat_data["free_credits"] = {}

    expiry_str = context.chat_data["premium_expiry"].get(user_id)
    if expiry_str:
        expiry = datetime.fromisoformat(expiry_str)
        if datetime.utcnow() < expiry:
            days_left = (expiry - datetime.utcnow()).days
            return True, f"🌟 VIP ({days_left}d left)"

    if user_id not in context.chat_data["free_credits"]:
        context.chat_data["free_credits"][user_id] = FREE_LIMIT

    remaining = context.chat_data["free_credits"][user_id]
    if remaining > 0:
        return True, f"🎁 Free: {remaining}/100"

    return False, "❌ Expired"

async def send_store_menu(chat_id, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "⭐️ <b>PREMIUM TRANSLATOR STORE</b> ⭐️\n\n"
        "Your free trial limit has been reached! Choose an unlimited plan below to continue:\n\n"
        "• <b>1 Month VIP:</b> 50 Stars\n"
        "• <b>3 Months VIP:</b> 120 Stars <i>(20% Off)</i>\n"
        "• <b>1 Year VIP Pass:</b> 399 Stars <i>(Best Value!)</i>"
    )
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("⭐️ 1 Month (50 Stars)", callback_data="buy_sub_1m")],
        [InlineKeyboardButton("⭐️ 3 Months (120 Stars)", callback_data="buy_sub_3m")],
        [InlineKeyboardButton("👑 1 Year Pass (399 Stars)", callback_data="buy_sub_1y")],
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
    welcome = (
        "✨ <b>Universal Polyglot Interpreter</b> ✨\n\n"
        "• <b>Zero Setup:</b> Speak naturally; the bot translates bidirectionally between your language and your friend's.\n"
        "• <b>100 Free Translations:</b> Granted automatically on start.\n"
        "• <b>Animated HUD:</b> Voice and text replies include visual cards.\n\n"
        "Send your first message or voice note to begin!"
    )
    try:
        await update.message.reply_animation(
            animation=ANIM_TRANSLATE_URL,
            caption=welcome,
            parse_mode="HTML"
        )
    except Exception:
        await update.message.reply_text(welcome, parse_mode="HTML")

async def premium_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_store_menu(update.effective_chat.id, context)

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    active, status = is_user_active(context, user_id)

    if not active:
        await send_store_menu(update.effective_chat.id, context)
        return

    text = update.message.text.strip()
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

    if "user_langs" not in context.chat_data:
        context.chat_data["user_langs"] = {}

    user_langs = context.chat_data["user_langs"]
    other_users = [uid for uid in user_langs if uid != user_id]
    target_lang = user_langs[other_users[0]] if other_users else None

    prompt = (
        f"Input message: \"{text}\"\n"
        f"Target language: {target_lang or 'English'}\n\n"
        "Instructions:\n"
        "1. Identify the input language precisely.\n"
        "2. Translate into the target language.\n"
        "3. Output strictly:\n"
        "SRC: [Detected Source Language]\n"
        "RES: [Translated text only]"
    )

    raw_response = execute_groq_text(prompt)
    src_lang = "Auto"
    translation = raw_response

    for line in raw_response.splitlines():
        line = line.strip()
        if line.startswith("SRC:"):
            src_lang = line.replace("SRC:", "").strip()
        elif line.startswith("RES:"):
            translation = line.replace("RES:", "").strip()

    if src_lang and "unknown" not in src_lang.lower():
        user_langs[user_id] = src_lang

    if "Free:" in status:
        context.chat_data["free_credits"][user_id] -= 1
        _, status = is_user_active(context, user_id)

    card_text = (
        f"⚡ <b>TRANSLATION HUD</b>\n"
        f"<code>{src_lang.upper()}</code> ➔ <code>{(target_lang or 'ENGLISH').upper()}</code>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"{translation}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🏷 <i>Status: {status}</i>"
    )

    await update.message.reply_text(card_text, parse_mode="HTML")

async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    active, status = is_user_active(context, user_id)

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

        if "Free:" in status:
            context.chat_data["free_credits"][user_id] -= 1
            _, status = is_user_active(context, user_id)

        card_text = (
            f"🎙️ <b>VOICE NOTE TRANSCRIBED</b>\n"
            f"<code>{src_lang.upper()}</code> ➔ <code>{target_lang.upper()}</code>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🗣 <i>\"{spoken_text}\"</i>\n\n"
            f"✨ <b>{translation}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🏷 <i>Status: {status}</i>"
        )

        try:
            await update.message.reply_animation(
                animation=ANIM_VOICE_URL,
                caption=card_text,
                parse_mode="HTML"
            )
        except Exception:
            await update.message.reply_text(card_text, parse_mode="HTML")

    except Exception as e:
        await update.message.reply_text(f"Voice Error: {str(e)[:80]}")
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)

# 6. Telegram Star Payments
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
        description=f"Unlimited two-way translations for {plan['days']} days.",
        payload=plan_key,
        provider_token="",  # Must remain empty for Telegram Stars
        currency="XTR",     # Telegram Stars currency code
        prices=prices,
    )

async def precheckout_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.pre_checkout_query
    if query.invoice_payload in PLANS:
        await query.answer(ok=True)
    else:
        await query.answer(ok=False, error_message="Invalid plan selected.")

async def successful_payment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Activates the subscription duration and fires an animated celebration."""
    user_id = str(update.effective_user.id)
    plan_key = update.message.successful_payment.invoice_payload
    plan = PLANS.get(plan_key, PLANS["sub_1m"])

    if "premium_expiry" not in context.chat_data:
        context.chat_data["premium_expiry"] = {}

    current_expiry_str = context.chat_data["premium_expiry"].get(user_id)
    now = datetime.utcnow()

    if current_expiry_str and datetime.fromisoformat(current_expiry_str) > now:
        base_time = datetime.fromisoformat(current_expiry_str)
    else:
        base_time = now

    new_expiry = base_time + timedelta(days=plan["days"])
    context.chat_data["premium_expiry"][user_id] = new_expiry.isoformat()

    celebration_text = (
        f"🎉 <b>VIP MEMBERSHIP UNLOCKED!</b> ⭐️\n\n"
        f"👑 <b>Tier:</b> {plan['name']}\n"
        f"⏳ <b>Valid Until:</b> <code>{new_expiry.strftime('%Y-%m-%d')}</code>\n\n"
        f"✨ <i>All restrictions lifted: Enjoy unlimited bidirectional translations!</i>"
    )

    try:
        await update.message.reply_animation(
            animation=ANIM_CELEBRATE_URL,
            caption=celebration_text,
            parse_mode="HTML"
        )
    except Exception:
        await update.message.reply_text(celebration_text, parse_mode="HTML")

# 7. Safe Runner Loop
async def run_bot():
    await start_web_server()

    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("premium", premium_command))
    app.add_handler(CallbackQueryHandler(plan_selection_callback, pattern="^buy_"))
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
