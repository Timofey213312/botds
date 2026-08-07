"""
Модуль системы тикетов (устойчивая версия)
- !ticket — сообщение с кнопкой «Открыть тикет»
- !ticket-add / !ticket-remove — управление участниками тикета
- Кнопка «Закрыть тикет» с сохранением транскрипта
"""

import io
import logging
import re
from datetime import datetime

import discord
from discord import app_commands
from discord.ext import commands

logger = logging.getLogger('discord_bot.tickets')

EMBED_COLOR = 0x9000FF
TICKET_PREFIX = 'ticket-'


def _staff_roles(guild):
    """Роли с правом управления каналами (администрация/модерация)"""
    return [role for role in guild.roles if role.permissions.manage_channels and not role.is_default()]


def _is_staff(member):
    return bool(member.guild_permissions.manage_channels or member.guild_permissions.administrator)


def _safe_channel_name(name, max_len=32):
    """Приводит имя к допустимому формату имени канала Discord"""
    name = re.sub(r'[^a-z0-9а-яё\-_ ]', '', name.lower()).strip()
    name = re.sub(r'\s+', '-', name)
    name = re.sub(r'-+', '-', name).strip('-')
    if not name:
        name = 'user'
    return name[:max_len]


async def _find_or_create_category(guild):
    """Поиск или создание категории тикетов"""
    for cat in guild.categories:
        if 'ticket' in (cat.name or '').lower() or 'тикет' in (cat.name or '').lower():
            return cat

    bot_member = guild.me
    if not bot_member.guild_permissions.manage_channels:
        return None

    overwrites = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False),
        guild.me: discord.PermissionOverwrite(
            view_channel=True, send_messages=True, read_message_history=True, manage_channels=True
        ),
    }
    for role in _staff_roles(guild):
        overwrites[role] = discord.PermissionOverwrite(
            view_channel=True, send_messages=True, read_message_history=True, manage_channels=True
        )
    try:
        return await guild.create_category('🎫 Тикеты', overwrites=overwrites)
    except discord.Forbidden:
        return None
    except Exception as e:
        logger.error(f'Ошибка создания категории тикетов: {e}')
        return None


def _find_transcript_channel(guild):
    """Поиск канала для сохранения транскриптов"""
    for channel in guild.text_channels:
        name = (channel.name or '').lower()
        for kw in ('транскрипт', 'transcript', 'логи', 'logs'):
            if kw in name:
                return channel
    return None


async def _open_ticket(interaction):
    user = interaction.user
    guild = interaction.guild

    if not guild.me.guild_permissions.manage_channels:
        await interaction.response.send_message(
            "❌ У бота нет прав `Управлять каналами`. Выдай их и попробуй снова.", ephemeral=True
        )
        return

    cat = await _find_or_create_category(guild)
    if cat is None:
        await interaction.response.send_message(
            "❌ Не удалось найти/создать категорию тикетов. Проверь права бота.", ephemeral=True
        )
        return

    # Проверка существующего тикета
    for ch in cat.channels:
        if ch.topic and f'owner:{user.id}' in ch.topic:
            try:
                await interaction.response.send_message(
                    f"❌ У тебя уже есть открытый тикет: {ch.mention}", ephemeral=True
                )
            except discord.InteractionResponded:
                pass
            return

    overwrites = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False),
        user: discord.PermissionOverwrite(
            view_channel=True, send_messages=True, read_message_history=True,
            attach_files=True, embed_links=True,
        ),
        guild.me: discord.PermissionOverwrite(
            view_channel=True, send_messages=True, read_message_history=True
        ),
    }
    for role in _staff_roles(guild):
        overwrites[role] = discord.PermissionOverwrite(
            view_channel=True, send_messages=True, read_message_history=True
        )

    base_name = f'{TICKET_PREFIX}{_safe_channel_name(user.name)}'
    name = base_name
    existing = {c.name for c in cat.channels}
    count = 2
    while name in existing:
        name = f'{base_name}-{count}'
        count += 1

    try:
        channel = await guild.create_text_channel(
            name, category=cat, overwrites=overwrites, topic=f'owner:{user.id}'
        )
    except discord.Forbidden:
        await interaction.response.send_message(
            "❌ У бота нет прав создавать каналы.", ephemeral=True
        )
        return
    except Exception as e:
        logger.error(f'Ошибка создания канала тикета: {e}')
        try:
            await interaction.response.send_message(f"❌ Ошибка создания тикета: {e}", ephemeral=True)
        except discord.InteractionResponded:
            pass
        return

    embed = discord.Embed(
        title="🎫 Новый тикет",
        description="Опишите вашу проблему, и администрация скоро ответит.",
        color=EMBED_COLOR,
    )
    embed.add_field(name="Создал", value=user.mention, inline=True)
    embed.set_footer(text=datetime.now().strftime('%d.%m.%Y %H:%M'))

    try:
        await channel.send(embed=embed, view=CloseTicketButton())
        await interaction.response.send_message(f"✅ Тикет создан: {channel.mention}", ephemeral=True)
    except discord.InteractionResponded:
        await interaction.followup.send(f"✅ Тикет создан: {channel.mention}", ephemeral=True)
    logger.info(f'{user} создал тикет {channel.name}')


