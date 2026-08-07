"""
Рабочий музыкальный модуль - только голосовое подключение
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
    """Настройка музыкальных команд"""
    
    @bot.hybrid_command(name="join", description="Присоединиться к голосовому каналу")
    async def join_cmd(ctx: commands.Context):
        """Присоединение к голосовому каналу"""
        try:
            if not ctx.author.voice:
                await ctx.send("❌ Вы должны быть в голосовом канале", ephemeral=True)
                return
            
            if ctx.voice_client:
                await ctx.send(f"✅ Уже подключен к {ctx.voice_client.channel.name}")
                return
            
            # Простое подключение к голосовому каналу
            voice_channel = ctx.author.voice.channel
            await voice_channel.connect()
            
            await ctx.send(f"✅ Подключился к {voice_channel.name}")
            logger.info(f'Подключился к {voice_channel.name}')
            
        except Exception as e:
            await ctx.send(f"❌ Ошибка: {e}", ephemeral=True)
            logger.error(f'Ошибка join: {e}')
    
    @bot.hybrid_command(name="play", description="Информация о музыкальной системе")
    async def play_cmd(ctx: commands.Context):
        """Информация о музыке"""
        embed = discord.Embed(
            title="🎵 Музыкальная система",
            description="Музыкальные команды работают в тестовом режиме",
            color=discord.Color.blue(),
            timestamp=datetime.now()
        )
        
        # Статус подключения
        voice_status = "✅ Подключен" if ctx.voice_client else "❌ Не подключен"
        embed.add_field(name="Голосовое подключение", value=voice_status, inline=True)
        
        if ctx.voice_client:
            embed.add_field(name="Канал", value=ctx.voice_client.channel.name, inline=True)
        
        # Информация о Lavalink
        embed.add_field(
            name="Lavalink статус", 
            value="🔄 В процессе настройки\nПока используется только голосовое подключение", 
            inline=False
        )
        
        # Доступные команды
        embed.add_field(
            name="Доступные команды",
            value="• `/join` - подключиться к каналу\n• `/leave` - выйти из канала\n• `/music` - информация о музыке",
            inline=False
        )
        
        # Что работает
        embed.add_field(
            name="✅ Что работает",
            value="• Голосовое подключение\n• Присоединение к каналу\n• Выход из канала",
            inline=True
        )
        
        # Что в разработке
        embed.add_field(
            name="🔄 В разработке",
            value="• Воспроизведение музыки\n• Очередь треков\n• Пауза/продолжение",
            inline=True
        )
        
        await ctx.send(embed=embed)
    
    @bot.hybrid_command(name="leave", description="Выйти из голосового канала")
    async def leave_cmd(ctx: commands.Context):
        """Выход из голосового канала"""
        try:
            if not ctx.voice_client:
                await ctx.send("❌ Бот не в голосовом канале", ephemeral=True)
                return
            
            channel_name = ctx.voice_client.channel.name
            await ctx.voice_client.disconnect()
            await ctx.send(f"👋 Вышел из {channel_name}")
            
        except Exception as e:
            await ctx.send(f"❌ Ошибка: {e}", ephemeral=True)
            logger.error(f'Ошибка leave: {e}')
    
    @bot.hybrid_command(name="music", description="Проверка музыкальной системы")
    async def music_cmd(ctx: commands.Context):
        """Проверка музыкальной системы"""
        embed = discord.Embed(
            title="🎵 Проверка музыкальной системы",
            color=discord.Color.green(),
            timestamp=datetime.now()
        )
        
        # Проверяем базовые вещи
        tests = []
        
        # Тест 1: Голосовое подключение
        try:
            if ctx.voice_client:
                tests.append("✅ Голосовое подключение: работает")
            else:
                tests.append("⚠️ Голосовое подключение: не активно")
        except:
            tests.append("❌ Голосовое подключение: ошибка")
        
        # Тест 2: Пользователь в голосовом канале
        try:
            if ctx.author.voice:
                tests.append(f"✅ Вы в канале: {ctx.author.voice.channel.name}")
            else:
                tests.append("❌ Вы не в голосовом канале")
        except:
            tests.append("❌ Проверка канала: ошибка")
        
        # Тест 3: Доступность Lavalink
        try:
            import requests
            response = requests.get("http://localhost:2333", timeout=2)
            if response.status_code == 404:
                tests.append("✅ Lavalink: работает (404 - это нормально)")
            elif response.status_code == 401:
                tests.append("❌ Lavalink: неправильный пароль")
            else:
                tests.append(f"⚠️ Lavalink: код {response.status_code}")
        except:
            tests.append("❌ Lavalink: недоступен")
        
        # Тест 4: Wavelink
        try:
            import wavelink
            tests.append(f"✅ Wavelink: установлен {wavelink.__version__}")
        except ImportError:
            tests.append("❌ Wavelink: не установлен")
        
        # Добавляем тесты в embed
        for i, test in enumerate(tests, 1):
            embed.add_field(name=f"Тест {i}", value=test, inline=False)
        
        # Инструкция
        embed.add_field(
            name="📋 Инструкция",
            value="1. Зайдите в голосовой канал\n2. Используйте `/join`\n3. Бот подключится и останется в канале",
            inline=False
        )
        
        await ctx.send(embed=embed)
    
    @bot.hybrid_command(name="connect", description="Подключиться и остаться в канале")
    async def connect_cmd(ctx: commands.Context):
        """Подключение и удержание соединения"""
        try:
            if not ctx.author.voice:
                await ctx.send("❌ Вы должны быть в голосовом канале", ephemeral=True)
                return
            
            if ctx.voice_client:
                await ctx.send(f"✅ Уже подключен к {ctx.voice_client.channel.name}")
                return
            
            # Подключаемся
            voice_channel = ctx.author.voice.channel
            await voice_channel.connect()
            
            # Отправляем подтверждение
            embed = discord.Embed(
                title="✅ Успешное подключение",
                description=f"Бот подключен к **{voice_channel.name}** и остаётся в канале",
                color=discord.Color.green(),
                timestamp=datetime.now()
            )
            
            embed.add_field(name="Статус", value="✅ Подключён и активен", inline=True)
            embed.add_field(name="Команды", value="Используйте `/leave` для выхода", inline=True)
            
            await ctx.send(embed=embed)
            
            # Логируем
            logger.info(f'Успешное подключение к {voice_channel.name}')
            
        except Exception as e:
            await ctx.send(f"❌ Ошибка подключения: {e}", ephemeral=True)
            logger.error(f'Ошибка connect: {e}')
    
    logger.info("✅ Рабочий музыкальный модуль загружен")