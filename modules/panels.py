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


async def _find_or_send(channel, label, build):
    """Удаляет все панели с этим label в канале и отправляет одну новую"""
    removed = 0
    try:
        messages = await _collect_panels(channel, label)
        for msg in messages:
            await msg.delete()
            removed += 1
    except Exception as e:
        logger.error(f'Ошибка удаления старых панелей в {channel.name}: {e}')
    embed, view = build(channel.guild)
    await channel.send(embed=embed, view=view)
    return removed


async def setup_all_panels(guild, author=None):
    """Пересоздаёт ВСЕ панели в нужных каналах, удаляя старые.
    Возвращает список строк с результатами."""
    results = []

    # 1. Текстовые панели (идеи, тикеты, войсы) — из реестра
    for panel in _registry:
        channel = _find_channel(guild, panel['channel_keywords'])
        if channel is None:
            results.append(f"⚠️ Канал для «{panel['label']}» не найден")
            continue
        removed = await _find_or_send(channel, panel['label'], panel['build'])
        results.append(f"✅ «{panel['label']}» → {channel.mention} (удалено старых: {removed})")

    # 2. Музыкальная панель — в голосовой канал (где автор или где бот)
    music_panel = getattr(guild.bot, 'ensure_music_panel', None)
    if music_panel:
        target_channel = None
        if author and author.voice and author.voice.channel:
            target_channel = author.voice.channel
        else:
            vc = guild.voice_client
            target_channel = vc.channel if vc else None
        if target_channel is None:
            results.append("⚠️ Музыкальная панель не размещена: нет голосового канала (зайди в войс)")
        else:
            await music_panel(guild.id, target_channel, force=True)
            results.append(f"✅ Музыкальная панель → {target_channel.mention}")

    return results


def setup_panels(bot):
    """Настройка команды !setup-panels"""
    from discord.ext import commands

    @bot.hybrid_command(name="setup-panels", description="Пересоздать все панели в нужных каналах (удаляет старые)")
    async def setup_panels_cmd(ctx: commands.Context):
        """Размещение всех панелей в правильных каналах"""
        try:
            if not ctx.author.guild_permissions.administrator:
                await ctx.send("❌ Только администратор может выполнить эту команду.", ephemeral=True)
                return
            await ctx.defer(ephemeral=True)
            results = await setup_all_panels(ctx.guild, author=ctx.author)
            await ctx.followup.send("\n".join(results), ephemeral=True)
            logger.info(f'{ctx.author} пересоздал все панели')
        except Exception as e:
            await ctx.send(f"❌ Ошибка: {e}", ephemeral=True)
            logger.error(f'Ошибка setup-panels: {e}')

    logger.info('Модуль панелей загружен (команда !setup-panels)')
