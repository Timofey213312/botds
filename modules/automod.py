"""
Модуль automod — автоматическая модерация ссылок.
Правило: ссылки запрещены ВЕЗДЕ, кроме канала "медиа-контент".
В медиа-канале разрешены только ссылки на YouTube (и добавленные домены).
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

# Домены, ссылки на которые разрешены в медиа-канале по умолчанию
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

    async def _get(guild_id):
        await bot.db.execute('''
            CREATE TABLE IF NOT EXISTS automod_settings (
                guild_id INTEGER PRIMARY KEY,
                media_channel_id TEXT DEFAULT NULL
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
            "SELECT media_channel_id FROM automod_settings WHERE guild_id = ?", (guild_id,))
        row = await cursor.fetchone()
        media_id = int(row[0]) if row and row[0] else None
        cursor = await bot.db.execute(
            "SELECT domains FROM automod_allowed WHERE guild_id = ?", (guild_id,))
        row = await cursor.fetchone()
        allowed = DEFAULT_ALLOWED[:]
        if row and row[0]:
            try:
                allowed += json.loads(row[0])
            except Exception:
                pass
        return media_id, allowed

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

            media_id, allowed = await _get(message.guild.id)

            perms = getattr(message.author, "guild_permissions", None)
            if perms is not None and perms.manage_messages:
                return

            text = message.content or ""
            urls = URL_RE.findall(text)
            if not urls:
                return

            is_media = (message.channel.id == media_id)
            bad = []

            if is_media:
                # В медиа-канале разрешён только YouTube / добавленные домены
                for u in urls:
                    dom = _domain_of(u)
                    if dom and dom not in allowed:
                        bad.append(u)
            else:
                # Везде кроме медиа-канала — любые ссылки запрещены
                bad = urls

            if bad:
                if message.channel.permissions_for(message.guild.me).manage_messages:
                    try:
                        await message.delete()
                    except Exception:
                        pass
                await _log(message.guild, message.author, bad[0], message.channel)
        except Exception as e:
            logger.error(f'ОШИБКА automod_listener: {e}', exc_info=True)

    @bot.hybrid_command(name="automod", description="Автомод: запрет ссылок везде кроме медиа-канала")
    @app_commands.describe(action="Что сделать", value="Значение")
    @commands.has_permissions(administrator=True)
    async def automod_cmd(ctx, action: str = "status", value: str = None):
        action = action.lower()

        if action == "status":
            media_id, allowed = await _get(ctx.guild.id)
            media_ch = ctx.guild.get_channel(media_id) if media_id else None
            embed = discord.Embed(title="Автомод (ссылки)", color=discord.Color.blue())
            embed.add_field(name="Медиа-канал (там только YouTube)",
                            value=media_ch.mention if media_ch else "не задан (ссылки запрещены везде)",
                            inline=False)
            embed.add_field(name="Разрешённые домены (в медиа)",
                            value=", ".join(sorted(set(allowed))) or "—", inline=False)
            embed.add_field(name="Команды",
                            value="media #канал — задать медиа-канал\nallowed add domain.com — добавить домен",
                            inline=False)
            await ctx.send(embed=embed)
            return

        if action == "media":
            if value is None:
                await ctx.send("Укажите канал: `!automod media #📷-медиа-контент`")
                return
            cid = int(value.strip().replace("<#", "").replace(">", ""))
            await bot.db.execute(
                "INSERT OR REPLACE INTO automod_settings (guild_id, media_channel_id) VALUES (?, ?)",
                (ctx.guild.id, str(cid)))
            await bot.db.commit()
            await ctx.send(f"Медиа-канал задан: {ctx.guild.get_channel(cid).mention} (там только YouTube, везде остальном ссылки запрещены)")
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
            _, allowed = await _get(ctx.guild.id)
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
