from telegram.ext import Updater, MessageHandler, Filters, CommandHandler
from openai import OpenAI
# from pydub import AudioSegment
import os
import concurrent.futures

# 환경 변수
BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENAI_KEY = os.getenv("OPENAI_KEY")

GPT_MODEL = "gpt-4o-mini"

if not BOT_TOKEN or not OPENAI_KEY:
    print("❌ BOT_TOKEN 또는 OPENAI_KEY 누락됨")
    exit(1)

client = OpenAI(api_key=OPENAI_KEY)
TRANSLATION_ACTIVE = True

TARGET_LANGS = {
    "Korean": ("ko", "🇰🇷 Korean"),
    "English": ("en", "🇺🇸 English"),
    "Japanese": ("ja", "🇯🇵 Japanese"),
    "Chinese": ("zh-CN", "🇨🇳 Chinese")
}

def safe_call(func):
    def wrapper(*args, **kwargs):
        for _ in range(3):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                print(f"⚠️ {func.__name__} error: {e}")
        return None
    return wrapper

@safe_call
def detect_language(text):
    prompt = (
        "Detect the language of this text. Respond with only ONE word: "
        "Korean, English, Japanese, or Chinese.\n\nText:\n" + text
    )
    response = client.chat.completions.create(
        model=GPT_MODEL,
        messages=[{"role": "user", "content": prompt}]
    )
    content = response.choices[0].message.content.strip()
    # print(f"🧭 Detected language: {content}")
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
        model=GPT_MODEL,
        messages=[{"role": "user", "content": prompt}]
    )
    translated = response.choices[0].message.content.strip()
    # print(f"✅ Translated to {target_code}: {translated}")
    return translated

@safe_call
def speech_to_text(file_path):
    audio = client.audio.transcriptions.create(
        model="whisper-1",
        file=open(file_path, "rb")
    )
    return audio.text

def translate_text_handler(text, update):
    msg_id = update.message.message_id
    source_lang = detect_language(text)
    if not source_lang:
        update.message.reply_text("⚠️ 언어 감지 실패.", reply_to_message_id=msg_id)
        return

    results = []
    tasks = {}

    with concurrent.futures.ThreadPoolExecutor() as executor:
        # 각 언어별 future를 명시적으로 매핑
        for lang, (code, label) in TARGET_LANGS.items():
            if lang != source_lang:
                future = executor.submit(translate, text, code)
                tasks[future] = (label, code)

        # 완료된 future 순서대로 결과 수집
        for future in concurrent.futures.as_completed(tasks):
            label, code = tasks[future]
            try:
                translated = future.result()
                if translated:
                    results.append(f"{label}:\n{translated}")
            except Exception as e:
                print(f"⚠️ 번역 실패 ({code}): {e}")

    if results:
        # 원문 댓글 + 언어별 줄 띄움
        output = "🌍 Translations:\n\n" + "\n\n".join(results)
        update.message.reply_text(output, reply_to_message_id=msg_id)
    else:
        update.message.reply_text("⚠️ 번역 결과가 없습니다.", reply_to_message_id=msg_id)

# def handle_voice(update, context):
#     voice = update.message.voice or update.message.audio
#     file = voice.get_file()
#     ogg = "/tmp/input.ogg"
#     wav = "/tmp/input.wav"
#     file.download(ogg)
#     AudioSegment.from_file(ogg).export(wav, format="wav")
#     text = speech_to_text(wav)
#     if text:
#         translate_text_handler(text, update)

def handle_text(update, context):
    global TRANSLATION_ACTIVE
    print(f"📩 Received: {update.message.text}")
    if not TRANSLATION_ACTIVE:
        update.message.reply_text("🚫 Translation paused.")
        return
    translate_text_handler(update.message.text, update)

def cmd_on(update, context):
    global TRANSLATION_ACTIVE
    TRANSLATION_ACTIVE = True
    update.message.reply_text("✅ Translation activated.")

def cmd_off(update, context):
    global TRANSLATION_ACTIVE
    TRANSLATION_ACTIVE = False
    update.message.reply_text("⛔ Translation paused.")

def cmd_lang(update, context):
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
dp.add_handler(CommandHandler("on", cmd_on))
dp.add_handler(CommandHandler("off", cmd_off))
dp.add_handler(CommandHandler("lang", cmd_lang))
dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_text))
# dp.add_handler(MessageHandler(Filters.voice | Filters.audio, handle_voice))

print("🤖 NWG Global Translator (OpenAI v1.0) Running...")
updater.start_polling()
updater.idle()
