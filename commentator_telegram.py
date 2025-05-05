import os
import logging
import asyncio
import csv
from datetime import datetime
from pyrogram import Client, errors
from pyrogram.types import Message
from pyrogram.enums import ChatType
from pyrogram.raw.functions import updates
from pyrogram.raw.types import updates as raw_updates
from openai import OpenAI
import aiohttp
import time

# Telegram API Credentials
API_ID = ""
API_HASH = ""
PHONE_NUMBER = ""

# OpenAI API Key
OPENAI_API_KEY = ""
ai_client = OpenAI(api_key=OPENAI_API_KEY)

# Telegram Bot для уведомлений
BOT_TOKEN = ""
NOTIFY_USERS = ["231", "@"]

# Задержки
COMMENT_DELAY = 600  # Задержка между комментариями для одного канала (в секундах)
GLOBAL_COMMENT_DELAY = 300  # Глобальная пауза между комментариями (в секундах)
RECONNECT_DELAY = 30  # Базовая задержка перед переподключением (в секундах)
MAX_RECONNECT_ATTEMPTS = 5  # Максимум попыток переподключения подряд

# Определяем возможные типы постов
ALLOWED_POST_TYPES = {
    "text": True,
    "text_photo": True,
    "text_video": True,
    "text_document": True,
    "text_audio": True,
    "photo": False,
    "video": False,
    "document": False,
    "audio": False
}

# Настройка логирования
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)
# Подавляем логи Pyrogram о подключениях
logging.getLogger("pyrogram").setLevel(logging.WARNING)

# Запуск Pyrogram-клиента
app = Client(
    "my_account",
    api_id=API_ID,
    api_hash=API_HASH,
    phone_number=PHONE_NUMBER,
    device_model="iPhone 14",
    system_version="16.0",
    app_version="8.9.0",
    lang_code="en"
)

# Хранилище данных сессии
last_message_ids = {}
last_comment_times = {}
state = None
start_time = datetime.now()
blacklist = set()
processed_posts = set()
reconnect_attempts = 0

# Файлы для blacklist, отчётов и обработанных постов
BLACKLIST_FILE = "blacklist.txt"
REPORTS_FILE = "reports.csv"
PROCESSED_POSTS_FILE = "processed_posts.txt"

# Загрузка blacklist и processed_posts
def load_blacklist_and_posts():
    global blacklist, processed_posts
    if os.path.exists(BLACKLIST_FILE):
        try:
            with open(BLACKLIST_FILE, "r") as f:
                blacklist.update(int(line.strip()) for line in f if line.strip())
            logger.info(f"ℹ️ Загружен blacklist: {len(blacklist)} записей")
        except Exception as e:
            logger.error(f"🚨 Ошибка чтения {BLACKLIST_FILE}: {e}")
    else:
        with open(BLACKLIST_FILE, "w") as f:
            pass

    if os.path.exists(PROCESSED_POSTS_FILE):
        try:
            with open(PROCESSED_POSTS_FILE, "r") as f:
                processed_posts.update(line.strip() for line in f if line.strip())
            logger.info(f"ℹ️ Загружен processed_posts: {len(processed_posts)} записей")
        except Exception as e:
            logger.error(f"🚨 Ошибка чтения {PROCESSED_POSTS_FILE}: {e}")
    else:
        with open(PROCESSED_POSTS_FILE, "w") as f:
            pass

# Сохранение blacklist
def save_blacklist(chat_id):
    global blacklist
    if chat_id not in blacklist:
        blacklist.add(chat_id)
        with open(BLACKLIST_FILE, "a") as f:
            f.write(f"{chat_id}\n")
        logger.info(f"ℹ️ Канал {chat_id} добавлен в blacklist")

# Сохранение processed_posts
def save_processed_post(chat_id, msg_id):
    global processed_posts
    key = f"{chat_id}:{msg_id}"
    if key not in processed_posts:
        processed_posts.add(key)
        with open(PROCESSED_POSTS_FILE, "a") as f:
            f.write(f"{key}\n")

# Сохранение отчёта в CSV
def save_report(chat_id, linked_chat_id, message, comment, tokens_in, tokens_out):
    report = {
        "date": datetime.now().isoformat(),
        "chat_id": chat_id,
        "linked_chat_id": linked_chat_id,
        "account_id": PHONE_NUMBER,
        "account_name": "my_account",
        "channel_title": message.chat.title,
        "channel_id": chat_id,
        "chat_title": message.chat.title,
        "chat_id_linked": linked_chat_id,
        "post_text": message.text or message.caption or "Нет текста",
        "post_type": get_post_type(message),
        "comment_text": comment,
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "tokens_total": tokens_in + tokens_out
    }
    file_exists = os.path.exists(REPORTS_FILE)
    with open(REPORTS_FILE, "a", newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=report.keys())
        if not file_exists:
            writer.writeheader()
        writer.writerow(report)

