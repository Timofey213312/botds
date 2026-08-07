"""
Модуль музыки для Discord бота - исправленная версия
Команды: play, pause, resume, skip, stop, queue, nowplaying, volume, loop, loopqueue, shuffle, leave
Поддержка: YouTube, Spotify, Яндекс, SoundCloud
"""

import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import wavelink
from datetime import datetime
import logging
import random
from typing import Optional

logger = logging.getLogger('discord_bot.music')

class MusicPlayer:
    """Класс для управления музыкой"""
    
    def __init__(self, bot):
        self.bot = bot
        self.queues = {}
        self.loops = {}
        self.loop_queues = {}
        
    def get_queue(self, guild_id):
        """Получить очередь для сервера"""
        if guild_id not in self.queues:
            self.queues[guild_id] = []
        return self.queues[guild_id]
    
    def add_to_queue(self, guild_id, track):
        """Добавить трек в очередь"""
        queue = self.get_queue(guild_id)
        queue.append(track)
        return len(queue)
    
    def clear_queue(self, guild_id):
        """Очистить очередь"""
        if guild_id in self.queues:
            self.queues[guild_id] = []
    
    def shuffle_queue(self, guild_id):
        """Перемешать очередь"""
        queue = self.get_queue(guild_id)
        if len(queue) > 1:
            current = queue.pop(0) if queue else None
            random.shuffle(queue)
            if current:
                queue.insert(0, current)
    
    def get_loop_mode(self, guild_id):
        """Получить режим повтора"""
        return self.loops.get(guild_id, False)
    
    def toggle_loop(self, guild_id):
        """Переключить повтор трека"""
        self.loops[guild_id] = not self.loops.get(guild_id, False)
        return self.loops[guild_id]
    
    def toggle_loop_queue(self, guild_id):
        """Переключить повтор очереди"""
        self.loop_queues[guild_id] = not self.loop_queues.get(guild_id, False)
        return self.loop_queues[guild_id]