async def _close_ticket(interaction):
    user = interaction.user
    channel = interaction.channel
    if not isinstance(channel, discord.TextChannel) or not channel.name.startswith(TICKET_PREFIX):
        try:
            await interaction.response.send_message("❌ Это не канал тикета.", ephemeral=True)
        except discord.InteractionResponded:
            pass
        return

    owner_ok = channel.topic and f'owner:{user.id}' in channel.topic
    if not owner_ok and not _is_staff(user):
        try:
            await interaction.response.send_message(
                "❌ Только автор тикета или администрация могут закрыть тикет.", ephemeral=True
            )
        except discord.InteractionResponded:
            pass
        return

    guild = channel.guild

    try:
        await interaction.response.defer(ephemeral=True)
    except discord.InteractionResponded:
        pass

    # Сохранение транскрипта
    log_channel = _find_transcript_channel(guild)
    if log_channel:
        try:
            lines = []
            async for msg in channel.history(limit=100, oldest_first=True):
                lines.append(
                    f'[{msg.created_at.strftime("%d.%m.%Y %H:%M")}] '
                    f'{msg.author.display_name}: {msg.clean_content}'
                )
            content = "\n".join(lines)
            if content.strip():
                await log_channel.send(
                    f"📝 **Транскрипт тикета {channel.name}**",
                    file=discord.File(io.BytesIO(content.encode('utf-8')), filename=f'{channel.name}.txt'),
                )
        except Exception as e:
            logger.error(f'Ошибка сохранения транскрипта: {e}')

    name = channel.name
    try:
        await channel.delete()
    except Exception as e:
        logger.error(f'Ошибка удаления канала: {e}')
        try:
            await interaction.followup.send("❌ Не удалось удалить канал тикета.", ephemeral=True)
        except Exception:
            pass
        return

    try:
        await interaction.followup.send("🔒 Тикет закрыт.", ephemeral=True)
    except Exception:
        pass
    logger.info(f'{user} закрыл тикет {name}')


