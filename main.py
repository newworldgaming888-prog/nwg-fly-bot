
import telegram
from telegram.ext import Updater, MessageHandler, Filters, CommandHandler, ChatMemberHandler
from openai import OpenAI
from pydub import AudioSegment

import os
if os.environ.get("RUN_ENV") != "fly":
    print("❌ Local execution disabled. Bot only runs on Fly.io.")
    exit()

BOT_TOKEN = "8551777734:AAEK-FaD7W_aY4HsJEXAhMXrq_EtsDkaDKQ"
OPENAI_KEY = "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"

print(f"api_key: {os.getenv("OPENAI_KEY")}")
client = OpenAI(api_key=os.getenv("OPENAI_KEY"))

ADMIN_ID = 123456789

TRANSLATION_ACTIVE = True

GPT_MODEL = "gpt-4o-mini"

TARGET_LANGS = {
    "Korean": ("ko", "🇰🇷 Korean"),
    "English": ("en", "🇺🇸 English"),
    "Japanese": ("ja", "🇯🇵 Japanese"),
    "Chinese": ("zh-CN", "🇨🇳 Chinese")
}

def is_admin(update):
    return True

def welcome(update, context):
    for member in update.message.new_chat_members:
        update.message.reply_text(
            f"👋 환영합니다, {member.first_name}!\n\n"
            "이 그룹은 자동 번역이 활성화되어 있습니다 🌍\n"
            "그냥 메시지를 보내면 자동으로 여러 언어로 번역돼요.\n\n"
            "명령어 안내: /help"
        )

def safe_call(func):
    def wrapper(*args, **kwargs):
        for _ in range(3):
            try:
                return func(*args, **kwargs)
            except:
                continue
        return None
    return wrapper

@safe_call
def detect_language(text):
    prompt = (
        "Detect the language of this text. Respond with only ONE word: "
        "Korean, English, Japanese, or Chinese.\n\nText:\n" + text
    )

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}]
    )

    content = response.choices[0].message.content.strip()
    print(f"🧭 Detected language: {content}")
    return content

@safe_call
def translate(text, target_code):
    prompt = f"""
Translate this message into {target_code}.
Use a natural, professional, and polite tone.
Return only the translated sentence.

Text: {text}
"""
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}]
    )
    translated = response.choices[0].message.content.strip()
    return translated

@safe_call
def speech_to_text(file_path):
    audio = openai.Audio.transcribe("whisper-1", open(file_path, "rb"))
    return audio["text"]

def translate_text_handler(text, update):
    print(f"🧭 1 translate_text_handler: {text}")
    msg_id = update.message.message_id
    source_lang = detect_language(text)
    print(f"🧭 2 translate_text_handler: {source_lang}")
    if not source_lang:
        return
    for lang, (code, label) in TARGET_LANGS.items():
        print(f"🧭 3 translate_text_handler: {lang, source_lang}")
        if lang != source_lang:
            translated = translate(text, code)
            if translated:
                update.message.reply_text(f"{label}:\n{translated}", reply_to_message_id=msg_id)

def handle_voice(update, context):
    voice = update.message.voice or update.message.audio
    file = voice.get_file()
    ogg = "/tmp/input.ogg"
    wav = "/tmp/input.wav"
    file.download(ogg)
    AudioSegment.from_file(ogg).export(wav, format="wav")
    text = speech_to_text(wav)
    if text:
        translate_text_handler(text, update)

def handle_text(update, context):
    if not TRANSLATION_ACTIVE:
        print("🚫 Translation paused")
        return
    translate_text_handler(update.message.text, update)
    

def cmd_on(update, context):
    global TRANSLATION_ACTIVE
    if is_admin(update):
        TRANSLATION_ACTIVE = True
        update.message.reply_text("✅ Translation activated.")

def cmd_off(update, context):
    global TRANSLATION_ACTIVE
    if is_admin(update):
        TRANSLATION_ACTIVE = False
        update.message.reply_text("⛔ Translation paused.")

def cmd_lang(update, context):
    if not is_admin(update):
        return
    if len(context.args) == 0:
        update.message.reply_text("Usage: /lang English|Korean|Japanese|Chinese")
        return
    selected = context.args[0].capitalize()
    if selected not in TARGET_LANGS:
        update.message.reply_text("❌ Invalid language.")
        return
    update.message.reply_text(f"🌍 Base translation language set to: {selected}")

updater = Updater(BOT_TOKEN, use_context=True)
dp = updater.dispatcher

dp.add_handler(ChatMemberHandler(welcome, ChatMemberHandler.CHAT_MEMBER))

dp.add_handler(CommandHandler("on", cmd_on))
dp.add_handler(CommandHandler("off", cmd_off))
dp.add_handler(CommandHandler("lang", cmd_lang))

dp.add_handler(MessageHandler(
    Filters.text & ~Filters.command,
    handle_text
))
dp.add_handler(MessageHandler(Filters.voice | Filters.audio, handle_voice))

updater.start_polling()
updater.idle()
