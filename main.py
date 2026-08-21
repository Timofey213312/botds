"""
Основной файл Discord бота с 70+ командами
Включает: модерацию, музыку, экономику, игры, утилиты
"""

import os
import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import logging
from datetime import datetime, timedelta
import random
import json
import aiosqlite
from dotenv import load_dotenv
import aiohttp
import math
from typing import Optional
import yt_dlp

# Загружаем переменные окружения
load_dotenv()

# Настройка логгирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('discord_bot')

# Конфигурация бота
TOKEN = os.getenv('DISCORD_TOKEN')
PREFIX = os.getenv('BOT_PREFIX', '!')
GUILD_ID = os.getenv('GUILD_ID')

if not TOKEN:
    logger.error("Токен не найден. Убедитесь, что DISCORD_TOKEN указан в .env файле")
    exit(1)

# Настройки интентов
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True
intents.voice_states = True
intents.moderation = True

# Создаем бота
class DiscordBot(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix=PREFIX,
            intents=intents,
            help_command=None
        )
        self.start_time = datetime.now()
        self.session = None
        self.db = None
        self.queues = {}
        self.music_players = {}
        self.cooldowns = {}
        
    async def setup_hook(self):
        """Настройка бота при запуске"""
        # Инициализация сессии HTTP
        self.session = aiohttp.ClientSession()
        
        # Инициализация базы данных
        await self.init_database()
        
        # Синхронизация slash команд
        await self.tree.sync()
        if GUILD_ID and GUILD_ID.strip() and GUILD_ID != "YOUR_GUILD_ID_HERE":
            try:
                guild = discord.Object(id=int(GUILD_ID))
                self.tree.copy_global_to(guild=guild)
                await self.tree.sync(guild=guild)
            except ValueError:
                logger.warning(f"Неверный формат GUILD_ID: {GUILD_ID}. Пропускаем синхронизацию для конкретного сервера.")
        
        logger.info(f"Бот запущен как {self.user}")
        logger.info(f"Префикс команд: {PREFIX}")
        logger.info(f"Slash команды синхронизированы")
        
        # Запуск фоновых задач
        loop = getattr(self, 'autoclean_loop', None)
        if loop and not loop.is_running():
            loop.start()

        panel_loop = getattr(self, 'panel_autoupdate', None)
        if panel_loop and not panel_loop.is_running():
            panel_loop.start()
        
    async def init_database(self):
        """Инициализация базы данных SQLite"""
        self.db = await aiosqlite.connect('bot_database.db')
        
        # Миграция: создание составного первичного ключа для users
        cursor = await self.db.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='users'"
        )
        existing = await cursor.fetchone()
        if existing and 'PRIMARY KEY (user_id, guild_id)' not in existing[0]:
            await self.db.execute("ALTER TABLE users RENAME TO users_old")
            await self.db.execute('''
                CREATE TABLE users (
                    user_id INTEGER,
                    guild_id INTEGER,
                    balance INTEGER DEFAULT 100,
                    xp INTEGER DEFAULT 0,
                    level INTEGER DEFAULT 1,
                    daily_claimed TEXT,
                    work_cooldown TEXT,
                    inventory TEXT DEFAULT '[]',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (user_id, guild_id)
                )
            ''')
            await self.db.execute('''
                INSERT INTO users (user_id, guild_id, balance, xp, level, daily_claimed, work_cooldown, inventory, created_at)
                SELECT user_id, guild_id, balance, xp, level, daily_claimed, work_cooldown, inventory, created_at FROM users_old
            ''')
            await self.db.execute("DROP TABLE users_old")
            await self.db.commit()
            logger.info("Таблица users мигрирована на составной первичный ключ")
        
        # Создание таблиц
        await self.db.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER,
                guild_id INTEGER,
                balance INTEGER DEFAULT 100,
                xp INTEGER DEFAULT 0,
                level INTEGER DEFAULT 1,
                daily_claimed TEXT,
                work_cooldown TEXT,
                inventory TEXT DEFAULT '[]',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (user_id, guild_id)
            )
        ''')
        
        await self.db.execute('''
            CREATE TABLE IF NOT EXISTS reminders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                guild_id INTEGER,
                reminder_text TEXT,
                remind_at TEXT,
                channel_id INTEGER,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        await self.db.execute('''
            CREATE TABLE IF NOT EXISTS polls (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message_id INTEGER,
                guild_id INTEGER,
                channel_id INTEGER,
                question TEXT,
                options TEXT,
                votes TEXT DEFAULT '{}',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        await self.db.execute('''
            CREATE TABLE IF NOT EXISTS warnings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                guild_id INTEGER,
                moderator_id INTEGER,
                reason TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        await self.db.commit()
        logger.info("База данных инициализирована")
        
    async def close(self):
        """Закрытие соединений при выключении"""
        if self.session:
            await self.session.close()
        if self.db:
            await self.db.close()
        await super().close()
        
    async def on_ready(self):
        """Событие при готовности бота"""
        logger.info(f'Бот запущен как {self.user.name}')
        logger.info(f'ID бота: {self.user.id}')
        logger.info(f'Время запуска: {self.start_time}')
        
        # Устанавливаем статус бота
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name="!help /help — все команды"
            )
        )

        # Авто-восстановление панелей с кнопками (устаревшие custom_id пересоздаются)
        try:
            from modules.panels import restore_panels
            asyncio.create_task(restore_panels(self))
        except Exception as e:
            logger.error(f'Ошибка запуска автовосстановления панелей: {e}')

        # Авто-публикация changelog в канал объявлений при новом обновлении
        try:
            from modules.changelog import maybe_post_on_startup
            asyncio.create_task(maybe_post_on_startup(self))
        except Exception as e:
            logger.error(f'Ошибка авто-публикации changelog: {e}')

