"""
Модуль логов модерации

Источники событий:
  1. Команды бота (!kick, !ban, !timeout, ...) — логируются напрямую из
     commands.moderation через bot.mod_log с реальным исполнителем (ctx.author).
  2. Ручные действия в Discord (клик по участнику, слэш-команды Discord) —
     отслеживаются через on_audit_log_entry_create. Записи, где исполнитель —
     сам бот, пропускаются (они уже залогированы из команд).

Каналы логов:
  - специфичный канал для типа события (ban/unban/kick/timeout),
  - иначе — общий канал логов.
  Поиск по названию канала; настройка через !set-log.
"""

import logging
from datetime import datetime, timezone

import discord
from discord.ext import commands
from discord import app_commands

logger = logging.getLogger('discord_bot.logger')

# Цвета событий
KICK_COLOR = 0xE67E22
BAN_COLOR = 0xE74C3C
UNBAN_COLOR = 0x2ECC71
TIMEOUT_COLOR = 0x9B59B6
UNTIMEOUT_COLOR = 0x1ABC9C

# Каналы логов: ключевые слова для автоматического поиска по названию
LOG_CHANNEL_KEYWORDS = ('логи', 'logs', 'мод-логи', 'audit', 'логи-модерации')
TYPE_KEYWORDS = {
    'ban': ('бан', 'ban', 'баны'),
    'unban': ('разбан', 'unban', 'анбан'),
    'kick': ('кик', 'kick', 'кики'),
    'timeout': ('тайм-аут', 'таймаут', 'timeout', 'мут', 'mute', 'муты'),
    'untimeout': ('тайм-аут', 'таймаут', 'timeout', 'мут', 'mute', 'муты'),
}
# Читаемое название действия для embed
ACTION_LABELS = {
    'ban': 'Бан',
    'unban': 'Разбан',
    'kick': 'Кик',
    'timeout': 'Тайм-аут',
    'untimeout': 'Снят тайм-аут',
}
# Приоритет канала при фолбэке (что ищем раньше в общем канале логов)
_LOG_CHANNEL_PRIORITY = (
    ('мод', 'логи'),
    ('мод', 'log'),
    ('модератор', 'логи'),
)


def _find_channel_by_keywords(guild, keywords):
    """Первый текстовый канал, в названии которого есть любое ключевое слово"""
    if not guild:
        return None
    for channel in guild.text_channels:
        name = (channel.name or '').lower()
        if any(kw in name for kw in keywords):
            return channel
    return None


def _find_log_channel(guild):
    """Поиск общего канала логов"""
    if not guild:
        return None
    for first, second in _LOG_CHANNEL_PRIORITY:
        for channel in guild.text_channels:
            name = (channel.name or '').lower()
            if first in name and second in name:
                return channel
    for channel in guild.text_channels:
        name = (channel.name or '').lower()
        if any(kw in name for kw in LOG_CHANNEL_KEYWORDS):
            return channel
    return None


def _pick_channel(guild, action_type):
    """Выбор канала для действия: специфичный → общий лог-канал"""
    keywords = TYPE_KEYWORDS.get(action_type)
    if keywords:
        channel = _find_channel_by_keywords(guild, keywords)
        if channel:
            return channel
    return _find_log_channel(guild)


def _normalize_action(action_type):
    """Приведение типа действия к каноничному ключу.

    Из moderation.py приходят строки вида "kick", "ban",
    "timeout (5 мин)" — нормализуем к 'timeout'.
    """
    if not action_type:
        return 'unknown'
    low = str(action_type).lower().strip()
    if low.startswith('timeout') or 'тайм-аут' in low or 'таймаут' in low or 'мут' in low:
        return 'timeout'
    if low.startswith('untimeout'):
        return 'untimeout'
    if low in ('ban', 'бан', 'забанен'):
        return 'ban'
    if low in ('unban', 'разбан', 'снят бан', 'анбан'):
        return 'unban'
    if low in ('kick', 'кик'):
        return 'kick'
    return low


def _format_duration(after, before=None):
    """Длительность тайм-аута в человекочитаемом виде.

    timed_out_until приходит aware (UTC), поэтому сравнение ведём
    только с aware datetime (discord.utils.utcnow()).
    """
    try:
        if before is not None:
            delta = after - before
        else:
            delta = after - discord.utils.utcnow()
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
    display_action = ACTION_LABELS.get(action, action)

    def _user_field(name, user):
        if user is None:
            return "неизвестно"
        try:
            return f"{user.mention}\n({user.name} · ID: `{user.id}`)"
        except Exception:
            return f"{user}"

    embed = discord.Embed(
        title=title,
        color=color,
        timestamp=discord.utils.utcnow(),
    )
    embed.add_field(name="Действие", value=display_action, inline=True)
    embed.add_field(name="Пользователь", value=_user_field('target', target), inline=True)
    embed.add_field(name="Исполнитель", value=_user_field('executor', executor), inline=True)
    if reason and reason != "Не указана":
        embed.add_field(name="Причина", value=reason, inline=False)
    if guild:
        embed.set_footer(text=f"Сервер: {guild.name}")
    return embed


