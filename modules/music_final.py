"""
Финальный модуль музыки с исправленным подключением
"""

import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import logging
from datetime import datetime
from typing import Optional
import wavelink

logger = logging.getLogger('discord_bot.music')

class MusicSystem:
    def __init__(self, bot):
        self.bot = bot
        self.queues = {}
        
    def get_queue(self, guild_id):
        if guild_id not in self.queues:
            self.queues[guild_id] = []
        return self.queues[guild_id]
    
    def add_to_queue(self, guild_id, track):
        queue = self.get_queue(guild_id)
        queue.append(track)
        return len(queue)

def setup_music(bot):
    """Настройка музыкальных команд"""
    
    music_system = MusicSystem(bot)
    
    # Сначала подключаемся к Lavalink
    @bot.event
    async def on_ready():
        """Подключение к Lavalink при запуске"""
        try:
            # Используем правильный пароль
            node = wavelink.Node(
                uri='http://localhost:2333',
                password='123456'
            )
            
            await wavelink.Pool.connect(client=bot, nodes=[node])
            logger.info("✅ Подключился к Lavalink с паролем 123456")
            print("✅ Музыка: подключено к Lavalink")
            
        except Exception as e:
            logger.warning(f"⚠️ Не удалось подключиться к Lavalink: {e}")
            print(f"⚠️  Музыка: Lavalink недоступен - {e}")
    
    @bot.hybrid_command(name="join", description="Присоединиться к голосовому каналу")
    async def join_cmd(ctx: commands.Context):
        """Присоединение к голосовому каналу"""
        try:
            if not ctx.author.voice:
                await ctx.send("❌ Вы должны быть в голосовом канале", ephemeral=True)
                return
            
            if ctx.voice_client:
                await ctx.send(f"✅ Уже в канале: {ctx.voice_client.channel.name}")
                return
            
            # Подключаемся через wavelink
            player: wavelink.Player = await ctx.author.voice.channel.connect(cls=wavelink.Player)
            await ctx.send(f"✅ Подключился к {player.channel.name}")
            logger.info(f'Подключился к {player.channel.name}')
            
        except Exception as e:
            await ctx.send(f"❌ Ошибка: {e}", ephemeral=True)
            logger.error(f'Ошибка join: {e}')
    
    @bot.hybrid_command(name="play", description="Воспроизвести музыку с YouTube")
    @app_commands.describe(query="Название песни или URL YouTube")
    async def play_cmd(ctx: commands.Context, *, query: str):
        """Воспроизведение музыки"""
        try:
            # Проверяем что пользователь в голосовом канале
            if not ctx.author.voice:
                await ctx.send("❌ Вы должны быть в голосовом канале", ephemeral=True)
                return
            
            # Получаем или создаем плеер
            player: wavelink.Player = ctx.voice_client
            
            if not player:
                # Подключаемся к каналу
                player: wavelink.Player = await ctx.author.voice.channel.connect(cls=wavelink.Player)
                await ctx.send(f"✅ Подключился к {player.channel.name}")
            
            # Ищем трек
            await ctx.defer()
            
            try:
                # Ищем на YouTube
                tracks = await wavelink.Playable.search(query)
                
                if not tracks:
                    await ctx.send("❌ Трек не найден", ephemeral=True)
                    return
                
                track = tracks[0]
                
                # Воспроизводим
                await player.play(track)
                
                embed = discord.Embed(
                    title="🎶 Сейчас играет",
                    description=f"**{track.title}**",
                    color=discord.Color.green(),
                    timestamp=datetime.now()
                )
                embed.add_field(name="Автор", value=track.author or "Неизвестно", inline=True)
                
                # Форматируем длительность
                minutes = track.length // 60000
                seconds = (track.length % 60000) // 1000
                embed.add_field(name="Длительность", value=f"{minutes}:{seconds:02d}", inline=True)
                
                if track.uri:
                    embed.add_field(name="Ссылка", value=f"[YouTube]({track.uri})", inline=True)
                
                if track.artwork:
                    embed.set_thumbnail(url=track.artwork)
                
                await ctx.send(embed=embed)
                logger.info(f'{ctx.author} воспроизвел: {track.title}')
                
            except Exception as e:
                await ctx.send(f"❌ Ошибка поиска: {e}", ephemeral=True)
                logger.error(f'Ошибка поиска: {e}')
                
        except Exception as e:
            await ctx.send(f"❌ Ошибка: {e}", ephemeral=True)
            logger.error(f'Ошибка play: {e}')
    
    @bot.hybrid_command(name="pause", description="Поставить музыку на паузу")
    async def pause_cmd(ctx: commands.Context):
        """Пауза музыки"""
        try:
            player: wavelink.Player = ctx.voice_client
            if not player or not player.playing:
                await ctx.send("❌ Музыка не играет", ephemeral=True)
                return
            
            await player.pause()
            await ctx.send("⏸️ Пауза")
            
        except Exception as e:
            await ctx.send(f"❌ Ошибка: {e}", ephemeral=True)
    
    @bot.hybrid_command(name="resume", description="Продолжить воспроизведение")
    async def resume_cmd(ctx: commands.Context):
        """Продолжить музыку"""
        try:
            player: wavelink.Player = ctx.voice_client
            if not player or not player.paused:
                await ctx.send("❌ Музыка не на паузе", ephemeral=True)
                return
            
            await player.resume()
            await ctx.send("▶️ Продолжаем")
            
        except Exception as e:
            await ctx.send(f"❌ Ошибка: {e}", ephemeral=True)
    
    @bot.hybrid_command(name="stop", description="Остановить музыку")
    async def stop_cmd(ctx: commands.Context):
        """Остановка музыки"""
        try:
            player: wavelink.Player = ctx.voice_client
            if not player:
                await ctx.send("❌ Бот не в голосовом канале", ephemeral=True)
                return
            
            await player.stop()
            music_system.queues[ctx.guild.id] = []
            await ctx.send("⏹️ Остановлено")
            
        except Exception as e:
            await ctx.send(f"❌ Ошибка: {e}", ephemeral=True)
    
    @bot.hybrid_command(name="leave", description="Выйти из голосового канала")
    async def leave_cmd(ctx: commands.Context):
        """Выход из голосового канала"""
        try:
            player: wavelink.Player = ctx.voice_client
            if not player:
                await ctx.send("❌ Бот не в голосовом канале", ephemeral=True)
                return
            
            await player.disconnect()
            await ctx.send("👋 Вышел")
            
        except Exception as e:
            await ctx.send(f"❌ Ошибка: {e}", ephemeral=True)
    
    @bot.hybrid_command(name="volume", description="Установить громкость")
    @app_commands.describe(level="Уровень громкости (1-100)")
    async def volume_cmd(ctx: commands.Context, level: int):
        """Настройка громкости"""
        try:
            if level < 1 or level > 100:
                await ctx.send("❌ Громкость должна быть от 1 до 100", ephemeral=True)
                return
            
            player: wavelink.Player = ctx.voice_client
            if not player:
                await ctx.send("❌ Бот не в голосовом канале", ephemeral=True)
                return
            
            await player.set_volume(level)
            await ctx.send(f"🔊 Громкость: {level}%")
            
        except Exception as e:
            await ctx.send(f"❌ Ошибка: {e}", ephemeral=True)
    
    logger.info("✅ Музыкальный модуль загружен")