# Создаем экземпляр бота
bot = DiscordBot()


# Глобальная проверка: команды доступны только модерации
async def _is_moderator(user, guild):
    if user == guild.me:
        return True
    if await bot.is_owner(user):
        return True
    p = user.guild_permissions
    return any([
        p.manage_messages, p.manage_guild, p.kick_members, p.ban_members,
        p.moderate_members, p.manage_roles, p.manage_channels, p.mute_members,
        p.move_members, p.manage_nicknames
    ])


async def _global_mod_check(ctx):
    if getattr(ctx, "guild", None) is None:
        return False
    return await _is_moderator(ctx.author, ctx.guild)


async def _global_mod_check_app(interaction):
    if not interaction.guild:
        return False
    return await _is_moderator(interaction.user, interaction.guild)


bot.add_check(_global_mod_check)
bot.interaction_check = _global_mod_check_app

# Импортируем модули команд
from modules.moderation import setup_moderation
from modules.music import setup_music
from modules.utilities import setup_utilities
from modules.help import setup_help
from modules.welcome import setup_welcome
from modules.rules import setup_rules
from modules.tickets import setup_tickets
from modules.autoclean import setup_autoclean
from modules.tempvoice import setup_tempvoice
from modules.ideas import setup_ideas
from modules.panels import setup_panels
from modules.fun import setup_fun
from modules.economy import setup_economy
from modules.text import setup_text
from modules.info import setup_info
from modules.antispam import setup_antispam
from modules.automod import setup_automod
from modules.applications import setup_applications
from modules.market import setup_market

# Настройка модулей (каждый в try/except, чтобы сбой одного не убивал остальные и их persistent views)
_setups = {
    "moderation": setup_moderation,
    "music": setup_music,
    "utilities": setup_utilities,
    "help": setup_help,
    "welcome": setup_welcome,
    "rules": setup_rules,
    "tickets": setup_tickets,
    "autoclean": setup_autoclean,
    "tempvoice": setup_tempvoice,
    "ideas": setup_ideas,
    "panels": setup_panels,
    "fun": setup_fun,
    "economy": setup_economy,
    "text": setup_text,
    "info": setup_info,
    "antispam": setup_antispam,
    "automod": setup_automod,
    "applications": setup_applications,
    "market": setup_market,
}
for _name, _fn in _setups.items():
    try:
        _fn(bot)
        logger.info(f"Модуль {_name} загружен")
    except Exception as _e:
        logger.error(f"ОШИБКА загрузки модуля {_name}: {_e}", exc_info=True)

# После загрузки всех модулей — проверяем, что persistent views зарегистрированы
_registered = sorted(set(
    c.custom_id
    for v in bot.persistent_views
    for c in v.children
    if getattr(c, 'custom_id', None)
))
logger.info(f"Persistent views зарегистрированы ({len(_registered)}): {', '.join(_registered)}")

@bot.event
async def on_command_error(ctx, error):
    """Обработка ошибок команд"""
    if isinstance(error, commands.CommandNotFound):
        return
    elif isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ У вас недостаточно прав для выполнения этой команды.", ephemeral=True)
    elif isinstance(error, commands.BotMissingPermissions):
        await ctx.send("❌ У бота недостаточно прав для выполнения этой команды.", ephemeral=True)
    elif isinstance(error, commands.CommandOnCooldown):
        await ctx.send(f"⏰ Эта команда на перезарядке. Попробуйте через {error.retry_after:.1f} секунд.", ephemeral=True)
    elif isinstance(error, commands.BadArgument):
        # Неверные аргументы (роль/канал не найдены и т.п.)
        await ctx.send(
            f"❌ Не удалось разобрать аргументы команды: {error}\n\n"
            "💡 Для команд с несколькими параметрами используй slash-версию: "
            f"`/{ctx.command.name}` — там поля указываются отдельно.",
            ephemeral=True
        )
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(
            f"❌ Не хватает аргумента: `{error.param.name}`. "
            f"Пример: `/{ctx.command.name}` — поля подскажут.",
            ephemeral=True
        )
    else:
        logger.error(f"Ошибка команды: {error}")
        await ctx.send("❌ Произошла ошибка при выполнении команды.", ephemeral=True)

if __name__ == "__main__":
    try:
        bot.run(TOKEN)
    except Exception as e:
        logger.error(f"Ошибка запуска бота: {e}")
        print(f"Ошибка: {e}")