class OpenTicketButton(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🎫 Открыть тикет", style=discord.ButtonStyle.primary, custom_id="ticket_open")
    async def open_button(self, interaction, button):
        logger.info(f'Кнопка «Открыть тикет» нажата пользователем {interaction.user} в {interaction.guild}')
        try:
            await _open_ticket(interaction)
        except discord.InteractionResponded:
            pass
        except Exception as e:
            try:
                await interaction.response.send_message(f"❌ Ошибка при создании тикета: {e}", ephemeral=True)
            except discord.InteractionResponded:
                pass
            logger.error(f'Ошибка открытия тикета: {e}')


class CloseTicketButton(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🔒 Закрыть тикет", style=discord.ButtonStyle.danger, custom_id="ticket_close")
    async def close_button(self, interaction, button):
        try:
            await _close_ticket(interaction)
        except discord.InteractionResponded:
            pass
        except Exception as e:
            try:
                await interaction.response.send_message(f"❌ Ошибка при закрытии тикета: {e}", ephemeral=True)
            except discord.InteractionResponded:
                pass
            logger.error(f'Ошибка закрытия тикета: {e}')


def setup_tickets(bot):
    """Настройка системы тикетов"""

    @bot.hybrid_command(name="ticket", description="Открыть систему тикетов (сообщение с кнопкой)")
    async def ticket_cmd(ctx: commands.Context):
        """Создание сообщения с кнопкой открытия тикета"""
        try:
            if not _is_staff(ctx.author):
                await ctx.send("❌ Недостаточно прав для настройки тикетов.", ephemeral=True)
                return
            embed = discord.Embed(
                title="🎫 Система тикетов",
                description="Нажмите кнопку ниже, чтобы создать тикет и связаться с администрацией.",
                color=EMBED_COLOR,
            )
            await ctx.send(embed=embed, view=OpenTicketButton())
            logger.info(f'{ctx.author} настроил систему тикетов')
        except Exception as e:
            await ctx.send(f"❌ Ошибка: {e}", ephemeral=True)
            logger.error(f'Ошибка ticket: {e}')

    @bot.hybrid_command(name="ticket-add", description="Добавить участника в тикет")
    @app_commands.describe(member="Участник для добавления")
    async def ticket_add_cmd(ctx: commands.Context, member: discord.Member):
        """Добавление участника в тикет"""
        try:
            if not _is_staff(ctx.author):
                await ctx.send("❌ Недостаточно прав.", ephemeral=True)
                return
            if not isinstance(ctx.channel, discord.TextChannel) or not ctx.channel.name.startswith(TICKET_PREFIX):
                await ctx.send("❌ Команда работает только в канале тикета.", ephemeral=True)
                return
            await ctx.channel.set_permissions(
                member, view_channel=True, send_messages=True, read_message_history=True
            )
            await ctx.send(f"✅ {member.mention} добавлен в тикет.")
            logger.info(f'{ctx.author} добавил {member} в {ctx.channel.name}')
        except Exception as e:
            await ctx.send(f"❌ Ошибка: {e}", ephemeral=True)
            logger.error(f'Ошибка ticket-add: {e}')

    @bot.hybrid_command(name="ticket-remove", description="Убрать участника из тикета")
    @app_commands.describe(member="Участник для удаления")
    async def ticket_remove_cmd(ctx: commands.Context, member: discord.Member):
        """Удаление участника из тикета"""
        try:
            if not _is_staff(ctx.author):
                await ctx.send("❌ Недостаточно прав.", ephemeral=True)
                return
            if not isinstance(ctx.channel, discord.TextChannel) or not ctx.channel.name.startswith(TICKET_PREFIX):
                await ctx.send("❌ Команда работает только в канале тикета.", ephemeral=True)
                return
            await ctx.channel.set_permissions(member, view_channel=False)
            await ctx.send(f"✅ {member.mention} убран из тикета.")
            logger.info(f'{ctx.author} убрал {member} из {ctx.channel.name}')
        except Exception as e:
            await ctx.send(f"❌ Ошибка: {e}", ephemeral=True)
            logger.error(f'Ошибка ticket-remove: {e}')

    bot.add_view(OpenTicketButton())
    bot.add_view(CloseTicketButton())
    from modules.panels import register_panel

    def _build_ticket_panel(guild):
        embed = discord.Embed(
            title="🎫 Система тикетов",
            description="Нажмите кнопку ниже, чтобы создать тикет и связаться с администрацией.",
            color=EMBED_COLOR,
        )
        return embed, OpenTicketButton()

    register_panel(
        channel_keywords=('ticket', 'тикет'),
        label="🎫 Открыть тикет",
        expected_ids=["ticket_open"],
        build=_build_ticket_panel,
    )
    logger.info(f'Модуль тикетов загружен (persistent views: ticket_open, ticket_close)')
