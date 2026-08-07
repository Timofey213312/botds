"""
Основной файл Discord бота с 70+ командами
Улучшенная версия с обработкой ошибок Lavalink
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
import sys

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
    print("❌ ОШИБКА: Токен не найден!")
    print("1. Убедитесь, что файл .env существует")
    print("2. Проверьте, что DISCORD_TOKEN указан правильно")
    print("3. Формат .env должен быть:")
    print("   DISCORD_TOKEN=ваш_токен")
    print("   BOT_PREFIX=!")
    exit(1)

# Настройки интентов
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True
intents.voice_states = True

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
        self.connected = False
        
    async def setup_hook(self):
        """Настройка бота при запуске"""
        # Инициализация сессии HTTP
        self.session = aiohttp.ClientSession()
        
        # Инициализация базы данных
        await self.init_database()
        
        # Импортируем и настраиваем модули
        await self.load_modules()
        
        # Синхронизация slash команд
        await self.sync_commands()
        
        logger.info(f"Бот готов к запуску")
        logger.info(f"Префикс команд: {PREFIX}")
        
    async def load_modules(self):
        """Загрузка модулей команд"""
        try:
            from modules.moderation import setup_moderation
            from modules.music_working import setup_music
            from modules.economy import setup_economy
            from modules.games import setup_games
            from modules.utilities import setup_utilities
            from modules.help_fixed import setup_help
            
            setup_moderation(self)
            setup_music(self)
            setup_economy(self)
            setup_games(self)
            setup_utilities(self)
            setup_help(self)
            
            logger.info("Все модули загружены успешно")
            
            # Пробуем подключиться к музыке (если доступно)
            await self.try_connect_music()
            
        except Exception as e:
            logger.error(f"Ошибка при загрузке модулей: {e}")
            print(f"⚠️  Предупреждение: {e}")
            print("Бот будет работать, но некоторые функции могут быть недоступны")
        
    async def try_connect_music(self):
        """Попытка подключения к музыкальному серверу (если доступно)"""
        try:
            import wavelink
            
            # Для wavelink 3.x
            try:
                # Создаем ноду
                node = wavelink.Node(
                    uri='http://localhost:2333',
                    password='youshallnotpass'
                )
                
                # Подключаем ноду
                await wavelink.Pool.connect(client=self, nodes=[node])
                logger.info("✅ Wavelink подключен для музыки")
                print("✅ Музыкальный модуль подключен")
                
            except AttributeError:
                # Старый метод для wavelink 2.x
                nodes = [wavelink.Node(uri='http://localhost:2333', password='youshallnotpass')]
                await wavelink.Pool.connect(nodes=nodes, client=self)
                logger.info("✅ Wavelink подключен для музыки (старая версия)")
                print("✅ Музыкальный модуль подключен (старая версия)")
                
        except ImportError:
            logger.info("⚠️ Wavelink не установлен. Музыкальные команды недоступны.")
            print("ℹ️  Wavelink не установлен. Для музыки установите: pip install wavelink")
        except Exception as e:
            logger.warning(f"⚠️ Не удалось подключить Wavelink: {e}")
            print(f"⚠️  Музыка недоступна: {e}")
            print("ℹ️  Убедитесь что Lavalink запущен на localhost:2333")
        
    async def init_database(self):
        """Инициализация базы данных SQLite"""
        try:
            self.db = await aiosqlite.connect('bot_database.db')
            
            # Создание таблиц
            await self.db.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    guild_id INTEGER,
                    balance INTEGER DEFAULT 100,
                    xp INTEGER DEFAULT 0,
                    level INTEGER DEFAULT 1,
                    daily_claimed TEXT,
                    work_cooldown TEXT,
                    inventory TEXT DEFAULT '[]',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
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
            logger.info("✅ База данных инициализирована")
            print("✅ База данных готова")
            
        except Exception as e:
            logger.error(f"❌ Ошибка базы данных: {e}")
            print(f"⚠️  Ошибка базы данных: {e}")
            print("ℹ️  Бот будет работать, но данные не сохранятся")
            
    async def sync_commands(self):
        """Синхронизация slash команд"""
        try:
            await self.tree.sync()
            
            if GUILD_ID and GUILD_ID.strip() and GUILD_ID != "YOUR_GUILD_ID_HERE":
                try:
                    guild = discord.Object(id=int(GUILD_ID))
                    self.tree.copy_global_to(guild=guild)
                    await self.tree.sync(guild=guild)
                    logger.info(f"✅ Slash команды синхронизированы для сервера {GUILD_ID}")
                except ValueError:
                    logger.warning(f"⚠️ Неверный формат GUILD_ID: {GUILD_ID}")
            else:
                logger.info("✅ Slash команды синхронизированы глобально")
                
            print("✅ Slash команды синхронизированы")
            
        except Exception as e:
            logger.error(f"❌ Ошибка синхронизации команд: {e}")
            print(f"⚠️  Ошибка синхронизации команд: {e}")
            print("ℹ️  Бот будет работать, но slash команды могут не отображаться")
            
    async def close(self):
        """Закрытие соединений при выключении"""
        if self.session:
            await self.session.close()
        if self.db:
            await self.db.close()
        await super().close()
        
    async def on_ready(self):
        """Событие при готовности бота"""
        self.connected = True
        
        logger.info(f'✅ Бот запущен как {self.user.name}')
        logger.info(f'📊 ID бота: {self.user.id}')
        logger.info(f'🕐 Время запуска: {self.start_time}')
        logger.info(f'🌐 Серверов: {len(self.guilds)}')
        
        # Устанавливаем статус бота
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.listening,
                name=f"{PREFIX}help | {len(self.guilds)} серверов"
            )
        )
        
        print("="*50)
        print(f"🎉 Бот успешно запущен!")
        print("="*50)
        print(f"🤖 Имя: {self.user.name}")
        print(f"🆔 ID: {self.user.id}")
        print(f"📅 Запущен: {self.start_time.strftime('%H:%M:%S')}")
        print(f"🌐 Серверов: {len(self.guilds)}")
        print(f"⚙️ Префикс команд: {PREFIX}")
        print("="*50)
        print("📋 Доступные команды:")
        print(f"• {PREFIX}help - Помощь по командам")
        print(f"• {PREFIX}ping - Проверить пинг")
        print(f"• {PREFIX}balance - Баланс и уровень")
        print(f"• {PREFIX}serverinfo - Информация о сервере")
        print("• /help - Slash команды")
        print("="*50)
        
    async def on_guild_join(self, guild):
        """Событие при добавлении бота на сервер"""
        logger.info(f'✅ Бот добавлен на сервер: {guild.name} (ID: {guild.id})')
        
        # Приветственное сообщение
        try:
            channel = guild.system_channel or next((c for c in guild.text_channels if c.permissions_for(guild.me).send_messages), None)
            if channel:
                embed = discord.Embed(
                    title="🤖 Приветствую!",
                    description=f"Спасибо за добавление **{self.user.name}** на ваш сервер!",
                    color=discord.Color.green(),
                    timestamp=datetime.now()
                )
                embed.add_field(name="⚙️ Префикс команд", value=f"`{PREFIX}`", inline=True)
                embed.add_field(name="📋 Основные команды", value=f"`{PREFIX}help`", inline=True)
                embed.add_field(name="🔗 Slash команды", value="Используйте `/` для быстрого доступа", inline=False)
                embed.add_field(name="💡 Быстрый старт", value=f"• `{PREFIX}ping` - Проверить пинг\n• `{PREFIX}balance` - Баланс\n• `{PREFIX}serverinfo` - Информация", inline=False)
                embed.set_footer(text=f"Всего команд: {len(self.commands)}")
                
                await channel.send(embed=embed)
        except Exception as e:
            logger.error(f"Ошибка приветственного сообщения: {e}")

# Создаем экземпляр бота
bot = DiscordBot()

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
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"❌ Недостаточно аргументов. Используйте `{PREFIX}help {ctx.command.name}` для справки.", ephemeral=True)
    else:
        logger.error(f"Ошибка команды {ctx.command}: {error}")
        await ctx.send("❌ Произошла ошибка при выполнении команды.", ephemeral=True)

# Предотвращение дублирования ответов для hybrid команд
@bot.before_invoke
async def before_invoke(ctx):
    """Предотвращение дублирования ответов"""
    ctx.send_once = True

if __name__ == "__main__":
    print("="*50)
    print("🤖 Запуск Discord бота...")
    print("="*50)
    
    try:
        print("🔧 Проверка конфигурации...")
        print(f"✅ Токен: {'*' * len(TOKEN) if TOKEN else 'Не найден'}")
        print(f"✅ Префикс: {PREFIX}")
        print(f"✅ ID сервера: {GUILD_ID if GUILD_ID and GUILD_ID != 'YOUR_GUILD_ID_HERE' else 'Не указан'}")
        
        print("\n🔌 Подключение к Discord...")
        bot.run(TOKEN)
        
    except discord.LoginFailure:
        print("❌ ОШИБКА: Неверный токен бота!")
        print("1. Проверьте токен в файле .env")
        print("2. Убедитесь, что токен действителен")
        print("3. Проверьте интенты на Discord Developer Portal")
        logger.error("Ошибка аутентификации: неверный токен")
    except KeyboardInterrupt:
        print("\n🛑 Бот остановлен пользователем")
        logger.info("Бот остановлен пользователем")
    except Exception as e:
        print(f"❌ Критическая ошибка: {e}")
        logger.error(f"Критическая ошибка: {e}")
        print("\nℹ️  Попробуйте:")
        print("1. Проверить интернет-подключение")
        print("2. Проверить токен бота")
        print("3. Убедиться что интенты включены")
        print("4. Перезапустить бота")