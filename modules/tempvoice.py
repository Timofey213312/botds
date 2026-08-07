"""
Модуль временных голосовых каналов
- Участник заходит в канал-«триггер» → создаётся его личный войс
- Канал удаляется, когда из него выходят все
- Панель управления войсом в канале «✨・voice-settings»
"""

import asyncio
import logging

import discord
from discord.ext import commands

logger = logging.getLogger('discord_bot.tempvoice')

# Название канала-триггера (можно менять на своё)
CREATE_CHANNEL_NAME = '➕ создать войс'
CREATE_CHANNEL_KEYWORDS = ('создать', 'create', 'триггер', '➕')

# Канал с панелью управления
SETTINGS_CHANNEL_NAME = '✨・voice-settings'
SETTINGS_CHANNEL_KEYWORDS = ('voice-settings', 'voice settings', 'настройки войс', 'voice-setting', 'настройки голосов')

# Префикс создаваемых каналов
TEMP_PREFIX = '🎧 | '
# Максимальное время существования пустого канала (секунды) перед удалением
DELETE_DELAY = 5

# Кэш: channel_id -> owner_id
_temp_channels = {}

PANEL_COLOR = 0x9000FF


def _find_create_channel(guild):
    """Поиск канала-триггера по названию"""
    for channel in guild.voice_channels:
        name = (channel.name or '').lower()
        for kw in CREATE_CHANNEL_KEYWORDS:
            if kw in name:
                return channel
    return None


def _find_settings_channel(guild):
    """Поиск канала с панелью управления"""
    for channel in guild.text_channels:
        name = (channel.name or '').lower()
        for kw in SETTINGS_CHANNEL_KEYWORDS:
            if kw in name:
                return channel
    return None


def _is_temp_channel(channel):
    """Является ли канал временным (созданным ботом)"""
    if not channel:
        return False
    return channel.id in _temp_channels or (channel.name or '').startswith(TEMP_PREFIX)


def _get_owner(channel):
    """Возвращает владельца временного канала или None"""
    if not channel:
        return None
    return _temp_channels.get(channel.id)


async def _ensure_owner(interaction) -> bool:
    """Проверка, что пользователь — владелец канала (или админ)"""
    member = interaction.user
    voice = member.voice
    if voice and voice.channel and _is_temp_channel(voice.channel):
        owner_id = _temp_channels.get(voice.channel.id)
        if member.id == owner_id:
            return True
        if member.guild_permissions.manage_channels:
            return True
    await interaction.response.send_message(
        "🚫 Ты должен быть **в своём временном войс-канале**, чтобы управлять им.", ephemeral=True
    )
    return False


def _build_settings_embed(member):
    """Embed панели управления"""
    embed = discord.Embed(
        title="🎛️ Управление твоим войсом",
        description=(
            "Нажми кнопку, чтобы настроить свой временный войс-канал.\n"
            "Ты должен находиться **в своём войсе**."
        ),
        color=PANEL_COLOR,
    )
    embed.add_field(name="📝 Переименовать", value="Изменить название канала", inline=True)
    embed.add_field(name="👥 Лимит", value="Изменить количество участников", inline=True)
    embed.add_field(name="🔒 Блокировка", value="Заблокировать/разблокировать войс", inline=True)
    embed.add_field(name="🙈 Скрыть", value="Скрыть/показать канал", inline=True)
    embed.add_field(name="🔇 Замутить", value="Замутить участника в войсе", inline=True)
    embed.add_field(name="🚫 Кикнуть", value="Выгнать участника из войса", inline=True)
    embed.add_field(name="👑 Передать", value="Передать владельца другому", inline=True)
    embed.add_field(name="🗑️ Удалить", value="Удалить свой войс", inline=True)
    embed.set_footer(text="Действует только на твой временный канал")
    return embed


class VoiceSettingsView(discord.ui.View):
    """Панель управления временным войсом"""

    def __init__(self, bot, timeout=600):
        super().__init__(timeout=timeout)
        self.bot = bot
        self.add_item(RenameButton())
        self.add_item(UserLimitButton())
        self.add_item(LockButton())
        self.add_item(HideButton())
        self.add_item(MuteUserButton())
        self.add_item(KickUserButton())
        self.add_item(TransferButton())
        self.add_item(DeleteButton())