# Преобразование @login в Telegram ID
async def resolve_notify_users(client: Client, notify_users: list) -> list:
    resolved_ids = []
    for user in notify_users:
        try:
            if user.startswith('@'):
                username = user[1:]
                user_obj = await client.get_users(username)
                resolved_ids.append(str(user_obj.id))
                logger.info(f"ℹ️ Логин {user} преобразован в ID: {user_obj.id}")
            else:
                resolved_ids.append(user)
        except Exception as e:
            logger.error(f"🚨 Ошибка при преобразовании {user}: {e}")
    return resolved_ids

# Отправка уведомления через Telegram-бот
async def send_notification(client: Client, chat_title: str, comment: str, notify_users: list):
    async with aiohttp.ClientSession() as session:
        resolved_users = await resolve_notify_users(client, notify_users)
        for user_id in resolved_users:
            try:
                url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
                payload = {
                    "chat_id": user_id,
                    "text": f"✅ Успешный комментарий в '{chat_title}': {comment}",
                    "parse_mode": "Markdown"
                }
                logger.debug(f"ℹ️ Отправка уведомления для ID: {user_id}")
                async with session.post(url, json=payload, ssl=False) as response:
                    if response.status != 200:
                        logger.warning(f"⚠️ Не удалось отправить уведомление для {user_id}: {await response.text()}")
            except Exception as e:
                logger.warning(f"⚠️ Ошибка отправки уведомления для {user_id}: {e}")

# Генерация комментария через OpenAI
async def generate_comment(post_text: str) -> tuple[str, int, int]:
    try:
        response = ai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a witty assistant creating comments for Telegram posts."},
                {"role": "system", "content": "First, analyze the post, if it's gore, porno, violence, death, crime, catastrophe, etc. - then reply REJECT."},
                {"role": "user", "content": f"Write cheerful, witty comment (10-20 words) in the same language as this post: {post_text}. No  emoji. "}
            ],
            max_tokens=50,
            temperature=0.7
        )
        tokens_in = len(post_text.split())
        tokens_out = len(response.choices[0].message.content.split())
        return response.choices[0].message.content.strip(), tokens_in, tokens_out
    except Exception as e:
        logger.error(f"🚨 Ошибка генерации комментария: {e}")
        return "", 0, 0

# Проверка типа поста
def get_post_type(message: Message) -> str:
    has_text = bool(message.text or message.caption)
    has_photo = bool(message.photo)
    has_video = bool(message.video)
    has_document = bool(message.document)
    has_audio = bool(message.audio)

    if has_text:
        if has_photo: return "text_photo"
        elif has_video: return "text_video"
        elif has_document: return "text_document"
        elif has_audio: return "text_audio"
        return "text"
    elif has_photo: return "photo"
    elif has_video: return "video"
    elif has_document: return "document"
    elif has_audio: return "audio"
    return "unknown"

# Проверка возможности комментирования
async def can_comment(client: Client, chat_id: int) -> tuple[bool, int | None]:
    if chat_id in blacklist:
        logger.debug(f"ℹ️ Канал {chat_id} в blacklist, пропускаем")
        return False, None
    try:
        chat_info = await client.get_chat(chat_id)
        if chat_info.linked_chat:
            linked_chat_id = chat_info.linked_chat.id
            logger.debug(f"🔗 Найден привязанный чат: {linked_chat_id}")
            return True, linked_chat_id
        save_blacklist(chat_id)
        return False, None
    except errors.FloodWait as fw:
        logger.warning(f"⏳ Flood wait для {chat_id}: ждём {fw.value} секунд")
        await asyncio.sleep(fw.value)
        return False, None
    except Exception as e:
        logger.error(f"🚨 Ошибка проверки комментирования для {chat_id}: {e}")
        return False, None

