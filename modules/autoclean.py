"""
Модуль автозачистки сообщений в голосовых каналах
Каждые 10 минут удаляет все сообщения из текстовых чатов, привязанных к голосовым каналам
"""

import logging

import discord
from discord.ext import commands, tasks

logger = logging.getLogger('discord_bot.autoclean')

CLEAN_INTERVAL_MINUTES = 10


def _linked_text_channel(vc):
    """Поиск текстового чата, привязанного к голосовому каналу"""
    for ch in vc.guild.text_channels:
        if ch.category_id == vc.category_id and (ch.name or '').lower() == (vc.name or '').lower():
            return ch
    return None


async def _clean_voice_channel(vc):
    """Очистка сообщений в привязанном к голосовому каналу текстовом чате"""
    if not vc.permissions_for(vc.guild.me).manage_messages:
        return
    # Ищем настоящий текстовый канал (там работает быстрое массовое удаление)
    target = _linked_text_channel(vc) or vc
    try:
        deleted = await target.purge(limit=None, check=lambda m: not m.pinned)
        if deleted:
            logger.info(f'Очищено {len(deleted)} сообщений в {vc.guild.name} / {vc.name}')
    except discord.Forbidden:
        pass
    except discord.HTTPException:
        pass
    except Exception as e:
        logger.error(f'Ошибка очистки {vc.guild.name} / {vc.name}: {e}')


def setup_autoclean(bot):
    """Настройка автозачистки голосовых каналов"""

    @tasks.loop(minutes=CLEAN_INTERVAL_MINUTES)
    async def clean_voice_channels():
        for guild in bot.guilds:
            for vc in guild.voice_channels:
                await _clean_voice_channel(vc)

    @clean_voice_channels.before_loop
    async def before_clean():
        await bot.wait_until_ready()

    bot.autoclean_loop = clean_voice_channels
    logger.info(f'Модуль автозачистки загружен (каждые {CLEAN_INTERVAL_MINUTES} минут)')
