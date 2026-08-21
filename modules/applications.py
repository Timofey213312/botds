"""
Модуль системы заявок (подача на роли)
- Авто-панель в каналах: ⚔️ клан, 🎥 медиа, 🪄 партнёр-менеджер, 🛡️ модератор
- Кнопка «Подать заявку» открывает форму (модальное окно)
- Заявка публикуется в канале с кнопками «Принять / Отклонить» для администрации
- Автор получает уведомление о статусе в ЛС
"""

import logging
from datetime import datetime

import discord
from discord import app_commands
from discord.ext import commands

logger = logging.getLogger('discord_bot.applications')

STATUS_REVIEW = '📝 На рассмотрении'
STATUS_APPROVED = '✅ Принято'
STATUS_REJECTED = '❌ Отклонено'

APPLICATIONS = {
    'clan': {
        'emoji': '⚔️',
        'title': 'Заявка в клан',
        'keywords': ('ᴄʟᴀɴ', 'clan'),
        'color': 0x9b59b6,
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
        'fields': [
            ('Твои ответы', 'Ответь на вопросы из канала выше — по одному пункту на строку', 4000, True, False),
        ],
    },
    'media': {
        'emoji': '🎥',
        'title': 'Заявка в медиа-команду',
        'keywords': ('ᴍᴇᴅɪᴀ', 'media'),
        'color': 0xe91e63,
        'fields': [
            ('Никнейм', 'Твой никнейм / ID', 100, True, False),
            ('Что умеешь?', 'Монтаж / дизайн / стримы / другое', 300, True, False),
            ('Примеры работ (ссылки)', 'Ссылки на портфолио / канал', 1000, True, True),
            ('Активность', 'Сколько времени готов уделять?', 300, False, False),
            ('Дополнительно', '', 1000, False, True),
        ],
    },
    'partner': {
        'emoji': '🪄',
        'title': 'Заявка в партнёр-менеджеры',
        'keywords': ('ᴘᴀʀᴛɴᴇʀ', 'partner'),
        'color': 0x00bcd4,
        'fields': [
            ('Никнейм / Контакты', 'Ник и где с тобой связаться', 200, True, False),
            ('Опыт партнёрства', 'Работал ли с проектами? С какими?', 1000, True, True),
            ('С какими проектами хочешь работать?', '', 1000, False, True),
            ('Чем можешь быть полезен?', '', 800, False, True),
            ('Дополнительно', '', 1000, False, True),
        ],
    },
    'moder': {
        'emoji': '🛡️',
        'title': 'Заявка в модераторы',
        'keywords': ('ᴍᴏᴅᴇʀ', 'moder', 'модер', 'моде'),
        'color': 0x4caf50,
        'fields': [
            ('Никнейм / Возраст', 'Например: Player, 18 лет', 100, True, False),
            ('Опыт модерации', 'Где модерировал, сколько времени', 1000, True, True),
            ('Почему именно ты?', 'Почему должен стать модератором', 1000, True, True),
            ('Активность', 'Сколько онлайна в день', 300, False, False),
            ('Дополнительно', '', 1000, False, True),
        ],
    },
}


def _is_staff(member):
    return bool(member.guild_permissions.manage_channels or member.guild_permissions.administrator)


def _detect_type(channel):
    name = (channel.name or '').lower()
    for key, cfg in APPLICATIONS.items():
        if any(kw in name for kw in cfg['keywords']):
            return key
    return None


def _find_field_index(embed, prefix):
    for i, f in enumerate(embed.fields):
        if f.name.startswith(prefix):
            return i
    return None


class ApplicationModal(discord.ui.Modal):
    q1 = discord.ui.TextInput(label="Вопрос 1", max_length=100)
    q2 = discord.ui.TextInput(label="Вопрос 2", max_length=300, required=False)
    q3 = discord.ui.TextInput(label="Вопрос 3", max_length=1000, required=False, style=discord.TextStyle.paragraph)
    q4 = discord.ui.TextInput(label="Вопрос 4", max_length=1000, required=False, style=discord.TextStyle.paragraph)
    q5 = discord.ui.TextInput(label="Вопрос 5", max_length=1000, required=False, style=discord.TextStyle.paragraph)

    def __init__(self, key, guild):
        cfg = APPLICATIONS[key]
        super().__init__(title=f"{cfg['emoji']} {cfg['title']}")
        self.key = key
        self.guild = guild
        for i, f in enumerate(cfg['fields'], start=1):
            label, placeholder, max_len, required, paragraph = f
            field = getattr(self, f'q{i}')
            field.label = label
            field.placeholder = placeholder or ''
            field.max_length = max_len
            field.required = required
            field.style = discord.TextStyle.paragraph if paragraph else discord.TextStyle.short

    async def on_submit(self, interaction):
        cfg = APPLICATIONS[self.key]
        user = interaction.user

        answers = []
        for i, f in enumerate(cfg['fields'], start=1):
            val = getattr(self, f'q{i}').value
            if val and val.strip():
                answers.append((f[0], val.strip()))

        if not answers:
            await interaction.response.send_message("❌ Заявка пустая.", ephemeral=True)
            return

        embed = discord.Embed(
            title=f"{cfg['emoji']} {cfg['title']}",
            description=f"Заявка от {user.mention}",
            color=cfg['color'],
            timestamp=datetime.now(),
        )
        embed.set_author(name=f"{user.display_name}", icon_url=user.display_avatar.url)
        if user.display_avatar:
            embed.set_thumbnail(url=user.display_avatar.url)
        for label, val in answers:
            embed.add_field(name=f"• {label}", value=val, inline=False)
        embed.add_field(name="📌 Статус", value=STATUS_REVIEW, inline=False)
        embed.set_footer(text=f"ID: {user.id} • type:{self.key} • Vector.prod • Заявки")

        await interaction.channel.send(embed=embed, view=ApplicationModerationView())
        await interaction.response.send_message(
            f"📨 Заявка отправлена в {interaction.channel.mention}. Ожидай решения администрации.",
            ephemeral=True,
        )
        logger.info(f'{user} подал заявку ({self.key}): {cfg["title"]}')


