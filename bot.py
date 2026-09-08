import os
import json
import edge_tts
from openai import OpenAI
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")

client = OpenAI(api_key=OPENAI_API_KEY)
USER_PREFERENCES = {}

VOICE_MAP = {
    "malayalam": "ml-IN-MidhunNeural",
    "french": "fr-FR-HenriNeural",
    "german": "de-DE-KillianNeural",
    "english": "en-US-ChristopherNeural",
    "spanish": "es-ES-AlvaroNeural",
    "arabic": "ar-SA-HamedNeural",
    "hindi": "hi-IN-MadhurNeural",
    "tamil": "ta-IN-ValluvarNeural",
    "italian": "it-IT-DiegoNeural",
    "russian": "ru-RU-DmitryNeural",
    "japanese": "ja-JP-KeitaNeural",
    "chinese": "zh-CN-YunxiNeural"
}

def analyze_and_translate(sender_id: int, input_text: str):
    known_users_str = json.dumps(USER_PREFERENCES)
    prompt = f"""
    You are a universal real-time multilingual translator for a 2-person chat.
    Input Text: "{input_text}"
    Current Speaker ID: {sender_id}
    Known users and their primary languages so far: {known_users_str}

    Instructions:
    1. Detect the language of the 'Input Text'.
    2. Determine the target language based on the other user's known language. Default to English if unknown.
    3. Provide natural, conversational translation.

    Return JSON ONLY with this structure:
    {{
      "detected_language": "LanguageName",
      "target_language": "TargetLanguageName",
      "translated_text": "translated content here"
    }}
    """
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
        temperature=0.2
    )
    data = json.loads(response.choices[0].message.content)
    detected_lang = data.get("detected_language", "English").strip()
    target_lang = data.get("target_language", "English").strip()
    translated_text = data.get("translated_text", "").strip()
    USER_PREFERENCES[sender_id] = detected_lang
    return detected_lang, target_lang, translated_text

async def generate_voice(text: str, target_lang: str, filename: str):
    lang_key = target_lang.lower()
    voice_name = VOICE_MAP.get(lang_key, "en-US-ChristopherNeural")
    try:
        communicate = edge_tts.Communicate(text, voice_name)
        await communicate.save(filename)
        return True
    except Exception:
        return False

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return

    sender_id = update.effective_user.id
    chat_id = update.effective_chat.id
    original_text = ""

    if update.message.voice:
        voice_file = await update.message.voice.get_file()
        in_path = f"voice_in_{update.message.id}.ogg"
        await voice_file.download_to_drive(in_path)
        with open(in_path, "rb") as audio:
            transcription = client.audio.transcriptions.create(model="whisper-1", file=audio)
        original_text = transcription.text
        if os.path.exists(in_path):
            os.remove(in_path)
    elif update.message.text:
        original_text = update.message.text

    if not original_text.strip():
        return

    detected_lang, target_lang, translated_text = analyze_and_translate(sender_id, original_text)

    header_text = f"🌐 **[{target_lang}]** {translated_text}\n_(From {detected_lang})_"
    await update.message.reply_text(header_text, parse_mode="Markdown")

    out_path = f"voice_out_{update.message.id}.mp3"
    voice_success = await generate_voice(translated_text, target_lang, out_path)

    if voice_success and os.path.exists(out_path):
        with open(out_path, "rb") as voice_file:
            await context.bot.send_voice(chat_id=chat_id, voice=voice_file, reply_to_message_id=update.message.message_id)
        os.remove(out_path)

def main():
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT | filters.VOICE, handle_message))
    print("Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
