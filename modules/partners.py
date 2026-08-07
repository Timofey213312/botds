"""
Модуль системы партнёрств
- !partner-panel — сообщение с кнопкой «🤝 Подать заявку» (модальное окно)
- Заявки попадают в канал модерации партнёров
- Администрация одобряет/отклоняет; одобренные публикуются в канале партнёрок
"""

import logging
from datetime import datetime

import discord
from discord import app_commands
from discord.ext import commands

logger = logging.getLogger('discord_bot.partners')

EMBED_COLOR = 0x9000FF

PARTNERS_CHANNEL_KEYWORDS = ('партн', 'partner')
REVIEW_CHANNEL_KEYWORDS = ('заявк', 'партн-модер', 'partner-review', 'модерац')


def _find_channel(guild, keywords):
    for channel in guild.text_channels:
        name = (channel.name or '').lower()
        for kw in keywords:
            if kw in name:
                return channel
    return None


def _find_partners_channel(guild):
    return _find_channel(guild, PARTNERS_CHANNEL_KEYWORDS)


def _find_review_channel(guild):
    return _find_channel(guild, REVIEW_CHANNEL_KEYWORDS)


def _is_staff(member):
    return bool(member.guild_permissions.manage_channels or member.guild_permissions.administrator)


class PartnerModal(discord.ui.Modal, title="🤝 Заявка на партнёрство"):
    server_name = discord.ui.TextInput(label="Название сервера", max_length=80)
    server_type = discord.ui.TextInput(
        label="Тип партнёрства",
        placeholder="Сервер или бот",
        max_length=20,
        default="Сервер",
    )
    description = discord.ui.TextInput(
        label="Описание",
        placeholder="Расскажите о вашем сервере/боте",
        style=discord.TextStyle.paragraph,
        max_length=1000,
    )
    invite = discord.ui.TextInput(
        label="Ссылка-приглашение",
        placeholder="https://discord.gg/...",
        max_length=100,
    )

    async def on_submit(self, interaction):
        review_channel = _find_review_channel(interaction.guild)
        if review_channel is None:
            await interaction.response.send_message(
                "❌ Канал заявок не найден. Создай канал с «заявк» в названии.",
                ephemeral=True,
            )
            return

        embed = discord.Embed(
            title=self.server_name.value,
            description=self.description.value or "_(без описания)_",
            color=EMBED_COLOR,
            timestamp=datetime.now(),
        )
        embed.set_author(name=f"{self.server_type.value}", icon_url=interaction.user.display_avatar.url)
        embed.add_field(name="Тип", value=self.server_type.value, inline=True)
        embed.add_field(name="Ссылка", value=self.invite.value, inline=True)
        embed.add_field(name="Заявитель", value=interaction.user.mention, inline=False)
        embed.set_footer(text=f"ID: {interaction.user.id} • {datetime.now().strftime('%d.%m.%Y %H:%M')}")

        await review_channel.send(embed=embed, view=PartnerReviewView())
        await interaction.response.send_message(
            f"✅ Заявка отправлена на рассмотрение: {review_channel.mention}",
            ephemeral=True,
        )
        logger.info(f'{interaction.user} подал заявку на партнёрство: {self.server_name.value}')


class PartnerReviewView(discord.ui.View):
    """Кнопки одобрения/отклонения заявки (для администрации)"""

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="✅ Одобрить", style=discord.ButtonStyle.success, custom_id="partner_approve")
    async def approve(self, interaction, button):
        await self._handle(interaction, approved=True)

    @discord.ui.button(label="❌ Отклонить", style=discord.ButtonStyle.danger, custom_id="partner_reject")
    async def reject(self, interaction, button):
        await self._handle(interaction, approved=False)

    async def _handle(self, interaction, approved):
        if not _is_staff(interaction.user):
            await interaction.response.send_message("❌ Только администрация может решать.", ephemeral=True)
            return

        embed = interaction.message.embeds[0]
        status = "✅ Одобрено" if approved else "❌ Отклонено"
        color = discord.Color.green() if approved else discord.Color.red()

        try:
            embed.color = color
            embed.add_field(name="Статус", value=f"{status} — {interaction.user.display_name}", inline=False)
        except Exception:
            embed.add_field(name="Статус", value=f"{status} — {interaction.user.display_name}", inline=False)

        await interaction.response.edit_message(embed=embed, view=None)

        if approved:
            await self._publish(interaction, embed)

        logger.info(f'{interaction.user} {"одобрил" if approved else "отклонил"} заявку: {embed.title}')

    async def _publish(self, interaction, original_embed):
        partners_channel = _find_partners_channel(interaction.guild)
        if partners_channel is None:
            return

        embed = discord.Embed(
            title=f"🤝 {original_embed.title}",
            description=original_embed.description or "",
            color=discord.Color.green(),
            timestamp=datetime.now(),
        )
        for field in original_embed.fields:
            if field.name == "Заявитель":
                continue
            embed.add_field(name=field.name, value=field.value, inline=field.inline)

        invite = next((f.value for f in original_embed.fields if f.name == "Ссылка"), None)
        if invite:
            embed.add_field(name="Присоединиться", value=f"[Открыть]({invite})", inline=False)

        await partners_channel.send(embed=embed)


class PartnerPanelView(discord.ui.View):
    """Панель с кнопкой подачи заявки"""

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🤝 Подать заявку", style=discord.ButtonStyle.primary, custom_id="partner_panel_open")
    async def open_modal(self, interaction, button):
        await interaction.response.send_modal(PartnerModal())


def setup_partners(bot):
    """Настройка системы партнёрств"""

    @bot.hybrid_command(name="partner-panel", description="Разместить панель подачи заявок на партнёрство")
    async def partner_panel_cmd(ctx: commands.Context):
        """Размещение панели с кнопкой в канале партнёров"""
        try:
            if not _is_staff(ctx.author):
                await ctx.send("❌ Недостаточно прав.", ephemeral=True)
                return
            channel = _find_partners_channel(ctx.guild)
            if channel is None:
                await ctx.send(
                    "❌ Канал партнёров не найден. Создай канал с «партн» в названии.",
                    ephemeral=True,
                )
                return

            embed = discord.Embed(
                title="🤝 Партнёрство",
                description="Нажми кнопку ниже, чтобы подать заявку на партнёрство.\n"
                            "Наша администрация рассмотрит её в ближайшее время.",
                color=EMBED_COLOR,
            )
            await channel.send(embed=embed, view=PartnerPanelView())
            logger.info(f'{ctx.author} разместил панель партнёрств в {channel.name}')
        except Exception as e:
            await ctx.send(f"❌ Ошибка: {e}", ephemeral=True)
            logger.error(f'Ошибка partner-panel: {e}')

    bot.add_view(PartnerPanelView())
    bot.add_view(PartnerReviewView())
    logger.info('Модуль партнёров загружен (persistent views: partner_panel_open, partner_approve, partner_reject)')
