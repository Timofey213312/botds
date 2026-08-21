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
                      "mute", "unmute", "timeout", "untimeout", "warn", "unwarn", "warnings", "clearwarn",
                      "purge", "slowmode", "lock", "unlock", "lockall", "unlockall", "nuke",
                       "nick", "role", "unrole", "roleall", "derole", "voicekick", "voicemute",
                       "voiceunmute", "voicedeafen", "voiceundeafen", "moveall", "massban",
                       "multikick", "botclear", "cleanup", "snipe", "modlog", "report",
                       "apply-setup", "antispam", "automod"]
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
    "utilities": {
        "name": "Утилиты",
        "description": "Полезные команды и информация",
        "emoji": "🔧",
        "color": discord.Color.blue(),
        "commands": ["serverinfo", "userinfo", "ping", "avatar", "calc", "remind",
                     "uptime", "poll", "translate", "quote", "fact", "stats"]
    },
    "fun": {
        "name": "Развлечения",
        "description": "Игры, рандом, реакции",
        "emoji": "🎮",
        "color": discord.Color.purple(),
        "commands": ["8ball", "coin", "dice", "rps", "meme", "joke", "roast", "compliment",
                     "ship", "rate", "fortune", "emojify", "reverse", "uwu", "mock",
                     "slap", "hug", "kiss", "punch", "pat", "cuddle", "highfive", "bite",
                     "random", "choose", "spinner", "iq", "gay", "simp", "topics", "wouldyou",
                     "ascii", "roll", "flip", "zalgo", "dadjoke", "trump", "biden", "cowsay"]
    },
    "economy": {
        "name": "Экономика",
        "description": "Баланс, работа, игры на деньги",
        "emoji": "💰",
        "color": discord.Color.gold(),
        "commands": ["balance", "daily", "work", "gamble", "slots", "give", "rob",
                     "leaderboard", "shop", "buy", "inventory", "fish", "level"]
    },
    "text": {
        "name": "Текст",
        "description": "Преобразование текста, кодировки",
        "emoji": "✏️",
        "color": discord.Color.teal(),
        "commands": ["upper", "lower", "capitalize", "title", "len", "words",
                     "binary", "unbinary", "hex", "unhex", "base64", "unbase64",
                     "md5", "sha1", "sha256", "password", "snake", "kebab", "camel",
                      "leet", "bold", "italic", "underline", "spoiler", "strike", "box"]
    },
    "info": {
        "name": "Информация",
        "description": "Информация о сервере и участниках",
        "emoji": "ℹ️",
        "color": discord.Color.dark_teal(),
        "commands": ["botinfo", "servericon", "serverbanner", "channelinfo", "roleinfo",
                     "roles", "emojis", "boosters", "invites", "created", "rolesof",
                     "permissions", "badges", "guildinfo", "membercount", "whois",
                     "banner", "activity", "status", "joined", "dictionary"]
    }
}

# Порядок отображения команд
CATEGORY_ORDER = ["moderation", "music", "utilities", "fun", "economy", "text", "info"]


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
    """Общая помощь: минималистичный обзор + навигация через select"""
    all_cmds = _get_commands(bot)
    embed = discord.Embed(
        title=f"{getattr(bot.user, 'name', 'Бот')}",
        description=(
            f"Префикс команд: **`{bot.command_prefix}`**   •   Slash: **`/{bot.command_prefix}`**\n"
            f"Всего команд: **{len(all_cmds)}**\n\n"
            f"Открой категорию через меню ниже ⌄"
        ),
        color=discord.Color.blurple(),
        timestamp=datetime.now()
    )
    if getattr(bot.user, "avatar", None):
        embed.set_thumbnail(url=bot.user.avatar.url)

    for cat_key in CATEGORY_ORDER:
        cat = CATEGORIES[cat_key]
        count = len(_get_commands(bot, cat_key))
        embed.add_field(
            name=f"{cat['emoji']}  {cat['name']}",
            value=f"{count} команд",
            inline=True
        )
    embed.set_footer(text="Выбери категорию в меню ↓")
    return embed


def _build_category_embed(bot, cat_key):
    """Embed со списком команд конкретной категории"""
    cat = CATEGORIES.get(cat_key)
    if cat is None:
        return _build_main_embed(bot)

    commands_list = _get_commands(bot, cat_key)
    commands_list.sort(key=lambda c: c.name)

    embed = discord.Embed(
        title=f"{cat['emoji']}  {cat['name']}",
        description=cat['description'],
        color=cat['color'],
        timestamp=datetime.now()
    )
    if getattr(bot.user, "avatar", None):
        embed.set_thumbnail(url=bot.user.avatar.url)

    for i in range(0, len(commands_list), 8):
        chunk = commands_list[i:i + 8]
        lines = [_format_cmd(bot, cmd) for cmd in chunk]
        embed.add_field(
            name=f"Команды {i + 1}–{i + len(chunk)}",
            value="\n".join(lines),
            inline=False
        )
    embed.set_footer(text=f"{len(commands_list)} команд · выбери другую в меню ↓")
    return embed


class HelpView(discord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=180)
        self.bot = bot
        for idx, cat_key in enumerate(CATEGORY_ORDER):
            cat = CATEGORIES[cat_key]
            row = 0 if idx < 4 else 1
            btn = discord.ui.Button(
                label=cat['name'][:80],
                emoji=cat['emoji'],
                style=discord.ButtonStyle.blurple,
                row=row
            )
            btn.callback = self._make_callback(cat_key)
            self.add_item(btn)
        back = discord.ui.Button(
            label="◀ Назад", emoji="🏠",
            style=discord.ButtonStyle.grey, row=2
        )
        back.callback = self._make_back()
        self.add_item(back)

    def _make_callback(self, cat_key):
        async def cb(interaction: discord.Interaction):
            embed = _build_category_embed(self.bot, cat_key)
            await interaction.response.edit_message(embed=embed, view=self)
        return cb

    def _make_back(self):
        async def cb(interaction: discord.Interaction):
            embed = _build_main_embed(self.bot)
            await interaction.response.edit_message(embed=embed, view=self)
        return cb


def setup_help(bot):
    """Настройка команды помощи"""

    @bot.hybrid_command(name="help", description="Показать все команды бота")
    @app_commands.describe(category="Категория команд (moderation, music, utilities)")
    async def help_cmd(ctx: commands.Context, category: str = None):
        """Команда помощи по боту"""
        try:
            view = HelpView(bot)
            if category and category.lower() in CATEGORIES:
                embed = _build_category_embed(bot, category.lower())
            else:
                embed = _build_main_embed(bot)
            await ctx.send(embed=embed, view=view)
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
