"""
Модуль automod — автоматическая модерация.
Правило: запрет всех ссылок кроме YouTube в выбранных каналах (медиа-контент).
"""

import json
import logging
import re
from urllib.parse import urlparse

import discord
from discord.ext import commands
from discord import app_commands

logger = logging.getLogger('discord_bot.automod')

URL_RE = re.compile(r'https?://[^\s<>]+', re.IGNORECASE)

# Домены, ссылки на которые разрешены по умолчанию
DEFAULT_ALLOWED = ["youtube.com", "youtu.be", "youtube-nocookie.com"]


def _domain_of(url):
    try:
        netloc = urlparse(url).netloc.lower()
        if netloc.startswith("www."):
            netloc = netloc[4:]
        return netloc
    except Exception:
        return ""


def setup_automod(bot):

    async def _get_channels(guild_id):
        await bot.db.execute('''
            CREATE TABLE IF NOT EXISTS automod_linkfilter (
                guild_id INTEGER,
                channel_id INTEGER,
                PRIMARY KEY (guild_id, channel_id)
            )
        ''')
        await bot.db.execute('''
            CREATE TABLE IF NOT EXISTS automod_allowed (
                guild_id INTEGER PRIMARY KEY,
                domains TEXT DEFAULT '[]'
            )
        ''')
        await bot.db.commit()
        cursor = await bot.db.execute(
            "SELECT channel_id FROM automod_linkfilter WHERE guild_id = ?", (guild_id,))
        channels = [r[0] for r in await cursor.fetchall()]
        cursor = await bot.db.execute(
            "SELECT domains FROM automod_allowed WHERE guild_id = ?", (guild_id,))
        row = await cursor.fetchone()
        allowed = DEFAULT_ALLOWED[:]
        if row and row[0]:
            try:
                allowed += json.loads(row[0])
            except Exception:
                pass
        return channels, allowed

    async def _log(guild, member, url, channel):
        try:
            cursor = await bot.db.execute(
                "SELECT log_channel FROM antispam_settings WHERE guild_id = ?", (guild.id,))
            row = await cursor.fetchone()
            if not row or not row[0]:
                return
            ch = guild.get_channel(row[0])
            if not ch:
                return
            embed = discord.Embed(
                title="Автомод: запрещённая ссылка",
                color=discord.Color.red(),
                timestamp=discord.utils.utcnow())
            embed.add_field(name="Нарушитель", value=member.mention, inline=True)
            embed.add_field(name="Канал", value=channel.mention, inline=True)
            embed.add_field(name="Ссылка", value=url[:1000], inline=False)
            await ch.send(embed=embed)
        except Exception:
            pass

    @bot.listen('on_message')
    async def automod_listener(message):
        try:
            if message.author == bot.user:
                return
            if not message.guild:
                return
            if not isinstance(message.channel, (discord.TextChannel, discord.Thread)):
                return

            channels, allowed = await _get_channels(message.guild.id)
            if message.channel.id not in channels:
                return

            perms = getattr(message.author, "guild_permissions", None)
            if perms is not None and perms.manage_messages:
                return

            text = message.content or ""
            urls = URL_RE.findall(text)
            if not urls:
                return

            bad = []
            for u in urls:
                dom = _domain_of(u)
                if dom and dom not in allowed:
                    bad.append(u)

            if bad:
                if message.channel.permissions_for(message.guild.me).manage_messages:
                    try:
                        await message.delete()
                    except Exception:
                        pass
                await _log(message.guild, message.author, bad[0], message.channel)
        except Exception as e:
            logger.error(f'ОШИБКА automod_listener: {e}', exc_info=True)

    @bot.hybrid_command(name="automod", description="Автомод: запрет ссылок кроме YouTube")
    @app_commands.describe(action="Что сделать", value="Значение")
    @commands.has_permissions(administrator=True)
    async def automod_cmd(ctx, action: str = "status", value: str = None):
        action = action.lower()

        if action == "status":
            channels, allowed = await _get_channels(ctx.guild.id)
            ch_mentions = [ctx.guild.get_channel(c).mention for c in channels if ctx.guild.get_channel(c)]
            embed = discord.Embed(title="Автомод (запрет ссылок)", color=discord.Color.blue())
            embed.add_field(name="Каналы с фильтром",
                            value="\n".join(ch_mentions) if ch_mentions else "нет", inline=False)
            embed.add_field(name="Разрешённые домены",
                            value=", ".join(sorted(set(allowed))) or "—", inline=False)
            embed.add_field(name="Команды",
                            value="links #канал — вкл фильтр\nlinks off #канал — выкл\nallowed add domain.com — добавить домен",
                            inline=False)
            await ctx.send(embed=embed)
            return

        if action == "links":
            if value is None:
                await ctx.send("Укажите канал: `!automod links #канал` или `links off #канал`")
                return
            parts = value.split()
            mode = parts[0]
            cid = int(parts[1].strip().replace("<#", "").replace(">", ""))
            if mode == "off":
                await bot.db.execute(
                    "DELETE FROM automod_linkfilter WHERE guild_id = ? AND channel_id = ?",
                    (ctx.guild.id, cid))
                await bot.db.commit()
                await ctx.send(f"Фильтр ссылок выключен в {ctx.guild.get_channel(cid).mention}")
            else:
                await bot.db.execute(
                    "INSERT OR IGNORE INTO automod_linkfilter (guild_id, channel_id) VALUES (?, ?)",
                    (ctx.guild.id, cid))
                await bot.db.commit()
                await ctx.send(f"Фильтр ссылок (кроме YouTube) включён в {ctx.guild.get_channel(cid).mention}")
            return

        if action == "allowed":
            if value is None:
                await ctx.send("Укажите: `!automod allowed add domain.com`")
                return
            parts = value.split()
            if parts[0] != "add":
                await ctx.send("Только `!automod allowed add domain.com`")
                return
            dom = parts[1].lower().replace("www.", "")
            _, allowed = await _get_channels(ctx.guild.id)
            if dom not in allowed:
                allowed.append(dom)
                await bot.db.execute(
                    "INSERT OR REPLACE INTO automod_allowed (guild_id, domains) VALUES (?, ?)",
                    (ctx.guild.id, json.dumps(allowed)))
                await bot.db.commit()
                await ctx.send(f"Домен разрешён: {dom}")
            else:
                await ctx.send(f"Домен уже разрешён: {dom}")
            return

        await ctx.send("Неизвестное действие. `!automod` — список команд.")
