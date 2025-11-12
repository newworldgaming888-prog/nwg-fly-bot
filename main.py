from telegram.ext import Updater, MessageHandler, Filters, CommandHandler, ChatMemberHandler
from openai import OpenAI
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
    1: ("en", "🇺🇸 English"),
    2: ("ja", "🇯🇵 Japanese"),
    3: ("zh-CN", "🇨🇳 Chinese"),
    4: ("ko", "🇰🇷 Korean")
}

isBotJoin = False

user_modes = {}  # 유저별 번역 모드 저장

# =============== 공통 유틸 ===============
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
    return response.choices[0].message.content.strip()

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
    return response.choices[0].message.content.strip()

# =============== 번역 로직 ===============
def translate_text_handler(text, update):
    msg_id = update.message.message_id
    user_id = update.message.from_user.id
    source_lang = detect_language(text)
    if not source_lang:
        update.message.reply_text("⚠️ 언어 감지 실패.", reply_to_message_id=msg_id)
        return

    modes = user_modes.get(user_id, [0])  # 기본 0
    results = []
    tasks = {}

    with concurrent.futures.ThreadPoolExecutor() as executor:
        if modes == [0]:
            # 기본 모드: 입력 언어 제외한 모든 언어로 번역
            for _, (code, label) in TARGET_LANGS.items():
                if source_lang.lower() not in label.lower():
                    future = executor.submit(translate, text, code)
                    tasks[future] = (label, code)
        else:
            # 지정 모드
            for mode in modes:
                if mode in TARGET_LANGS:
                    code, label = TARGET_LANGS[mode]
                    # 🟢 입력 언어와 같은 언어는 제외
                    if source_lang.lower() not in label.lower():
                        future = executor.submit(translate, text, code)
                        tasks[future] = (label, code)

        for future in concurrent.futures.as_completed(tasks):
            label, code = tasks[future]
            try:
                translated = future.result()
                if translated:
                    results.append(f"{label}:\n{translated}")
            except Exception as e:
                print(f"⚠️ 번역 실패 ({code}): {e}")

    if results:
        output = "🌍 Translations:\n\n" + "\n\n".join(results)
        update.message.reply_text(output, reply_to_message_id=msg_id)
    else:
        update.message.reply_text("⚠️ 번역 결과가 없습니다.", reply_to_message_id=msg_id)

# =============== 명령어 핸들러 ===============
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

def cmd_set(update, context):
    user_id = update.message.from_user.id
    try:
        raw = context.args[0]
        modes = [int(x) for x in raw.split(',')]
        for m in modes:
            if m not in [0, 1, 2, 3, 4]:
                raise ValueError
        user_modes[user_id] = modes
        update.message.reply_text(f"✅ 번역 모드가 /set {raw} 으로 설정되었습니다.")
    except:
        update.message.reply_text("❌ 사용법: /set [0~4] 또는 /set 1,2,3 형식으로 입력")

def cmd_mode(update, context):
    user_id = update.message.from_user.id
    modes = user_modes.get(user_id, [0])
    if modes == [0]:
        update.message.reply_text("🌐 현재 모드: 자동 번역 모드 (/set 0)")
    else:
        langs = [TARGET_LANGS[m][1] for m in modes if m in TARGET_LANGS]
        update.message.reply_text(f"🈯 현재 번역 대상 언어: {', '.join(langs)} (/set {','.join(map(str, modes))})")


# 1-A) my_chat_member 전용 (봇이 추가/차단/복귀 될 때)
def on_my_chat_member(update, context):
    if isBotJoin == True:
        isBotJoin = False
        return
    
    chat = update.my_chat_member.chat
    new_status = update.my_chat_member.new_chat_member.status  # 'member', 'administrator', 'kicked', etc.

    # 봇이 방에 정상 참가 상태가 될 때만 환영 메시지
    if new_status in ("member", "administrator"):
        welcome_msg = (
             "🤖 **NWG Global Translator** activated!\n\n"
                    "Available commands:\n"
                    "• /on — Enable translation\n"
                    "• /off — Disable translation\n"
                    "• /set [0~4 or combination] — Set translation languages (e.g., /set 1,2)\n"
                    "• 1. 🇺🇸 English\n"
                    "• 2. 🇯🇵 Japanese\n"
                    "• 3. 🇨🇳 Chinese\n"
                    "• 4. 🇰🇷 Korean\n"
                    "• /mode — View current translation mode\n\n"
                    "🗣️ Now, when you type a message, it will automatically be translated into the selected languages!"
        )
        context.bot.send_message(chat.id, welcome_msg, parse_mode="Markdown")

# 1-B) 메시지의 new_chat_members 경로 (방에 누가 들어왔을 때)

def on_new_members(update, context):
    isBotJoin = True
    # 봇 자신이 들어온 경우만 환영
    for member in update.message.new_chat_members:
        if member.id == context.bot.id:
            welcome_msg = (
                 "🤖 **NWG Global Translator** activated!\n\n"
                    "Available commands:\n"
                    "• /on — Enable translation\n"
                    "• /off — Disable translation\n"
                    "• /set [0~4 or combination] — Set translation languages (e.g., /set 1,2)\n"
                    "• 1. 🇺🇸 English\n"
                    "• 2. 🇯🇵 Japanese\n"
                    "• 3. 🇨🇳 Chinese\n"
                    "• 4. 🇰🇷 Korean\n"
                    "• /mode — View current translation mode\n\n"
                    "🗣️ Now, when you type a message, it will automatically be translated into the selected languages!"
            )
            update.message.reply_text(welcome_msg, parse_mode="Markdown")

# =============== 실행 설정 ===============
updater = Updater(BOT_TOKEN, use_context=True)
dp = updater.dispatcher

dp.add_handler(CommandHandler("on", cmd_on))
dp.add_handler(CommandHandler("off", cmd_off))
dp.add_handler(CommandHandler("set", cmd_set))
dp.add_handler(CommandHandler("mode", cmd_mode))
dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_text))
# 교체: 두 경로 모두 등록
dp.add_handler(ChatMemberHandler(on_my_chat_member, ChatMemberHandler.MY_CHAT_MEMBER))
dp.add_handler(MessageHandler(Filters.status_update.new_chat_members, on_new_members))


print("🤖 NWG Global Translator (OpenAI + /set + /mode + Auto-Welcome) Running...")
updater.start_polling()
updater.idle()
