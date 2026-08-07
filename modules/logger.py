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


def _log_embed(title, color, action, target, executor, reason, guild):
    """Сборка embed лога"""
    embed = discord.Embed(
        title=title,
        color=color,
        timestamp=datetime.now()
    )
    embed.add_field(name="🎯 Действие", value=action, inline=True)
    embed.add_field(name="👤 Пользователь", value=f"{target.mention}\n({target.name} · ID: `{target.id}`)", inline=True)
    embed.add_field(name="👮 Исполнитель", value=f"{executor.mention}\n({executor.name} · ID: `{executor.id}`)", inline=True)
    if reason and reason != "Не указана":
        embed.add_field(name="📝 Причина", value=reason, inline=False)
    embed.set_footer(text=f"Сервер: {guild.name}")
    return embed


async def _send_log(bot, guild, embed, action_type):
    """Отправка лога в соответствующий канал"""
    # Специфичный канал для типа события
    type_keywords = {
        'ban': BAN_CHANNEL_KEYWORDS,
        'unban': UNBAN_CHANNEL_KEYWORDS,
        'kick': KICK_CHANNEL_KEYWORDS,
    }.get(action_type)

    channel = None
    if type_keywords:
        channel = _find_channel_by_keywords(guild, type_keywords)
    # Если специфичного канала нет — общий канал логов
    if channel is None:
        channel = _find_log_channel(guild)
    if not channel:
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
    @app_commands.describe(type="Тип логов: ban, unban, kick")
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
                embed.set_footer(text="Создай каналы #баны, #разбаны, #кики — или общий #логи")
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
            }
            if type_lower not in type_map:
                await ctx.send("❌ Тип должен быть: `ban`, `unban` или `kick`", ephemeral=True)
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
