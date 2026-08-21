"""
Модуль autorules — автоматические наказания за механические нарушения правил клана.
Реализованы правила:
  1.1 Флуд в текстовых каналах -> мут 10 минут
  1.9 Пинг @everyone / ролей без прав -> мут 1 день + warn
  1.3 / 4.3 Спам (повтор одинаковых сообщений) -> мут 1 час
Остальные правила (оскорбления, предательство и т.п.) требуют ручного решения администрации.
"""

import asyncio
import json
import logging
import time

import discord
from discord.ext import commands
from discord import app_commands

logger = logging.getLogger('discord_bot.autorules')

DEFAULTS = {
    "enabled": 1,
    "flood_enabled": 1,
    "flood_limit": 5,
    "flood_window": 10,
    "flood_timeout": 10,
    "ping_enabled": 1,
    "ping_timeout": 1440,
    "ping_warn": 1,
    "spam_enabled": 1,
    "spam_limit": 3,
    "spam_timeout": 60,
    "whitelist": "[]",
}


def setup_autorules(bot):
    """Настройка авто-правил"""

    if not hasattr(bot, "_autorules_flood"):
        bot._autorules_flood = {}
    if not hasattr(bot, "_autorules_spam"):
        bot._autorules_spam = {}

    async def _get_settings(guild_id):
        await bot.db.execute('''
            CREATE TABLE IF NOT EXISTS autorules_settings (
                guild_id INTEGER PRIMARY KEY,
                enabled INTEGER DEFAULT 1,
                flood_enabled INTEGER DEFAULT 1,
                flood_limit INTEGER DEFAULT 5,
                flood_window INTEGER DEFAULT 10,
                flood_timeout INTEGER DEFAULT 10,
                ping_enabled INTEGER DEFAULT 1,
                ping_timeout INTEGER DEFAULT 1440,
                ping_warn INTEGER DEFAULT 1,
                spam_enabled INTEGER DEFAULT 1,
                spam_limit INTEGER DEFAULT 3,
                spam_timeout INTEGER DEFAULT 60,
                whitelist TEXT DEFAULT '[]'
            )
        ''')
        await bot.db.commit()
        cursor = await bot.db.execute(
            "SELECT enabled, flood_enabled, flood_limit, flood_window, flood_timeout, "
            "ping_enabled, ping_timeout, ping_warn, spam_enabled, spam_limit, spam_timeout, whitelist "
            "FROM autorules_settings WHERE guild_id = ?", (guild_id,))
        row = await cursor.fetchone()
        if row is None:
            await bot.db.execute(
                "INSERT INTO autorules_settings (guild_id) VALUES (?)", (guild_id,))
            await bot.db.commit()
            return dict(DEFAULTS)
        keys = ["enabled", "flood_enabled", "flood_limit", "flood_window", "flood_timeout",
                "ping_enabled", "ping_timeout", "ping_warn", "spam_enabled", "spam_limit",
                "spam_timeout", "whitelist"]
        return dict(zip(keys, row))

    def _get_whitelist(s):
        try:
            return json.loads(s or "[]")
        except Exception:
            return []

    async def _add_warn(guild_id, user_id, moderator_id, reason):
        try:
            await bot.db.execute(
                "INSERT INTO warnings (user_id, guild_id, moderator_id, reason, created_at) "
                "VALUES (?, ?, ?, ?, datetime('now'))",
                (user_id, guild_id, moderator_id, reason))
            await bot.db.commit()
        except Exception as e:
            logger.error(f'Ошибка записи предупреждения autorules: {e}')

    async def _timeout(guild, member, minutes, reason):
        if not isinstance(member, discord.Member):
            return
        if not guild.me.guild_permissions.moderate_members:
            return
        if member.top_role >= guild.me.top_role:
            return
        try:
            await member.timeout(discord.utils.utcnow() + discord.timedelta(minutes=minutes), reason=reason)
        except discord.Forbidden:
            logger.warning(f'autorules: нет прав на тайм-аут {member}')
        except Exception as e:
            logger.error(f'autorules: ошибка тайм-аута: {e}')

    async def _log(guild, member, rule, action, content=""):
        try:
            cursor = await bot.db.execute(
                "SELECT log_channel FROM antispam_settings WHERE guild_id = ?", (guild.id,))
            row = await cursor.fetchone()
            if not row or not row[0]:
                return
            channel = guild.get_channel(row[0])
            if not channel:
                return
            embed = discord.Embed(
                title="Авто-наказание (autorules)",
                color=discord.Color.orange(),
                timestamp=discord.utils.utcnow())
            embed.add_field(name="Нарушитель", value=member.mention, inline=True)
            embed.add_field(name="Правило", value=rule, inline=True)
            embed.add_field(name="Действие", value=action, inline=False)
            if content:
                embed.add_field(name="Сообщение", value=content[:1000], inline=False)
            await channel.send(embed=embed)
        except Exception:
            pass

    @bot.listen('on_message')
    async def autorules_listener(message):
        try:
            if message.author == bot.user:
                return
            if not message.guild:
                return
            if not isinstance(message.channel, (discord.TextChannel, discord.Thread)):
                return

            settings = await _get_settings(message.guild.id)
            if not settings["enabled"]:
                return

            whitelist = _get_whitelist(settings["whitelist"])
            if message.channel.id in whitelist:
                return

            author = message.author
            perms = getattr(author, "guild_permissions", None)
            if perms is not None and perms.manage_messages:
                return

            now = time.time()
            gid = message.guild.id
            uid = author.id

            # --- 1.9 Пинг @everyone / ролей без прав ---
            if settings["ping_enabled"]:
                mention_everyone = message.mention_everyone
                role_ping = False
                if message.role_mentions:
                    can_mention = perms is not None and perms.mention_everyone
                    if not can_mention:
                        role_ping = True
                if mention_everyone or role_ping:
                    reason = "1.9 Пинг @everyone / ролей без прав"
                    await _timeout(message.guild, author, settings["ping_timeout"], reason)
                    if settings["ping_warn"]:
                        await _add_warn(gid, uid, bot.user.id, reason)
                    await _log(message.guild, author, reason,
                               f"мут {settings['ping_timeout']} мин" + (" + warn" if settings["ping_warn"] else ""),
                               message.content[:1000])
                    return

            # --- 1.1 Флуд ---
            if settings["flood_enabled"]:
                fkey = (gid, uid)
                times = bot._autorules_flood.get(fkey, [])
                times = [t for t in times if now - t < settings["flood_window"]]
                times.append(now)
                bot._autorules_flood[fkey] = times
                if len(times) > settings["flood_limit"]:
                    bot._autorules_flood[fkey] = []
                    reason = "1.1 Флуд в текстовых каналах"
                    await _timeout(message.guild, author, settings["flood_timeout"], reason)
                    await _log(message.guild, author, reason,
                               f"мут {settings['flood_timeout']} мин ({len(times)} сообщений)",
                               message.content[:1000])
                    return

            # --- 1.3 / 4.3 Спам (повтор одинаковых сообщений) ---
            if settings["spam_enabled"]:
                content_key = message.content.strip() or ",".join(
                    str(a.id) for a in message.attachments)
                if not content_key:
                    return
                skey = (gid, uid)
                prev = bot._autorules_spam.get(skey)
                if prev and prev["content"] == content_key:
                    prev["count"] += 1
                else:
                    prev = {"content": content_key, "count": 1}
                bot._autorules_spam[skey] = prev
                if prev["count"] >= settings["spam_limit"]:
                    bot._autorules_spam[skey] = {"content": "", "count": 0}
                    reason = "1.3 / 4.3 Спам (повторяющиеся сообщения)"
                    await _timeout(message.guild, author, settings["spam_timeout"], reason)
                    await _log(message.guild, author, reason,
                               f"мут {settings['spam_timeout']} мин", content_key[:1000])
                    return
        except Exception as e:
            logger.error(f'ОШИБКА autorules_listener: {e}', exc_info=True)

    @bot.hybrid_command(name="autorules", description="Настройки авто-наказаний за нарушения правил")
    @app_commands.describe(action="Что сделать", value="Значение")
    @commands.has_permissions(administrator=True)
    async def autorules_cmd(ctx, action: str = "status", value: str = None):
        settings = await _get_settings(ctx.guild.id)
        action = action.lower()

        if action == "status":
            embed = discord.Embed(title="Авто-правила (autorules)", color=discord.Color.blue())
            embed.add_field(name="Включён", value="Да" if settings["enabled"] else "Нет", inline=True)
            embed.add_field(name="Флуд (1.1)", value=f"{'Да' if settings['flood_enabled'] else 'Нет'} | {settings['flood_limit']} за {settings['flood_window']}с -> мут {settings['flood_timeout']} мин", inline=False)
            embed.add_field(name="Пинг @everyone/ролей (1.9)", value=f"{'Да' if settings['ping_enabled'] else 'Нет'} -> мут {settings['ping_timeout']} мин" + (" + warn" if settings['ping_warn'] else ""), inline=False)
            embed.add_field(name="Спам (1.3/4.3)", value=f"{'Да' if settings['spam_enabled'] else 'Нет'} | {settings['spam_limit']} одинаковых -> мут {settings['spam_timeout']} мин", inline=False)
            wl = _get_whitelist(settings["whitelist"])
            embed.add_field(name="Белый список каналов", value=str(len(wl)), inline=True)
            embed.add_field(name="Команды", value="on / off / flood on|off / ping on|off / spam on|off / whitelist add|remove #канал", inline=False)
            await ctx.send(embed=embed)
            return

        if action == "on":
            await bot.db.execute("UPDATE autorules_settings SET enabled = 1 WHERE guild_id = ?", (ctx.guild.id,))
            await bot.db.commit()
            await ctx.send("Autorules включён.")
            return
        if action == "off":
            await bot.db.execute("UPDATE autorules_settings SET enabled = 0 WHERE guild_id = ?", (ctx.guild.id,))
            await bot.db.commit()
            await ctx.send("Autorules выключен.")
            return
        if action in ("flood", "ping", "spam"):
            col = f"{action}_enabled"
            if value is None:
                await ctx.send(f"Укажите: `!autorules {action} on` или `off`")
                return
            val = 1 if value.lower() == "on" else 0
            await bot.db.execute(f"UPDATE autorules_settings SET {col} = ? WHERE guild_id = ?", (val, ctx.guild.id))
            await bot.db.commit()
            await ctx.send(f"Autorules [{action}] {'включён' if val else 'выключен'}.")
            return
        if action == "whitelist":
            if value is None:
                await ctx.send("Используйте: `!autorules whitelist add #канал` или `remove`")
                return
            parts = value.split()
            mode = parts[0]
            cid = int(parts[1].strip().replace("<#", "").replace(">", ""))
            wl = _get_whitelist(settings["whitelist"])
            if mode == "add" and cid not in wl:
                wl.append(cid)
            elif mode == "remove" and cid in wl:
                wl.remove(cid)
            await bot.db.execute("UPDATE autorules_settings SET whitelist = ? WHERE guild_id = ?", (json.dumps(wl), ctx.guild.id))
            await bot.db.commit()
            await ctx.send(f"Белый список каналов: {len(wl)}")
            return

        await ctx.send("Неизвестное действие. `!autorules` — список команд.")
