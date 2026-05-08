import socks
import asyncio
from telethon import TelegramClient, events
from telethon.tl.functions.messages import ImportChatInviteRequest
from telegram import Bot
import os
import re
import time
import logging
from config import API_ID, API_HASH, BOT_TOKEN, TARGET_CHANNEL, PROXY, CHANNELS, PRIVATE_CHANNELS

# НАСТРОЙКА ЛОГИРОВАНИЯ
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("bot.log", encoding="utf-8"),
        logging.StreamHandler()
    ]
)

# CLIENT
client = TelegramClient(
    'session_name',
    API_ID,
    API_HASH,
    proxy=(socks.SOCKS5, PROXY[0], PROXY[1]),
    timeout=20
)

# BOT
bot = Bot(token=BOT_TOKEN)

# КЛЮЧЕВОЕ СЛОВО
KEYWORD = 'куплю'

# ЗАГРУЖАЕМ КАТАЛОГ МОДЕЛЕЙ
MODELS_FILE = 'models.txt'
models = set()
if os.path.exists(MODELS_FILE):
    with open(MODELS_FILE, 'r', encoding='utf-8') as f:
        for line in f:
            model = line.strip().lower()
            if model:
                models.add(model)
else:
    logging.warning(f"Файл {MODELS_FILE} не найден. Фильтр по моделям не будет работать.")

logging.info(f"Загружено моделей: {len(models)}")

# Функция экранирования MarkdownV2
def escape_md(text: str) -> str:
    if not text:
        return ""
    return re.sub(r'([_\*\[\]\(\)~>`#+\-=|{}.!])', r'\\\1', text)

# ВРЕМЯ СТАРТА
START_TIME = time.time()

# множество для фильтрации повторных сообщений
sent_messages = set()

async def get_channels():
    channels = []

    # публичные
    for ch in CHANNELS:
        entity = await client.get_entity(ch)
        channels.append(entity)

    # приватные
    for link in PRIVATE_CHANNELS:
        try:
            # Проверяем через get_entity, если уже участник
            entity = await client.get_entity(link)
            channels.append(entity)
        except Exception:
            # Если не участник, делаем импорт
            try:
                entity = await client(ImportChatInviteRequest(link.split('+')[-1]))
                channels.append(entity.chats[0])
            except Exception as e:
                logging.error(f"Не удалось подключиться к приватному каналу {link}: {e}")

    return channels

async def handler(event):
    if event.message.date.timestamp() < START_TIME:
        return

    if event.message.id in sent_messages:
        return

    text = event.message.text
    if not text:
        return

    text_lower = text.lower()
    if KEYWORD.lower() not in text_lower:
        return

    matched_model = next((m for m in models if m in text_lower), None)
    if not matched_model:
        return

    # Добавляем ID в множество, чтобы не дублировать
    sent_messages.add(event.message.id)

    chat = await event.get_chat()
    sender = await event.get_sender()
    username = getattr(sender, 'username', None)
    first_name = getattr(sender, 'first_name', 'Неизвестно')
    sender_info = f"@{username}" if username else first_name
    message_link = f"https://t.me/{chat.username}/{event.message.id}" if getattr(chat, 'username', None) else ""

    result_message = (
        f"*Канал:* {escape_md(chat.title)}\n"
        f"*Отправитель:* {escape_md(sender_info)}\n"
        f"*Модель:* {escape_md(matched_model)}\n"
        f"*Сообщение:*\n_{escape_md(text)}_\n"
        f"{escape_md(message_link)}"
    )

    await bot.send_message(
        chat_id=TARGET_CHANNEL,
        text=result_message,
        parse_mode="MarkdownV2"
    )

    logging.info(f"Сообщение отправлено в канал. Модель: {matched_model}")

async def main():
    await client.start()
    me = await client.get_me()
    logging.info(f"Вошел как: {me.first_name}")
    logging.info("Бот запущен... Ожидаем сообщения...")

    all_channels = await get_channels()
    client.add_event_handler(handler, events.NewMessage(chats=all_channels))

    await client.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())