class ApplicationModerationView(discord.ui.View):
    """Кнопки принятия/отклонения заявки (для администрации)"""

    def __init__(self):
        super().__init__(timeout=None)

    async def _update_status(self, interaction, status, color):
        if not _is_staff(interaction.user):
            await interaction.response.send_message("❌ Только администрация может менять статус заявки.", ephemeral=True)
            return
        embed = interaction.message.embeds[0]
        idx = _find_field_index(embed, '📌 Статус')
        if idx is not None:
            embed.set_field_at(idx, name="📌 Статус", value=status, inline=False)
        embed.color = color
        embed.set_footer(text=f"Решение: {interaction.user.display_name} • Vector.prod • Заявки")
        await interaction.response.edit_message(embed=embed, view=None)

        # Уведомление автора в ЛС
        try:
            import re as _re
            m = _re.search(r'ID:\s*(\d+)', embed.footer.text or '')
            if m:
                author = await interaction.guild.fetch_member(int(m.group(1)))
                if author:
                    msg = discord.Embed(
                        title=f"{embed.title}",
                        description=f"Статус твоей заявки: **{status}**",
                        color=color,
                        timestamp=datetime.now(),
                    )
                    if author.display_avatar:
                        msg.set_thumbnail(url=author.display_avatar.url)
                    msg.set_footer(text=f"{interaction.guild.name} • Vector.prod • Заявки")
                    await author.send(embed=msg)
        except discord.Forbidden:
            pass
        except Exception as e:
            logger.error(f'Ошибка уведомления автора заявки: {e}')
        logger.info(f'{interaction.user} {status} заявку: {embed.title}')

    @discord.ui.button(label="✅ Принять", style=discord.ButtonStyle.success, custom_id="apply_accept")
    async def approve(self, interaction, button):
        await self._update_status(interaction, STATUS_APPROVED, discord.Color.green())

    @discord.ui.button(label="❌ Отклонить", style=discord.ButtonStyle.danger, custom_id="apply_reject")
    async def reject(self, interaction, button):
        await self._update_status(interaction, STATUS_REJECTED, discord.Color.red())


class ApplicationPanelView(discord.ui.View):
    """Панель с кнопкой подачи заявки (тип определяется по каналу)"""

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="📝 Подать заявку", style=discord.ButtonStyle.primary, custom_id="apply_open")
    async def open_modal(self, interaction, button):
        key = _detect_type(interaction.channel)
        if key is None:
            await interaction.response.send_message(
                "❌ Не удалось определить тип заявки для этого канала.", ephemeral=True
            )
            return
        await interaction.response.send_modal(ApplicationModal(key, interaction.guild))


def _build_application_panel(guild, key):
    cfg = APPLICATIONS[key]
    embed = discord.Embed(
        title=f"{cfg['emoji']} {cfg['title']}",
        description=(
            "Хочешь присоединиться? Нажми кнопку **«Подать заявку»** ниже, "
            "заполни форму — и твоя заявка появится здесь.\n\n"
            "Администрация рассмотрит её и примет решение ✅ / ❌."
        ),
        color=cfg['color'],
        timestamp=datetime.now(),
    )
    if cfg.get('questions'):
        embed.add_field(
            name="📋 Вопросы заявки",
            value="\n".join(f"{i}. {q}" for i, q in enumerate(cfg['questions'], 1)),
            inline=False,
        )
    embed.set_footer(text="Vector.prod • Заявки")
    return embed, ApplicationPanelView()


def setup_applications(bot):
    """Настройка системы заявок"""

    @bot.hybrid_command(name="apply-setup", description="Разместить панель заявок в текущем канале")
    async def apply_setup_cmd(ctx: commands.Context):
        """Размещение панели заявок в канале (по типу канала)"""
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
    from modules.panels import register_panel

    for key, cfg in APPLICATIONS.items():
        register_panel(
            channel_keywords=cfg['keywords'],
            label="📝 Подать заявку",
            expected_ids=["apply_open"],
            build=lambda guild, k=key: _build_application_panel(guild, k),
        )
    logger.info('Модуль заявок загружен (persistent views: apply_open, apply_accept, apply_reject)')