# Обработка сообщений
async def process_message(client: Client, message: Message):
    chat_id = message.chat.id
    chat_title = message.chat.title or f"Chat ID {chat_id}"
    message_id = message.id
    message_time = message.date
    post_key = f"{chat_id}:{message_id}"

    if post_key in processed_posts:
        return

    if message_time < start_time:
        save_processed_post(chat_id, message_id)
        return

    current_time = datetime.now()
    last_comment_time = last_comment_times.get(chat_id)
    if last_comment_time and (current_time - last_comment_time).total_seconds() < COMMENT_DELAY:
        save_processed_post(chat_id, message_id)
        return

    post_type = get_post_type(message)
    if not ALLOWED_POST_TYPES.get(post_type, False):
        save_processed_post(chat_id, message_id)
        return

    logger.info(f"🔔 Новый пост в '{chat_title}' (ID: {chat_id})")

    can_comment_result, linked_chat_id = await can_comment(client, chat_id)
    if not can_comment_result:
        save_processed_post(chat_id, message_id)
        return

    target_message = None
    for _ in range(5):
        async for linked_msg in client.get_chat_history(linked_chat_id, limit=50):
            if (linked_msg.forward_from_chat and linked_msg.forward_from_chat.id == chat_id and
                linked_msg.forward_from_message_id == message_id) or \
               (linked_msg.from_user is None and linked_msg.sender_chat and linked_msg.sender_chat.id == chat_id and
                linked_msg.text == (message.text or message.caption)):
                target_message = linked_msg
                break
        if target_message:
            break
        await asyncio.sleep(2)

    if not target_message:
        save_processed_post(chat_id, message_id)
        return

    try:
        await client.get_chat_member(linked_chat_id, "me")
    except errors.BadRequest as e:
        if "USER_BANNED_IN_CHANNEL" in str(e) or "USER_NOT_PARTICIPANT" in str(e):
            try:
                await client.join_chat(linked_chat_id)
                await client.get_chat_member(linked_chat_id, "me")
            except errors.BadRequest as join_e:
                if "INVITE_REQUEST_SENT" in str(join_e):
                    save_processed_post(chat_id, message_id)
                    return
                else:
                    logger.error(f"🚨 Ошибка вступления в {linked_chat_id}: {join_e}")
                    save_processed_post(chat_id, message_id)
                    return
            except errors.FloodWait as fw:
                logger.warning(f"⏳ Flood wait при вступлении в {linked_chat_id}: ждём {fw.value} секунд")
                await asyncio.sleep(fw.value)
                save_processed_post(chat_id, message_id)
                return
            except Exception as join_e:
                logger.error(f"🚨 Ошибка вступления в {linked_chat_id}: {join_e}")
                save_processed_post(chat_id, message_id)
                return
        else:
            logger.error(f"🚨 Ошибка проверки доступа к {linked_chat_id}: {e}")
            save_processed_post(chat_id, message_id)
            return
    except Exception as e:
        logger.error(f"🚨 Ошибка проверки статуса в {linked_chat_id}: {e}")
        save_processed_post(chat_id, message_id)
        return

    comment, tokens_in, tokens_out = await generate_comment(message.text or message.caption or "")
    if comment == "REJECT" or not comment:
        save_processed_post(chat_id, message_id)
        return

    comment = comment.strip('"\'')
    try:
        await client.send_message(linked_chat_id, comment, reply_to_message_id=target_message.id)
        logger.info(f"✅ Комментарий отправлен в '{chat_title}': {comment}")
        save_report(chat_id, linked_chat_id, message, comment, tokens_in, tokens_out)
        last_comment_times[chat_id] = datetime.now()
        last_message_ids[chat_id] = message_id
        await send_notification(client, chat_title, comment, NOTIFY_USERS)
        await asyncio.sleep(GLOBAL_COMMENT_DELAY)
    except (errors.Forbidden, errors.ChatWriteForbidden) as e:
        logger.info(f"❌ Нет прав на отправку в {linked_chat_id}: {e}")
        save_blacklist(chat_id)
    except errors.FloodWait as fw:
        logger.warning(f"⏳ Flood wait при отправке в {linked_chat_id}: ждём {fw.value} секунд")
        await asyncio.sleep(fw.value)
    except Exception as e:
        logger.error(f"🚨 Ошибка отправки в {linked_chat_id}: {e}")
    save_processed_post(chat_id, message_id)

