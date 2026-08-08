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
        "name": "Модерация",
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
        "name": "Музыка",
        "description": "Команды для воспроизведения музыки",
        "emoji": "🎵",
        "color": discord.Color.green(),
        "commands": ["play", "playlist", "join", "pause", "resume", "skip", "stop", "leave",
                     "queue", "nowplaying", "volume", "bassboost", "loop", "loopqueue",
                     "shuffle", "panel"]
    },
    "economy": {
        "name": "Экономика",
        "description": "Экономическая система с XP, уровнями и магазином",
        "emoji": "💰",
        "color": discord.Color.gold(),
        "commands": ["balance", "daily", "pay", "work", "leaderboard", "shop", "buy"]
    },
    "games": {
        "name": "Игры",
        "description": "Мини-игры и развлечения",
        "emoji": "🎮",
        "color": discord.Color.blurple(),
        "commands": ["8ball", "coinflip", "guess", "quest"]
    },
    "utilities": {
        "name": "Утилиты",
        "description": "Полезные команды и информация",
        "emoji": "🔧",
        "color": discord.Color.blue(),
        "commands": ["serverinfo", "userinfo", "ping", "avatar", "calc", "remind",
                     "uptime", "poll", "translate", "quote", "fact", "stats"]
    }
}


def _get_commands(bot, cat_key=None):
    """Все видимые команды (или только категории). Безопасно."""
    result = []
    for cmd in bot.commands:
        try:
            if getattr(cmd, 'hidden', False):
                continue
            if cat_key is not None and cmd.name not in CATEGORIES[cat_key]["commands"]:
                continue
            result.append(cmd)
        except Exception:
            continue
    return result


def _build_main_embed(bot):
    """Общая помощь: список категорий"""
    all_cmds = _get_commands(bot)
    embed = discord.Embed(
        title="📚 Помощь по командам бота",
        description=f"Префикс команд: **{bot.command_prefix}**\n"
                    f"Также поддерживаются slash-команды (`/команда`)\n"
                    f"Всего команд: **{len(all_cmds)}**",
        color=discord.Color.blue(),
        timestamp=datetime.now()
    )
    for cat_key, cat_info in CATEGORIES.items():
        count = len(_get_commands(bot, cat_key))
        embed.add_field(
            name=f"{cat_info['emoji']} {cat_info['name']} ({count} команд)",
            value="Нажми кнопку ниже, чтобы увидеть команды",
            inline=True
        )
    embed.set_footer(text=f"Нажми кнопку с категорией, чтобы увидеть её команды • {_footer()}")
    return embed


def _build_category_embed(bot, cat_key):
    """Embed со списком команд конкретной категории"""
    cat = CATEGORIES.get(cat_key)
    if cat is None:
        return _build_main_embed(bot)

    commands_list = _get_commands(bot, cat_key)
    commands_list.sort(key=lambda c: c.name)

    embed = discord.Embed(
        title=f"{cat['emoji']} {cat['name']}",
        description=cat['description'],
        color=cat['color'],
        timestamp=datetime.now()
    )
    # Discord ограничивает embed 25 полями, поэтому группируем команды
    # по 10 в одно поле
    for i in range(0, len(commands_list), 10):
        chunk = commands_list[i:i + 10]
        lines = []
        for cmd in chunk:
            params = ""
            for param in cmd.clean_params:
                params += f" [{param}]"
            lines.append(f"`{bot.command_prefix}{cmd.name}{params}` — {cmd.description or 'Описание не указано'}")
        embed.add_field(
            name=f"Команды {i + 1}–{i + len(chunk)} из {len(commands_list)}",
            value="\n".join(lines),
            inline=False
        )
    embed.set_footer(text=f"Всего команд в категории: {len(commands_list)} • {_footer()}")
    return embed


class HelpView(discord.ui.View):
    """Постоянная кнопочная навигация по помощи (persistent)"""

    def __init__(self):
        super().__init__(timeout=None)
        self._add_all_buttons()

    def _add_all_buttons(self):
        for i, cat_key in enumerate(CATEGORIES):
            cat = CATEGORIES[cat_key]
            self.add_item(CategoryButton(cat_key, row=i // 3))
        self.add_item(BackButton(row=3))
        self.add_item(CloseButton(row=3))

    async def show(self, interaction, cat_key=None):
        """Переключить содержимое панели"""
        bot = interaction.client
        if cat_key is None:
            embed = _build_main_embed(bot)
        else:
            embed = _build_category_embed(bot, cat_key)
        await interaction.response.edit_message(embed=embed, view=self)


class CategoryButton(discord.ui.Button):
    """Кнопка выбора категории"""

    def __init__(self, cat_key, row=0):
        cat = CATEGORIES[cat_key]
        super().__init__(
            label=cat["name"], style=discord.ButtonStyle.secondary, emoji=cat["emoji"],
            custom_id=f"help_cat_{cat_key}", row=row,
        )
        self.cat_key = cat_key

    async def callback(self, interaction: discord.Interaction):
        view = self.view
        if not isinstance(view, HelpView):
            await interaction.response.send_message("❌ Панель устарела, вызови `!help` заново.", ephemeral=True)
            return
        await view.show(interaction, self.cat_key)


class BackButton(discord.ui.Button):
    """Кнопка возврата к общему списку"""

    def __init__(self, row=3):
        super().__init__(
            label="Главная", style=discord.ButtonStyle.primary,
            custom_id="help_back", row=row,
        )

    async def callback(self, interaction: discord.Interaction):
        view = self.view
        if not isinstance(view, HelpView):
            await interaction.response.send_message("❌ Панель устарела, вызови `!help` заново.", ephemeral=True)
            return
        await view.show(interaction, None)


class CloseButton(discord.ui.Button):
    """Кнопка закрытия помощи"""

    def __init__(self, row=3):
        super().__init__(
            label="Закрыть", style=discord.ButtonStyle.danger,
            custom_id="help_close", row=row,
        )

    async def callback(self, interaction: discord.Interaction):
        try:
            await interaction.response.defer()
            await interaction.message.delete()
        except Exception:
            pass


HELP_VERSION = "v3"


def _footer():
    return f"Сборка {HELP_VERSION} • Кнопки: {len(CATEGORIES) + 2}"


def setup_help(bot):
    """Настройка команды помощи"""

    # Регистрируем постоянную панель помощи (работает после рестарта)
    bot.help_view = HelpView()
    bot.add_view(bot.help_view)

    @bot.hybrid_command(name="help", description="Показать все команды бота")
    @app_commands.describe(category="Категория команд (moderation, music, economy, games, utilities)")
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
            logger.error(f'Ошибка help: {e}', exc_info=True)
            await ctx.send(f"❌ Ошибка при показе помощи: {e}", ephemeral=True)

    # Автодополнение категорий для slash-команды
    @help_cmd.autocomplete('category')
    async def help_category_autocomplete(interaction, current):
        choices = [
            app_commands.Choice(name=f"{CATEGORIES[cat]['emoji']} {CATEGORIES[cat]['name']}", value=cat)
            for cat in CATEGORIES if current.lower() in cat.lower()
        ][:10]
        return choices

    logger.info("Модуль помощи загружен")
