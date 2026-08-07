"""
Модуль приветствия новых участников
Канал: 👋-добро-пожаловать
"""

import logging

import discord
from discord.ext import commands

logger = logging.getLogger('discord_bot.welcome')

# Ключевые слова для поиска канала приветствия
WELCOME_CHANNEL_KEYWORDS = ('добро-пожаловать', 'добро-пожаловат', 'welcome', 'привет')

GIF_URL = 'https://i.ibb.co/Df3Bq6pp/2645475a9eef90f4a1fe67b76ae7d9fa.gif'
RULES_LINK = 'https://discord.com/channels/1418133713421598802/1418133714382094379'
MEDIA_LINK = 'https://discord.com/channels/1418133713421598802/1418133714382094381'
EMBED_COLOR = 0x9000FF


def _find_welcome_channel(guild):
    """Поиск канала приветствия по названию"""
    for channel in guild.text_channels:
        name = (channel.name or '').lower()
        for kw in WELCOME_CHANNEL_KEYWORDS:
            if kw in name:
                return channel
    return None


def _find_boost_channel(guild):
    """Поиск канала для благодарностей за буст (иначе канал приветствия)"""
    for channel in guild.text_channels:
        name = (channel.name or '').lower()
        if 'буст' in name or 'boost' in name or 'благодар' in name:
            return channel
    return _find_welcome_channel(guild)


def build_welcome_embed(member, guild):
    """Сборка embed приветствия для нового участника (шаблон)"""
    embed = discord.Embed(
        description=(
            f"Привет — {member.mention}ㅤ\n"
            f"Добро пожаловать на сервер {guild.name}\n"
            f"\n"
            f"\n"
            f"Это несомненно лучший доминирующий\n"
            f"клан на ReallyWorld\n"
            f"\n"
            f"\n"
            f"Советую ознакомиться с правилами\n"
            f"в разделе — {RULES_LINK}\n"
            f"Можешь взглянуть на медиа ролики и\n"
            f"найти любимчика — {MEDIA_LINK}\n"
            f"\n"
            f"\n"
            f"Желаем удачи на {guild.name}\n"
        ),
        color=EMBED_COLOR,
    )
    embed.set_author(name="Vector.Prod | Console")
    embed.set_image(url=GIF_URL)
    embed.set_footer(text=f"Всего участников: {guild.member_count}")
    return embed


def build_boost_embed(member, guild):
    """Сборка embed благодарности за буст сервера"""
    embed = discord.Embed(
        title=f"🎉 Спасибо за буст",
        description=(
            f"Приветствую тебя дорогой {member.mention},\n"
            f"ты подарил нам **буст сервера**, тем самым ты продвинул клан,\n"
            f"вся наша команда клана выражает тебе благодарность.\n"
            f"\n"
            f"С уважением, Администрация {guild.name}"
        ),
        color=EMBED_COLOR,
    )
    embed.set_author(name="Vector.Prod | Console")
    return embed


def setup_welcome(bot):
    """Настройка приветствия"""

    async def send_welcome(member, guild):
        channel = _find_welcome_channel(guild)
        if not channel:
            logger.info(f'Канал приветствия не найден на сервере {guild.name}')
            return False
        embed = build_welcome_embed(member, guild)
        await channel.send(
            embed=embed,
            allowed_mentions=discord.AllowedMentions(users=True, roles=False, everyone=False),
        )
        return True

    @bot.event
    async def on_member_join(member):
        """Отправка приветствия новому участнику"""
        try:
            await send_welcome(member, member.guild)
            logger.info(f'Отправлено приветствие для {member} на сервере {member.guild.name}')
        except Exception as e:
            logger.error(f'Ошибка отправки приветствия для {member}: {e}')

    @bot.event
    async def on_member_update(before, after):
        """Благодарность за новый буст сервера"""
        if after.premium_since is None:
            return
        if before.premium_since is not None:
            return
        try:
            channel = _find_boost_channel(after.guild)
            if not channel:
                logger.info(f'Канал благодарностей не найден на сервере {after.guild.name}')
                return
            embed = build_boost_embed(after, after.guild)
            await channel.send(embed=embed)
            logger.info(f'Отправлена благодарность за буст от {after} на сервере {after.guild.name}')
        except Exception as e:
            logger.error(f'Ошибка отправки благодарности за буст: {e}')

    logger.info("Модуль приветствия загружен")