# Низкоуровневая обработка обновлений
async def fetch_updates(client: Client):
    global state, reconnect_attempts
    while True:
        try:
            if state is None:
                state = await client.invoke(updates.GetState())
                logger.info(f"📡 Инициализировано состояние обновлений")
                reconnect_attempts = 0  # Сбрасываем счётчик при успешном подключении

            difference = await client.invoke(
                updates.GetDifference(
                    pts=state.pts,
                    qts=state.qts,
                    date=state.date
                )
            )

            if isinstance(difference, raw_updates.DifferenceEmpty):
                logger.debug("📡 Нет новых обновлений")
            elif isinstance(difference, raw_updates.Difference):
                for msg in difference.new_messages:
                    chat_id = getattr(msg.peer_id, 'channel_id', None)
                    if chat_id and chat_id not in blacklist:
                        message = await client.get_messages(chat_id, msg.id)
                        if message and message.chat.type == ChatType.CHANNEL:
                            await process_message(client, message)
                state.pts = difference.state.pts
                state.qts = difference.state.qts
                state.date = difference.state.date
            elif isinstance(difference, raw_updates.DifferenceSlice):
                for msg in difference.new_messages:
                    chat_id = getattr(msg.peer_id, 'channel_id', None)
                    if chat_id and chat_id not in blacklist:
                        message = await client.get_messages(chat_id, msg.id)
                        if message and message.chat.type == ChatType.CHANNEL:
                            await process_message(client, message)
                state.pts = difference.intermediate_state.pts
                state.qts = difference.intermediate_state.qts
                state.date = difference.intermediate_state.date
            else:
                logger.warning("📡 Неизвестный тип разницы, обновляем состояние")
                state = await client.invoke(updates.GetState())
            reconnect_attempts = 0  # Сбрасываем счётчик при успешной операции
        except errors.ChannelPrivate:
            logger.info(f"❌ Канал приватный, добавлен в blacklist")
            save_blacklist(chat_id)
        except errors.FloodWait as fw:
            logger.warning(f"⏳ Flood wait при обновлениях: ждём {fw.value} секунд")
            await asyncio.sleep(fw.value)
        except (ConnectionResetError, OSError) as e:
            reconnect_attempts += 1
            if reconnect_attempts >= MAX_RECONNECT_ATTEMPTS:
                logger.error(f"🚨 Достигнуто максимум попыток переподключения ({MAX_RECONNECT_ATTEMPTS})")
                raise
            delay = RECONNECT_DELAY * (2 ** reconnect_attempts)  # Экспоненциальный backoff
            logger.warning(f"⚠️ Сетевая ошибка: {e}. Пауза {delay} секунд перед переподключением")
            await asyncio.sleep(delay)
        except Exception as e:
            logger.error(f"🚨 Ошибка при обновлениях: {e}")
        await asyncio.sleep(10)  # Увеличена пауза с 5 до 10 секунд

# Polling как резервный механизм
async def poll_channels(client: Client):
    global reconnect_attempts
    while True:
        try:
            async for dialog in client.get_dialogs():
                chat = dialog.chat
                if chat.type != ChatType.CHANNEL or chat.id in blacklist:
                    continue
                chat_id = chat.id
                async for msg in client.get_chat_history(chat_id, limit=1):
                    post_key = f"{chat_id}:{msg.id}"
                    if post_key in processed_posts:
                        continue
                    if chat_id not in last_message_ids or msg.id > last_message_ids[chat_id]:
                        await process_message(client, msg)
            reconnect_attempts = 0  # Сбрасываем счётчик при успешной операции
        except errors.ChannelPrivate:
            logger.info(f"❌ Канал приватный, добавлен в blacklist")
            save_blacklist(chat_id)
        except errors.FloodWait as fw:
            logger.warning(f"⏳ Flood wait в polling: ждём {fw.value} секунд")
            await asyncio.sleep(fw.value)
        except (ConnectionResetError, OSError) as e:
            reconnect_attempts += 1
            if reconnect_attempts >= MAX_RECONNECT_ATTEMPTS:
                logger.error(f"🚨 Достигнуто максимум попыток переподключения ({MAX_RECONNECT_ATTEMPTS})")
                raise
            delay = RECONNECT_DELAY * (2 ** reconnect_attempts)  # Экспоненциальный backoff
            logger.warning(f"⚠️ Сетевая ошибка: {e}. Пауза {delay} секунд перед переподключением")
            await asyncio.sleep(delay)
        except Exception as e:
            logger.error(f"🚨 Ошибка в polling: {e}")
        await asyncio.sleep(30)  # Увеличена пауза с 10 до 30 секунд

# Хук на старт клиента
@app.on_raw_update()
async def on_client_start(client: Client, update, users, chats):
    if not hasattr(app, '_updates_task'):
        logger.info("🚀 Клиент запущен")
        load_blacklist_and_posts()
        app._updates_task = asyncio.create_task(fetch_updates(client))
        app._polling_task = asyncio.create_task(poll_channels(client))

# Точка входа
if __name__ == "__main__":
    logger.info("🚀 Запуск Telegram-комментатора")
    try:
        app.run()
    except errors.AuthKeyUnregistered:
        logger.error("🚨 Ошибка: [401 AUTH_KEY_UNREGISTERED] - Ключ авторизации не зарегистрирован")
        logger.info("ℹ️ Удалите файл 'my_account.session' и перезапустите скрипт")
    except errors.UserDeactivatedBan:
        logger.error("🚨 Ошибка: [401 USER_DEACTIVATED_BAN] - Аккаунт заблокирован Telegram")
        logger.info("ℹ️ Обратитесь в поддержку Telegram для восстановления аккаунта")
    except Exception as e:
        logger.error(f"🚨 Неизвестная ошибка при запуске: {e}")
