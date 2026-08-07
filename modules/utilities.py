"""
Модуль утилит для Discord бота
Команды: serverinfo, userinfo, ping, avatar, weather, calc, remind, uptime, poll, translate, quote, fact, stats
Полезные функции и информация
"""

import discord
from discord.ext import commands
from discord import app_commands
import asyncio
from datetime import datetime, timedelta
import logging
import random
import math
import json
import aiohttp
from typing import Optional

logger = logging.getLogger('discord_bot.utilities')

def setup_utilities(bot):
    """Настройка команд утилит"""
    
    @bot.hybrid_command(name="serverinfo", description="Информация о сервере")
    async def serverinfo_cmd(ctx: commands.Context):
        """Информация о сервере"""
        try:
            guild = ctx.guild
            
            # Статистика участников
            total_members = guild.member_count
            online_members = len([m for m in guild.members if m.status != discord.Status.offline])
            bots = len([m for m in guild.members if m.bot])
            humans = total_members - bots
            
            # Статистика каналов
            text_channels = len(guild.text_channels)
            voice_channels = len(guild.voice_channels)
            categories = len(guild.categories)
            
            # Статистика ролей (без @everyone)
            roles = len(guild.roles) - 1
            
            # Уровень верификации
            verification_levels = {
                discord.VerificationLevel.none: "Нет",
                discord.VerificationLevel.low: "Низкий",
                discord.VerificationLevel.medium: "Средний",
                discord.VerificationLevel.high: "Высокий",
                discord.VerificationLevel.highest: "Самый высокий"
            }
            
            # Уровень NSFW
            nsfw_levels = {
                discord.NSFWLevel.default: "По умолчанию",
                discord.NSFWLevel.explicit: "Эксплицитный",
                discord.NSFWLevel.safe: "Безопасный",
                discord.NSFWLevel.age_restricted: "Возрастное ограничение"
            }
            
            embed = discord.Embed(
                title=f"📊 Информация о сервере: {guild.name}",
                color=discord.Color.blue(),
                timestamp=datetime.now()
            )
            
            if guild.icon:
                embed.set_thumbnail(url=guild.icon.url)
            
            embed.add_field(name="👑 Владелец", value=guild.owner.mention, inline=True)
            embed.add_field(name="🆔 ID сервера", value=f"`{guild.id}`", inline=True)
            embed.add_field(name="📅 Создан", value=guild.created_at.strftime("%d.%m.%Y"), inline=True)
            
            embed.add_field(name="👥 Участники", value=f"Всего: **{total_members}**\nОнлайн: **{online_members}**\nЛюдей: **{humans}**\nБотов: **{bots}**", inline=True)
            embed.add_field(name="📁 Каналы", value=f"Текстовые: **{text_channels}**\nГолосовые: **{voice_channels}**\nКатегории: **{categories}**", inline=True)
            embed.add_field(name="🎭 Роли", value=f"**{roles}** ролей", inline=True)
            
            embed.add_field(name="🔒 Уровень верификации", value=verification_levels.get(guild.verification_level, "Неизвестно"), inline=True)
            embed.add_field(name="🔞 Уровень NSFW", value=nsfw_levels.get(guild.nsfw_level, "Неизвестно"), inline=True)
            embed.add_field(name="🚀 Бусты", value=f"Уровень: **{guild.premium_tier}**\nБустеров: **{guild.premium_subscription_count}**", inline=True)
            
            if guild.banner:
                embed.set_image(url=guild.banner.url)
            
            await ctx.send(embed=embed)
            logger.info(f'{ctx.author} посмотрел информацию о сервере')
            
        except Exception as e:
            await ctx.send(f"❌ Ошибка: {e}", ephemeral=True)
            logger.error(f'Ошибка serverinfo: {e}')
    
    @bot.hybrid_command(name="userinfo", description="Информация об участнике")
    @app_commands.describe(member="Участник для проверки (опционально)")
    async def userinfo_cmd(ctx: commands.Context, member: Optional[discord.Member] = None):
        """Информация об участнике"""
        try:
            target = member or ctx.author
            
            # Форматирование статуса
            status_emojis = {
                discord.Status.online: "🟢",
                discord.Status.idle: "🟡", 
                discord.Status.dnd: "🔴",
                discord.Status.offline: "⚫"
            }
            
            # Форматирование активности
            activity_text = "Нет активности"
            if target.activities:
                for activity in target.activities:
                    if isinstance(activity, discord.Game):
                        activity_text = f"🎮 Играет в **{activity.name}**"
                        break
                    elif isinstance(activity, discord.Streaming):
                        activity_text = f"📺 Стримит **{activity.name}**"
                        break
                    elif isinstance(activity, discord.CustomActivity):
                        activity_text = f"💭 {activity.name}"
                        break
            
            # Роли пользователя (без @everyone)
            roles = [role.mention for role in target.roles if role.name != "@everyone"]
            roles_text = ", ".join(roles[-10:]) if roles else "Нет ролей"
            if len(roles) > 10:
                roles_text += f" и ещё {len(roles)-10}"
            
            embed = discord.Embed(
                title=f"👤 Информация о {target.name}",
                color=target.color if target.color else discord.Color.blue(),
                timestamp=datetime.now()
            )
            
            embed.set_thumbnail(url=target.avatar.url if target.avatar else target.default_avatar.url)
            
            embed.add_field(name="📛 Имя", value=f"**{target.name}**", inline=True)
            embed.add_field(name="📝 Никнейм", value=f"**{target.display_name}**", inline=True)
            embed.add_field(name="🆔 ID", value=f"`{target.id}`", inline=True)
            
            embed.add_field(name="📅 Зарегистрирован в Discord", value=target.created_at.strftime("%d.%m.%Y %H:%M"), inline=True)
            embed.add_field(name="📅 Присоединился к серверу", value=target.joined_at.strftime("%d.%m.%Y %H:%M"), inline=True)
            
            embed.add_field(name="🎭 Высшая роль", value=target.top_role.mention, inline=True)
            embed.add_field(name="📊 Статус", value=f"{status_emojis.get(target.status, '⚫')} {str(target.status).capitalize()}", inline=True)
            embed.add_field(name="🎯 Активность", value=activity_text, inline=True)
            
            embed.add_field(name="🤖 Бот?", value="✅ Да" if target.bot else "❌ Нет", inline=True)
            
            embed.add_field(name="🎭 Роли", value=roles_text if len(roles_text) < 1024 else "Слишком много ролей для отображения", inline=False)
            
            await ctx.send(embed=embed)
            logger.info(f'{ctx.author} посмотрел информацию о {target.name}')
            
        except Exception as e:
            await ctx.send(f"❌ Ошибка: {e}", ephemeral=True)
            logger.error(f'Ошибка userinfo: {e}')
    
    @bot.hybrid_command(name="ping", description="Проверить пинг бота")
    async def ping_cmd(ctx: commands.Context):
        """Пинг бота"""
        try:
            latency = round(bot.latency * 1000)
            
            # Цвет в зависимости от пинга
            if latency < 100:
                color = discord.Color.green()
                status = "Отличный"
                emoji = "🟢"
            elif latency < 200:
                color = discord.Color.yellow()
                status = "Хороший"
                emoji = "🟡"
            elif latency < 400:
                color = discord.Color.orange()
                status = "Средний"
                emoji = "🟠"
            else:
                color = discord.Color.red()
                status = "Плохой"
                emoji = "🔴"
            
            embed = discord.Embed(
                title=f"{emoji} Пинг бота",
                color=color,
                timestamp=datetime.now()
            )
            embed.add_field(name="Задержка", value=f"**{latency}ms**", inline=True)
            embed.add_field(name="Статус", value=f"**{status}**", inline=True)
            
            await ctx.send(embed=embed)
            logger.info(f'{ctx.author} проверил пинг: {latency}ms')
            
        except Exception as e:
            await ctx.send(f"❌ Ошибка: {e}", ephemeral=True)
            logger.error(f'Ошибка ping: {e}')
    
    @bot.hybrid_command(name="avatar", description="Показать аватар участника")
    @app_commands.describe(member="Участник (опционально)")
    async def avatar_cmd(ctx: commands.Context, member: Optional[discord.Member] = None):
        """Аватар пользователя"""
        try:
            target = member or ctx.author
            
            embed = discord.Embed(
                title=f"🖼️ Аватар {target.name}",
                color=discord.Color.blue(),
                timestamp=datetime.now()
            )
            
            avatar_url = target.avatar.url if target.avatar else target.default_avatar.url
            embed.set_image(url=avatar_url)
            
            embed.add_field(name="Ссылка", value=f"[Открыть оригинал]({avatar_url})", inline=True)
            
            if target.guild_avatar:
                embed.add_field(name="Аватар сервера", value=f"[Открыть]({target.guild_avatar.url})", inline=True)
            
            await ctx.send(embed=embed)
            logger.info(f'{ctx.author} посмотрел аватар {target.name}')
            
        except Exception as e:
            await ctx.send(f"❌ Ошибка: {e}", ephemeral=True)
            logger.error(f'Ошибка avatar: {e}')
    
    @bot.hybrid_command(name="calc", description="Калькулятор")
    @app_commands.describe(expression="Математическое выражение")
    async def calc_cmd(ctx: commands.Context, *, expression: str):
        """Калькулятор"""
        try:
            # Безопасная обработка выражения
            allowed_chars = "0123456789+-*/(). "
            
            if any(char not in allowed_chars for char in expression):
                await ctx.send("❌ Выражение содержит недопустимые символы", ephemeral=True)
                return
            
            # Заменяем запятые на точки для десятичных чисел
            expression = expression.replace(",", ".")
            
            # Пытаемся вычислить
            try:
                result = eval(expression, {"__builtins__": {}}, {})
                
                # Форматируем результат
                if isinstance(result, (int, float)):
                    if result.is_integer():
                        result_str = str(int(result))
                    else:
                        result_str = f"{result:.4f}"
                else:
                    result_str = str(result)
                
                embed = discord.Embed(
                    title="🧮 Калькулятор",
                    color=discord.Color.green(),
                    timestamp=datetime.now()
                )
                embed.add_field(name="Выражение", value=f"`{expression}`", inline=False)
                embed.add_field(name="Результат", value=f"**{result_str}**", inline=False)
                
                await ctx.send(embed=embed)
                logger.info(f'{ctx.author} вычислил: {expression} = {result_str}')
                
            except Exception as e:
                await ctx.send(f"❌ Ошибка вычисления: {e}", ephemeral=True)
                
        except Exception as e:
            await ctx.send(f"❌ Ошибка калькулятора: {e}", ephemeral=True)
            logger.error(f'Ошибка calc: {e}')
    
    @bot.hybrid_command(name="remind", description="Установить напоминание")
    @app_commands.describe(time="Время (например: 10m, 1h, 2d)", message="Текст напоминания")
    async def remind_cmd(ctx: commands.Context, time: str, *, message: str):
        """Напоминание"""
        try:
            # Парсим время
            time_lower = time.lower()
            seconds = 0
            
            if time_lower.endswith("m"):
                seconds = int(time_lower[:-1]) * 60
            elif time_lower.endswith("h"):
                seconds = int(time_lower[:-1]) * 3600
            elif time_lower.endswith("d"):
                seconds = int(time_lower[:-1]) * 86400
            elif time_lower.endswith("s"):
                seconds = int(time_lower[:-1])
            else:
                seconds = int(time_lower)
            
            if seconds < 10 or seconds > 86400:  # От 10 секунд до 1 дня
                await ctx.send("❌ Время должно быть от 10 секунд до 1 дня", ephemeral=True)
                return
            
            remind_time = datetime.now() + timedelta(seconds=seconds)
            
            # Сохраняем напоминание в БД
            await bot.db.execute(
                "INSERT INTO reminders (user_id, guild_id, reminder_text, remind_at, channel_id) VALUES (?, ?, ?, ?, ?)",
                (ctx.author.id, ctx.guild.id, message, remind_time.isoformat(), ctx.channel.id)
            )
            await bot.db.commit()
            
            embed = discord.Embed(
                title="⏰ Напоминание установлено",
                color=discord.Color.green(),
                timestamp=datetime.now()
            )
            embed.add_field(name="Текст", value=message, inline=False)
            embed.add_field(name="Через", value=f"**{time}**", inline=True)
            embed.add_field(name="Напомнить в", value=remind_time.strftime("%H:%M:%S"), inline=True)
            
            await ctx.send(embed=embed)
            
            # Запускаем напоминание
            async def send_reminder():
                await asyncio.sleep(seconds)
                try:
                    reminder_embed = discord.Embed(
                        title="🔔 Напоминание!",
                        description=f"**{message}**",
                        color=discord.Color.gold(),
                        timestamp=datetime.now()
                    )
                    reminder_embed.set_footer(text=f"Установлено {ctx.author.name}")
                    
                    await ctx.send(f"{ctx.author.mention}", embed=reminder_embed)
                    
                    # Удаляем из БД
                    await bot.db.execute(
                        "DELETE FROM reminders WHERE user_id = ? AND guild_id = ? AND reminder_text = ?",
                        (ctx.author.id, ctx.guild.id, message)
                    )
                    await bot.db.commit()
                    
                    logger.info(f'Напоминание для {ctx.author}: {message}')
                    
                except Exception as e:
                    logger.error(f'Ошибка отправки напоминания: {e}')
            
            bot.loop.create_task(send_reminder())
            logger.info(f'{ctx.author} установил напоминание на {time}: {message}')
            
        except Exception as e:
            await ctx.send(f"❌ Ошибка при установке напоминания: {e}", ephemeral=True)
            logger.error(f'Ошибка remind: {e}')
    
    @bot.hybrid_command(name="uptime", description="Время работы бота")
    async def uptime_cmd(ctx: commands.Context):
        """Время работы бота"""
        try:
            uptime = datetime.now() - bot.start_time
            
            days = uptime.days
            hours = uptime.seconds // 3600
            minutes = (uptime.seconds % 3600) // 60
            seconds = uptime.seconds % 60
            
            uptime_str = f"{days}д {hours}ч {minutes}м {seconds}с"
            
            embed = discord.Embed(
                title="⏱️ Время работы бота",
                color=discord.Color.blue(),
                timestamp=datetime.now()
            )
            embed.add_field(name="Запущен", value=bot.start_time.strftime("%d.%m.%Y %H:%M:%S"), inline=False)
            embed.add_field(name="Работает", value=f"**{uptime_str}**", inline=False)
            
            await ctx.send(embed=embed)
            logger.info(f'{ctx.author} проверил аптайм: {uptime_str}')
            
        except Exception as e:
            await ctx.send(f"❌ Ошибка: {e}", ephemeral=True)
            logger.error(f'Ошибка uptime: {e}')
    
    @bot.hybrid_command(name="poll", description="Создать опрос")
    @app_commands.describe(question="Вопрос опроса", options="Варианты через запятую (до 10)")
    async def poll_cmd(ctx: commands.Context, question: str, options: str):
        """Создание опроса"""
        try:
            options_list = [opt.strip() for opt in options.split(",")]
            
            if len(options_list) < 2:
                await ctx.send("❌ Укажите хотя бы 2 варианта", ephemeral=True)
                return
                
            if len(options_list) > 10:
                await ctx.send("❌ Максимум 10 вариантов", ephemeral=True)
                return
            
            # Эмодзи для вариантов
            poll_emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
            
            description = ""
            for i, option in enumerate(options_list):
                if i < len(poll_emojis):
                    description += f"{poll_emojis[i]} {option}\n"
                else:
                    description += f"• {option}\n"
            
            embed = discord.Embed(
                title=f"📊 Опрос: {question}",
                description=description,
                color=discord.Color.purple(),
                timestamp=datetime.now()
            )
            embed.set_footer(text=f"Создал: {ctx.author.name}")
            
            message = await ctx.send(embed=embed)
            
            # Добавляем реакции
            for i in range(min(len(options_list), len(poll_emojis))):
                await message.add_reaction(poll_emojis[i])
            
            # Сохраняем опрос в БД
            await bot.db.execute(
                "INSERT INTO polls (message_id, guild_id, channel_id, question, options) VALUES (?, ?, ?, ?, ?)",
                (message.id, ctx.guild.id, ctx.channel.id, question, json.dumps(options_list))
            )
            await bot.db.commit()
            
            logger.info(f'{ctx.author} создал опрос: {question}')
            
        except Exception as e:
            await ctx.send(f"❌ Ошибка при создании опроса: {e}", ephemeral=True)
            logger.error(f'Ошибка poll: {e}')
    
    @bot.hybrid_command(name="translate", description="Перевести текст")
    @app_commands.describe(text="Текст для перевода", language="Язык перевода (например: en, ru, es)")
    async def translate_cmd(ctx: commands.Context, text: str, language: str = "en"):
        """Перевод текста"""
        try:
            # В реальном боте здесь был бы API переводчика
            # Для демонстрации используем заглушку
            
            translations = {
                "en": {"hello": "привет", "goodbye": "до свидания", "thank you": "спасибо"},
                "ru": {"привет": "hello", "до свидания": "goodbye", "спасибо": "thank you"},
                "es": {"hello": "hola", "goodbye": "adiós", "thank you": "gracias"}
            }
            
            lang_names = {"en": "английский", "ru": "русский", "es": "испанский"}
            
            if language not in translations:
                await ctx.send("❌ Поддерживаемые языки: en, ru, es", ephemeral=True)
                return
            
            # Простой "перевод" для демонстрации
            text_lower = text.lower()
            translated = translations[language].get(text_lower, f"[Перевод '{text}' на {lang_names.get(language, language)}]")
            
            embed = discord.Embed(
                title="🌐 Переводчик",
                color=discord.Color.blue(),
                timestamp=datetime.now()
            )
            embed.add_field(name="Исходный текст", value=text, inline=False)
            embed.add_field(name="Язык перевода", value=lang_names.get(language, language), inline=True)
            embed.add_field(name="Перевод", value=translated, inline=False)
            
            await ctx.send(embed=embed)
            logger.info(f'{ctx.author} перевел текст: {text} -> {language}')
            
        except Exception as e:
            await ctx.send(f"❌ Ошибка при переводе: {e}", ephemeral=True)
            logger.error(f'Ошибка translate: {e}')
    
    @bot.hybrid_command(name="quote", description="Случайная цитата")
    async def quote_cmd(ctx: commands.Context):
        """Случайная цитата"""
        try:
            quotes = [
                {"text": "Будь тем изменением, которое хочешь видеть в мире.", "author": "Махатма Ганди"},
                {"text": "Единственный способ сделать великую работу — любить то, что делаешь.", "author": "Стив Джобс"},
                {"text": "Жизнь — это то, что происходит с тобой, пока ты строишь планы.", "author": "Джон Леннон"},
                {"text": "Успех — это способность идти от неудачи к неудаче, не теряя энтузиазма.", "author": "Уинстон Черчилль"},
                {"text": "Не откладывай на завтра то, что можно сделать сегодня.", "author": "Бенджамин Франклин"},
                {"text": "Мечты становятся реальностью, когда идеи встречаются с действием.", "author": "Альберт Эйнштейн"},
                {"text": "Лучший способ предсказать будущее — создать его.", "author": "Питер Друкер"},
                {"text": "Не бойтесь совершенства. Вам его никогда не достичь.", "author": "Сальвадор Дали"},
                {"text": "Единственное, что стоит между тобой и твоей целью, — это история, которую ты постоянно рассказываешь себе.", "author": "Джордан Белфорт"},
                {"text": "Самый большой риск — не рисковать вообще.", "author": "Марк Цукерберг"},
            ]
            
            quote = random.choice(quotes)
            
            embed = discord.Embed(
                title="💭 Случайная цитата",
                description=f"*{quote['text']}*",
                color=discord.Color.dark_gold(),
                timestamp=datetime.now()
            )
            embed.set_footer(text=f"— {quote['author']}")
            
            await ctx.send(embed=embed)
            logger.info(f'{ctx.author} получил случайную цитату')
            
        except Exception as e:
            await ctx.send(f"❌ Ошибка: {e}", ephemeral=True)
            logger.error(f'Ошибка quote: {e}')
    
    @bot.hybrid_command(name="fact", description="Интересный факт")
    async def fact_cmd(ctx: commands.Context):
        """Интересный факт"""
        try:
            facts = [
                "Медузы существуют на Земле более 650 миллионов лет — они старше динозавров и акул.",
                "Сердце голубого кита настолько велико, что через его аорту может проплыть человек.",
                "Осьминог имеет три сердца: два прокачивают кровь через жабры, а одно — через тело.",
                "Мед никогда не портится. Археологи находили съедобный мёд в древнеегипетских гробницах.",
                "Тигры имеют не только полосатый мех, но и полосатую кожу.",
                "Бананы — это ягоды, а клубника — нет.",
                "У улитки около 25 000 зубов.",
                "Венера — единственная планета Солнечной системы, вращающаяся по часовой стрелке.",
                "Человеческое тело содержит достаточно железа, чтобы сделать гвоздь длиной 7,5 см.",
                "Свету от Солнца требуется около 8 минут и 20 секунд, чтобы достичь Земли.",
                "Колибри — единственная птица, способная летать назад.",
                "У человека и банана около 50% общих генов.",
                "Земля — единственная планета, названная не в честь бога.",
                "Морские выдры держатся за лапы во время сна, чтобы их не унесло течением.",
            ]
            
            fact = random.choice(facts)
            
            embed = discord.Embed(
                title="📚 Интересный факт",
                description=fact,
                color=discord.Color.purple(),
                timestamp=datetime.now()
            )
            
            await ctx.send(embed=embed)
            logger.info(f'{ctx.author} получил интересный факт')
            
        except Exception as e:
            await ctx.send(f"❌ Ошибка: {e}", ephemeral=True)
            logger.error(f'Ошибка fact: {e}')
    
    @bot.hybrid_command(name="stats", description="Статистика бота")
    async def stats_cmd(ctx: commands.Context):
        """Статистика бота"""
        try:
            # Статистика бота
            guilds_count = len(bot.guilds)
            total_members = sum(guild.member_count for guild in bot.guilds)
            
            # Подсчет команд
            commands_count = len(bot.commands)
            
            # Время работы
            uptime = datetime.now() - bot.start_time
            days = uptime.days
            hours = uptime.seconds // 3600
            minutes = (uptime.seconds % 3600) // 60
            
            embed = discord.Embed(
                title="📊 Статистика бота",
                color=discord.Color.blue(),
                timestamp=datetime.now()
            )
            
            embed.add_field(name="🌐 Серверов", value=f"**{guilds_count}**", inline=True)
            embed.add_field(name="👥 Пользователей", value=f"**{total_members}**", inline=True)
            embed.add_field(name="📝 Команд", value=f"**{commands_count}**", inline=True)
            
            embed.add_field(name="⏱️ Время работы", value=f"**{days}**д **{hours}**ч **{minutes}**м", inline=True)
            embed.add_field(name="🏓 Пинг", value=f"**{round(bot.latency * 1000)}**ms", inline=True)
            embed.add_field(name="📅 Запущен", value=bot.start_time.strftime("%d.%m.%Y"), inline=True)
            
            # Техническая информация
            embed.add_field(name="⚙️ Версия Discord.py", value="2.4.0", inline=True)
            embed.add_field(name="🐍 Python", value="3.11+", inline=True)
            embed.add_field(name="🎵 Музыка", value="Wavelink 3.4.1", inline=True)
            
            if bot.user.avatar:
                embed.set_thumbnail(url=bot.user.avatar.url)
            
            await ctx.send(embed=embed)
            logger.info(f'{ctx.author} посмотрел статистику бота')
            
        except Exception as e:
            await ctx.send(f"❌ Ошибка: {e}", ephemeral=True)
            logger.error(f'Ошибка stats: {e}')
    
    logger.info("Модуль утилит загружен")