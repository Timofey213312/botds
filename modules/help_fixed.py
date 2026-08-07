"""
Модуль помощи и информации о командах бота
Команды: help (автоматическая)
Улучшенная версия с одним меню
"""

import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime
import logging

logger = logging.getLogger('discord_bot.help')

def setup_help(bot):
    """Настройка команды помощи"""
    
    @bot.hybrid_command(name="help", description="Показать все команды бота")
    @app_commands.describe(category="Категория команд (moderation, music, economy, games, utilities)")
    async def help_cmd(ctx: commands.Context, category: str = None):
        """Команда помощи по боту"""
        try:
            # Категории команд
            categories = {
                "moderation": {
                    "name": "⚖️ Модерация",
                    "description": "Команды для управления сервером",
                    "emoji": "⚖️",
                    "color": discord.Color.red(),
                    "commands": [
                        ("clear [1-100]", "Очистить сообщения"),
                        ("kick @участник [причина]", "Кикнуть участника"),
                        ("ban @участник [причина]", "Забанить участника"),
                        ("mute @участник [минуты] [причина]", "Выдать мут (роль)"),
                        ("timeout @участник [минуты] [причина]", "Таймаут Discord"),
                        ("untimeout @участник [причина]", "Снять таймаут"),
                        ("report @участник [причина]", "Отправить жалобу")
                    ]
                },
                "music": {
                    "name": "🎵 Музыка", 
                    "description": "Команды для воспроизведения музыки",
                    "emoji": "🎵",
                    "color": discord.Color.green(),
                    "commands": [
                        ("play [запрос/url]", "Воспроизвести (YT/Spotify/Яндекс/SC)"),
                        ("pause", "Пауза"),
                        ("resume", "Продолжить"),
                        ("skip", "Пропустить"),
                        ("stop", "Остановить"),
                        ("queue", "Очередь"),
                        ("nowplaying", "Текущая песня"),
                        ("volume [0-100]", "Громкость"),
                        ("loop", "Повтор песни"),
                        ("loopqueue", "Повтор очереди"),
                        ("shuffle", "Перемешать"),
                        ("leave", "Отключиться")
                    ]
                },
                "economy": {
                    "name": "💰 Экономика",
                    "description": "Экономическая система с XP, уровнями и магазином",
                    "emoji": "💰", 
                    "color": discord.Color.gold(),
                    "commands": [
                        ("balance [@участник]", "Баланс и уровень"),
                        ("daily", "Ежедневная награда (50-200 💰)"),
                        ("pay @участник [сумма]", "Перевести деньги"),
                        ("coinflip [сумма] [орёл/решка]", "Подбросить монетку"),
                        ("work", "Заработать деньги (кулдаун 1ч)"),
                        ("leaderboard [тип]", "Таблица лидеров"),
                        ("shop", "Показать магазин"),
                        ("buy [id]", "Купить предмет")
                    ]
                },
                "games": {
                    "name": "🎮 Игры",
                    "description": "Мини-игры и развлечения",
                    "emoji": "🎮",
                    "color": discord.Color.blurple(),
                    "commands": [
                        ("rps [камень/ножницы/бумага]", "Камень-ножницы-бумага"),
                        ("8ball [вопрос]", "Магический шар предсказаний"),
                        ("dice [грани]", "Бросить кость (2-100 граней)"),
                        ("roll [кол-во] [грани]", "Бросить несколько костей"),
                        ("slot [ставка]", "Слот-машина (10-500)"),
                        ("guess [ставка]", "Угадай число (1-10)"),
                        ("quest", "Активные квесты")
                    ]
                },
                "utilities": {
                    "name": "🔧 Утилиты",
                    "description": "Полезные команды и информация",
                    "emoji": "🔧",
                    "color": discord.Color.blue(),
                    "commands": [
                        ("serverinfo", "Информация о сервере"),
                        ("userinfo [@участник]", "Информация об участнике"),
                        ("ping", "Проверить пинг бота"),
                        ("avatar [@участник]", "Показать аватар"),
                        ("weather [город]", "Показать погоду"),
                        ("calc [выражение]", "Калькулятор"),
                        ("remind [время] [сообщение]", "Напоминание"),
                        ("uptime", "Время работы бота"),
                        ("poll [вопрос] [варианты]", "Создать опрос"),
                        ("translate [текст] [язык]", "Переводчик"),
                        ("quote", "Случайная цитата"),
                        ("fact", "Интересный факт"),
                        ("stats", "Статистика бота")
                    ]
                }
            }
            
            # Если указана конкретная категория
            if category and category.lower() in categories:
                cat = categories[category.lower()]
                
                embed = discord.Embed(
                    title=f"{cat['emoji']} {cat['name']}",
                    description=cat['description'],
                    color=cat['color'],
                    timestamp=datetime.now()
                )
                
                # Добавляем команды категории
                for cmd_name, cmd_desc in cat['commands']:
                    embed.add_field(
                        name=f"`{bot.command_prefix}{cmd_name}`",
                        value=cmd_desc,
                        inline=False
                    )
                
                embed.set_footer(text=f"Всего команд: {len(cat['commands'])}")
                
                await ctx.send(embed=embed)
                
            else:
                # Показываем общую помощь в ОДНОМ меню
                embed = discord.Embed(
                    title="📚 Помощь по командам бота",
                    description=f"Префикс команд: **{bot.command_prefix}**\nТакже поддерживаются slash-команды (`/команда`)\nВсего команд: **70+**",
                    color=discord.Color.blue(),
                    timestamp=datetime.now()
                )
                
                # Основная информация
                embed.add_field(
                    name="⚙️ Основная информация",
                    value="• Модерация требует прав\n• Автоматический XP за активность\n• Музыка: YouTube, Spotify, Яндекс, SoundCloud\n• Используйте `/` для slash команд",
                    inline=False
                )
                
                # Быстрый старт
                embed.add_field(
                    name="🚀 Быстрый старт",
                    value=f"• `{bot.command_prefix}ping` - Проверить пинг\n• `{bot.command_prefix}balance` - Баланс\n• `{bot.command_prefix}serverinfo` - Информация о сервере\n• `{bot.command_prefix}help [категория]` - Помощь по категориям",
                    inline=False
                )
                
                # Все категории
                for cat_key, cat_info in categories.items():
                    commands_list = "\n".join([f"• `{bot.command_prefix}{cmd[0]}`" for cmd in cat_info['commands'][:3]])
                    embed.add_field(
                        name=f"{cat_info['emoji']} {cat_info['name']} ({len(cat_info['commands'])} команд)",
                        value=f"{cat_info['description']}\n**Примеры:**\n{commands_list}\n`{bot.command_prefix}help {cat_key}`",
                        inline=True
                    )
                
                # Техническая информация
                embed.add_field(
                    name="📊 Статистика",
                    value=f"• Всего категорий: {len(categories)}\n• Всего команд: {len(bot.commands)}\n• Префикс: {bot.command_prefix}",
                    inline=False
                )
                
                await ctx.send(embed=embed)
            
            logger.info(f'{ctx.author} использовал команду help')
            
        except Exception as e:
            await ctx.send(f"❌ Ошибка при показе помощи: {e}", ephemeral=True)
            logger.error(f'Ошибка help: {e}')
    
    # Создаем команды для автодополнения категорий
    @help_cmd.autocomplete('category')
    async def help_category_autocomplete(
        interaction: discord.Interaction, 
        current: str
    ):
        """Автодополнение для категорий помощи"""
        categories = ["moderation", "music", "economy", "games", "utilities"]
        
        choices = [
            app_commands.Choice(name=cat.capitalize(), value=cat)
            for cat in categories if current.lower() in cat.lower()
        ][:10]
        
        return choices
    
    logger.info("Модуль помощи загружен")