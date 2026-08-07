"""
Модуль музыки через yt-dlp + FFmpeg (без Lavalink)
Команды: play, pause, resume, skip, stop, queue, nowplaying, volume (0-1000),
loop, loopqueue, shuffle, bassboost (0-20 дБ), panel, leave, join
Панель управления музыкой с кнопками: !panel
"""

import asyncio
import audioop
import logging
import os
import random
import re
import shutil
import time
from datetime import datetime
from pathlib import Path

import discord
import yt_dlp
from discord import app_commands
from discord.ext import commands, tasks

logger = logging.getLogger('discord_bot.music')

# Опции FFmpeg для стриминга
FFMPEG_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn',
}


def _find_ffmpeg():
    """Найти исполняемый файл FFmpeg"""
    exe = shutil.which('ffmpeg')
    if exe:
        return exe
    local = Path(os.environ.get('LOCALAPPDATA', '')) / 'Microsoft' / 'WinGet' / 'Packages'
    if local.exists():
        try:
            for p in local.rglob('ffmpeg.exe'):
                return str(p)
        except OSError:
            pass
    return 'ffmpeg'


FFMPEG_EXE = _find_ffmpeg()

# Уровень баса по умолчанию для кнопки/переключателя (очень сильный)
STRONG_BASS = 35