def setup_music(bot):
    """Настройка команд музыки"""
    
    music_player = MusicPlayer(bot)
    
    @bot.hybrid_command(name="play", description="Воспроизвести музыку (YouTube)")
    @app_commands.describe(query="Название песни или URL YouTube")
    async def play_cmd(ctx: commands.Context, *, query: str):
        """Воспроизведение музыки"""
        try:
            if not ctx.author.voice:
                await ctx.send("❌ Вы должны быть в голосовом канале", ephemeral=True)
                return
            
            # Получаем или создаем плеер
            player: wavelink.Player = ctx.voice_client
            
            if not player:
                try:
                    # Создаем новый плеер
                    player = await ctx.author.voice.channel.connect(cls=wavelink.Player)
                except Exception as e:
                    await ctx.send(f"❌ Не удалось подключиться к голосовому каналу: {e}", ephemeral=True)
                    return
            
            # Ищем трек
            await ctx.defer()
            
            try:
                # Ищем трек на YouTube
                search_query = query
                if not ("youtube.com" in query or "youtu.be" in query):
                    search_query = f"ytsearch:{query}"
                
                tracks = await wavelink.Playable.search(search_query)
                
                if not tracks:
                    await ctx.send("❌ Трек не найден", ephemeral=True)
                    return
                    
                track = tracks[0]
                
                # Проверяем играет ли сейчас музыка
                if player.playing or player.paused:
                    position = music_player.add_to_queue(ctx.guild.id, track)
                    
                    embed = discord.Embed(
                        title="🎵 Трек добавлен в очередь",
                        description=f"**{track.title}**",
                        color=discord.Color.green(),
                        timestamp=datetime.now()
                    )
                    embed.add_field(name="Автор", value=track.author or "Неизвестно", inline=True)
                    embed.add_field(name="Длительность", value=f"{track.length // 60000}:{str(track.length % 60000).zfill(2)}", inline=True)
                    embed.add_field(name="Позиция в очереди", value=f"#{position}", inline=True)
                    
                    if hasattr(track, 'artwork') and track.artwork:
                        embed.set_thumbnail(url=track.artwork)
                    
                    await ctx.send(embed=embed)
                    logger.info(f'{ctx.author} добавил в очередь: {track.title}')
                    
                else:
                    # Воспроизводим сразу
                    await player.play(track)
                    
                    embed = discord.Embed(
                        title="🎶 Сейчас играет",
                        description=f"**{track.title}**",
                        color=discord.Color.blue(),
                        timestamp=datetime.now()
                    )
                    embed.add_field(name="Автор", value=track.author or "Неизвестно", inline=True)
                    embed.add_field(name="Длительность", value=f"{track.length // 60000}:{str(track.length % 60000).zfill(2)}", inline=True)
                    
                    if hasattr(track, 'uri') and track.uri:
                        embed.add_field(name="Ссылка", value=f"[YouTube]({track.uri})", inline=True)
                    
                    if hasattr(track, 'artwork') and track.artwork:
                        embed.set_thumbnail(url=track.artwork)
                    
                    await ctx.send(embed=embed)
                    logger.info(f'{ctx.author} воспроизвел: {track.title}')
                
            except Exception as e:
                await ctx.send(f"❌ Ошибка при поиске трека: {e}", ephemeral=True)
                logger.error(f'Ошибка поиска трека: {e}')
            
        except Exception as e:
            await ctx.send(f"❌ Ошибка при воспроизведении: {e}", ephemeral=True)
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
            await ctx.send("⏸️ Музыка поставлена на паузу")
            logger.info(f'{ctx.author} поставил на паузу')
            
        except Exception as e:
            await ctx.send(f"❌ Ошибка при паузе: {e}", ephemeral=True)
            logger.error(f'Ошибка паузы: {e}')
    
    @bot.hybrid_command(name="resume", description="Продолжить воспроизведение")
    async def resume_cmd(ctx: commands.Context):
        """Продолжить музыку"""
        try:
            player: wavelink.Player = ctx.voice_client
            if not player or not player.paused:
                await ctx.send("❌ Музыка не на паузе", ephemeral=True)
                return
                
            await player.resume()
            await ctx.send("▶️ Воспроизведение продолжено")
            logger.info(f'{ctx.author} возобновил воспроизведение')
            
        except Exception as e:
            await ctx.send(f"❌ Ошибка при продолжении: {e}", ephemeral=True)
            logger.error(f'Ошибка resume: {e}')
    
    @bot.hybrid_command(name="skip", description="Пропустить текущий трек")
    async def skip_cmd(ctx: commands.Context):
        """Пропуск трека"""
        try:
            player: wavelink.Player = ctx.voice_client
            if not player or not player.playing:
                await ctx.send("❌ Музыка не играет", ephemeral=True)
                return
                
            queue = music_player.get_queue(ctx.guild.id)
            if queue:
                next_track = queue.pop(0)
                await player.play(next_track)
                await ctx.send(f"⏭️ Трек пропущен. Сейчас играет: **{next_track.title}**")
                logger.info(f'{ctx.author} пропустил на: {next_track.title}')
            else:
                await player.stop()
                await ctx.send("⏭️ Трек пропущен. Очередь пуста")
                logger.info(f'{ctx.author} пропустил трек')
            
        except Exception as e:
            await ctx.send(f"❌ Ошибка при пропуске: {e}", ephemeral=True)
            logger.error(f'Ошибка skip: {e}')
    
    @bot.hybrid_command(name="stop", description="Остановить воспроизведение")
    async def stop_cmd(ctx: commands.Context):
        """Остановка музыки"""
        try:
            player: wavelink.Player = ctx.voice_client
            if not player:
                await ctx.send("❌ Бот не в голосовом канале", ephemeral=True)
                return
                
            music_player.clear_queue(ctx.guild.id)
            await player.stop()
            await ctx.send("⏹️ Воспроизведение остановлено")
            logger.info(f'{ctx.author} остановил музыку')
            
        except Exception as e:
            await ctx.send(f"❌ Ошибка при остановке: {e}", ephemeral=True)
            logger.error(f'Ошибка stop: {e}')
    
    @bot.hybrid_command(name="queue", description="Показать очередь треков")
    async def queue_cmd(ctx: commands.Context):
        """Очередь треков"""
        try:
            queue = music_player.get_queue(ctx.guild.id)
            if not queue:
                await ctx.send("📭 Очередь пуста")
                return
                
            embed = discord.Embed(
                title="📋 Очередь треков",
                color=discord.Color.purple(),
                timestamp=datetime.now()
            )
            
            for i, track in enumerate(queue[:10], 1):
                track_title = getattr(track, 'title', 'Неизвестный трек')[:50]
                track_author = getattr(track, 'author', 'Неизвестно')
                track_duration = f"{getattr(track, 'length', 0) // 60000}:{str(getattr(track, 'length', 0) % 60000).zfill(2)}"
                
                embed.add_field(
                    name=f"{i}. {track_title}",
                    value=f"Автор: {track_author} | Длительность: {track_duration}",
                    inline=False
                )
                
            if len(queue) > 10:
                embed.set_footer(text=f"И ещё {len(queue)-10} треков...")
                
            await ctx.send(embed=embed)
            logger.info(f'{ctx.author} посмотрел очередь: {len(queue)} треков')
            
        except Exception as e:
            await ctx.send(f"❌ Ошибка при показе очереди: {e}", ephemeral=True)
            logger.error(f'Ошибка queue: {e}')
    
    @bot.hybrid_command(name="nowplaying", description="Информация о текущем треке")
    async def nowplaying_cmd(ctx: commands.Context):
        """Текущий трек"""
        try:
            player: wavelink.Player = ctx.voice_client
            if not player or not player.current:
                await ctx.send("❌ Сейчас ничего не играет", ephemeral=True)
                return
                
            track = player.current
            
            embed = discord.Embed(
                title="🎵 Сейчас играет",
                description=f"**{getattr(track, 'title', 'Неизвестный трек')}**",
                color=discord.Color.blue(),
                timestamp=datetime.now()
            )
            
            embed.add_field(name="Автор", value=getattr(track, 'author', 'Неизвестно'), inline=True)
            embed.add_field(name="Длительность", value=f"{getattr(track, 'length', 0) // 60000}:{str(getattr(track, 'length', 0) % 60000).zfill(2)}", inline=True)
            
            if hasattr(track, 'uri') and track.uri:
                embed.add_field(name="Ссылка", value=f"[Открыть]({track.uri})", inline=True)
            
            if hasattr(track, 'artwork') and track.artwork:
                embed.set_thumbnail(url=track.artwork)
            
            if player.paused:
                embed.set_footer(text="⏸️ На паузе")
                
            await ctx.send(embed=embed)
            logger.info(f'{ctx.author} посмотрел текущий трек')
            
        except Exception as e:
            await ctx.send(f"❌ Ошибка: {e}", ephemeral=True)
            logger.error(f'Ошибка nowplaying: {e}')
    
    @bot.hybrid_command(name="volume", description="Установить громкость (0-100)")
    @app_commands.describe(level="Уровень громкости (0-100)")
    async def volume_cmd(ctx: commands.Context, level: int):
        """Настройка громкости"""
        try:
            if level < 0 or level > 100:
                await ctx.send("❌ Громкость должна быть от 0 до 100", ephemeral=True)
                return
                
            player: wavelink.Player = ctx.voice_client
            if not player:
                await ctx.send("❌ Бот не в голосовом канале", ephemeral=True)
                return
                
            await player.set_volume(level)
            await ctx.send(f"🔊 Громкость установлена на **{level}%**")
            logger.info(f'{ctx.author} установил громкость: {level}%')
            
        except Exception as e:
            await ctx.send(f"❌ Ошибка при настройке громкости: {e}", ephemeral=True)
            logger.error(f'Ошибка volume: {e}')
    
    @bot.hybrid_command(name="loop", description="Повтор текущего трека")
    async def loop_cmd(ctx: commands.Context):
        """Повтор трека"""
        try:
            is_looping = music_player.toggle_loop(ctx.guild.id)
            status = "включен" if is_looping else "выключен"
            await ctx.send(f"🔁 Повтор трека **{status}**")
            logger.info(f'{ctx.author} {status} повтор трека')
            
        except Exception as e:
            await ctx.send(f"❌ Ошибка: {e}", ephemeral=True)
            logger.error(f'Ошибка loop: {e}')
    
    @bot.hybrid_command(name="loopqueue", description="Повтор всей очереди")
    async def loopqueue_cmd(ctx: commands.Context):
        """Повтор очереди"""
        try:
            is_looping = music_player.toggle_loop_queue(ctx.guild.id)
            status = "включен" if is_looping else "выключен"
            await ctx.send(f"🔂 Повтор очереди **{status}**")
            logger.info(f'{ctx.author} {status} повтор очереди')
            
        except Exception as e:
            await ctx.send(f"❌ Ошибка: {e}", ephemeral=True)
            logger.error(f'Ошибка loopqueue: {e}')
    
    @bot.hybrid_command(name="shuffle", description="Перемешать очередь")
    async def shuffle_cmd(ctx: commands.Context):
        """Перемешивание очереди"""
        try:
            music_player.shuffle_queue(ctx.guild.id)
            await ctx.send("🔀 Очередь перемешана")
            logger.info(f'{ctx.author} перемешал очередь')
            
        except Exception as e:
            await ctx.send(f"❌ Ошибка при перемешивании: {e}", ephemeral=True)
            logger.error(f'Ошибка shuffle: {e}')
    
    @bot.hybrid_command(name="leave", description="Отключиться от голосового канала")
    async def leave_cmd(ctx: commands.Context):
        """Выход из голосового канала"""
        try:
            player: wavelink.Player = ctx.voice_client
            if not player:
                await ctx.send("❌ Бот не в голосовом канале", ephemeral=True)
                return
                
            music_player.clear_queue(ctx.guild.id)
            await player.disconnect()
            await ctx.send("👋 Отключился от голосового канала")
            logger.info(f'{ctx.author} отключил бота от голосового канала')
            
        except Exception as e:
            await ctx.send(f"❌ Ошибка при отключении: {e}", ephemeral=True)
            logger.error(f'Ошибка leave: {e}')
    
    # События wavelink
    @bot.event
    async def on_wavelink_track_end(payload: wavelink.TrackEventPayload):
        """Событие окончания трека"""
        try:
            player = payload.player
            if not player:
                return
            
            guild_id = player.guild.id
            
            # Проверяем режим повтора трека
            if music_player.get_loop_mode(guild_id) and payload.track:
                await player.play(payload.track)
                return
            
            # Проверяем режим повтора очереди
            queue = music_player.get_queue(guild_id)
            if music_player.get_loop_mode(guild_id) and queue and payload.track:
                music_player.add_to_queue(guild_id, payload.track)
            
            # Берем следующий трек из очереди
            if queue:
                next_track = queue.pop(0)
                await player.play(next_track)
                
        except Exception as e:
            logger.error(f'Ошибка в on_wavelink_track_end: {e}')
    
    logger.info("✅ Модуль музыки загружен (исправленная версия)")