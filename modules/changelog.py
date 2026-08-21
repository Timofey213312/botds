"""
Модуль changelog — публикация сводки изменений от имени бота в канал новостей
- !changelog — постит красивую сводку обо всех обновлениях в 📢-новости
"""

import logging
from datetime import datetime

import discord
from discord.ext import commands

logger = logging.getLogger('discord_bot.changelog')

NEWS_KEYWORDS = ('новости', 'news')
EMBED_COLOR = 0x9000FF

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


def _build_embed():
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
    embed.set_footer(text="Vector.prod • Changelog")
    return embed


def setup_changelog(bot):
    @bot.hybrid_command(name="changelog", description="Опубликовать сводку изменений в канал новостей")
    async def changelog_cmd(ctx: commands.Context):
        try:
            if not (ctx.author.guild_permissions.manage_channels or ctx.author.guild_permissions.administrator):
                await ctx.send("❌ Недостаточно прав.", ephemeral=True)
                return
            channel = _find_channel(ctx.guild, NEWS_KEYWORDS)
            if channel is None:
                await ctx.send("❌ Канал новостей не найден (в названии должно быть «новости»).", ephemeral=True)
                return
            await channel.send(embed=_build_embed())
            await ctx.send(f"✅ Сводка опубликована в {channel.mention}", ephemeral=True)
            logger.info(f'{ctx.author} опубликовал changelog в {channel.name}')
        except Exception as e:
            await ctx.send(f"❌ Ошибка: {e}", ephemeral=True)
            logger.error(f'Ошибка changelog: {e}')

    logger.info('Модуль changelog загружен (команда !changelog)')
