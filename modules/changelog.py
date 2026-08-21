"""
Модуль auto-changelog
- При каждом новом обновлении бота (смена VERSION) весь changelog постится
  в канал 📣-объявления-клана от имени бота.
- Чтобы опубликовать при следующем запуске — обнови VERSION и CHANGELOG.
"""

import logging
import os
from datetime import datetime

import discord

logger = logging.getLogger('discord_bot.changelog')

VERSION = "2026-08-22"
NEWS_KEYWORDS = ('объявления-клана', 'объявления', 'announce', 'новости')
EMBED_COLOR = 0x9000FF
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data')
VERSION_FILE = os.path.join(DATA_DIR, 'last_changelog.txt')

CHANGELOG = (
    ("🔧 Модерация", [
        "Новые команды: unmute, massban, multikick, botclear, cleanup, roleall, derole, voicedeafen / voiceundeafen, modlog, snipe",
        "Все команды бота теперь доступны только модерации",
    ]),
    ("🎫 Тикеты", [
        "Выбор темы тикета через выпадающий список",
        "Красивые эмбеды, подтверждение закрытия, сохранение транскрипта",
    ]),
    ("💡 Идеи", [
        "Обновлённые эстетичные эмбеды",
        "Канал приёма идей: 🔨-📥-приём-идей",
    ]),
    ("📝 Заявки (канальный формат)", [
        "Заявка открывает приватный канал с вопросами — ответ прямо в канале",
        "Клан (11 вопросов), Медиа (5 вопросов), Модераторы",
        "Кнопки: Принять / Отклонить / Закрыть",
    ]),
    ("🛒 Купи-продай", [
        "Форма объявления: тип сделки, товар, цена, описание, контакт",
        "Авто-цвет (продажа — зелёная, покупка — синяя), кнопка снятия",
    ]),
    ("🤖 Антиреклама (OCR)", [
        "Удаление рекламных фото через распознавание текста (Tesseract)",
    ]),
    ("🔗 Автомод", [
        "Запрет ссылок везде, кроме медиа-канала (там только YouTube)",
    ]),
)


def _find_channel(guild, keywords):
    for channel in guild.text_channels:
        name = (channel.name or '').lower()
        if any(kw in name for kw in keywords):
            return channel
    return None


def build_changelog_embed():
    embed = discord.Embed(
        title="📢 Обновление бота",
        description="Собрали всё новое и улучшенное в одном месте. Приятного использования! ✨",
        color=EMBED_COLOR,
        timestamp=datetime.now(),
    )
    for title, items in CHANGELOG:
        embed.add_field(
            name=title,
            value="\n".join(f"• {i}" for i in items),
            inline=False,
        )
    embed.set_footer(text=f"Vector.prod • Changelog • v{VERSION}")
    return embed


async def post_full_changelog(bot):
    for guild in bot.guilds:
        channel = _find_channel(guild, NEWS_KEYWORDS)
        if channel is None:
            continue
        try:
            await channel.send(embed=build_changelog_embed())
            logger.info(f'Changelog опубликован в {channel.name} (v{VERSION})')
        except Exception as e:
            logger.error(f'Ошибка публикации changelog в {channel.name}: {e}')


async def maybe_post_on_startup(bot):
    """Постит changelog только если VERSION изменилась с прошлого запуска"""
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        last = ""
        if os.path.exists(VERSION_FILE):
            with open(VERSION_FILE, 'r', encoding='utf-8') as f:
                last = f.read().strip()
        if last == VERSION:
            logger.info(f'Changelog актуален (v{VERSION}), публикация не требуется')
            return
        await post_full_changelog(bot)
        with open(VERSION_FILE, 'w', encoding='utf-8') as f:
            f.write(VERSION)
    except Exception as e:
        logger.error(f'Ошибка авто-публикации changelog: {e}')
