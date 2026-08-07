"""
Модуль игр для Discord бота
Команды: rps, 8ball, dice, roll, slot, guess, quest
Мини-игры и развлечения
"""

import discord
from discord.ext import commands
from discord import app_commands
import asyncio
from datetime import datetime
import logging
import random
import json

logger = logging.getLogger('discord_bot.games')

def setup_games(bot):
    """Настройка команд игр"""
    
    @bot.hybrid_command(name="8ball", description="Магический шар предсказаний")
    @app_commands.describe(question="Ваш вопрос")
    async def eightball_cmd(ctx: commands.Context, *, question: str):
        """Магический шар 8ball"""
        try:
            responses = [
                "Бесспорно! ✨",
                "Предрешено! ✅",
                "Никаких сомнений! 👍",
                "Определённо да! 👌",
                "Можешь быть уверен! 😊",
                "Мне кажется — «да»! 🤔",
                "Вероятнее всего! 📊",
                "Хорошие перспективы! 🌟",
                "Знаки говорят — «да»! 🔮",
                "Да! 🎉",
                "Пока не ясно, попробуй снова! 🔄",
                "Спроси позже! ⏳",
                "Лучше не рассказывать! 🤫",
                "Сейчас нельзя предсказать! 🙅‍♂️",
                "Сконцентрируйся и спроси опять! 🧘‍♂️",
                "Даже не думай! ❌",
                "Мой ответ — «нет»! 👎",
                "По моим данным — «нет»! 📉",
                "Перспективы не очень! 😕",
                "Весьма сомнительно! 🤨"
            ]
            
            response = random.choice(responses)
            
            embed = discord.Embed(
                title="🎱 Магический шар",
                color=discord.Color.dark_purple(),
                timestamp=datetime.now()
            )
            embed.add_field(name="Ваш вопрос", value=f"*{question}*", inline=False)
            embed.add_field(name="Ответ шара", value=f"**{response}**", inline=False)
            embed.set_thumbnail(url="https://cdn.discordapp.com/emojis/876284405487927326.png")
            
            await ctx.send(embed=embed)
            logger.info(f'{ctx.author} спросил 8ball: {question[:50]}...')
            
        except Exception as e:
            await ctx.send(f"❌ Ошибка: {e}", ephemeral=True)
            logger.error(f'Ошибка 8ball: {e}')
    
    @bot.hybrid_command(name="guess", description="Угадай число (1-10)")
    @app_commands.describe(bet="Ваша ставка")
    @commands.cooldown(1, 15, commands.BucketType.user)
    async def guess_cmd(ctx: commands.Context, bet: int = 10):
        """Игра угадай число"""
        try:
            from modules.economy import EconomySystem
            economy = EconomySystem(bot)
            
            if bet <= 0:
                await ctx.send("❌ Ставка должна быть положительной", ephemeral=True)
                return
            
            if bet > 200:
                await ctx.send("❌ Максимальная ставка: 200 💰", ephemeral=True)
                return
            
            user_data = await economy.get_user_data(ctx.author.id, ctx.guild.id)
            
            if user_data["balance"] < bet:
                await ctx.send("❌ Недостаточно средств", ephemeral=True)
                return
            
            embed = discord.Embed(
                title="🔢 Угадай число от 1 до 10",
                description="У вас есть 15 секунд, чтобы написать число в чат!",
                color=discord.Color.blurple(),
                timestamp=datetime.now()
            )
            embed.add_field(name="Ставка", value=f"**{bet}** 💰", inline=True)
            embed.add_field(name="Потенциальный выигрыш", value=f"**{bet * 2}** 💰", inline=True)
            
            message = await ctx.send(embed=embed)
            
            # Загадываем число
            secret_number = random.randint(1, 10)
            
            def check(m):
                return m.author == ctx.author and m.channel == ctx.channel and m.content.isdigit()
            
            try:
                guess_msg = await bot.wait_for('message', timeout=15.0, check=check)
                guess = int(guess_msg.content)
                
                if guess == secret_number:
                    win_amount = bet * 2
                    await economy.update_balance(ctx.author.id, ctx.guild.id, win_amount)
                    await economy.add_xp(ctx.author.id, ctx.guild.id, 20)
                    
                    result_embed = discord.Embed(
                        title="🎉 Поздравляем! Вы угадали!",
                        description=f"Загаданное число: **{secret_number}**\nВаша догадка: **{guess}**",
                        color=discord.Color.green(),
                        timestamp=datetime.now()
                    )
                    result_embed.add_field(name="Выигрыш", value=f"**+{win_amount}** 💰", inline=True)
                    result_embed.add_field(name="Новый баланс", value=f"{user_data['balance'] + win_amount} 💰", inline=True)
                    
                    logger.info(f'{ctx.author} угадал число: {guess} = {secret_number}, выигрыш {win_amount}')
                else:
                    await economy.update_balance(ctx.author.id, ctx.guild.id, -bet)
                    
                    result_embed = discord.Embed(
                        title="😢 Вы не угадали",
                        description=f"Загаданное число: **{secret_number}**\nВаша догадка: **{guess}**",
                        color=discord.Color.red(),
                        timestamp=datetime.now()
                    )
                    result_embed.add_field(name="Потеряно", value=f"**{bet}** 💰", inline=True)
                    result_embed.add_field(name="Новый баланс", value=f"{user_data['balance'] - bet} 💰", inline=True)
                    
                    logger.info(f'{ctx.author} не угадал число: {guess} != {secret_number}, потеря {bet}')
                
                await message.edit(embed=result_embed)
                
            except asyncio.TimeoutError:
                timeout_embed = discord.Embed(
                    title="⏰ Время вышло!",
                    description=f"Вы не успели угадать число.\nЗагаданное число было: **{secret_number}**",
                    color=discord.Color.orange(),
                    timestamp=datetime.now()
                )
                await message.edit(embed=timeout_embed)
                logger.info(f'{ctx.author} не успел угадать число')
                
        except Exception as e:
            await ctx.send(f"❌ Ошибка в игре: {e}", ephemeral=True)
            logger.error(f'Ошибка guess: {e}')
    
    @bot.hybrid_command(name="quest", description="Показать активные квесты")
    async def quest_cmd(ctx: commands.Context):
        """Активные квесты"""
        try:
            quests = [
                {
                    "id": 1,
                    "name": "🎯 Новичок",
                    "description": "Получите 1000 опыта",
                    "reward": "500 💰 + Редкий предмет",
                    "progress": "0/1000 XP"
                },
                {
                    "id": 2, 
                    "name": "💰 Богач",
                    "description": "Накопите 5000 монет",
                    "reward": "1000 💰 + Золотой медальон",
                    "progress": "0/5000 💰"
                },
                {
                    "id": 3,
                    "name": "🎮 Игрок",
                    "description": "Сыграйте 10 раз в мини-игры",
                    "reward": "300 💰 + Свиток опыта",
                    "progress": "0/10 игр"
                },
                {
                    "id": 4,
                    "name": "🎵 Меломан",
                    "description": "Прослушайте 50 песен",
                    "reward": "400 💰 + Наушники",
                    "progress": "0/50 песен"
                },
                {
                    "id": 5,
                    "name": "⚔️ Воин",
                    "description": "Достигните 10 уровня",
                    "reward": "1000 💰 + Эпический меч",
                    "progress": "0/10 уровень"
                }
            ]
            
            embed = discord.Embed(
                title="📜 Активные квесты",
                description="Выполняйте квесты для получения наград!",
                color=discord.Color.dark_gold(),
                timestamp=datetime.now()
            )
            
            for quest in quests:
                embed.add_field(
                    name=f"{quest['name']}",
                    value=f"{quest['description']}\n**Награда:** {quest['reward']}\n**Прогресс:** {quest['progress']}",
                    inline=False
                )
            
            embed.set_footer(text="Система квестов в разработке")
            
            await ctx.send(embed=embed)
            logger.info(f'{ctx.author} посмотрел квесты')
            
        except Exception as e:
            await ctx.send(f"❌ Ошибка: {e}", ephemeral=True)
            logger.error(f'Ошибка quest: {e}')
    
    logger.info("Модуль игр загружен")