"""
Модуль помощи и информации о командах бота
Команды: help (автоматическая)
"""

import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime
import logging

logger = logging.getLogger('discord_bot.help')

CATEGORIES = {
    "moderation": {
        "name": "⚖️ Модерация",
        "description": "Команды для управления сервером",
        "emoji": "⚖️",
        "color": discord.Color.red(),
        "commands": ["clear", "kick", "ban", "mute", "timeout", "untimeout", "report"]
    },
    "music": {
        "name": "🎵 Музыка",
        "description": "Команды для воспроизведения музыки",
        "emoji": "🎵",
        "color": discord.Color.green(),
        "commands": ["play", "playlist", "join", "pause", "resume", "skip", "stop", "leave",
                     "queue", "nowplaying", "volume", "bassboost", "loop", "loopqueue",
                     "shuffle", "panel"]
    },
    "economy": {
        "name": "💰 Экономика",
        "description": "Экономическая система с XP, уровнями и магазином",
        "emoji": "💰",
        "color": discord.Color.gold(),
        "commands": ["balance", "daily", "pay", "work", "leaderboard", "shop", "buy"]
    },
    "games": {
        "name": "🎮 Игры",
        "description": "Мини-игры и развлечения",
        "emoji": "🎮",
        "color": discord.Color.blurple(),
        "commands": ["8ball", "coinflip", "guess", "quest"]
    },
    "utilities": {
        "name": "🔧 Утилиты",
        "description": "Полезные команды и информация",
        "emoji": "🔧",
        "color": discord.Color.blue(),
        "commands": ["serverinfo", "userinfo", "ping", "avatar", "calc", "remind",
                     "uptime", "poll", "translate", "quote", "fact", "stats"]
    }
}

def _build_main_embed(bot):
    """Общая помощь: список категорий"""
    total_cmds = len([c for c in bot.commands if not c.hidden])
    embed = discord.Embed(
        title="📚 Помощь по командам бота",
        description=f"Префикс команд: **{bot.command_prefix}**\nТакже поддерживаются slash-команды (`/команда`)\nВсего команд: **{total_cmds}**",
        color=discord.Color.blue(),
        timestamp=datetime.now()
    )
    for cat_key, cat_info in CATEGORIES.items():
        count = len([c for c in bot.commands if not c.hidden and c.name in cat_info["commands"]])
        embed.add_field(
            name=f"{cat_info['emoji']} {cat_info['name']} ({count} команд)",
            value="Нажми кнопку ниже, чтобы увидеть команды",
            inline=True
        )
    embed.set_footer(text="Нажми кнопку с категорией, чтобы увидеть её команды")
    return embed


def _build_category_embed(bot, cat_key):
    """Embed со списком команд конкретной категории"""
    cat = CATEGORIES[cat_key]
    commands_list = []
    for cmd in bot.commands:
        if not cmd.hidden and cmd.name in cat["commands"]:
            commands_list.append(cmd)
    commands_list.sort(key=lambda c: c.name)

    embed = discord.Embed(
        title=f"{cat['emoji']} {cat['name']}",
        description=cat['description'],
        color=cat['color'],
        timestamp=datetime.now()
    )
    for cmd in commands_list:
        params = ""
        for param in cmd.clean_params:
            params += f" [{param}]"
        embed.add_field(
            name=f"{bot.command_prefix}{cmd.name}{params}",
            value=cmd.description or "Описание не указано",
            inline=False
        )
    embed.set_footer(text=f"Всего команд в категории: {len(commands_list)}")
    return embed


class HelpView(discord.ui.View):
    """Кнопочная навигация по помощи"""

    def __init__(self, bot, timeout=120):
        super().__init__(timeout=timeout)
        self.bot = bot
        self.current = "main"
        self._add_buttons()

    def _add_buttons(self):
        self.clear_items()
        if self.current == "main":
            for cat_key in CATEGORIES:
                self.add_item(CategoryButton(cat_key, self.bot))
            self.add_item(CloseButton())
        else:
            self.add_item(BackButton(self.bot))
            for cat_key in CATEGORIES:
                self.add_item(CategoryButton(cat_key, self.bot))
            self.add_item(CloseButton())

    async def show(self, interaction, cat_key=None):
        self.current = cat_key or "main"
        if self.current == "main":
            embed = _build_main_embed(self.bot)
        else:
            embed = _build_category_embed(self.bot, self.current)
        self._add_buttons()
        await interaction.response.edit_message(embed=embed, view=self)


class CategoryButton(discord.ui.Button):
    """Кнопка выбора категории"""

    def __init__(self, cat_key, bot):
        cat = CATEGORIES[cat_key]
        super().__init__(label=cat["name"], style=discord.ButtonStyle.secondary, emoji=cat["emoji"])
        self.cat_key = cat_key
        self.bot = bot

    async def callback(self, interaction: discord.Interaction):
        if not isinstance(self.view, HelpView):
            return
        await self.view.show(interaction, self.cat_key)


class BackButton(discord.ui.Button):
    """Кнопка возврата к общему списку"""

    def __init__(self, bot):
        super().__init__(label="🏠 Главная", style=discord.ButtonStyle.primary)
        self.bot = bot

    async def callback(self, interaction: discord.Interaction):
        if not isinstance(self.view, HelpView):
            return
        await self.view.show(interaction, "main")


class CloseButton(discord.ui.Button):
    """Кнопка закрытия помощи"""

    def __init__(self):
        super().__init__(label="❌ Закрыть", style=discord.ButtonStyle.danger)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        await interaction.message.delete()


def setup_help(bot):
    """Настройка команды помощи"""

    @bot.hybrid_command(name="help", description="Показать все команды бота")
    @app_commands.describe(category="Категория команд (moderation, music, economy, games, utilities, tickets, other)")
    async def help_cmd(ctx: commands.Context, category: str = None):
        """Команда помощи по боту"""
        try:
            if category and category.lower() in CATEGORIES:
                embed = _build_category_embed(bot, category.lower())
            else:
                embed = _build_main_embed(bot)
            view = HelpView(bot)
            await ctx.send(embed=embed, view=view)
            logger.info(f'{ctx.author} использовал команду help')
        except Exception as e:
            await ctx.send(f"❌ Ошибка при показе помощи: {e}", ephemeral=True)
            logger.error(f'Ошибка help: {e}')

    # Автодополнение категорий для slash-команды
    @help_cmd.autocomplete('category')
    async def help_category_autocomplete(
        interaction: discord.Interaction,
        current: str
    ):
        """Автодополнение для категорий помощи"""
        choices = [
            app_commands.Choice(name=cat.capitalize(), value=cat)
            for cat in CATEGORIES if current.lower() in cat.lower()
        ][:10]
        return choices

    logger.info("Модуль помощи загружен")
