"""
Модуль логов модерации
Фиксирует кики, баны и разбаны в канале для логов
"""

import logging
from datetime import datetime

import discord
from discord.ext import commands
from discord import app_commands

logger = logging.getLogger('discord_bot.logger')

# Ключевые слова для поиска каналов логов
LOG_CHANNEL_KEYWORDS = ('логи', 'logs', 'мод-логи', 'audit', 'логи-модерации')
# Каналы для каждого типа события (проверяются первыми)
BAN_CHANNEL_KEYWORDS = ('бан', 'ban', 'баны')
UNBAN_CHANNEL_KEYWORDS = ('разбан', 'unban', 'анбан')
KICK_CHANNEL_KEYWORDS = ('кик', 'kick', 'кики')
TIMEOUT_CHANNEL_KEYWORDS = ('тайм-аут', 'таймаут', 'timeout', 'мут', 'mute', 'муты')
# Цвета событий
KICK_COLOR = 0xE67E22
BAN_COLOR = 0xE74C3C
UNBAN_COLOR = 0x2ECC71


def _find_channel_by_keywords(guild, keywords):
    """Поиск канала по ключевым словам"""
    for channel in guild.text_channels:
        name = (channel.name or '').lower()
        for kw in keywords:
            if kw in name:
                return channel
    return None


def _find_log_channel(guild):
    """Поиск общего канала логов по названию"""
    for channel in guild.text_channels:
        name = (channel.name or '').lower()
        if 'мод' in name or 'mod' in name:
            if any(kw in name for kw in ('логи', 'log')):
                return channel
        if any(kw in name for kw in LOG_CHANNEL_KEYWORDS):
            return channel
    return None


def _format_duration(after, before=None):
    """Формат длительности тайм-аута (после - до)"""
    try:
        end = after
        start = before
        if start is None:
            # Тайм-аут выдан "сейчас"
            delta = end - datetime.now()
        else:
            delta = end - start
        seconds = int(delta.total_seconds())
        if seconds <= 0:
            return "неизвестно"
        days, rem = divmod(seconds, 86400)
        hours, rem = divmod(rem, 3600)
        minutes, seconds = divmod(rem, 60)
        parts = []
        if days:
            parts.append(f"{days} дн")
        if hours:
            parts.append(f"{hours} ч")
        if minutes:
            parts.append(f"{minutes} мин")
        if seconds:
            parts.append(f"{seconds} сек")
        return " ".join(parts) if parts else "неизвестно"
    except Exception:
        return "неизвестно"


def _log_embed(title, color, action, target, executor, reason, guild):
    """Сборка embed лога"""
    # Человеческое название действия
    action_labels = {
        'ban': 'Бан',
        'unban': 'Разбан',
        'kick': 'Кик',
        'timeout': 'Тайм-аут',
        'untimeout': 'Снят тайм-аут',
    }
    display_action = action_labels.get(action, action)
    embed = discord.Embed(
        title=title,
        color=color,
        timestamp=datetime.now()
    )
    embed.add_field(name="🎯 Действие", value=display_action, inline=True)
    embed.add_field(name="👤 Пользователь", value=f"{target.mention}\n({target.name} · ID: `{target.id}`)", inline=True)
    embed.add_field(name="👮 Исполнитель", value=f"{executor.mention}\n({executor.name} · ID: `{executor.id}`)", inline=True)
    if reason and reason != "Не указана":
        embed.add_field(name="📝 Причина", value=reason, inline=False)
    embed.set_footer(text=f"Сервер: {guild.name}")
    return embed


async def log_mod_action(bot, guild, action_type, title, color, target, executor, reason="Не указана"):
    """Публичная отправка лога модерации (вызывается из команд модерации,
    чтобы лог попал в канал даже если действие сделано командой бота)."""
    try:
        embed = _log_embed(
            title=title,
            color=color,
            action=action_type,
            target=target,
            executor=executor,
            reason=reason,
            guild=guild,
        )
        return await _send_log(bot, guild, embed, action_type)
    except Exception as e:
        logger.error(f'Ошибка log_mod_action: {e}')
        return False


async def _send_log(bot, guild, embed, action_type):
    """Отправка лога в соответствующий канал"""
    # Нормализация названия типа (кириллица → английский ключ)
    norm_map = {
        'кик': 'kick', 'кики': 'kick',
        'бан': 'ban', 'баны': 'ban', 'забанен': 'ban',
        'разбан': 'unban', 'снят бан': 'unban',
        'мут': 'timeout', 'тайм-аут': 'timeout', 'таймаут': 'timeout',
        'снят тайм-аут': 'untimeout', 'снятие тайм-аута': 'untimeout',
    }
    action_type = norm_map.get(action_type, action_type)

    # Специфичный канал для типа события
    type_keywords = {
        'ban': BAN_CHANNEL_KEYWORDS,
        'unban': UNBAN_CHANNEL_KEYWORDS,
        'kick': KICK_CHANNEL_KEYWORDS,
        'timeout': TIMEOUT_CHANNEL_KEYWORDS,
        'untimeout': TIMEOUT_CHANNEL_KEYWORDS,
    }.get(action_type)

    channel = None
    if type_keywords:
        channel = _find_channel_by_keywords(guild, type_keywords)
    # Если специфичного канала нет — общий канал логов
    if channel is None:
        channel = _find_log_channel(guild)
    if not channel:
        logger.warning(f'Канал логов для действия «{action_type}» не найден на {guild.name}. '
                       f'Создай канал с названием «логи» или настрой !set-log')
        return False
    try:
        await channel.send(embed=embed)
        return True
    except discord.Forbidden:
        logger.error(f'Нет прав писать в канал {channel.name} на {guild.name}')
        return False
    except Exception as e:
        logger.error(f'Ошибка отправки лога на {guild.name}: {e}')
        return False