# ============ ПЕРЕИМЕНОВАТЬ ============

class RenameButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Переименовать", style=discord.ButtonStyle.primary, emoji="📝", row=0)

    async def callback(self, interaction: discord.Interaction):
        if not await _ensure_owner(interaction):
            return
        await interaction.response.send_modal(RenameModal())


class RenameModal(discord.ui.Modal):
    def __init__(self):
        super().__init__(title="Переименовать войс")
        self.name = discord.ui.TextInput(label="Новое название", placeholder="Мой канал", max_length=30)
        self.add_item(self.name)

    async def on_submit(self, interaction: discord.Interaction):
        channel = interaction.user.voice.channel
        try:
            await channel.edit(name=f"{TEMP_PREFIX}{self.name.value[:28]}", reason="Переименование временного войса")
            await interaction.response.send_message(f"📝 Войс переименован в `{TEMP_PREFIX}{self.name.value[:28]}`.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Ошибка: {e}", ephemeral=True)


# ============ ЛИМИТ ============

class UserLimitButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Лимит", style=discord.ButtonStyle.secondary, emoji="👥", row=0)

    async def callback(self, interaction: discord.Interaction):
        if not await _ensure_owner(interaction):
            return
        await interaction.response.send_modal(UserLimitModal())


class UserLimitModal(discord.ui.Modal):
    def __init__(self):
        super().__init__(title="Лимит участников")
        self.limit = discord.ui.TextInput(label="Лимит (0 = без лимита)", placeholder="5", default="0")
        self.add_item(self.limit)

    async def on_submit(self, interaction: discord.Interaction):
        channel = interaction.user.voice.channel
        try:
            limit = max(0, min(99, int(self.limit.value)))
            await channel.edit(user_limit=limit, reason="Изменение лимита временного войса")
            text = "без лимита" if limit == 0 else f"**{limit}**"
            await interaction.response.send_message(f"👥 Лимит войса: {text}.", ephemeral=True)
        except ValueError:
            await interaction.response.send_message("❌ Лимит должен быть числом (0-99).", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Ошибка: {e}", ephemeral=True)


# ============ БЛОКИРОВКА ============

class LockButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Блокировка", style=discord.ButtonStyle.secondary, emoji="🔒", row=0)

    async def callback(self, interaction: discord.Interaction):
        if not await _ensure_owner(interaction):
            return
        channel = interaction.user.voice.channel
        try:
            overwrite = channel.overwrites_for(channel.guild.default_role)
            locked = not overwrite.connect
            overwrite.connect = not locked
            await channel.set_permissions(channel.guild.default_role, overwrite=overwrite)
            state = "🔒 войс **заблокирован**" if not locked else "🔓 войс **разблокирован**"
            await interaction.response.send_message(state, ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Ошибка: {e}", ephemeral=True)


# ============ СКРЫТЬ ============

class HideButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Скрыть", style=discord.ButtonStyle.secondary, emoji="🙈", row=0)

    async def callback(self, interaction: discord.Interaction):
        if not await _ensure_owner(interaction):
            return
        channel = interaction.user.voice.channel
        try:
            overwrite = channel.overwrites_for(channel.guild.default_role)
            hidden = not overwrite.view_channel
            overwrite.view_channel = not hidden
            await channel.set_permissions(channel.guild.default_role, overwrite=overwrite)
            state = "🙈 канал **скрыт**" if not hidden else "👀 канал **показан**"
            await interaction.response.send_message(state, ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Ошибка: {e}", ephemeral=True)


# ============ ЗАМУТИТЬ ============

class MuteUserButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Замутить", style=discord.ButtonStyle.secondary, emoji="🔇", row=1)

    async def callback(self, interaction: discord.Interaction):
        if not await _ensure_owner(interaction):
            return
        await interaction.response.send_modal(MuteUserModal())


class MuteUserModal(discord.ui.Modal):
    def __init__(self):
        super().__init__(title="Замутить участника")
        self.member = discord.ui.TextInput(label="Ник или ID участника", placeholder="Пример: @ник")
        self.add_item(self.member)

    async def on_submit(self, interaction: discord.Interaction):
        channel = interaction.user.voice.channel
        member = _resolve_voice_member(interaction, channel, self.member.value.strip())
        if member is None:
            return
        try:
            new_state = not member.voice.mute
            await member.edit(mute=new_state, reason="Мут через панель войса")
            state = "замьючен" if new_state else "размьючен"
            await interaction.response.send_message(f"🔇 **{member}** {state}.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Ошибка: {e}", ephemeral=True)


# ============ КИКНУТЬ ============

class KickUserButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Кикнуть", style=discord.ButtonStyle.danger, emoji="🚫", row=1)

    async def callback(self, interaction: discord.Interaction):
        if not await _ensure_owner(interaction):
            return
        await interaction.response.send_modal(KickUserModal())


class KickUserModal(discord.ui.Modal):
    def __init__(self):
        super().__init__(title="Выгнать из войса")
        self.member = discord.ui.TextInput(label="Ник или ID участника", placeholder="Пример: @ник")
        self.add_item(self.member)

    async def on_submit(self, interaction: discord.Interaction):
        channel = interaction.user.voice.channel
        member = _resolve_voice_member(interaction, channel, self.member.value.strip())
        if member is None:
            return
        try:
            await member.move_to(None, reason="Выгнан из временного войса")
            await interaction.response.send_message(f"🚫 **{member}** выгнан из войса.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Ошибка: {e}", ephemeral=True)


# ============ ПЕРЕДАТЬ ============

class TransferButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Передать", style=discord.ButtonStyle.secondary, emoji="👑", row=1)

    async def callback(self, interaction: discord.Interaction):
        if not await _ensure_owner(interaction):
            return
        await interaction.response.send_modal(TransferModal())


class TransferModal(discord.ui.Modal):
    def __init__(self):
        super().__init__(title="Передать владельца")
        self.member = discord.ui.TextInput(label="Ник или ID участника", placeholder="Пример: @ник")
        self.add_item(self.member)

    async def on_submit(self, interaction: discord.Interaction):
        channel = interaction.user.voice.channel
        member = _resolve_voice_member(interaction, channel, self.member.value.strip())
        if member is None:
            return
        _temp_channels[channel.id] = member.id
        await interaction.response.send_message(f"👑 Владелец войса теперь **{member}**.", ephemeral=True)


# ============ УДАЛИТЬ ============

class DeleteButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Удалить войс", style=discord.ButtonStyle.danger, emoji="🗑️", row=1)

    async def callback(self, interaction: discord.Interaction):
        if not await _ensure_owner(interaction):
            return
        channel = interaction.user.voice.channel
        try:
            await channel.delete(reason="Удалён владельцем через панель")
            _temp_channels.pop(channel.id, None)
            await interaction.response.send_message("🗑️ Войс удалён.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Ошибка: {e}", ephemeral=True)


def _resolve_voice_member(interaction, channel, text):
    """Поиск участника, находящегося в этом войсе"""
    text = text.strip()
    member = None
    if text.isdigit():
        member = channel.guild.get_member(int(text))
    if member is None:
        member = channel.guild.get_member_named(text.lstrip('@'))
    if member is None or not member.voice or member.voice.channel != channel:
        return None
    return member


def setup_tempvoice(bot):
    """Настройка временных войс-каналов"""

    @bot.hybrid_command(name="tempvoice", description="Настройка временных войс-каналов (канал-триггер)")
    @commands.has_permissions(manage_channels=True)
    async def tempvoice_cmd(ctx: commands.Context, trigger_channel: discord.VoiceChannel = None):
        """Настройка канала-триггера"""
        try:
            if trigger_channel is None:
                trigger_channel = _find_create_channel(ctx.guild)
            if trigger_channel is None:
                await ctx.send(
                    "❌ Канал-триггер не найден. Укажи канал: "
                    f"`{bot.command_prefix}tempvoice #канал`",
                    ephemeral=True
                )
                return

            global CREATE_CHANNEL_NAME
            CREATE_CHANNEL_NAME = trigger_channel.name

            embed = discord.Embed(
                title="🎧 Временные войс-каналы",
                description=(
                    f"Канал-триггер: **{trigger_channel.name}**\n"
                    f"Зайди в него — бот создаст твой личный войс-канал.\n"
                    f"Когда все выйдут — канал автоматически удалится."
                ),
                color=0x9000FF,
            )
            await ctx.send(embed=embed, ephemeral=True)
            logger.info(f'{ctx.author} настроил временные войс-каналы: {trigger_channel.name}')
        except Exception as e:
            await ctx.send(f"❌ Ошибка: {e}", ephemeral=True)
            logger.error(f'Ошибка tempvoice: {e}')

    @bot.hybrid_command(name="voice-panel", description="Отправить панель управления войсом в канал настроек")
    @commands.has_permissions(manage_channels=True)
    async def voice_panel_cmd(ctx: commands.Context):
        """Размещение панели в канале voice-settings"""
        try:
            settings_channel = _find_settings_channel(ctx.guild)
            if settings_channel is None:
                await ctx.send(
                    "❌ Канал `✨・voice-settings` не найден. Создай его или переименуй канал, "
                    "содержащий «voice-settings».",
                    ephemeral=True
                )
                return

            view = VoiceSettingsView(bot)
            await settings_channel.send(embed=_build_settings_embed(ctx.author), view=view)
            logger.info(f'{ctx.author} разместил панель в {settings_channel.name}')
        except Exception as e:
            await ctx.send(f"❌ Ошибка: {e}", ephemeral=True)
            logger.error(f'Ошибка voice-panel: {e}')

    @bot.listen('on_voice_state_update')
    async def tempvoice_handler(member, before, after):
        """Создание и удаление временных войс-каналов"""
        try:
            guild = member.guild

            # ВОШЁЛ в канал-триггер → создаём личный канал
            if after and after.channel and before.channel != after.channel:
                create_channel = _find_create_channel(guild)
                if create_channel and after.channel.id == create_channel.id:
                    await _create_temp_channel(bot, member, create_channel)
                    return

            # ВЫШЕЛ из временного канала → проверяем пустоту и удаляем
            if before and before.channel and after and after.channel != before.channel:
                await _check_and_delete(before.channel)
            elif before and before.channel and not after:
                await _check_and_delete(before.channel)

            # Перешёл между временными каналами — не трогаем

        except Exception as e:
            logger.error(f'Ошибка tempvoice_handler: {e}')

    logger.info("Модуль временных войс-каналов загружен")


async def _create_temp_channel(bot, member, create_channel):
    """Создание личного войс-канала для участника"""
    # Если у участника уже есть временный канал — не создаём второй
    for ch_id in list(_temp_channels.keys()):
        ch = create_channel.guild.get_channel(ch_id)
        if ch and _temp_channels[ch_id] == member.id and member.voice and ch == member.voice.channel:
            return

    # Убираем из названия инвалидные символы
    nick = (member.display_name or member.name).replace('|', 'I')[:28]

    try:
        temp_channel = await create_channel.guild.create_voice_channel(
            name=f"{TEMP_PREFIX}{nick}",
            category=create_channel.category,
            position=create_channel.position + 1,
            reason="Временный войс-канал"
        )
        _temp_channels[temp_channel.id] = member.id
        logger.info(f'Создан временный канал {temp_channel.name} для {member}')

        # Перемещаем участника в новый канал
        if member.voice and member.voice.channel:
            await member.move_to(temp_channel, reason="Вход во временный войс-канал")

        # Через некоторое время проверяем пустоту (на случай если не сработает on_voice_state_update)
        bot.loop.create_task(_auto_cleanup(temp_channel))
    except Exception as e:
        logger.error(f'Ошибка создания временного канала: {e}')


async def _auto_cleanup(temp_channel):
    """Фоновая проверка пустоты канала"""
    await asyncio.sleep(60)
    if temp_channel.id in _temp_channels:
        await _check_and_delete(temp_channel)


async def _check_and_delete(channel):
    """Удаление временного канала, если он пуст"""
    if not _is_temp_channel(channel):
        return
    if not hasattr(channel, 'members'):
        return
    if len(channel.members) > 0:
        return

    await asyncio.sleep(DELETE_DELAY)
    try:
        # Перепроверяем после задержки
        ch = channel.guild.get_channel(channel.id)
        if ch and hasattr(ch, 'members') and len(ch.members) == 0:
            _temp_channels.pop(channel.id, None)
            await ch.delete(reason="Временный войс-канал опустел")
            logger.info(f'Удалён пустой временный канал {ch.name}')
    except Exception as e:
        logger.error(f'Ошибка удаления временного канала: {e}')
