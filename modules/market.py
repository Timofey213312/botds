"""
Модуль маркетплейса (канал 🛒купи-продай)
- Панель с кнопкой «Разместить объявление» (открывает форму)
- Форма: тип сделки, товар, цена, описание, контакт → аккуратный эмбед в канал
- Кнопка «🗑 Снять объявление» (только автор или администрация)
"""

import logging
import re
from datetime import datetime

import discord
from discord import app_commands
from discord.ext import commands

logger = logging.getLogger('discord_bot.market')

EMBED_COLOR = 0x2ecc71
PANEL_KEYWORDS = ('купи-продай', 'купи', 'продай', 'market', 'купля')


def _is_staff(member):
    return bool(member.guild_permissions.manage_channels or member.guild_permissions.administrator)


def _find_channel(guild, keywords):
    for channel in guild.text_channels:
        name = (channel.name or '').lower()
        if any(kw in name for kw in keywords):
            return channel
    return None


def _deal_style(text):
    t = (text or '').lower()
    if 'продаж' in t:
        return '💰 Продажа', 0x2ecc71
    if 'покуп' in t:
        return '🛒 Покупка', 0x3498db
    return '📦 Сделка', EMBED_COLOR


class MarketModal(discord.ui.Modal):
    deal = discord.ui.TextInput(label="Тип сделки", placeholder="Продажа или Покупка", max_length=50, required=True)
    item = discord.ui.TextInput(label="Товар / услуга", placeholder="Что продаёте или ищете", max_length=100, required=True)
    price = discord.ui.TextInput(label="Цена", placeholder="Напр.: 500₽ / договорная", max_length=100, required=True)
    desc = discord.ui.TextInput(label="Описание", placeholder="Детали, состояние, условия", max_length=1500, required=False, style=discord.TextStyle.paragraph)
    contact = discord.ui.TextInput(label="Контакт", placeholder="Где с вами связаться (ник/ссылка)", max_length=200, required=False)

    def __init__(self, guild):
        super().__init__(title="🛒 Объявление")
        self.guild = guild

    async def on_submit(self, interaction):
        user = interaction.user
        d_type, d_color = _deal_style(self.deal.value)
        embed = discord.Embed(
            title=f"{d_type}: {self.item.value}",
            description=self.desc.value or "_(без описания)_",
            color=d_color,
            timestamp=datetime.now(),
        )
        embed.set_author(name=f"{user.display_name}", icon_url=user.display_avatar.url)
        if user.display_avatar:
            embed.set_thumbnail(url=user.display_avatar.url)
        embed.add_field(name="💱 Тип", value=self.deal.value, inline=True)
        embed.add_field(name="💰 Цена", value=self.price.value, inline=True)
        if self.contact.value and self.contact.value.strip():
            embed.add_field(name="📞 Контакт", value=self.contact.value.strip(), inline=False)
        embed.set_footer(text=f"ID: {user.id} • Vector.prod • Купи-продай")
        await interaction.channel.send(embed=embed, view=MarketRemoveView())
        await interaction.response.send_message("✅ Объявление размещено!", ephemeral=True)
        logger.info(f'{user} разместил объявление: {self.item.value}')


class MarketRemoveView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🗑 Снять объявление", style=discord.ButtonStyle.danger, custom_id="market_remove")
    async def remove(self, interaction, button):
        try:
            author_id = None
            m = re.search(r'ID:\s*(\d+)', (interaction.message.embeds[0].footer.text or '') if interaction.message.embeds else '')
            if m:
                author_id = int(m.group(1))
        except Exception:
            author_id = None
        if author_id != interaction.user.id and not _is_staff(interaction.user):
            await interaction.response.send_message("❌ Только автор объявления или администрация может снять его.", ephemeral=True)
            return
        try:
            await interaction.response.defer(ephemeral=True)
            await interaction.message.delete()
            await interaction.followup.send("🗑 Объявление снято.", ephemeral=True)
            logger.info(f'{interaction.user} снял объявление')
        except Exception as e:
            logger.error(f'Ошибка снятия объявления: {e}')


class MarketPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="📦 Разместить объявление", style=discord.ButtonStyle.primary, custom_id="market_open")
    async def open_modal(self, interaction, button):
        await interaction.response.send_modal(MarketModal(interaction.guild))


def _build_market_panel(guild):
    embed = discord.Embed(
        title="🛒 Купи-продай",
        description=(
            "Торговая площадка клана. Хочешь продать или купить что-то? "
            "Нажми **«Разместить объявление»**, заполни форму — и твоё предложение "
            "появится здесь красивым блоком.\n\n"
            "• 💰 Продажа — зелёным\n• 🛒 Покупка — синим\n"
            "Снять объявление можно кнопкой под ним."
        ),
        color=EMBED_COLOR,
        timestamp=datetime.now(),
    )
    embed.set_footer(text="Vector.prod • Купи-продай")
    return embed, MarketPanelView()


def setup_market(bot):
    """Настройка модуля маркетплейса"""

    @bot.hybrid_command(name="market-setup", description="Разместить панель объявлений в канале купи-продай")
    async def market_setup_cmd(ctx: commands.Context):
        try:
            if not _is_staff(ctx.author):
                await ctx.send("❌ Недостаточно прав.", ephemeral=True)
                return
            channel = _find_channel(ctx.guild, PANEL_KEYWORDS)
            if channel is None:
                await ctx.send("❌ Канал купи-продай не найден (в названии должно быть «купи-продай»).", ephemeral=True)
                return
            embed, view = _build_market_panel(ctx.guild)
            await channel.send(embed=embed, view=view)
            logger.info(f'{ctx.author} разместил панель маркетплейса в {channel.name}')
        except Exception as e:
            await ctx.send(f"❌ Ошибка: {e}", ephemeral=True)
            logger.error(f'Ошибка market-setup: {e}')

    bot.add_view(MarketPanelView())
    bot.add_view(MarketRemoveView())
    from modules.panels import register_panel

    register_panel(
        channel_keywords=PANEL_KEYWORDS,
        label="📦 Разместить объявление",
        expected_ids=["market_open"],
        build=_build_market_panel,
    )
    logger.info('Модуль маркетплейса загружен (persistent views: market_open, market_remove)')
