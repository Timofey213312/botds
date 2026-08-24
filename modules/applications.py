"""
Модуль системы заявок (канальный формат)
- Панель с кнопкой «Подать заявку» в каналах: ⚔️ клан, 🎥 медиа, 🪄 партнёр-менеджер, 🛡️ модератор
- По кнопке создаётся приватный канал для заявителя, бот публикует вопросы
- Заявитель отвечает прямо в канале
- Администрация: «Принять / Отклонить / Закрыть» (статус + уведомление в ЛС)
"""

import logging
import re
from datetime import datetime

import discord
from discord import app_commands
from discord.ext import commands

logger = logging.getLogger('discord_bot.applications')

EMBED_COLOR = 0x9000FF
STATUS_REVIEW = '📝 На рассмотрении'
STATUS_APPROVED = '✅ Принято'
STATUS_REJECTED = '❌ Отклонено'

APPLICATIONS = {
    'clan': {
        'emoji': '⚔️',
        'title': 'Заявка в клан',
        'keywords': ('ᴄʟᴀɴ', 'clan'),
        'color': 0x9b59b6,
        'role_id': 1511851270921650216,
        'questions': [
            'Играть не менее 3 часов',
            'Успешные кланы, в которых ты играл(а)',
            'Стараться быть на связи и помогать тиммейтам',
            'Быть адекватным',
            'Твой часовой пояс',
            'Готов ли ты помогать фармить клан коины?',
            'Твой возраст',
            'Почему выбрал именно нас',
            'Какой у тебя Донат',
            'Ник человека, который тебя пригласил в клан',
            'Готов ли ты собирать инвентарь с первых дней вайпа и ходить на все клановые ивенты',
        ],
    },
    'media': {
        'emoji': '🎥',
        'title': 'Заявка в медиа-команду',
        'keywords': ('ᴍᴇᴅɪᴀ', 'media'),
        'color': 0xe91e63,
        'role_id': 1511848199478972547,
        'questions': [
            'Ваше настоящее имя',
            'Ваш возраст',
            'Сколько у вас просмотров (YT от 60), (TT от 400)',
            'Ссылка на ваш YT/TT',
            'Сколько у вас подписчиков',
        ],
    },
    'partner': {
        'emoji': '🪄',
        'title': 'Заявка на партнёрство',
        'keywords': ('ᴨᴀᴩᴛ', 'ᴘᴀʀᴛɴᴇʀ', 'партн', 'partner'),
        'color': 0x00bcd4,
        'role_id': 1511848598638432356,
        'requirements': [
            'Иметь не менее 50 участников на сервере.',
        ],
    },
    'moder': {
        'emoji': '🛡️',
        'title': 'Заявка в модераторы',
        'keywords': ('ᴍᴏᴅᴇʀ', 'moder', 'модер', 'моде'),
        'color': 0x4caf50,
        'role_id': 1511848007149158582,
        'questions': [
            'Твой никнейм / возраст',
            'Опыт модерации (где и сколько)',
            'Почему именно ты должен стать модератором?',
            'Сколько времени онлайн в день?',
            'Чем можешь помочь клану?',
        ],
    },
}


def _is_staff(member):
    p = member.guild_permissions
    return bool(p.administrator or p.manage_channels or p.manage_roles
                or p.kick_members or p.ban_members or p.moderate_members)


def _staff_roles(guild):
    return [r for r in guild.roles if r.permissions.manage_channels and not r.is_default()]


def _detect_type(channel):
    name = (channel.name or '').lower()
    for key, cfg in APPLICATIONS.items():
        if any(kw in name for kw in cfg['keywords']):
            return key
    return None


def _safe_channel_name(name, max_len=28):
    name = re.sub(r'[^a-z0-9а-яё\-_ ]', '', name.lower()).strip()
    name = re.sub(r'\s+', '-', name)
    name = re.sub(r'-+', '-', name).strip('-')
    return name[:max_len] or 'user'


async def _find_or_create_category(guild):
    for cat in guild.categories:
        if 'заявк' in (cat.name or '').lower() or 'applicat' in (cat.name or '').lower():
            return cat
    if not guild.me.guild_permissions.manage_channels:
        return None
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False),
        guild.me: discord.PermissionOverwrite(
            view_channel=True, send_messages=True, read_message_history=True, manage_channels=True),
    }
    for role in _staff_roles(guild):
        overwrites[role] = discord.PermissionOverwrite(
            view_channel=True, send_messages=True, read_message_history=True, manage_channels=True)
    try:
        return await guild.create_category('📝 Заявки', overwrites=overwrites)
    except Exception as e:
        logger.error(f'Ошибка создания категории заявок: {e}')
        return None


