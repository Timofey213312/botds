"""
Авто-восстановление панелей с кнопками после рестарта бота.
При старте бот находит панели (по названию канала и label кнопки)
и пересоздаёт те, у которых custom_id устарел — иначе кнопки «умирают».
"""

import logging

import discord

logger = logging.getLogger('discord_bot.panels')

# Реестр панелей: каждый модуль регистрирует свою через register_panel()
_registry = []


def register_panel(channel_keywords, label, expected_ids, build):
    """Регистрация панели для авто-восстановления"""
    _registry.append({
        'channel_keywords': channel_keywords,
        'label': label,
        'expected_ids': set(expected_ids),
        'build': build,
    })


def _find_channel(guild, keywords):
    for channel in guild.text_channels:
        name = (channel.name or '').lower()
        for kw in keywords:
            if kw in name:
                return channel
    return None


async def _collect_panels(channel, label):
    """Собирает сообщения бота в канале, содержащие нужную кнопку"""
    found = []
    try:
        async for message in channel.history(limit=80):
            if message.author.id != channel.guild.me.id:
                continue
            for row in message.components:
                for comp in row.children:
                    if isinstance(comp, discord.Button) and comp.label == label:
                        found.append(message)
                        break
    except Exception as e:
        logger.error(f'Ошибка поиска панели в {channel.name}: {e}')
    return found


async def restore_panels(bot):
    """Основная функция: пересоздаёт панели с устаревшими custom_id"""
    logger.info('Авто-восстановление панелей: начало')
    restored = 0
    for guild in bot.guilds:
        for panel in _registry:
            channel = _find_channel(guild, panel['channel_keywords'])
            if channel is None:
                continue
            try:
                messages = await _collect_panels(channel, panel['label'])
                for msg in messages:
                    # Проверяем, совпадают ли custom_id с актуальными
                    current_ids = set()
                    for row in msg.components:
                        for comp in row.children:
                            if isinstance(comp, discord.Button) and comp.custom_id:
                                current_ids.add(comp.custom_id)
                    if current_ids == panel['expected_ids']:
                        continue  # панель актуальна — не трогаем
                    # Панель устарела/мёртвая — пересоздаём
                    await msg.delete()
                    embed, view = panel['build'](guild)
                    await channel.send(embed=embed, view=view)
                    restored += 1
                    logger.info(f'Панель «{panel["label"]}» пересоздана в {channel.name}')
            except Exception as e:
                logger.error(f'Ошибка восстановления панели в {channel.name}: {e}')
    logger.info(f'Авто-восстановление панелей завершено, пересоздано: {restored}')
