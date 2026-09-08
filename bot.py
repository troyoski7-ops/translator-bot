import os
import asyncio
from aiohttp import web
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
)
from google import genai

# Credentials
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8653764956:AAG1x3qHbG5WMouZ6GiWOtJ5jROMLAbs9tY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

client = genai.Client(api_key=GEMINI_API_KEY)

# ലഭ്യമായ പ്രധാന ഭാഷകൾ
SUPPORTED_LANGUAGES = {
    "ml": "Malayalam",
    "en": "English",
    "fr": "French",
    "de": "German",
    "ar": "Arabic",
    "es": "Spanish",
    "ru": "Russian",
    "hi": "Hindi",
    "ta": "Tamil",
    "it": "Italian",
    "ja": "Japanese",
    "zh": "Chinese"
}

# User Pair Storage (In-memory: defaults to Malayalam <-> French)
user_pairs = {}

def get_user_pair(user_id):
    if user_id not in user_pairs:
        user_pairs[user_id] = {"my_lang": "Malayalam", "partner_lang": "French"}
    return user_pairs[user_id]

# Render Dummy Web Server (Fix port scan)
async def handle_ping(request):
    return web.Response(text="Bot is live and running!")

async def start_web_server():
    app = web.Application()
    app.router.add_get('/', handle_ping)
    app.router.add_get('/healthz', handle_ping)
    
    port = int(os.environ.get("PORT", 10000))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()

# Gemini Helper with Auto-failover
async def generate_gemini(contents):
    models_to_try = ["gemini-3.6-flash", "gemini-2.5-flash"]
    for model_name in models_to_try:
        for attempt in range(2):
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=contents
                )
                if response and response.text:
                    return response.text.strip()
            except Exception as e:
                if "503" in str(e) and attempt == 0:
                    await asyncio.sleep(1)
                    continue
                break
    return "സെർവറിൽ ചെറിയ തിരക്കുണ്ട്, ദയവായി വീണ്ടും ശ്രമിക്കൂ."

# Command Handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    pair = get_user_pair(user_id)
    
    msg = (
        f"👋 ഹലോ!\n\n"
        f"ഇതൊരു Two-Way Translator Bot ആണ്. നിങ്ങൾക്കും നിങ്ങളുടെ സുഹൃത്തിനും ഏത് ഭാഷയിലും ചാറ്റ് ചെയ്യാം.\n\n"
        f"📌 **നിലവിലെ സെറ്റിംഗ്സ്:**\n"
        f"• നിങ്ങളുടെ ഭാഷ: **{pair['my_lang']}**\n"
        f"• സുഹൃത്തിന്റെ ഭാഷ: **{pair['partner_lang']}**\n\n"
        f"🔹 ഭാഷ മാറ്റാൻ: /setpair ക്ലിക്ക് ചെയ്യുക.\n"
        f"🔹 ഇനി നേരിട്ട് Text അല്ലെങ്കിൽ Voice മെസ്സേജ് അയക്കൂ!"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")

async def set_pair_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("1️⃣ എന്റെ ഭാഷ മാറ്റുക", callback_data="change_my_lang")],
        [InlineKeyboardButton("2️⃣ സുഹൃത്തിന്റെ ഭാഷ മാറ്റുക", callback_data="change_partner_lang")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("ഏത് ഭാഷയാണ് മാറ്റേണ്ടത്?", reply_markup=reply_markup)

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = update.effective_user.id
    pair = get_user_pair(user_id)

    if data in ["change_my_lang", "change_partner_lang"]:
        target = "my" if data == "change_my_lang" else "partner"
        buttons = []
        row = []
        for code, name in SUPPORTED_LANGUAGES.items():
            row.append(InlineKeyboardButton(name, callback_data=f"set_{target}_{code}"))
            if len(row) == 3:
                buttons.append(row)
                row = []
        if row:
            buttons.append(row)
        
        reply_markup = InlineKeyboardMarkup(buttons)
        target_name = "നിങ്ങളുടെ ഭാഷ" if target == "my" else "സുഹൃത്തിന്റെ ഭാഷ"
        await query.edit_message_text(f"തിരഞ്ഞെടുക്കുക ({target_name}):", reply_markup=reply_markup)

    elif data.startswith("set_"):
        _, target, code = data.split("_")
        chosen_lang = SUPPORTED_LANGUAGES.get(code, "English")
        
        if target == "my":
            pair["my_lang"] = chosen_lang
        else:
            pair["partner_lang"] = chosen_lang
            
        done_text = (
            f"✅ **ഭാഷ വിജയകരമായി സെറ്റ് ചെയ്തു!**\n\n"
            f"• നിങ്ങളുടെ ഭാഷ: **{pair['my_lang']}**\n"
            f"• സുഹൃത്തിന്റെ ഭാഷ: **{pair['partner_lang']}**\n\n"
            f"ഇനി ചാറ്റ് ചെയ്യാൻ ടെക്സ്റ്റോ വോയ്‌സോ അയക്കൂ!"
        )
        await query.edit_message_text(done_text, parse_mode="Markdown")

# Message Handlers
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    user_id = update.effective_user.id
    pair = get_user_pair(user_id)
    l1, l2 = pair["my_lang"], pair["partner_lang"]

    try:
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
        prompt = (
            f"You are a real-time conversational bilingual translator between {l1} and {l2}.\n"
            f"Task:\n"
            f"1. Detect whether the input is primarily in {l1} or {l2} (or related foreign language).\n"
            f"2. If it is in {l1}, translate it accurately to {l2}.\n"
            f"3. If it is in {l2} (or any other language), translate it accurately to {l1}.\n"
            f"4. Output ONLY the translation without any notes or explanations.\n\n"
            f"Input:\n{user_text}"
        )
        result = await generate_gemini(prompt)
        await update.message.reply_text(result)
    except Exception as e:
        await update.message.reply_text(f"Error: {str(e)}")

async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    voice = update.message.voice or update.message.audio
    if not voice:
        return
    
    user_id = update.effective_user.id
    pair = get_user_pair(user_id)
    l1, l2 = pair["my_lang"], pair["partner_lang"]

    try:
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="record_voice")
        file = await context.bot.get_file(voice.file_id)
        voice_file_path = f"temp_{voice.file_id}.ogg"
        await file.download_to_drive(voice_file_path)

        uploaded_audio = client.files.upload(file=voice_file_path)

        contents = [
            uploaded_audio,
            f"Listen to the audio.\n"
            f"1. Accurately transcribe the spoken speech.\n"
            f"2. If spoken in {l1}, translate to {l2}. If spoken in {l2} (or other languages), translate to {l1}.\n"
            f"Output strictly in this format:\n"
            f"🗣 [Transcribed Speech]\n"
            f"🌐 [Translated Text]"
        ]
        
        result_text = await generate_gemini(contents)
        await update.message.reply_text(result_text)

        if os.path.exists(voice_file_path):
            os.remove(voice_file_path)
    except Exception as e:
        await update.message.reply_text("വോയ്സ് പ്രോസസ്സ് ചെയ്യാൻ സാധിച്ചില്ല, ദയവായി വീണ്ടും അയക്കൂ.")

# Main Runner
async def main():
    await start_web_server()

    application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("setpair", set_pair_command))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    application.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, handle_voice))

    print("Two-way Multi-language Bot is starting polling...")
    async with application:
        await application.start()
        await application.updater.start_polling(drop_pending_updates=True)
        while True:
            await asyncio.sleep(3600)

if __name__ == "__main__":
    asyncio.run(main())