def _find_field_index(embed, prefix):
    for i, f in enumerate(embed.fields):
        if f.name.startswith(prefix):
            return i
    return None


def _add_app_fields(embed, cfg):
    """Добавляет в эмбед блоки требований / бонусов / вопросов / примечания"""
    if cfg.get('requirements'):
        embed.add_field(
            name="📋 Требования",
            value="\n".join(f"• {r}" for r in cfg['requirements']),
            inline=False,
        )
    if cfg.get('benefits'):
        embed.add_field(
            name="🎁 Что вы получите взамен",
            value="\n".join(f"• {b}" for b in cfg['benefits']),
            inline=False,
        )
    if cfg.get('questions'):
        embed.add_field(
            name="❓ Вопросы заявки",
            value="\n".join(f"{i}. {q}" for i, q in enumerate(cfg['questions'], 1)),
            inline=False,
        )
    if cfg.get('note'):
        embed.add_field(name="ℹ️ Примечание", value=cfg['note'], inline=False)


async def _open_application(interaction, key):
    user = interaction.user
    guild = interaction.guild

    if not guild.me.guild_permissions.manage_channels:
        await interaction.response.send_message(
            "❌ У бота нет прав `Управлять каналами`.", ephemeral=True)
        return

    cat = await _find_or_create_category(guild)
    if cat is None:
        await interaction.response.send_message(
            "❌ Не удалось найти/создать категорию заявок.", ephemeral=True)
        return

    # Проверка уже открытой заявки
    for ch in cat.channels:
        if ch.topic and f'owner:{user.id}' in ch.topic:
            try:
                await interaction.response.send_message(
                    f"❌ У тебя уже есть открытая заявка: {ch.mention}", ephemeral=True)
            except discord.InteractionResponded:
                pass
            return

    cfg = APPLICATIONS[key]
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False),
        user: discord.PermissionOverwrite(
            view_channel=True, send_messages=True, read_message_history=True,
            attach_files=True, embed_links=True),
        guild.me: discord.PermissionOverwrite(
            view_channel=True, send_messages=True, read_message_history=True),
    }
    for role in _staff_roles(guild):
        overwrites[role] = discord.PermissionOverwrite(
            view_channel=True, send_messages=True, read_message_history=True)

    base = f"заявка-{key}-{_safe_channel_name(user.name)}"
    name = base
    existing = {c.name for c in cat.channels}
    n = 2
    while name in existing:
        name = f"{base}-{n}"
        n += 1

    try:
        channel = await guild.create_text_channel(
            name, category=cat, overwrites=overwrites, topic=f'owner:{user.id} | type:{key}')
    except discord.Forbidden:
        await interaction.response.send_message("❌ У бота нет прав создавать каналы.", ephemeral=True)
        return
    except Exception as e:
        logger.error(f'Ошибка создания канала заявки: {e}')
        try:
            await interaction.response.send_message(f"❌ Ошибка: {e}", ephemeral=True)
        except discord.InteractionResponded:
            pass
        return

    embed = discord.Embed(
        title=f"{cfg['emoji']} {cfg['title']}",
        thumbnail=True,
        description=(
            f"Здравствуй, {user.mention}! 👋\n"
            "Ответь на вопросы ниже **прямо в этом канале**, по пунктам. "
            "Администрация рассмотрит заявку и примет решение ✅ / ❌."
        ),
        color=cfg['color'],
        timestamp=datetime.now(),
    )
    if user.display_avatar:
        embed.set_thumbnail(url=user.display_avatar.url)
    _add_app_fields(embed, cfg)
    embed.add_field(name="📌 Статус", value=STATUS_REVIEW, inline=False)
    embed.set_footer(text=f"ID: {user.id} • type:{key} • Vector.prod • Заявки")

    try:
        await channel.send(embed=embed, view=ApplicationModerationView())
        await interaction.response.send_message(f"✅ Заявка создана: {channel.mention}", ephemeral=True)
    except discord.InteractionResponded:
        await interaction.followup.send(f"✅ Заявка создана: {channel.mention}", ephemeral=True)
    logger.info(f'{user} создал заявку ({key}) в канале {channel.name}')


