"""
Модуль системы идей
- !idea-panel — сообщение с кнопкой «💡 Предложить идею» (модальное окно)
- Идеи публикуются в канале идей с голосованием
- Администрация одобряет/отклоняет идеи (статусы)
"""

import logging
from datetime import datetime

import discord
from discord import app_commands
from discord.ext import commands

logger = logging.getLogger('discord_bot.ideas')

EMBED_COLOR = 0x9000FF
PANEL_CHANNEL_KEYWORDS = ('idea', 'иде', 'suggest')
SUBMIT_CHANNEL_KEYWORDS = ('приём-заявок', 'прием-заявок', 'приём', 'прием')
STATUS_UNDER_REVIEW = '📝 На рассмотрении'
STATUS_APPROVED = '✅ Принято'
STATUS_REJECTED = '❌ Отклонено'


def _find_channel(guild, keywords):
    """Поиск канала по ключевым словам"""
    for channel in guild.text_channels:
        name = (channel.name or '').lower()
        for kw in keywords:
            if kw in name:
                return channel
    return None


def _find_panel_channel(guild):
    """Канал для панели с кнопкой (идеи)"""
    return _find_channel(guild, PANEL_CHANNEL_KEYWORDS)


def _find_submit_channel(guild):
    """Канал для приёма заявок-идей (📥-приём-заявок)"""
    return _find_channel(guild, SUBMIT_CHANNEL_KEYWORDS)


def _is_staff(member):
    return bool(member.guild_permissions.manage_channels or member.guild_permissions.administrator)


class IdeaModal(discord.ui.Modal, title="💡 Предложить идею"):
    title_field = discord.ui.TextInput(
        label="Название идеи",
        placeholder="Короткое название идеи",
        max_length=80,
    )
    description = discord.ui.TextInput(
        label="Описание",
        placeholder="Опишите вашу идею подробнее...",
        style=discord.TextStyle.paragraph,
        max_length=1500,
        required=False,
    )

    def __init__(self, guild):
        super().__init__()
        self.guild = guild

    async def on_submit(self, interaction):
        channel = _find_submit_channel(interaction.guild)
        if channel is None:
            await interaction.response.send_message(
                "❌ Канал приёма заявок не найден. Создай канал с «приём-заявок» в названии.",
                ephemeral=True,
            )
            return

        embed = discord.Embed(
            title=self.title_field.value,
            description=self.description.value or "_(без описания)_",
            color=EMBED_COLOR,
            timestamp=datetime.now(),
        )
        embed.set_author(name=f"💡 Идея от {interaction.user.display_name}", icon_url=interaction.user.display_avatar.url)
        embed.add_field(name="Статус", value=STATUS_UNDER_REVIEW, inline=False)
        embed.set_footer(text=f"ID: {interaction.user.id} • {datetime.now().strftime('%d.%m.%Y %H:%M')}")

        msg = await channel.send(embed=embed, view=IdeaModerationView())
        await msg.add_reaction('👍')
        await msg.add_reaction('👎')
        await interaction.response.send_message(
            "📨 Ваша идея отправлена. Ожидайте, пока администрация рассмотрит её.",
            ephemeral=True,
        )
        logger.info(f'{interaction.user} предложил идею: {self.title_field.value}')


class IdeaModerationView(discord.ui.View):
    """Кнопки одобрения/отклонения идеи (для администрации)"""

    def __init__(self):
        super().__init__(timeout=None)

    async def _update_status(self, interaction, status, color):
        if not _is_staff(interaction.user):
            await interaction.response.send_message("❌ Только администрация может менять статус идеи.", ephemeral=True)
            return
        embed = interaction.message.embeds[0]
        embed.color = color
        embed.set_field_at(0, name="Статус", value=status, inline=False)
        embed.set_footer(
            text=f"{embed.footer.text if embed.footer.text else ''} • {interaction.user.display_name}"
        )
        await interaction.response.edit_message(embed=embed, view=None)

        # Уведомление автора идеи в ЛС
        await self._notify_author(interaction, embed, status)
        logger.info(f'{interaction.user} {status} идею: {embed.title}')

    async def _notify_author(self, interaction, embed, status):
        try:
            import re as _re
            m = _re.search(r'ID:\s*(\d+)', embed.footer.text or '')
            if not m:
                return
            author = await interaction.guild.fetch_member(int(m.group(1)))
            if not author:
                return
            msg = discord.Embed(
                title=f"💡 Статус вашей идеи",
                description=f"Идея: **{embed.title}**\n\nСтатус: **{status}**",
                color=embed.color,
            )
            msg.add_field(name="Описание", value=(embed.description or '_(без описания)_')[:500], inline=False)
            msg.set_footer(text=interaction.guild.name)
            await author.send(embed=msg)
        except discord.Forbidden:
            pass
        except Exception as e:
            logger.error(f'Ошибка отправки уведомления автору идеи: {e}')

    @discord.ui.button(label="✅ Принять", style=discord.ButtonStyle.success, custom_id="idea_approve")
    async def approve(self, interaction, button):
        await self._update_status(interaction, STATUS_APPROVED, discord.Color.green())

    @discord.ui.button(label="❌ Отклонить", style=discord.ButtonStyle.danger, custom_id="idea_reject")
    async def reject(self, interaction, button):
        await self._update_status(interaction, STATUS_REJECTED, discord.Color.red())


class IdeaPanelView(discord.ui.View):
    """Панель с кнопкой открытия формы идеи"""

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="💡 Предложить идею", style=discord.ButtonStyle.primary, custom_id="idea_panel_open")
    async def open_modal(self, interaction, button):
        await interaction.response.send_modal(IdeaModal(interaction.guild))


def setup_ideas(bot):
    """Настройка системы идей"""

    @bot.hybrid_command(name="idea-panel", description="Разместить панель предложения идей в канале идей")
    async def idea_panel_cmd(ctx: commands.Context):
        """Размещение панели с кнопкой в канале идей"""
        try:
            if not _is_staff(ctx.author):
                await ctx.send("❌ Недостаточно прав.", ephemeral=True)
                return
            channel = _find_panel_channel(ctx.guild)
            if channel is None:
                await ctx.send(
                    "❌ Канал идей не найден. Создай канал с «idea» или «иде» в названии.",
                    ephemeral=True,
                )
                return

            embed = discord.Embed(
                title="💡 Предложи идею",
                description="Нажми кнопку ниже, чтобы отправить свою идею.\n"
                            "Администрация рассмотрит её и поставит статус.",
                color=EMBED_COLOR,
            )
            await channel.send(embed=embed, view=IdeaPanelView())
            logger.info(f'{ctx.author} разместил панель идей в {channel.name}')
        except Exception as e:
            await ctx.send(f"❌ Ошибка: {e}", ephemeral=True)
            logger.error(f'Ошибка idea-panel: {e}')

    bot.add_view(IdeaPanelView())
    bot.add_view(IdeaModerationView())
    from modules.panels import register_panel

    def _build_idea_panel(guild):
        embed = discord.Embed(
            title="💡 Предложи идею",
            description="Нажми кнопку ниже, чтобы отправить свою идею.\n"
                        "Администрация рассмотрит её и поставит статус.",
            color=EMBED_COLOR,
        )
        return embed, IdeaPanelView()

    register_panel(
        channel_keywords=PANEL_CHANNEL_KEYWORDS,
        label="💡 Предложить идею",
        expected_ids=["idea_panel_open"],
        build=_build_idea_panel,
    )
    logger.info('Модуль идей загружен (persistent views: idea_panel_open, idea_approve, idea_reject)')
