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
        "commands": ["clear", "kick", "ban", "unban", "softban", "hackban", "banlist",
                     "mute", "timeout", "untimeout", "warn", "unwarn", "warnings", "clearwarn",
                     "purge", "slowmode", "lock", "unlock", "lockall", "unlockall", "nuke",
                     "nick", "role", "unrole", "voicekick", "voicemute", "voiceunmute", "moveall",
                     "report"]
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
    """Постоянная кнопочная навигация по помощи (persistent)"""

    def __init__(self, bot=None):
        super().__init__(timeout=None)
        self.bot = bot
        self._add_all_buttons()

    def _add_all_buttons(self):
        # Строка 0-2: категории
        row = 0
        for i, cat_key in enumerate(CATEGORIES):
            cat = CATEGORIES[cat_key]
            self.add_item(CategoryButton(cat_key, cat["name"], cat["emoji"], row=i // 3))
        # Строка 3: назад + закрыть
        self.add_item(BackButton(row=3))
        self.add_item(CloseButton(row=3))

    async def show(self, interaction, cat_key=None):
        self.current = cat_key or "main"
        if self.current == "main":
            embed = _build_main_embed(self.bot)
        else:
            embed = _build_category_embed(self.bot, self.current)
        # Панель persistent: не меняем кнопки, только embed
        await interaction.response.edit_message(embed=embed)


class CategoryButton(discord.ui.Button):
    """Кнопка выбора категории"""

    def __init__(self, cat_key, name, emoji, row=0):
        super().__init__(
            label=name, style=discord.ButtonStyle.secondary, emoji=emoji,
            custom_id=f"help_cat_{cat_key}", row=row,
        )
        self.cat_key = cat_key

    async def callback(self, interaction: discord.Interaction):
        if not isinstance(self.view, HelpView):
            return
        await self.view.show(interaction, self.cat_key)


class BackButton(discord.ui.Button):
    """Кнопка возврата к общему списку"""

    def __init__(self, row=3):
        super().__init__(
            label="🏠 Главная", style=discord.ButtonStyle.primary,
            custom_id="help_back", row=row,
        )

    async def callback(self, interaction: discord.Interaction):
        if not isinstance(self.view, HelpView):
            return
        await self.view.show(interaction, "main")


class CloseButton(discord.ui.Button):
    """Кнопка закрытия помощи"""

    def __init__(self, row=3):
        super().__init__(
            label="❌ Закрыть", style=discord.ButtonStyle.danger,
            custom_id="help_close", row=row,
        )

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        await interaction.message.delete()


def setup_help(bot):
    """Настройка команды помощи"""

    # Регистрируем постоянную панель помощи (работает после рестарта)
    bot.help_view = HelpView(bot)
    bot.add_view(bot.help_view)

    @bot.hybrid_command(name="help", description="Показать все команды бота")
    @app_commands.describe(category="Категория команд (moderation, music, economy, games, utilities, tickets, other)")
    async def help_cmd(ctx: commands.Context, category: str = None):
        """Команда помощи по боту"""
        try:
            if category and category.lower() in CATEGORIES:
                embed = _build_category_embed(bot, category.lower())
            else:
                embed = _build_main_embed(bot)
            await ctx.send(embed=embed, view=bot.help_view)
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
