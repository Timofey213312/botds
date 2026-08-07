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
            CREATE TABLE IF NOT EXISTS economy_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                description TEXT,
                price INTEGER,
                type TEXT,
                effect TEXT
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

# Создаем экземпляр бота
bot = DiscordBot()

# Импортируем модули команд
from modules.moderation import setup_moderation
from modules.music import setup_music
from modules.economy import setup_economy
from modules.games import setup_games
from modules.utilities import setup_utilities
from modules.help import setup_help
from modules.welcome import setup_welcome
from modules.rules import setup_rules
from modules.tickets import setup_tickets
from modules.autoclean import setup_autoclean
from modules.tempvoice import setup_tempvoice
from modules.logger import setup_logger
from modules.ideas import setup_ideas

# Настройка модулей
setup_moderation(bot)
setup_music(bot)
setup_economy(bot)
setup_games(bot)
setup_utilities(bot)
setup_help(bot)
setup_welcome(bot)
setup_rules(bot)
setup_tickets(bot)
setup_autoclean(bot)
setup_tempvoice(bot)
setup_logger(bot)
setup_ideas(bot)

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
    else:
        logger.error(f"Ошибка команды: {error}")
        await ctx.send("❌ Произошла ошибка при выполнении команды.", ephemeral=True)

if __name__ == "__main__":
    try:
        bot.run(TOKEN)
    except Exception as e:
        logger.error(f"Ошибка запуска бота: {e}")
        print(f"Ошибка: {e}")