def setup_logger(bot):
    """Настройка системы логов"""

    # Доступ командам модерации для отправки логов в канал
    bot.mod_log = log_mod_action

    # Логирование банов и разбанов через audit log (надёжно определяет исполнителя)
    @bot.listen('on_audit_log_entry_create')
    async def log_mod_actions(entry):
        try:
            guild = entry.guild
            if not guild:
                return

            executor = entry.user
            if executor is None or executor.id == bot.user.id:
                return
            if executor.bot and executor.id != bot.user.id:
                return

            target = entry.target

            if entry.action == discord.AuditLogAction.ban:
                embed = _log_embed(
                    title="🔨 Участник забанен",
                    color=BAN_COLOR,
                    action="Бан",
                    target=target,
                    executor=executor,
                    reason=entry.reason,
                    guild=guild,
                )
                await _send_log(bot, guild, embed, 'ban')
                logger.info(f'ЛОГ: бан {target} от {executor}')

            elif entry.action == discord.AuditLogAction.member_update:
                # Проверяем, менялся ли тайм-аут (timeout)
                before_timeout = getattr(entry.before, 'timed_out_until', None)
                after_timeout = getattr(entry.after, 'timed_out_until', None)

                if before_timeout is None and after_timeout is not None:
                    # Тайм-аут выдан
                    duration = _format_duration(after_timeout, None)
                    embed = _log_embed(
                        title="🔇 Участник в тайм-ауте",
                        color=0x9B59B6,
                        action=f"Тайм-аут ({duration})",
                        target=target,
                        executor=executor,
                        reason=entry.reason,
                        guild=guild,
                    )
                    await _send_log(bot, guild, embed, 'timeout')
                    logger.info(f'ЛОГ: тайм-аут {target} от {executor} ({duration})')
                elif before_timeout is not None and after_timeout is None:
                    # Тайм-аут снят
                    embed = _log_embed(
                        title="🔓 Тайм-аут снят",
                        color=0x1ABC9C,
                        action="Снят тайм-аут",
                        target=target,
                        executor=executor,
                        reason=entry.reason,
                        guild=guild,
                    )
                    await _send_log(bot, guild, embed, 'untimeout')
                    logger.info(f'ЛОГ: снят тайм-аут {target} от {executor}')
                elif before_timeout is not None and after_timeout is not None and before_timeout != after_timeout:
                    # Тайм-аут продлён/изменён
                    duration = _format_duration(after_timeout, before_timeout)
                    embed = _log_embed(
                        title="🔇 Тайм-аут изменён",
                        color=0x9B59B6,
                        action=f"Тайм-аут изменён ({duration})",
                        target=target,
                        executor=executor,
                        reason=entry.reason,
                        guild=guild,
                    )
                    await _send_log(bot, guild, embed, 'timeout')
                    logger.info(f'ЛОГ: изменён тайм-аут {target} от {executor} ({duration})')

            elif entry.action == discord.AuditLogAction.unban:
                embed = _log_embed(
                    title="⚖️ Снят бан",
                    color=UNBAN_COLOR,
                    action="Разбан",
                    target=target,
                    executor=executor,
                    reason=entry.reason,
                    guild=guild,
                )
                await _send_log(bot, guild, embed, 'unban')
                logger.info(f'ЛОГ: разбан {target} от {executor}')

            elif entry.action == discord.AuditLogAction.kick:
                embed = _log_embed(
                    title="👢 Участник кикнут",
                    color=KICK_COLOR,
                    action="Кик",
                    target=target,
                    executor=executor,
                    reason=entry.reason,
                    guild=guild,
                )
                await _send_log(bot, guild, embed, 'kick')
                logger.info(f'ЛОГ: кик {target} от {executor}')

        except Exception as e:
            logger.error(f'Ошибка обработки лога: {e}')

    # Резервное логирование через on_member_ban/on_member_unban (для надёжности)
    @bot.listen('on_member_ban')
    async def log_ban(guild, user):
        try:
            # Если audit log уже записал — не дублируем
            embed = discord.Embed(
                title="🔨 Участник забанен",
                description=f"**{user}** (`{user.id}`) забанен",
                color=BAN_COLOR,
                timestamp=datetime.now()
            )
            embed.set_footer(text=f"Сервер: {guild.name}")
            await _send_log(bot, guild, embed, 'ban')
        except Exception as e:
            logger.error(f'Ошибка резервного лога бана: {e}')

    @bot.listen('on_member_unban')
    async def log_unban(guild, user):
        try:
            embed = discord.Embed(
                title="⚖️ Снят бан",
                description=f"**{user}** (`{user.id}`) разбанен",
                color=UNBAN_COLOR,
                timestamp=datetime.now()
            )
            embed.set_footer(text=f"Сервер: {guild.name}")
            await _send_log(bot, guild, embed, 'unban')
        except Exception as e:
            logger.error(f'Ошибка резервного лога разбана: {e}')

    @bot.hybrid_command(name="set-log", description="Указать каналы для логов модерации")
    @app_commands.describe(type="Тип логов: ban, unban, kick, timeout")
    @commands.has_permissions(manage_channels=True)
    async def set_log_cmd(ctx: commands.Context, type: str = None, channel: discord.TextChannel = None):
        """Настройка каналов логов. Каналы подбираются по названию автоматически,
        но можно указать конкретный: !set-log ban #канал"""
        try:
            if type is None:
                # Показываем статус найденных каналов
                embed = discord.Embed(
                    title="📋 Каналы логов",
                    color=0x9000FF,
                    timestamp=datetime.now()
                )
                chan = _find_channel_by_keywords(ctx.guild, BAN_CHANNEL_KEYWORDS) or _find_log_channel(ctx.guild)
                embed.add_field(name="🔨 Баны", value=chan.mention if chan else "❌ не найден (нужно «бан»/«логи»)", inline=False)
                chan = _find_channel_by_keywords(ctx.guild, UNBAN_CHANNEL_KEYWORDS) or _find_log_channel(ctx.guild)
                embed.add_field(name="⚖️ Разбаны", value=chan.mention if chan else "❌ не найден (нужно «разбан»/«логи»)", inline=False)
                chan = _find_channel_by_keywords(ctx.guild, KICK_CHANNEL_KEYWORDS) or _find_log_channel(ctx.guild)
                embed.add_field(name="👢 Кики", value=chan.mention if chan else "❌ не найден (нужно «кик»/«логи»)", inline=False)
                chan = _find_channel_by_keywords(ctx.guild, TIMEOUT_CHANNEL_KEYWORDS) or _find_log_channel(ctx.guild)
                embed.add_field(name="🔇 Тайм-ауты", value=chan.mention if chan else "❌ не найден (нужно «тайм-аут»/«мут»/«логи»)", inline=False)
                embed.set_footer(text="Создай каналы #баны, #разбаны, #кики, #тайм-ауты — или общий #логи")
                await ctx.send(embed=embed, ephemeral=True)
                return

            type_lower = type.lower().strip()
            type_map = {
                'ban': ('баны', BAN_CHANNEL_KEYWORDS),
                'бан': ('баны', BAN_CHANNEL_KEYWORDS),
                'unban': ('разбаны', UNBAN_CHANNEL_KEYWORDS),
                'разбан': ('разбаны', UNBAN_CHANNEL_KEYWORDS),
                'kick': ('кики', KICK_CHANNEL_KEYWORDS),
                'кик': ('кики', KICK_CHANNEL_KEYWORDS),
                'timeout': ('тайм-ауты', TIMEOUT_CHANNEL_KEYWORDS),
                'таймаут': ('тайм-ауты', TIMEOUT_CHANNEL_KEYWORDS),
                'тайм-аут': ('тайм-ауты', TIMEOUT_CHANNEL_KEYWORDS),
                'mute': ('тайм-ауты', TIMEOUT_CHANNEL_KEYWORDS),
                'мут': ('тайм-ауты', TIMEOUT_CHANNEL_KEYWORDS),
            }
            if type_lower not in type_map:
                await ctx.send("❌ Тип должен быть: `ban`, `unban`, `kick` или `timeout`", ephemeral=True)
                return

            label, keywords = type_map[type_lower]
            if channel is None:
                channel = _find_channel_by_keywords(ctx.guild, keywords) or _find_log_channel(ctx.guild)
            if channel is None:
                await ctx.send(
                    f"❌ Канал для «{label}» не найден. Создай канал с названием, содержащим "
                    f"одно из: `{', '.join(keywords)}`, или укажи его: `{bot.command_prefix}set-log {type_lower} #канал`",
                    ephemeral=True
                )
                return
            await ctx.send(f"✅ Логи «{label}» будут идти в {channel.mention}", ephemeral=True)
            logger.info(f'{ctx.author} настроил логи {type_lower}: {channel.name}')
        except Exception as e:
            await ctx.send(f"❌ Ошибка: {e}", ephemeral=True)
            logger.error(f'Ошибка set-log: {e}')

    logger.info("Модуль логов загружен")
