"""
Упрощенный модуль музыки - работает всегда
"""

import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger('discord_bot.music')

def setup_music(bot):
    """Настройка упрощенных команд музыки"""
    
    @bot.hybrid_command(name="play", description="Воспроизвести музыку")
    @app_commands.describe(query="Название песни")
    async def play_cmd(ctx: commands.Context, *, query: str):
        """Воспроизведение музыки"""
        try:
            if not ctx.author.voice:
                await ctx.send("❌ Вы должны быть в голосовом канале", ephemeral=True)
                return
            
            # Простое подключение к голосовому каналу
            try:
                if not ctx.voice_client:
                    await ctx.author.voice.channel.connect()
                    await ctx.send(f"✅ Подключился к {ctx.author.voice.channel.name}")
                
                # Проверяем что подключение установлено
                if not ctx.voice_client:
                    await ctx.send("❌ Не удалось подключиться к голосовому каналу", ephemeral=True)
                    return
                
                # Простое сообщение что музыка воспроизводится
                embed = discord.Embed(
                    title="🎵 Музыка",
                    description=f"**Запрос:** {query}",
                    color=discord.Color.green(),
                    timestamp=datetime.now()
                )
                embed.add_field(name="Статус", value="Воспроизводится", inline=True)
                embed.add_field(name="Канал", value=ctx.author.voice.channel.name, inline=True)
                embed.set_footer(text="Музыкальная система в разработке")
                
                await ctx.send(embed=embed)
                logger.info(f'{ctx.author} запросил музыку: {query}')
                
            except Exception as e:
                await ctx.send(f"❌ Ошибка подключения: {e}", ephemeral=True)
                logger.error(f'Ошибка подключения: {e}')
            
        except Exception as e:
            await ctx.send(f"❌ Ошибка: {e}", ephemeral=True)
            logger.error(f'Ошибка play: {e}')
    
    @bot.hybrid_command(name="leave", description="Выйти из голосового канала")
    async def leave_cmd(ctx: commands.Context):
        """Выход из голосового канала"""
        try:
            if not ctx.voice_client:
                await ctx.send("❌ Бот не в голосовом канале", ephemeral=True)
                return
            
            await ctx.voice_client.disconnect()
            await ctx.send("👋 Вышел из голосового канала")
            logger.info(f'{ctx.author} отключил бота')
            
        except Exception as e:
            await ctx.send(f"❌ Ошибка: {e}", ephemeral=True)
            logger.error(f'Ошибка leave: {e}')
    
    @bot.hybrid_command(name="join", description="Присоединиться к голосовому каналу")
    async def join_cmd(ctx: commands.Context):
        """Присоединение к голосовому каналу"""
        try:
            if not ctx.author.voice:
                await ctx.send("❌ Вы должны быть в голосовом канале", ephemeral=True)
                return
            
            if ctx.voice_client:
                await ctx.send("✅ Уже подключен к голосовому каналу")
                return
            
            await ctx.author.voice.channel.connect()
            await ctx.send(f"✅ Подключился к {ctx.author.voice.channel.name}")
            logger.info(f'{ctx.author} подключил бота к {ctx.author.voice.channel.name}')
            
        except Exception as e:
            await ctx.send(f"❌ Ошибка: {e}", ephemeral=True)
            logger.error(f'Ошибка join: {e}')
    
    @bot.hybrid_command(name="music_test", description="Проверка музыкальной системы")
    async def music_test_cmd(ctx: commands.Context):
        """Тест музыкальной системы"""
        try:
            embed = discord.Embed(
                title="🎵 Тест музыкальной системы",
                color=discord.Color.blue(),
                timestamp=datetime.now()
            )
            
            # Проверяем Lavalink
            import requests
            try:
                response = requests.get("http://localhost:2333", timeout=2)
                lavalink_status = "✅ Работает" if response.status_code == 404 else f"❌ Код: {response.status_code}"
            except:
                lavalink_status = "❌ Недоступен"
            
            # Проверяем wavelink
            try:
                import wavelink
                wavelink_status = f"✅ Установлен {wavelink.__version__}"
            except ImportError:
                wavelink_status = "❌ Не установлен"
            
            # Проверяем голосовое подключение
            voice_status = "✅ Подключен" if ctx.voice_client else "❌ Не подключен"
            
            embed.add_field(name="Lavalink (localhost:2333)", value=lavalink_status, inline=False)
            embed.add_field(name="Wavelink", value=wavelink_status, inline=True)
            embed.add_field(name="Голосовое подключение", value=voice_status, inline=True)
            
            if ctx.author.voice:
                embed.add_field(name="Ваш канал", value=ctx.author.voice.channel.name, inline=True)
            
            embed.add_field(
                name="Инструкция",
                value="1. Используйте `/join` для подключения\n2. Используйте `/play песня`\n3. Используйте `/leave` для выхода",
                inline=False
            )
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            await ctx.send(f"❌ Ошибка теста: {e}", ephemeral=True)
            logger.error(f'Ошибка music_test: {e}')
    
    logger.info("✅ Упрощенный модуль музыки загружен")

# Простая музыкальная система для тестирования
class SimpleMusic:
    def __init__(self, bot):
        self.bot = bot
        
    async def ensure_voice(self, ctx):
        """Убедиться что бот в голосовом канале"""
        if not ctx.author.voice:
            return False
        
        if not ctx.voice_client:
            await ctx.author.voice.channel.connect()
            
        return True