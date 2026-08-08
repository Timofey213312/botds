"""
Модуль помощи и информации о командах бота
Команды: help (автоматическая), без кнопок
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

# Порядок отображения команд
CATEGORY_ORDER = ["moderation", "music", "economy", "games", "utilities"]


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


def _format_cmd(bot, cmd):
    """Формат одной команды: `!name [param]` — описание"""
    params = ""
    for param in cmd.clean_params:
        params += f" [{param}]"
    return f"`{bot.command_prefix}{cmd.name}{params}` — {cmd.description or 'Описание не указано'}"


def _build_main_embed(bot):
    """Общая помощь: список категорий"""
    all_cmds = _get_commands(bot)
    embed = discord.Embed(
        title="📚 Помощь по командам бота",
        description=f"Префикс команд: **{bot.command_prefix}**\n"
                    f"Также поддерживаются slash-команды (`/команда`)\n"
                    f"Всего команд: **{len(all_cmds)}**\n\n"
                    f"Используй `{bot.command_prefix}help <категория>` для подробностей.\n"
                    f"Категории: {', '.join('`' + k + '`' for k in CATEGORY_ORDER)}",
        color=discord.Color.blue(),
        timestamp=datetime.now()
    )
    for cat_key in CATEGORY_ORDER:
        cat = CATEGORIES[cat_key]
        count = len(_get_commands(bot, cat_key))
        embed.add_field(
            name=f"{cat['emoji']} {cat['name']} ({count} команд)",
            value=f"`{bot.command_prefix}help {cat_key}`",
            inline=True
        )
    embed.set_footer(text=f"Пример: {bot.command_prefix}help moderation")
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
    # Discord ограничивает embed 25 полями, поэтому группируем команды по 10
    for i in range(0, len(commands_list), 10):
        chunk = commands_list[i:i + 10]
        lines = [_format_cmd(bot, cmd) for cmd in chunk]
        embed.add_field(
            name=f"Команды {i + 1}–{i + len(chunk)} из {len(commands_list)}",
            value="\n".join(lines),
            inline=False
        )
    embed.set_footer(text=f"Всего команд в категории: {len(commands_list)}")
    return embed


def setup_help(bot):
    """Настройка команды помощи"""

    @bot.hybrid_command(name="help", description="Показать все команды бота")
    @app_commands.describe(category="Категория команд (moderation, music, economy, games, utilities)")
    async def help_cmd(ctx: commands.Context, category: str = None):
        """Команда помощи по боту"""
        try:
            if category and category.lower() in CATEGORIES:
                embed = _build_category_embed(bot, category.lower())
            else:
                embed = _build_main_embed(bot)
            await ctx.send(embed=embed)
            logger.info(f'{ctx.author} использовал команду help')
        except Exception as e:
            logger.error(f'Ошибка help: {e}', exc_info=True)
            await ctx.send(f"❌ Ошибка при показе помощи: {e}", ephemeral=True)

    # Автодополнение категорий для slash-команды
    @help_cmd.autocomplete('category')
    async def help_category_autocomplete(interaction, current):
        choices = [
            app_commands.Choice(name=f"{CATEGORIES[cat]['emoji']} {CATEGORIES[cat]['name']}", value=cat)
            for cat in CATEGORY_ORDER if current.lower() in cat.lower()
        ][:10]
        return choices

    logger.info("Модуль помощи загружен (без кнопок)")