class ApplicationModerationView(discord.ui.View):
    """Кнопки для администрации: принять / отклонить / закрыть"""

    def __init__(self):
        super().__init__(timeout=None)

    async def _update_status(self, interaction, status, color, delete=False):
        if not _is_staff(interaction.user):
            await interaction.response.send_message("❌ Только администрация.", ephemeral=True)
            return
            return
        embed = interaction.message.embeds[0]
        idx = _find_field_index(embed, '📌 Статус')
        if idx is not None:
            embed.set_field_at(idx, name="📌 Статус", value=status, inline=False)
        embed.color = color
        m = re.search(r'ID:\s*(\d+)', embed.footer.text or '')
        author = None
        if m:
            try:
                author = await interaction.guild.fetch_member(int(m.group(1)))
            except Exception:
                author = None
        embed.set_footer(text=f"Решение: {interaction.user.display_name} • Vector.prod • Заявки")
        await interaction.response.edit_message(embed=embed, view=ApplicationCloseView())

        if author:
            try:
                msg = discord.Embed(
                    title=embed.title,
                    description=f"Статус твоей заявки: **{status}**",
                    color=color, timestamp=datetime.now())
                if author.display_avatar:
                    msg.set_thumbnail(url=author.display_avatar.url)
                msg.set_footer(text=f"{interaction.guild.name} • Vector.prod • Заявки")
                await author.send(embed=msg)
            except discord.Forbidden:
                pass
            except Exception as e:
                logger.error(f'Ошибка уведомления автора заявки: {e}')
            try:
                await interaction.channel.send(
                    f"{author.mention}, твоя заявка: **{status}**. "
                    "Если вопросов больше нет и всё решено — будем благодарны, если закроешь "
                    "её кнопкой **«🔒 Закрыть заявку»** ☺️",
                    allowed_mentions=discord.AllowedMentions(users=[author]))
            except Exception as e:
                logger.error(f'Ошибка пинга автора заявки: {e}')

        if delete:
            try:
                await interaction.channel.delete()
                logger.info(f'Заявка закрыта и удалена: {interaction.channel.name}')
            except Exception as e:
                logger.error(f'Ошибка удаления канала заявки: {e}')
        else:
            logger.info(f'{interaction.user} {status} заявку: {embed.title}')

    async def _grant_role(self, interaction):
        """Выдаёт роль заявителю при принятии (берёт owner/type из topic канала)"""
        topic = getattr(interaction.channel, 'topic', '') or ''
        m_owner = re.search(r'owner:(\d+)', topic)
        m_type = re.search(r'type:(\w+)', topic)
        if not m_owner or not m_type:
            return
        cfg = APPLICATIONS.get(m_type.group(1))
        role_id = cfg.get('role_id') if cfg else None
        if not role_id:
            return
        guild = interaction.guild
        try:
            member = await guild.fetch_member(int(m_owner.group(1)))
        except Exception:
            return
        role = guild.get_role(int(role_id))
        if not role:
            logger.warning(f'Роль для выдачи не найдена на сервере (ID: {role_id})')
            return
        try:
            await member.add_roles(role, reason=f'Принята заявка ({m_type.group(1)})')
            logger.info(f'Выдана роль {role.name!r} участнику {member}')
        except discord.Forbidden:
            logger.warning(f'Нет прав на выдачу роли {role.name!r} (иерархия/Manage Roles)')
        except Exception as e:
            logger.error(f'Ошибка выдачи роли {role.name!r}: {e}')

    @discord.ui.button(label="✅ Принять", style=discord.ButtonStyle.success, custom_id="apply_accept")
    async def approve(self, interaction, button):
        if not _is_staff(interaction.user):
            await interaction.response.send_message("❌ Только администрация.", ephemeral=True)
            return
        await self._update_status(interaction, STATUS_APPROVED, discord.Color.green())
        await self._grant_role(interaction)

    @discord.ui.button(label="❌ Отклонить", style=discord.ButtonStyle.danger, custom_id="apply_reject")
    async def reject(self, interaction, button):
        if not _is_staff(interaction.user):
            await interaction.response.send_message("❌ Только администрация.", ephemeral=True)
            return
        await self._update_status(interaction, STATUS_REJECTED, discord.Color.red())

    @discord.ui.button(label="🔒 Закрыть", style=discord.ButtonStyle.secondary, custom_id="apply_close")
    async def close(self, interaction, button):
        topic = getattr(interaction.channel, 'topic', '') or ''
        m_owner = re.search(r'owner:(\d+)', topic)
        owner_id = int(m_owner.group(1)) if m_owner else None
        if not _is_staff(interaction.user) and interaction.user.id != owner_id:
            await interaction.response.send_message(
                "❌ Только администрация или автор заявки может закрыть её.", ephemeral=True)
            return
        try:
            await interaction.response.send_message("🔒 Заявка закрыта.", ephemeral=True)
        except discord.InteractionResponded:
            pass
        try:
            await interaction.channel.delete()
            logger.info(f'Заявка закрыта: {interaction.channel.name} (пользователем {interaction.user})')
        except Exception as e:
            logger.error(f'Ошибка удаления канала заявки: {e}')