def _ffmpeg_options(bass_db=0):
    """Опции FFmpeg с учётом bass boost (бас-фильтр в дБ).
    При уровне >= 25 дБ дополнительно усиливается суб-бас (60 Гц) для более мощного звука.
    """
    if bass_db and bass_db > 0:
        opts = f'-vn -af bass=g={bass_db}'
        if bass_db >= 25:
            sub = min(25, bass_db // 2)
            opts += f',equalizer=f=60:t=q:w=1.0:g={sub}'
        return {
            'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
            'options': opts,
        }
    return FFMPEG_OPTIONS


class BoostVolumeTransformer(discord.PCMVolumeTransformer):
    """PCMVolumeTransformer без ограничения громкости в 200% (для volume до 1000%)"""

    def read(self) -> bytes:
        ret = self.original.read()
        return audioop.mul(ret, 2, self._volume)


class MusicPlayer:
    """Класс для управления музыкой"""

    def __init__(self, bot):
        self.bot = bot
        self.queues = {}
        self.current = {}
        self.loops = {}
        self.loop_queues = {}
        self.volumes = {}
        self.volume_transformers = {}
        self.bass_levels = {}
        self.panel_messages = {}
        self.restarting = {}
        self.track_started_at = {}
        self.paused_position = {}

    def start_tracking(self, guild_id):
        """Зафиксировать старт трека (для полосы прогресса)"""
        self.track_started_at[guild_id] = time.monotonic()
        self.paused_position.pop(guild_id, None)

    def pause_tracking(self, guild_id):
        """Запомнить позицию при паузе"""
        if guild_id in self.track_started_at:
            self.paused_position[guild_id] = time.monotonic() - self.track_started_at[guild_id]
            self.track_started_at.pop(guild_id, None)

    def resume_tracking(self, guild_id):
        """Продолжить отсчёт после возобновления"""
        if guild_id in self.paused_position:
            self.track_started_at[guild_id] = time.monotonic() - self.paused_position.pop(guild_id)

    def get_position(self, guild_id, vc=None):
        """Текущая позиция трека в секундах"""
        if guild_id in self.paused_position:
            return self.paused_position[guild_id]
        if guild_id in self.track_started_at:
            return time.monotonic() - self.track_started_at[guild_id]
        return 0

    def get_queue(self, guild_id):
        if guild_id not in self.queues:
            self.queues[guild_id] = []
        return self.queues[guild_id]

    def add_to_queue(self, guild_id, track):
        queue = self.get_queue(guild_id)
        queue.append(track)
        return len(queue)

    def clear_queue(self, guild_id):
        if guild_id in self.queues:
            self.queues[guild_id] = []
        self.current[guild_id] = None

    def shuffle_queue(self, guild_id):
        queue = self.get_queue(guild_id)
        if len(queue) > 1:
            random.shuffle(queue)

    def get_loop_mode(self, guild_id):
        return self.loops.get(guild_id, False)

    def toggle_loop(self, guild_id):
        self.loops[guild_id] = not self.loops.get(guild_id, False)
        return self.loops[guild_id]

    def toggle_loop_queue(self, guild_id):
        self.loop_queues[guild_id] = not self.loop_queues.get(guild_id, False)
        return self.loop_queues[guild_id]

    def get_volume(self, guild_id):
        return self.volumes.get(guild_id, 1.0)

    def set_volume(self, guild_id, level):
        volume = max(0.05, min(10.0, level / 100))
        self.volumes[guild_id] = volume
        transformer = self.volume_transformers.get(guild_id)
        if transformer:
            transformer.volume = volume
        return volume

    def get_bass(self, guild_id):
        return self.bass_levels.get(guild_id, 0)

    def set_bass(self, guild_id, level):
        self.bass_levels[guild_id] = level
        return level

    def toggle_bass(self, guild_id):
        current = self.get_bass(guild_id)
        new = STRONG_BASS if current == 0 else 0
        self.bass_levels[guild_id] = new
        return new


def format_duration(seconds) -> str:
    """Форматирование длительности трека (секунды -> ЧЧ:ММ:СС)"""
    total = max(0, int(seconds))
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


async def search_tracks(query: str, source: str = 'youtube', limit: int = 5):
    """Поиск нескольких похожих треков через yt-dlp

    source: youtube | soundcloud | yandex
    Возвращает список словарей треков (макс limit штук)
    """
    if not re.match(r'https?://', query):
        prefixes = {
            'youtube': 'ytsearch',
            'soundcloud': 'scsearch',
            'yandex': 'ymsearch',
        }
        prefix = prefixes.get(source, 'ytsearch')
        query = f'{prefix}{limit}:{query}'

    ydl_opts = {
        'format': 'bestaudio/best',
        'noplaylist': True,
        'quiet': True,
        'no_warnings': True,
        'extract_flat': 'in_playlist',
    }

    def _extract():
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            try:
                info = ydl.extract_info(query, download=False)
            except Exception as e:
                logger.error(f'Ошибка извлечения ({source}): {e}')
                return None
            return info

    try:
        info = await asyncio.to_thread(_extract)
    except Exception as e:
        logger.error(f'Ошибка поиска yt-dlp ({source}): {e}')
        return []
    if not info:
        return []

    entries = []
    if info:
        if 'entries' in info:
            entries = [e for e in info['entries'] if e]
        else:
            entries = [info]

    tracks = []
    for e in entries[:limit]:
        if not e or not e.get('url'):
            continue
        tracks.append({
            'title': e.get('title') or 'Неизвестно',
            'url': e.get('url'),
            'webpage_url': e.get('webpage_url') or e.get('original_url') or e.get('url'),
            'duration': e.get('duration') or 0,
            'thumbnail': e.get('thumbnail'),
            'channel': e.get('channel') or e.get('uploader') or 'Неизвестно',
        })
    return tracks


async def search_track(query: str, source: str = 'youtube'):
    """Поиск трека через yt-dlp, возвращает словарь с данными

    source: youtube | soundcloud | yandex
    """
    if not re.match(r'https?://', query):
        prefixes = {
            'youtube': 'ytsearch:',
            'soundcloud': 'scsearch:',
            'yandex': 'ymsearch:',
        }
        query = prefixes.get(source, 'ytsearch:') + query

    ydl_opts = {
        'format': 'bestaudio/best',
        'noplaylist': True,
        'quiet': True,
        'no_warnings': True,
    }

    def _extract():
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(query, download=False)
            if info and 'entries' in info:
                info = info['entries'][0]
            return info

    try:
        info = await asyncio.to_thread(_extract)
    except Exception as e:
        logger.error(f'Ошибка поиска yt-dlp: {e}')
        return None

    if not info or not info.get('url'):
        return None

    return {
        'title': info.get('title') or 'Неизвестно',
        'url': info.get('url'),
        'webpage_url': info.get('webpage_url') or info.get('original_url') or info.get('url'),
        'duration': info.get('duration') or 0,
        'thumbnail': info.get('thumbnail'),
        'channel': info.get('channel') or info.get('uploader') or 'Неизвестно',
    }


async def search_playlist(query: str):
    """Поиск плейлиста через yt-dlp, возвращает список треков и название"""
    ydl_opts = {
        'format': 'bestaudio/best',
        'quiet': True,
        'no_warnings': True,
        'extract_flat': True,
    }

    def _extract():
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(query, download=False)
            return info

    try:
        info = await asyncio.to_thread(_extract)
    except Exception as e:
        logger.error(f'Ошибка поиска плейлиста yt-dlp: {e}')
        return None, []

    if not info:
        return None, []

    if 'entries' not in info or not info['entries']:
        return None, []

    title = info.get('title') or 'Плейлист'
    tracks = []
    for entry in info['entries']:
        if not entry:
            continue
        if entry.get('_type') == 'playlist' and 'entries' in entry:
            for sub in entry['entries']:
                if sub and sub.get('id'):
                    tracks.append(sub)
        elif entry.get('id'):
            tracks.append(entry)

    return title, tracks


def _playlist_item_to_track(entry):
    """Преобразовать элемент (flat) в полный трек"""
    if not entry:
        return None
    vid = entry.get('id')
    if not vid:
        return None
    return search_track(f'https://www.youtube.com/watch?v={vid}')


def _extract_video_id(url):
    """Извлечение ID видео YouTube из ссылки"""
    if not url:
        return None
    m = re.search(r'(?:v=|/watch\?v=|youtu\.be/|shorts/)([\w-]{11})', url)
    return m.group(1) if m else None


async def search_similar_tracks(track, limit=5):
    """Поиск похожих треков через YouTube radio (mix)"""
    video_id = _extract_video_id(track.get('webpage_url'))
    if not video_id:
        return []
    mix_url = f'https://www.youtube.com/watch?v={video_id}&list=RD{video_id}'

    def _extract():
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': True,
            'playlist_items': '1-15',
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(mix_url, download=False)
            if info and 'entries' in info:
                return [e for e in info['entries'] if e and e.get('id')]
            return []

    try:
        entries = await asyncio.to_thread(_extract)
    except Exception as e:
        logger.error(f'Ошибка поиска похожих (radio): {e}')
        return []

    # Полное извлечение первых треков для получения потоковых URL
    similar = []
    for entry in entries:
        if len(similar) >= limit:
            break
        vid = entry.get('id')
        if not vid:
            continue
        tr = await search_track(f'https://www.youtube.com/watch?v={vid}')
        if tr:
            similar.append(tr)
    return similar


def setup_music(bot):
    """Настройка команд музыки"""

    music_player = MusicPlayer(bot)

    async def play_track(guild_id, vc, track, channel=None):
        """Воспроизвести трек и запланировать следующий"""
        music_player.current[guild_id] = track
        music_player.start_tracking(guild_id)
        volume = music_player.get_volume(guild_id)
        bass = music_player.get_bass(guild_id)

        source = BoostVolumeTransformer(
            discord.FFmpegPCMAudio(track['url'], executable=FFMPEG_EXE, **_ffmpeg_options(bass)),
            volume=volume,
        )
        music_player.volume_transformers[guild_id] = source

        def after(error):
            if error:
                logger.error(f'Ошибка воспроизведения: {error}')
            asyncio.run_coroutine_threadsafe(_advance(guild_id), bot.loop)

        vc.play(source, after=after)
        await ensure_panel(guild_id, channel)
        await update_panel(guild_id)

    async def _advance(guild_id):
        """Воспроизвести следующий трек из очереди"""
        guild = bot.get_guild(guild_id)
        if not guild:
            return
        vc = guild.voice_client
        if not vc:
            return
        if vc.is_playing() or vc.is_paused():
            return
        if music_player.restarting.get(guild_id):
            return

        queue = music_player.get_queue(guild_id)
        loop_song = music_player.get_loop_mode(guild_id)
        loop_queue = music_player.loop_queues.get(guild_id, False)
        current = music_player.current.get(guild_id)

        if loop_song and current:
            await play_track(guild_id, vc, current)
            return

        if queue:
            nxt = queue.pop(0)
            if loop_queue and current:
                queue.append(current)
            await play_track(guild_id, vc, nxt)
        else:
            music_player.current[guild_id] = None

    async def now_playing_embed(track):
        embed = discord.Embed(
            title="🎶 Сейчас играет",
            description=f"**{track['title']}**",
            color=discord.Color.blue(),
            timestamp=datetime.now(),
        )
        embed.add_field(name="Автор", value=track['channel'], inline=True)
        embed.add_field(name="Длительность", value=format_duration(track['duration']), inline=True)
        if track.get('webpage_url'):
            embed.add_field(name="Ссылка", value=f"[Открыть]({track['webpage_url']})", inline=True)
        if track.get('thumbnail'):
            embed.set_thumbnail(url=track['thumbnail'])
        return embed

    def _progress_line(position, duration, size=20):
        """Полоса прогресса: ▬▬▬🔘▬▬▬ + время осталось"""
        if not duration or duration <= 0:
            return None
        pos = max(0, min(int(position), int(duration)))
        ratio = pos / duration
        filled = int(ratio * size)
        bar = '▬' * filled + '🔘' + '▬' * (size - filled)
        return f"{format_duration(pos)} {bar} {format_duration(duration)}"

    def get_panel_embed(guild_id):
        """Сборка embed для музыкальной панели"""
        track = music_player.current.get(guild_id)
        volume = music_player.get_volume(guild_id)
        bass = music_player.get_bass(guild_id)
        loop = music_player.get_loop_mode(guild_id)
        loopq = music_player.loop_queues.get(guild_id, False)
        queue = music_player.get_queue(guild_id)

        guild = bot.get_guild(guild_id)
        vc = guild.voice_client if guild else None
        position = music_player.get_position(guild_id, vc)

        embed = discord.Embed(
            title="🎛️ Музыкальная панель",
            color=discord.Color.blurple(),
            timestamp=datetime.now(),
        )
        if track:
            value = f"**{track['title']}**\n{track['channel']} | {format_duration(track['duration'])}"
            line = _progress_line(position, track.get('duration') or 0)
            if line:
                value += f"\n{line}"
            embed.add_field(
                name="🎶 Сейчас играет",
                value=value,
                inline=False,
            )
            if track.get('thumbnail'):
                embed.set_thumbnail(url=track['thumbnail'])
        else:
            embed.add_field(name="🎶 Сейчас играет", value="Ничего", inline=False)

        if queue:
            lines = []
            for i, t in enumerate(queue[:5], 1):
                lines.append(f"`{i}.` **{t['title'][:45]}** ({format_duration(t['duration'])})")
            if len(queue) > 5:
                lines.append(f"... и ещё {len(queue) - 5} треков")
            embed.add_field(name=f"📋 В очереди ({len(queue)})", value="\n".join(lines), inline=False)
        else:
            embed.add_field(name="📋 Очередь", value="Пусто", inline=True)

        embed.add_field(name="🔊 Громкость", value=f"**{int(volume * 100)}%**", inline=True)
        embed.add_field(name="🎚️ Басс", value=f"**{bass} дБ**" if bass else "Выкл", inline=True)
        embed.add_field(name="🔁 Повтор", value="Вкл" if loop else "Выкл", inline=True)
        embed.add_field(name="🔂 Повтор очереди", value="Вкл" if loopq else "Выкл", inline=True)
        return embed

    async def update_panel(guild_id):
        """Обновить embed сообщения панели"""
        msg = music_player.panel_messages.get(guild_id)
        if not msg:
            return
        try:
            await msg.edit(embed=get_panel_embed(guild_id))
        except discord.NotFound:
            music_player.panel_messages.pop(guild_id, None)
        except Exception as e:
            logger.error(f'Ошибка обновления панели: {e}')

    @tasks.loop(seconds=5)
    async def panel_autoupdate():
        """Автообновление панелей, чтобы двигался ползунок"""
        for guild_id, msg in list(music_player.panel_messages.items()):
            vc = msg.guild.voice_client if msg.guild else None
            if vc and (vc.is_playing() or vc.is_paused()):
                await update_panel(guild_id)

    bot.panel_autoupdate = panel_autoupdate

    async def ensure_panel(guild_id, channel=None, force=False):
        """Отправить панель в текстовый канал"""
        if not force and music_player.panel_messages.get(guild_id):
            return
        if channel is None:
            guild = bot.get_guild(guild_id)
            vc = guild.voice_client if guild else None
            channel = vc.channel if vc else None
        if channel is None:
            return
        try:
            old = music_player.panel_messages.get(guild_id)
            if old:
                try:
                    await old.delete()
                except Exception:
                    pass
            embed = get_panel_embed(guild_id)
            view = MusicPanel()
            msg = await channel.send(embed=embed, view=view)
            music_player.panel_messages[guild_id] = msg
            logger.info(f'Панель отправлена в канал {channel.name}')
        except Exception as e:
            logger.error(f'Ошибка автоотправки панели: {e}')

    bot.ensure_music_panel = ensure_panel

    async def restart_track(guild_id):
        """Перезапустить текущий трек (для применения bass boost)"""
        guild = bot.get_guild(guild_id)
        if not guild:
            return
        vc = guild.voice_client
        track = music_player.current.get(guild_id)
        if not vc or not track or not (vc.is_playing() or vc.is_paused()):
            return
        music_player.restarting[guild_id] = True
        try:
            vc.stop()
            await asyncio.sleep(0.2)
            await play_track(guild_id, vc, track)
        finally:
            music_player.restarting.pop(guild_id, None)

    class AddTrackModal(discord.ui.Modal, title="Добавить трек в очередь"):
        """Модальное окно для добавления трека по названию или ссылке"""

        query = discord.ui.TextInput(
            label="Название песни или ссылка",
            placeholder="Например: Never Gonna Give You Up",
            max_length=200,
        )

        def __init__(self, guild_id, vc):
            super().__init__()
            self.guild_id = guild_id
            self.vc = vc

        async def on_submit(self, interaction):
            await interaction.response.defer(ephemeral=True)
            track = await search_track(self.query.value)
            if not track:
                await interaction.followup.send("❌ Трек не найден", ephemeral=True)
                return
            vc = self.vc
            if vc and (vc.is_playing() or vc.is_paused()):
                pos = music_player.add_to_queue(self.guild_id, track)
                await interaction.followup.send(
                    f"🎵 Добавлен в очередь (#{pos}): **{track['title']}**", ephemeral=True
                )
            else:
                await play_track(self.guild_id, vc, track, interaction.channel)
                await interaction.followup.send(f"▶️ Играет: **{track['title']}**", ephemeral=True)
            await update_panel(self.guild_id)

    class MusicPanel(discord.ui.View):
        """Расширенная панель управления музыкой"""

        def __init__(self):
            super().__init__(timeout=None)

        async def interaction_check(self, interaction):
            vc = interaction.guild.voice_client if interaction.guild else None
            if not vc:
                await interaction.response.send_message("❌ Бот не в голосовом канале", ephemeral=True)
                return False
            return True

        # ---- Строка 1: транспорт ----
        @discord.ui.button(label="⏯️", style=discord.ButtonStyle.primary, custom_id="mp_toggle", row=0)
        async def btn_toggle(self, interaction, button):
            vc = interaction.guild.voice_client
            if vc.is_playing():
                vc.pause()
                music_player.pause_tracking(interaction.guild_id)
                await interaction.response.send_message("⏸️ Пауза", ephemeral=True)
            elif vc.is_paused():
                vc.resume()
                music_player.resume_tracking(interaction.guild_id)
                await interaction.response.send_message("▶️ Продолжаю", ephemeral=True)
            else:
                await interaction.response.send_message("❌ Ничего не играет", ephemeral=True)
            await update_panel(interaction.guild_id)

        @discord.ui.button(label="⏭️", style=discord.ButtonStyle.secondary, custom_id="mp_skip", row=0)
        async def btn_skip(self, interaction, button):
            vc = interaction.guild.voice_client
            if vc.is_playing() or vc.is_paused():
                vc.stop()
                music_player.track_started_at.pop(interaction.guild_id, None)
                music_player.paused_position.pop(interaction.guild_id, None)
                await interaction.response.send_message("⏭️ Пропуск", ephemeral=True)
            else:
                await interaction.response.send_message("❌ Ничего не играет", ephemeral=True)
            await update_panel(interaction.guild_id)

        @discord.ui.button(label="⏹️", style=discord.ButtonStyle.danger, custom_id="mp_stop", row=0)
        async def btn_stop(self, interaction, button):
            vc = interaction.guild.voice_client
            music_player.clear_queue(interaction.guild_id)
            vc.stop()
            await interaction.response.send_message("⏹️ Остановлено", ephemeral=True)
            await update_panel(interaction.guild_id)

        @discord.ui.button(label="🔀", style=discord.ButtonStyle.secondary, custom_id="mp_shuffle", row=0)
        async def btn_shuffle(self, interaction, button):
            music_player.shuffle_queue(interaction.guild_id)
            await interaction.response.send_message("🔀 Очередь перемешана", ephemeral=True)
            await update_panel(interaction.guild_id)

        @discord.ui.button(label="👋", style=discord.ButtonStyle.danger, custom_id="mp_leave", row=0)
        async def btn_leave(self, interaction, button):
            vc = interaction.guild.voice_client
            music_player.clear_queue(interaction.guild_id)
            vc.stop()
            await vc.disconnect()
            await interaction.response.send_message("👋 Отключился", ephemeral=True)
            await update_panel(interaction.guild_id)

        # ---- Строка 2: очередь/повторы ----
        @discord.ui.button(label="➕", style=discord.ButtonStyle.success, custom_id="mp_add", row=1)
        async def btn_add(self, interaction, button):
            await interaction.response.send_modal(
                AddTrackModal(interaction.guild_id, interaction.guild.voice_client)
            )

        @discord.ui.button(label="📜", style=discord.ButtonStyle.secondary, custom_id="mp_queue", row=1)
        async def btn_queue(self, interaction, button):
            queue = music_player.get_queue(interaction.guild_id)
            current = music_player.current.get(interaction.guild_id)
            if not queue and not current:
                await interaction.response.send_message("📭 Очередь пуста", ephemeral=True)
                return
            embed = discord.Embed(title="📋 Очередь треков", color=discord.Color.purple(), timestamp=datetime.now())
            lines = []
            if current:
                lines.append(f"**Сейчас:** {current['title']} ({format_duration(current['duration'])})")
            for i, t in enumerate(queue[:10], 1):
                lines.append(f"`{i}.` **{t['title'][:50]}** — {format_duration(t['duration'])}")
            if len(queue) > 10:
                lines.append(f"... и ещё {len(queue) - 10} треков")
            embed.description = "\n".join(lines)
            await interaction.response.send_message(embed=embed, ephemeral=True)

        @discord.ui.button(label="🧹", style=discord.ButtonStyle.secondary, custom_id="mp_clear", row=1)
        async def btn_clear(self, interaction, button):
            music_player.get_queue(interaction.guild_id).clear()
            await interaction.response.send_message("🧹 Очередь очищена", ephemeral=True)
            await update_panel(interaction.guild_id)

        @discord.ui.button(label="🔁", style=discord.ButtonStyle.secondary, custom_id="mp_loop", row=1)
        async def btn_loop(self, interaction, button):
            is_looping = music_player.toggle_loop(interaction.guild_id)
            status = "включен" if is_looping else "выключен"
            await interaction.response.send_message(f"🔁 Повтор трека **{status}**", ephemeral=True)
            await update_panel(interaction.guild_id)

        @discord.ui.button(label="🔂", style=discord.ButtonStyle.secondary, custom_id="mp_loopq", row=1)
        async def btn_loopq(self, interaction, button):
            is_looping = music_player.toggle_loop_queue(interaction.guild_id)
            status = "включен" if is_looping else "выключен"
            await interaction.response.send_message(f"🔂 Повтор очереди **{status}**", ephemeral=True)
            await update_panel(interaction.guild_id)

        # ---- Строка 3: выбор громкости ----
        @discord.ui.select(
            placeholder="🔊 Громкость",
            min_values=1,
            max_values=1,
            row=2,
            custom_id="mp_vol_sel",
            options=[
                discord.SelectOption(label="25%", value="25"),
                discord.SelectOption(label="50%", value="50"),
                discord.SelectOption(label="75%", value="75"),
                discord.SelectOption(label="100%", value="100"),
                discord.SelectOption(label="150%", value="150"),
                discord.SelectOption(label="200%", value="200"),
                discord.SelectOption(label="300%", value="300"),
                discord.SelectOption(label="500%", value="500"),
                discord.SelectOption(label="750%", value="750"),
                discord.SelectOption(label="1000%", value="1000"),
            ],
        )
        async def vol_select(self, interaction, select):
            level = int(select.values[0])
            music_player.set_volume(interaction.guild_id, level)
            await interaction.response.send_message(f"🔊 Громкость: **{level}%**", ephemeral=True)
            await update_panel(interaction.guild_id)

        # ---- Строка 4: выбор баса ----
        @discord.ui.select(
            placeholder="🎚️ Басс",
            min_values=1,
            max_values=1,
            row=3,
            custom_id="mp_bass_sel",
            options=[
                discord.SelectOption(label="Выкл", value="0"),
                discord.SelectOption(label="Лёгкий (10 дБ)", value="10"),
                discord.SelectOption(label="Средний (20 дБ)", value="20"),
                discord.SelectOption(label="Сильный (35 дБ)", value="35"),
                discord.SelectOption(label="Экстремальный (50 дБ)", value="50"),
            ],
        )
        async def bass_select(self, interaction, select):
            level = int(select.values[0])
            music_player.set_bass(interaction.guild_id, level)
            if level > 0:
                await restart_track(interaction.guild_id)
            await interaction.response.send_message(
                f"🎚️ Басс: **{level} дБ**" if level else "🎚️ Басс выключен",
                ephemeral=True,
            )
            await update_panel(interaction.guild_id)

        # ---- Строка 5: тонкая подстройка громкости ----
        @discord.ui.button(label="🔊−", style=discord.ButtonStyle.secondary, custom_id="mp_vol_down", row=4)
        async def btn_vol_down(self, interaction, button):
            current = music_player.get_volume(interaction.guild_id)
            new_level = max(5, int((current - 0.1) * 100))
            music_player.set_volume(interaction.guild_id, new_level)
            await interaction.response.send_message(f"🔊 Громкость: **{new_level}%**", ephemeral=True)
            await update_panel(interaction.guild_id)

        @discord.ui.button(label="🔊+", style=discord.ButtonStyle.secondary, custom_id="mp_vol_up", row=4)
        async def btn_vol_up(self, interaction, button):
            current = music_player.get_volume(interaction.guild_id)
            new_level = min(1000, int((current + 0.1) * 100))
            music_player.set_volume(interaction.guild_id, new_level)
            await interaction.response.send_message(f"🔊 Громкость: **{new_level}%**", ephemeral=True)
            await update_panel(interaction.guild_id)

        # ---- Строка 5: похожая музыка ----
        @discord.ui.button(label="🎶 Похожая музыка", style=discord.ButtonStyle.success, custom_id="mp_similar", row=4)
        async def btn_similar(self, interaction, button):
            vc = interaction.guild.voice_client
            track = music_player.current.get(interaction.guild_id)
            if not vc or not track:
                await interaction.response.send_message("❌ Сейчас ничего не играет", ephemeral=True)
                return
            await interaction.response.defer(ephemeral=True)
            similar = await search_similar_tracks(track, limit=6)
            if not similar:
                await interaction.followup.send("❌ Не удалось найти похожие треки", ephemeral=True)
                return
            view = SimilarMusicSelect(interaction.guild_id, vc, similar)
            embed = discord.Embed(
                title="🎶 Похожая музыка",
                description=f"На основе: **{track['title']}**\nВыбери трек, чтобы добавить его в очередь:",
                color=discord.Color.green(),
                timestamp=datetime.now(),
            )
            await interaction.followup.send(embed=embed, view=view, ephemeral=True)
            await update_panel(interaction.guild_id)

    class SimilarMusicSelect(discord.ui.View):
        """Выбор похожего трека из списка"""

        def __init__(self, guild_id, vc, tracks):
            super().__init__(timeout=120)
            self.guild_id = guild_id
            self.vc = vc
            self.tracks = tracks
            options = []
            for i, t in enumerate(tracks):
                label = t['title'][:90]
                options.append(discord.SelectOption(label=label, value=str(i)))
            select = discord.ui.Select(
                placeholder="🎵 Выбери похожий трек...",
                min_values=1,
                max_values=1,
                options=options,
            )
            select.callback = self._on_select
            self.add_item(select)

        async def _on_select(self, interaction):
            idx = int(interaction.data['values'][0])
            track = self.tracks[idx]
            if self.vc and (self.vc.is_playing() or self.vc.is_paused()):
                pos = music_player.add_to_queue(self.guild_id, track)
                await interaction.response.send_message(
                    f"🎵 Добавлен в очередь (#{pos}): **{track['title']}**", ephemeral=True
                )
            else:
                await play_track(self.guild_id, self.vc, track)
                await interaction.response.send_message(
                    f"▶️ Играет: **{track['title']}**", ephemeral=True
                )
            await update_panel(self.guild_id)

    class AutoSearchView(discord.ui.View):
        """Список найденных треков из всех источников"""

        SOURCES = {
            'youtube': '🔴 YouTube',
            'soundcloud': '🎧 SoundCloud',
            'yandex': '🎶 Яндекс',
        }

        def __init__(self, tracks):
            super().__init__(timeout=120)
            self.tracks = tracks
            options = []
            for i, (source, track) in enumerate(tracks):
                title = track['title'][:60]
                channel = (track.get('channel') or '')[:30]
                label = f"{self.SOURCES.get(source, source)} | {title}"
                desc = channel if channel else None
                options.append(discord.SelectOption(label=label, value=str(i), description=desc))
            select = discord.ui.Select(
                placeholder="🎵 Выбери трек...",
                min_values=1,
                max_values=1,
                options=options,
            )
            select.callback = self._on_select
            self.add_item(select)
            self.add_item(discord.ui.Button(label="❌ Закрыть", style=discord.ButtonStyle.secondary, custom_id="auto_cancel"))

        async def _on_select(self, interaction):
            try:
                await interaction.response.defer(ephemeral=True)
                idx = int(interaction.data['values'][0])
                source, track = self.tracks[idx]

                if not interaction.user.voice:
                    await interaction.followup.send("❌ Вы должны быть в голосовом канале", ephemeral=True)
                    return

                vc = interaction.guild.voice_client
                if not vc:
                    try:
                        vc = await interaction.user.voice.channel.connect()
                    except Exception as e:
                        await interaction.followup.send(f"❌ Не удалось подключиться: {e}", ephemeral=True)
                        return

                # Полное извлечение трека по ссылке (нужен рабочий потоковый URL)
                if track.get('webpage_url'):
                    full = await search_track(track['webpage_url'], source)
                    if full:
                        track = full
                    else:
                        # Трек недоступен (DRM) — пробуем найти то же на YouTube
                        await interaction.followup.send(
                            f"⚠️ **{track['title']}** недоступен ({self.SOURCES.get(source, source)}). "
                            f"Ищу на YouTube...",
                            ephemeral=True,
                        )
                        yt = await search_track(track['title'], 'youtube')
                        if not yt:
                            await interaction.followup.send(
                                f"❌ Не удалось найти аналог на YouTube. Попробуй другой трек.",
                                ephemeral=True,
                            )
                            return
                        track = yt
                        source = 'youtube'
                        await interaction.followup.send(
                            f"▶️ Найден аналог на YouTube: **{track['title']}**",
                            ephemeral=True,
                        )

                if vc.is_playing() or vc.is_paused():
                    position = music_player.add_to_queue(interaction.guild_id, track)
                    await interaction.followup.send(
                        f"🎵 Добавлен в очередь (#{position}): **{track['title']}** ({self.SOURCES.get(source, source)})",
                        ephemeral=True,
                    )
                else:
                    await play_track(interaction.guild_id, vc, track, interaction.channel)
                    await interaction.followup.send(
                        f"▶️ Играет: **{track['title']}** ({self.SOURCES.get(source, source)})",
                        ephemeral=True,
                    )

                await update_panel(interaction.guild_id)
                await interaction.message.edit(content=f"🔎 Результаты по запросу:", view=None)
                await ensure_panel(interaction.guild_id, interaction.channel, force=True)
            except Exception as e:
                logger.error(f'Ошибка выбора трека: {e}')
                try:
                    await interaction.followup.send(f"❌ Ошибка: {e}", ephemeral=True)
                except Exception:
                    pass

        @discord.ui.button(label="❌ Закрыть", style=discord.ButtonStyle.secondary, custom_id="auto_cancel_btn")
        async def btn_cancel(self, interaction, button):
            await interaction.response.edit_message(content="Поиск закрыт", view=None)

    bot.add_view(MusicPanel())

    @bot.hybrid_command(name="play", description="Воспроизвести музыку (YouTube, SoundCloud, Яндекс Музыка)")
    @app_commands.describe(query="Название песни, ссылка или ссылка на плейлист")
    async def play_cmd(ctx: commands.Context, *, query: str):
        """Воспроизведение музыки"""
        try:
            if not ctx.author.voice:
                await ctx.send("❌ Вы должны быть в голосовом канале", ephemeral=True)
                return

            vc = ctx.voice_client
            if not vc:
                try:
                    vc = await ctx.author.voice.channel.connect()
                except Exception as e:
                    await ctx.send(f"❌ Не удалось подключиться к голосовому каналу: {e}", ephemeral=True)
                    return

            await ctx.defer()

            # Определяем, ссылка ли это на плейлист
            if re.match(r'https?://', query) and ('list=' in query or 'playlist' in query.lower() or 'set/' in query.lower()):
                title, raw_tracks = await search_playlist(query)
                if not raw_tracks:
                    await ctx.send("❌ Плейлист не найден или пуст", ephemeral=True)
                    return

                # Разрешаем треки по одному (получаем потоковые URL)
                await ctx.send(f"📂 Загружаю плейлист **{title}** ({len(raw_tracks)} треков)...")
                playlist_tracks = []
                for entry in raw_tracks[:25]:
                    tr = await _playlist_item_to_track(entry)
                    if tr:
                        playlist_tracks.append(tr)
                    await asyncio.sleep(0.1)

                if not playlist_tracks:
                    await ctx.send("❌ Не удалось загрузить треки из плейлиста", ephemeral=True)
                    return

                for tr in playlist_tracks:
                    music_player.add_to_queue(ctx.guild.id, tr)

                if not (vc.is_playing() or vc.is_paused()) and playlist_tracks:
                    await play_track(ctx.guild.id, vc, playlist_tracks[0], ctx.channel)
                    embed = await now_playing_embed(playlist_tracks[0])
                    await ctx.send(embed=embed)
                else:
                    await ctx.send(f"📂 Добавлено **{len(playlist_tracks)}** треков в очередь из плейлиста **{title}**")

                await update_panel(ctx.guild.id)
                logger.info(f'{ctx.author} загрузил плейлист: {title} ({len(playlist_tracks)} треков)')
                return

            # Обычный текстовый запрос — ищем сразу во всех источниках
            await ctx.send("🔎 Ищу трек во всех источниках...")

            sources = ['youtube', 'soundcloud']
            results = await asyncio.gather(
                *(search_tracks(query, s, limit=8) for s in sources),
                return_exceptions=True,
            )

            tracks = []
            for source, res in zip(sources, results):
                if isinstance(res, list):
                    for tr in res:
                        if tr and tr.get('url'):
                            tracks.append((source, tr))

            if not tracks:
                await ctx.send("❌ Трек не найден ни в одном источнике", ephemeral=True)
                return

            view = AutoSearchView(tracks)
            embed = discord.Embed(
                title="🔎 Найдено треков",
                description=f"Запрос: **{query}**\nНайдено: **{len(tracks)}** результатов.",
                color=discord.Color.blurple(),
                timestamp=datetime.now(),
            )
            await ctx.send(embed=embed, view=view)

            logger.info(f'{ctx.author} начал поиск: {query}')

        except Exception as e:
            await ctx.send(f"❌ Ошибка при воспроизведении: {e}", ephemeral=True)
            logger.error(f'Ошибка play: {e}')

    @bot.hybrid_command(name="playlist", description="Добавить плейлист в очередь")
    @app_commands.describe(url="Ссылка на плейлист YouTube")
    async def playlist_cmd(ctx: commands.Context, *, url: str):
        """Добавление плейлиста в очередь"""
        try:
            if not ctx.author.voice:
                await ctx.send("❌ Вы должны быть в голосовом канале", ephemeral=True)
                return

            vc = ctx.voice_client
            if not vc:
                try:
                    vc = await ctx.author.voice.channel.connect()
                except Exception as e:
                    await ctx.send(f"❌ Не удалось подключиться к голосовому каналу: {e}", ephemeral=True)
                    return

            await ctx.defer()

            title, raw_tracks = await search_playlist(url)
            if not raw_tracks:
                await ctx.send("❌ Плейлист не найден или пуст", ephemeral=True)
                return

            await ctx.send(f"📂 Загружаю плейлист **{title}** ({len(raw_tracks)} треков)...")
            playlist_tracks = []
            for entry in raw_tracks[:25]:
                tr = await _playlist_item_to_track(entry)
                if tr:
                    playlist_tracks.append(tr)
                await asyncio.sleep(0.1)

            if not playlist_tracks:
                await ctx.send("❌ Не удалось загрузить треки из плейлиста", ephemeral=True)
                return

            for tr in playlist_tracks:
                music_player.add_to_queue(ctx.guild.id, tr)

            if not (vc.is_playing() or vc.is_paused()) and playlist_tracks:
                await play_track(ctx.guild.id, vc, playlist_tracks[0], ctx.channel)
                embed = await now_playing_embed(playlist_tracks[0])
                await ctx.send(embed=embed)
            else:
                await ctx.send(f"📂 Добавлено **{len(playlist_tracks)}** треков в очередь из плейлиста **{title}**")

            await update_panel(ctx.guild.id)
            logger.info(f'{ctx.author} загрузил плейлист: {title} ({len(playlist_tracks)} треков)')

        except Exception as e:
            await ctx.send(f"❌ Ошибка при загрузке плейлиста: {e}", ephemeral=True)
            logger.error(f'Ошибка playlist: {e}')

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
            voice_channel = ctx.author.voice.channel
            await voice_channel.connect()
            await ctx.send(f"✅ Подключился к {voice_channel.name}")
            logger.info(f'Подключился к {voice_channel.name}')
        except Exception as e:
            await ctx.send(f"❌ Ошибка: {e}", ephemeral=True)
            logger.error(f'Ошибка join: {e}')

    @bot.hybrid_command(name="pause", description="Поставить музыку на паузу")
    async def pause_cmd(ctx: commands.Context):
        """Пауза музыки"""
        try:
            vc = ctx.voice_client
            if not vc or not vc.is_playing():
                await ctx.send("❌ Музыка не играет", ephemeral=True)
                return
            vc.pause()
            music_player.pause_tracking(ctx.guild.id)
            await ctx.send("⏸️ Музыка поставлена на паузу")
            logger.info(f'{ctx.author} поставил на паузу')
        except Exception as e:
            await ctx.send(f"❌ Ошибка при паузе: {e}", ephemeral=True)
            logger.error(f'Ошибка pause: {e}')

    @bot.hybrid_command(name="resume", description="Продолжить воспроизведение")
    async def resume_cmd(ctx: commands.Context):
        """Продолжить музыку"""
        try:
            vc = ctx.voice_client
            if not vc or not vc.is_paused():
                await ctx.send("❌ Музыка не на паузе", ephemeral=True)
                return
            vc.resume()
            music_player.resume_tracking(ctx.guild.id)
            await ctx.send("▶️ Воспроизведение продолжено")
            logger.info(f'{ctx.author} возобновил воспроизведение')
        except Exception as e:
            await ctx.send(f"❌ Ошибка при продолжении: {e}", ephemeral=True)
            logger.error(f'Ошибка resume: {e}')

    @bot.hybrid_command(name="skip", description="Пропустить текущий трек")
    async def skip_cmd(ctx: commands.Context):
        """Пропуск трека"""
        try:
            vc = ctx.voice_client
            if not vc or not vc.is_playing():
                await ctx.send("❌ Музыка не играет", ephemeral=True)
                return
            current = music_player.current.get(ctx.guild.id)
            vc.stop()
            queue = music_player.get_queue(ctx.guild.id)
            if queue:
                next_track = queue[0]
                await ctx.send(f"⏭️ Трек пропущен. Сейчас играет: **{next_track['title']}**")
            else:
                await ctx.send(f"⏭️ Трек пропущен. Очередь пуста")
            logger.info(f'{ctx.author} пропустил трек: {current["title"] if current else "?"}')
        except Exception as e:
            await ctx.send(f"❌ Ошибка при пропуске: {e}", ephemeral=True)
            logger.error(f'Ошибка skip: {e}')

    @bot.hybrid_command(name="stop", description="Остановить воспроизведение")
    async def stop_cmd(ctx: commands.Context):
        """Остановка музыки"""
        try:
            vc = ctx.voice_client
            if not vc:
                await ctx.send("❌ Бот не в голосовом канале", ephemeral=True)
                return
            music_player.clear_queue(ctx.guild.id)
            vc.stop()
            await ctx.send("⏹️ Воспроизведение остановлено")
            await update_panel(ctx.guild.id)
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
                timestamp=datetime.now(),
            )

            for i, track in enumerate(queue[:10], 1):
                embed.add_field(
                    name=f"{i}. {track['title'][:50]}",
                    value=f"Автор: {track['channel']} | Длительность: {format_duration(track['duration'])}",
                    inline=False,
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
            vc = ctx.voice_client
            track = music_player.current.get(ctx.guild.id)
            if not vc or not track:
                await ctx.send("❌ Сейчас ничего не играет", ephemeral=True)
                return

            embed = await now_playing_embed(track)
            if vc.is_paused():
                embed.set_footer(text="⏸️ На паузе")

            await ctx.send(embed=embed)
            logger.info(f'{ctx.author} посмотрел текущий трек')
        except Exception as e:
            await ctx.send(f"❌ Ошибка: {e}", ephemeral=True)
            logger.error(f'Ошибка nowplaying: {e}')

    @bot.hybrid_command(name="volume", description="Установить громкость (0-1000)")
    @app_commands.describe(level="Уровень громкости (0-1000)")
    async def volume_cmd(ctx: commands.Context, level: int):
        """Настройка громкости"""
        try:
            if level < 0 or level > 1000:
                await ctx.send("❌ Громкость должна быть от 0 до 1000", ephemeral=True)
                return
            music_player.set_volume(ctx.guild.id, level)
            await ctx.send(f"🔊 Громкость установлена на **{level}%**")
            logger.info(f'{ctx.author} установил громкость: {level}%')
        except Exception as e:
            await ctx.send(f"❌ Ошибка при настройке громкости: {e}", ephemeral=True)
            logger.error(f'Ошибка volume: {e}')

    @bot.hybrid_command(name="bassboost", description="Усилить басы (0-100 дБ). Без аргумента — очень сильный вкл/выкл")
    @app_commands.describe(level="Уровень баса в дБ (0-100)")
    async def bassboost_cmd(ctx: commands.Context, level: int = None):
        """Bass boost"""
        try:
            if level is None:
                level = STRONG_BASS if music_player.get_bass(ctx.guild.id) == 0 else 0
            elif level < 0 or level > 100:
                await ctx.send("❌ Уровень баса должен быть от 0 до 100 дБ", ephemeral=True)
                return
            music_player.set_bass(ctx.guild.id, level)
            if level > 0 and ctx.voice_client and (ctx.voice_client.is_playing() or ctx.voice_client.is_paused()):
                await restart_track(ctx.guild.id)
            await ctx.send(f"🎚️ Басс: **{level} дБ**" if level else "🎚️ Басс выключен")
            logger.info(f'{ctx.author} установил басс: {level} дБ')
        except Exception as e:
            await ctx.send(f"❌ Ошибка при настройке баса: {e}", ephemeral=True)
            logger.error(f'Ошибка bassboost: {e}')

    @bot.hybrid_command(name="panel", description="Показать панель управления музыкой в голосовом канале")
    async def panel_cmd(ctx: commands.Context):
        """Панель управления музыкой"""
        try:
            # Удаляем старую панель, чтобы не копить дубли
            old = music_player.panel_messages.get(ctx.guild.id)
            if old:
                try:
                    await old.delete()
                except discord.NotFound:
                    pass
                except discord.HTTPException:
                    pass
                music_player.panel_messages.pop(ctx.guild.id, None)

            embed = get_panel_embed(ctx.guild.id)
            view = MusicPanel()

            if ctx.author.voice and ctx.author.voice.channel:
                msg = await ctx.author.voice.channel.send(embed=embed, view=view)
            else:
                msg = await ctx.send(embed=embed, view=view)

            music_player.panel_messages[ctx.guild.id] = msg
            logger.info(f'{ctx.author} открыл панель управления музыкой')
        except Exception as e:
            await ctx.send(f"❌ Ошибка при открытии панели: {e}", ephemeral=True)
            logger.error(f'Ошибка panel: {e}')

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
            vc = ctx.voice_client
            if not vc:
                await ctx.send("❌ Бот не в голосовом канале", ephemeral=True)
                return
            music_player.clear_queue(ctx.guild.id)
            vc.stop()
            music_player.track_started_at.pop(ctx.guild.id, None)
            music_player.paused_position.pop(ctx.guild.id, None)
            await vc.disconnect()
            await ctx.send("👋 Отключился от голосового канала")
            await update_panel(ctx.guild.id)
            logger.info(f'{ctx.author} отключил бота от голосового канала')
        except Exception as e:
            await ctx.send(f"❌ Ошибка при отключении: {e}", ephemeral=True)
            logger.error(f'Ошибка leave: {e}')

    @bot.event
    async def on_voice_state_update(member, before, after):
        """Автоматический выход бота, если он остался один в канале"""
        if member.id != bot.user.id:
            return
        if before.channel and after.channel != before.channel:
            music_player.clear_queue(before.channel.guild.id)

    logger.info("Модуль музыки загружен (yt-dlp + FFmpeg)")