async def log_mod_action(bot, guild, action_type, title, color, target, executor, reason="Не указана"):
    """Публичная отправка лога модерации.

    Вызывается из команд модерации (modules/moderation.py), чтобы лог попал
    в канал, даже когда действие выполняет сам бот (audit log таких записей
    не видит корректно, т.к. исполнитель — бот).
    """
    try:
        key = _normalize_action(action_type)
        embed = _log_embed(
            title=title,
            color=color,
            action=key,
            target=target,
            executor=executor,
            reason=reason,
            guild=guild,
        )
        return await _send_log(bot, guild, embed, key)
    except Exception as e:
        logger.error(f'Ошибка log_mod_action: {e}')
        return False


async def _send_log(bot, guild, embed, action_type):
    """Отправка лога в канал для данного типа события"""
    key = _normalize_action(action_type)
    if not guild:
        return False
    channel = _pick_channel(guild, key)
    if channel is None:
        logger.warning(
            f'Канал логов для «{key}» не найден на {guild.name}. '
            f'Создай канал с «логи» в названии или настрой через !set-log'
        )
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

    @bot.listen('on_audit_log_entry_create')
    async def log_mod_actions(entry):
        """Логирование ручных действий модерации через audit log.

        Пропускаем записи, где исполнитель — бот: такие действия
        (через команды !kick и т.п.) уже залогированы из команд через mod_log.
        """
        try:
            guild = entry.guild
            if not guild:
                return

            executor = entry.user
            if executor is None or executor.id == bot.user.id:
                return
            if executor.bot:
                return

            target = entry.target
            action = entry.action

            if action == discord.AuditLogAction.ban:
                embed = _log_embed(
                    title="Участник забанен",
                    color=BAN_COLOR,
                    action='ban',
                    target=target,
                    executor=executor,
                    reason=entry.reason,
                    guild=guild,
                )
                await _send_log(bot, guild, embed, 'ban')
                logger.info(f'ЛОГ: бан {target} от {executor}')

            elif action == discord.AuditLogAction.unban:
                embed = _log_embed(
                    title="Снят бан",
                    color=UNBAN_COLOR,
                    action='unban',
                    target=target,
                    executor=executor,
                    reason=entry.reason,
                    guild=guild,
                )
                await _send_log(bot, guild, embed, 'unban')
                logger.info(f'ЛОГ: разбан {target} от {executor}')

            elif action == discord.AuditLogAction.kick:
                embed = _log_embed(
                    title="Участник кикнут",
                    color=KICK_COLOR,
                    action='kick',
                    target=target,
                    executor=executor,
                    reason=entry.reason,
                    guild=guild,
                )
                await _send_log(bot, guild, embed, 'kick')
                logger.info(f'ЛОГ: кик {target} от {executor}')

            elif action == discord.AuditLogAction.member_update:
                before_timeout = getattr(entry.before, 'timed_out_until', None)
                after_timeout = getattr(entry.after, 'timed_out_until', None)

                if before_timeout is None and after_timeout is not None:
                    # Тайм-аут выдан
                    duration = _format_duration(after_timeout)
                    embed = _log_embed(
                        title="Участник в тайм-ауте",
                        color=TIMEOUT_COLOR,
                        action=f"timeout ({duration})",
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
                        title="Тайм-аут снят",
                        color=UNTIMEOUT_COLOR,
                        action='untimeout',
                        target=target,
                        executor=executor,
                        reason=entry.reason,
                        guild=guild,
                    )
                    await _send_log(bot, guild, embed, 'untimeout')
                    logger.info(f'ЛОГ: снят тайм-аут {target} от {executor}')

                elif (before_timeout is not None and after_timeout is not None
                        and before_timeout != after_timeout):
                    # Тайм-аут изменён/продлён
                    duration = _format_duration(after_timeout, before_timeout)
                    embed = _log_embed(
                        title="Тайм-аут изменён",
                        color=TIMEOUT_COLOR,
                        action=f"timeout ({duration})",
                        target=target,
                        executor=executor,
                        reason=entry.reason,
                        guild=guild,
                    )
                    await _send_log(bot, guild, embed, 'timeout')
                    logger.info(f'ЛОГ: изменён тайм-аут {target} от {executor} ({duration})')

        except Exception as e:
            logger.error(f'Ошибка обработки audit log: {e}')

    @bot.hybrid_command(name="set-log", description="Указать каналы для логов модерации")
    @app_commands.describe(type="Тип логов: ban, unban, kick, timeout", channel="Канал для логов")
    @commands.has_permissions(manage_channels=True)
    async def set_log_cmd(ctx: commands.Context, type: str = None, channel: discord.TextChannel = None):
        """Настройка каналов логов. Каналы подбираются по названию автоматически,
        но можно указать конкретный: !set-log ban #канал"""
        try:
            if type is None:
                # Показываем статус найденных каналов
                embed = discord.Embed(
                    title="Каналы логов",
                    color=0x9000FF,
                    timestamp=discord.utils.utcnow(),
                )
                for key, label in (('ban', 'Баны'), ('unban', 'Разбаны'),
                                   ('kick', 'Кики'), ('timeout', 'Тайм-ауты')):
                    chan = _pick_channel(ctx.guild, key)
                    value = chan.mention if chan else "нет канала"
                    embed.add_field(name=label, value=value, inline=False)
                embed.set_footer(text="Создай каналы #баны, #разбаны, #кики, #тайм-ауты — или общий #логи")
                await ctx.send(embed=embed, ephemeral=True)
                return

            type_lower = _normalize_action(type)
            if type_lower not in TYPE_KEYWORDS:
                await ctx.send("Тип должен быть: `ban`, `unban`, `kick` или `timeout`", ephemeral=True)
                return

            label = ACTION_LABELS.get(type_lower, type_lower)
            if channel is None:
                channel = _pick_channel(ctx.guild, type_lower)
            if channel is None:
                await ctx.send(
                    f"Канал для «{label}» не найден. Создай канал с «{TYPE_KEYWORDS[type_lower][0]}» "
                    f"в названии или укажи его: `{bot.command_prefix}set-log {type_lower} #канал`",
                    ephemeral=True,
                )
                return
            await ctx.send(f"Логи «{label}» будут идти в {channel.mention}", ephemeral=True)
            logger.info(f'{ctx.author} настроил логи {type_lower}: {channel.name}')
        except Exception as e:
            await ctx.send(f"Ошибка: {e}", ephemeral=True)
            logger.error(f'Ошибка set-log: {e}')

    @bot.hybrid_command(name="log-check", description="Проверить каналы логов и отправить тестовый лог")
    @commands.has_permissions(manage_channels=True)
    async def log_check_cmd(ctx: commands.Context):
        """Диагностика системы логов"""
        try:
            embed = discord.Embed(
                title="Проверка системы логов",
                color=0x9000FF,
                timestamp=discord.utils.utcnow(),
            )

            # Право на просмотр audit log — без него ручные действия не логируются
            bot_perms = ctx.guild.me.guild_permissions if ctx.guild.me else None
            has_audit = bool(bot_perms and bot_perms.view_audit_log)
            embed.add_field(
                name="Право «Просмотр журнала аудита»",
                value="есть" if has_audit else "НЕТ — ручные баны/кики/тайм-ауты не будут логироваться",
                inline=False,
            )
            embed.add_field(
                name="Бот: mod_log",
                value="установлен" if getattr(bot, 'mod_log', None) else "НЕ установлен",
                inline=False,
            )

            for key, label in (('ban', 'Баны'), ('unban', 'Разбаны'),
                               ('kick', 'Кики'), ('timeout', 'Тайм-ауты')):
                chan = _pick_channel(ctx.guild, key)
                embed.add_field(name=label, value=chan.mention if chan else "нет канала", inline=False)

            await ctx.send(embed=embed, ephemeral=True)

            # Отправляем тестовый лог в каждый тип логов, чтобы проверить доставку
            results = []
            for key, label, color in (
                ('ban', 'Баны', BAN_COLOR),
                ('unban', 'Разбаны', UNBAN_COLOR),
                ('kick', 'Кики', KICK_COLOR),
                ('timeout', 'Тайм-ауты', TIMEOUT_COLOR),
            ):
                test_embed = discord.Embed(
                    title=f"Тестовый лог — {label}",
                    description=f"Проверка системы логов от {ctx.author.mention}",
                    color=color,
                    timestamp=discord.utils.utcnow(),
                )
                sent = await _send_log(bot, ctx.guild, test_embed, key)
                results.append(f"{label}: {'OK' if sent else 'НЕТ канала'}")

            sent_count = sum(1 for r in results if 'OK' in r)
            if sent_count == len(results):
                await ctx.send("Тестовые логи отправлены во все каналы логов.", ephemeral=True)
            else:
                await ctx.send(
                    "Некоторые тестовые логи не отправлены:\n" + "\n".join(results)
                    + "\nСоздай каналы #баны, #разбаны, #кики, #тайм-ауты или общий #логи.",
                    ephemeral=True,
                )
            logger.info(f'{ctx.author} проверил логи: {"; ".join(results)}')
        except Exception as e:
            await ctx.send(f"Ошибка: {e}", ephemeral=True)
            logger.error(f'Ошибка log-check: {e}')

    logger.info("Модуль логов загружен")