class ApplicationCloseView(discord.ui.View):
    """Кнопка закрытия заявки для создателя (после принятия/отклонения)"""

    def __init__(self):
        super().__init__(timeout=None)

    async def _can_close(self, interaction):
        topic = getattr(interaction.channel, 'topic', '') or ''
        m = re.search(r'owner:(\d+)', topic)
        owner_id = int(m.group(1)) if m else None
        if owner_id and interaction.user.id == owner_id:
            return True
        return _is_staff(interaction.user)

    @discord.ui.button(label="🔒 Закрыть заявку", style=discord.ButtonStyle.danger, custom_id="apply_user_close")
    async def close_app(self, interaction, button):
        if not await self._can_close(interaction):
            await interaction.response.send_message(
                "❌ Только создатель заявки или администрация может закрыть её.", ephemeral=True)
            return
        try:
            await interaction.response.send_message("🔒 Заявка закрыта.")
        except discord.InteractionResponded:
            pass
        try:
            await interaction.channel.delete()
            logger.info(f'Заявка закрыта пользователем/админом: {interaction.channel.name}')
        except Exception as e:
            logger.error(f'Ошибка удаления канала заявки: {e}')


class ApplicationPanelView(discord.ui.View):
    """Панель с кнопкой подачи заявки (тип определяется по каналу)"""

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="📝 Подать заявку", style=discord.ButtonStyle.primary, custom_id="apply_open")
    async def open_app(self, interaction, button):
        key = _detect_type(interaction.channel)
        if key is None:
            await interaction.response.send_message(
                "❌ Не удалось определить тип заявки для этого канала.", ephemeral=True)
            return
        await _open_application(interaction, key)


def _build_application_panel(guild, key):
    cfg = APPLICATIONS[key]
    embed = discord.Embed(
        title=f"{cfg['emoji']} {cfg['title']}",
        description=(
            "Хочешь присоединиться? Нажми кнопку **«Подать заявку»** ниже — "
            "для тебя откроется приватный канал с вопросами, и ты ответишь прямо там.\n\n"
            "Администрация рассмотрит заявку и примет решение ✅ / ❌."
        ),
        color=cfg['color'],
        timestamp=datetime.now(),
    )
    _add_app_fields(embed, cfg)
    embed.set_footer(text="Vector.prod • Заявки")
    return embed, ApplicationPanelView()


def setup_applications(bot):
    """Настройка системы заявок"""

    @bot.hybrid_command(name="apply-setup", description="Разместить панель заявок в текущем канале")
    async def apply_setup_cmd(ctx: commands.Context):
        try:
            if not _is_staff(ctx.author):
                await ctx.send("❌ Недостаточно прав.", ephemeral=True)
                return
            key = _detect_type(ctx.channel)
            if key is None:
                await ctx.send(
                    "❌ Канал не похож на канал заявок. Допустимые: "
                    + ", ".join(f"{c['emoji']} {c['title']}" for c in APPLICATIONS.values()),
                    ephemeral=True,
                )
                return
            embed, view = _build_application_panel(ctx.guild, key)
            await ctx.channel.send(embed=embed, view=view)
            logger.info(f'{ctx.author} разместил панель заявок ({key}) в {ctx.channel.name}')
        except Exception as e:
            await ctx.send(f"❌ Ошибка: {e}", ephemeral=True)
            logger.error(f'Ошибка apply-setup: {e}')

    bot.add_view(ApplicationPanelView())
    bot.add_view(ApplicationModerationView())
    bot.add_view(ApplicationCloseView())
    from modules.panels import register_panel

    for key, cfg in APPLICATIONS.items():
        register_panel(
            channel_keywords=cfg['keywords'],
            label="📝 Подать заявку",
            expected_ids=["apply_open"],
            build=lambda guild, k=key: _build_application_panel(guild, k),
        )
    logger.info('Модуль заявок загружен (persistent views: apply_open, apply_accept, apply_reject, apply_close)')
