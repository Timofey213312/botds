"""
Модуль расширенной информации
Команды: информация о сервере, участниках, каналах, ролях
"""

import logging
from datetime import datetime

import discord
from discord.ext import commands
from discord import app_commands

logger = logging.getLogger('discord_bot.info')


def setup_info(bot):
    """Настройка информационных команд"""

    @bot.command(name="botinfo", description="Информация о боте")
    async def botinfo(ctx):
        embed = discord.Embed(title="🤖 Информация о боте", color=discord.Color.blurple())
        embed.add_field(name="Имя", value=bot.user.name, inline=True)
        embed.add_field(name="Пинг", value=f"{round(bot.latency * 1000)} мс", inline=True)
        embed.add_field(name="Серверов", value=str(len(bot.guilds)), inline=True)
        embed.add_field(name="Команд", value=str(len(bot.commands)), inline=True)
        embed.add_field(name="Пользователей", value=str(sum(g.member_count or 0 for g in bot.guilds)), inline=True)
        embed.set_thumbnail(url=bot.user.display_avatar.url)
        await ctx.send(embed=embed)

    @bot.command(name="servericon", description="Иконка сервера")
    async def servericon(ctx):
        if not ctx.guild.icon:
            await ctx.send("❌ У сервера нет иконки", ephemeral=True)
            return
        embed = discord.Embed(title=f"🖼️ Иконка сервера: {ctx.guild.name}", color=discord.Color.blurple())
        embed.set_image(url=ctx.guild.icon.url)
        await ctx.send(embed=embed)

    @bot.command(name="serverbanner", description="Баннер сервера")
    async def serverbanner(ctx):
        if not ctx.guild.banner:
            await ctx.send("❌ У сервера нет баннера", ephemeral=True)
            return
        embed = discord.Embed(title=f"🖼️ Баннер сервера: {ctx.guild.name}", color=discord.Color.blurple())
        embed.set_image(url=ctx.guild.banner.url)
        await ctx.send(embed=embed)

    @bot.command(name="channelinfo", description="Информация о канале")
    async def channelinfo(ctx, channel: discord.TextChannel = None):
        channel = channel or ctx.channel
        embed = discord.Embed(title=f"#️⃣ Канал: {channel.name}", color=discord.Color.blurple())
        embed.add_field(name="ID", value=str(channel.id), inline=True)
        embed.add_field(name="Категория", value=channel.category.name if channel.category else "Нет", inline=True)
        embed.add_field(name="Тема", value=channel.topic or "Нет", inline=False)
        embed.add_field(name="Слоу-мод", value=f"{channel.slowmode_delay} сек" if channel.slowmode_delay else "Выкл", inline=True)
        embed.add_field(name="NSFW", value="Да" if channel.nsfw else "Нет", inline=True)
        embed.add_field(name="Создан", value=channel.created_at.strftime("%d.%m.%Y"), inline=True)
        await ctx.send(embed=embed)

    @bot.command(name="roleinfo", description="Информация о роли")
    async def roleinfo(ctx, role: discord.Role):
        embed = discord.Embed(title=f"🎭 Роль: {role.name}", color=role.color)
        embed.add_field(name="ID", value=str(role.id), inline=True)
        embed.add_field(name="Цвет", value=str(role.color), inline=True)
        embed.add_field(name="Участников", value=str(len(role.members)), inline=True)
        embed.add_field(name="Позиция", value=str(role.position), inline=True)
        embed.add_field(name="Упоминаемая", value="Да" if role.mentionable else "Нет", inline=True)
        embed.add_field(name="Отображается отдельно", value="Да" if role.hoist else "Нет", inline=True)
        perms = []
        for perm, value in role.permissions:
            if value:
                perms.append(perm.replace("_", " "))
        embed.add_field(name="Права", value=", ".join(perms[:20]) if perms else "Нет", inline=False)
        await ctx.send(embed=embed)

    @bot.command(name="roles", description="Список всех ролей")
    async def roles_list(ctx):
        roles = sorted(ctx.guild.roles, key=lambda r: r.position, reverse=True)
        text = "\n".join(f"{r.mention} — {len(r.members)} уч." for r in roles if r.name != "@everyone")
        embed = discord.Embed(title=f"🎭 Роли сервера ({len(ctx.guild.roles) - 1})", description=text[:4000], color=discord.Color.blurple())
        await ctx.send(embed=embed)

    @bot.command(name="emojis", description="Список эмодзи сервера")
    async def emojis_list(ctx):
        emojis = ctx.guild.emojis
        if not emojis:
            await ctx.send("📭 На сервере нет эмодзи", ephemeral=True)
            return
        embed = discord.Embed(title=f"😀 Эмодзи сервера ({len(emojis)})", color=discord.Color.blurple())
        lines = []
        for e in emojis:
            lines.append(f"{e} `:{e.name}:`")
        embed.description = " ".join(lines[:100])
        await ctx.send(embed=embed)

    @bot.command(name="boosters", description="Бустеры сервера")
    async def boosters(ctx):
        boosts = [m for m in ctx.guild.members if m.premium_since]
        embed = discord.Embed(title=f"💎 Бустеры ({len(boosts)})", color=discord.Color.pink())
        embed.description = "\n".join(f"✨ {m.mention}" for m in boosts[:50]) if boosts else "Бустеров нет"
        embed.add_field(name="Уровень буста", value=f"Уровень {ctx.guild.premium_tier} ({ctx.guild.premium_subscription_count} бустов)")
        await ctx.send(embed=embed)

    @bot.command(name="invites", description="Список приглашений")
    async def invites(ctx):
        try:
            invites_list = await ctx.guild.invites()
        except discord.Forbidden:
            await ctx.send("❌ Нет прав на просмотр приглашений", ephemeral=True)
            return
        if not invites_list:
            await ctx.send("📭 На сервере нет приглашений", ephemeral=True)
            return
        sorted_invites = sorted(invites_list, key=lambda i: i.uses or 0, reverse=True)[:15]
        embed = discord.Embed(title=f"🔗 Приглашения ({len(invites_list)})", color=discord.Color.blurple())
        for inv in sorted_invites:
            embed.add_field(
                name=f"{inv.code} — {inv.uses} использований",
                value=f"Создано: {inv.inviter.name if inv.inviter else 'unknown'} | Канал: #{inv.channel.name if inv.channel else '?'}",
                inline=False
            )
        await ctx.send(embed=embed)

    @bot.command(name="created", description="Дата создания аккаунта")
    async def created(ctx, member: discord.Member = None):
        member = member or ctx.author
        embed = discord.Embed(title=f"🎂 {member.display_name}", color=discord.Color.blurple())
        embed.add_field(name="Аккаунт создан", value=member.created_at.strftime("%d.%m.%Y %H:%M"), inline=False)
        embed.add_field(name="Присоединился", value=member.joined_at.strftime("%d.%m.%Y %H:%M") if member.joined_at else "?", inline=False)
        await ctx.send(embed=embed)

    @bot.command(name="rolesof", description="Роли пользователя")
    async def rolesof(ctx, member: discord.Member = None):
        member = member or ctx.author
        roles = [r.mention for r in reversed(member.roles) if r.name != "@everyone"]
        text = " ".join(roles) if roles else "Нет ролей"
        embed = discord.Embed(title=f"🎭 Роли: {member.display_name}", description=text, color=discord.Color.blurple())
        await ctx.send(embed=embed)

    @bot.command(name="permissions", description="Права пользователя")
    async def permissions(ctx, member: discord.Member = None):
        member = member or ctx.author
        perms = [perm.replace("_", " ") for perm, value in member.guild_permissions if value]
        embed = discord.Embed(title=f"🔑 Права: {member.display_name}", description=", ".join(perms) if perms else "Нет прав", color=discord.Color.blurple())
        await ctx.send(embed=embed)

    @bot.command(name="badges", description="Бейджи пользователя")
    async def badges(ctx, member: discord.Member = None):
        member = member or ctx.author
        flags = member.public_flags.all()
        names = {
            "staff": "👨‍💼 Сотрудник Discord",
            "partner": "🤝 Партнёр",
            "hypesquad": "🎉 HypeSquad",
            "bug_hunter": "🐞 Bug Hunter",
            "early_supporter": "💖 Ранний сторонник",
            "verified_bot_developer": "🤖 Разработчик ботов",
            "verified_developer": "🤖 Разработчик ботов",
            "discord_certified_moderator": "🛡️ Сертифицированный модератор",
        }
        labels = [names.get(f.name, f.name.replace("_", " ")) for f in flags]
        embed = discord.Embed(title=f"🏅 Бейджи: {member.display_name}", description="\n".join(labels) if labels else "Нет бейджей", color=discord.Color.blurple())
        await ctx.send(embed=embed)

    @bot.command(name="guildinfo", description="Полная информация о сервере")
    async def guildinfo(ctx):
        guild = ctx.guild
        embed = discord.Embed(title=f"🛡️ Сервер: {guild.name}", color=discord.Color.blurple())
        embed.set_thumbnail(url=guild.icon.url if guild.icon else None)
        embed.add_field(name="Владелец", value=guild.owner.mention if guild.owner else "?", inline=True)
        embed.add_field(name="ID", value=str(guild.id), inline=True)
        embed.add_field(name="Участников", value=str(guild.member_count), inline=True)
        embed.add_field(name="Ботов", value=str(len([m for m in guild.members if m.bot])), inline=True)
        embed.add_field(name="Каналов", value=str(len(guild.channels)), inline=True)
        embed.add_field(name="Ролей", value=str(len(guild.roles)), inline=True)
        embed.add_field(name="Эмодзи", value=str(len(guild.emojis)), inline=True)
        embed.add_field(name="Уровень буста", value=str(guild.premium_tier), inline=True)
        embed.add_field(name="Создан", value=guild.created_at.strftime("%d.%m.%Y"), inline=True)
        embed.add_field(name="Регион", value=str(guild.region) if guild.region else "?", inline=True)
        embed.add_field(name="Верифицирован", value="Да" if guild.verified else "Нет", inline=True)
        await ctx.send(embed=embed)

    @bot.command(name="membercount", description="Количество участников")
    async def membercount(ctx):
        guild = ctx.guild
        humans = len([m for m in guild.members if not m.bot])
        bots = len([m for m in guild.members if m.bot])
        online = len([m for m in guild.members if m.status != discord.Status.offline])
        embed = discord.Embed(title=f"👥 Участники: {guild.name}", color=discord.Color.blurple())
        embed.add_field(name="Всего", value=str(guild.member_count), inline=True)
        embed.add_field(name="Людей", value=str(humans), inline=True)
        embed.add_field(name="Ботов", value=str(bots), inline=True)
        embed.add_field(name="Онлайн", value=str(online), inline=True)
        await ctx.send(embed=embed)

    @bot.command(name="whois", description="Подробная информация о пользователе")
    async def whois(ctx, member: discord.Member = None):
        member = member or ctx.author
        embed = discord.Embed(title=f"ℹ️ {member.display_name}", color=member.color)
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="Никнейм", value=member.display_name, inline=True)
        embed.add_field(name="Имя", value=member.name, inline=True)
        embed.add_field(name="ID", value=str(member.id), inline=False)
        embed.add_field(name="Топ роль", value=member.top_role.mention, inline=True)
        embed.add_field(name="Аккаунт создан", value=member.created_at.strftime("%d.%m.%Y"), inline=True)
        embed.add_field(name="Присоединился", value=member.joined_at.strftime("%d.%m.%Y") if member.joined_at else "?", inline=True)
        embed.add_field(name="Бот", value="Да" if member.bot else "Нет", inline=True)
        await ctx.send(embed=embed)

    @bot.command(name="banner", description="Баннер пользователя")
    async def banner_cmd(ctx, member: discord.Member = None):
        member = member or ctx.author
        user = await bot.fetch_user(member.id)
        if not user.banner:
            await ctx.send("❌ У пользователя нет баннера", ephemeral=True)
            return
        embed = discord.Embed(title=f"🖼️ Баннер: {member.display_name}", color=discord.Color.blurple())
        embed.set_image(url=user.banner.url)
        await ctx.send(embed=embed)

    @bot.command(name="activity", description="Активность пользователя")
    async def activity(ctx, member: discord.Member = None):
        member = member or ctx.author
        if not member.activity:
            await ctx.send(f"🌙 {member.mention} сейчас ничем не занят", ephemeral=True)
            return
        act = member.activity
        embed = discord.Embed(title=f"📊 Активность: {member.display_name}", color=discord.Color.blurple())
        embed.add_field(name="Тип", value=str(act.type).replace("custom", "кастомный").replace("playing", "играет").replace("listening", "слушает").replace("watching", "смотрит").replace("streaming", "стримит"), inline=True)
        embed.add_field(name="Название", value=act.name or "?", inline=True)
        if act.details:
            embed.add_field(name="Детали", value=act.details, inline=False)
        await ctx.send(embed=embed)

    @bot.command(name="status", description="Статус пользователя")
    async def status(ctx, member: discord.Member = None):
        member = member or ctx.author
        statuses = {
            discord.Status.online: "🟢 Онлайн",
            discord.Status.idle: "🌙 Неактивен",
            discord.Status.dnd: "🔴 Не беспокоить",
            discord.Status.offline: "⚫ Оффлайн",
            discord.Status.unknown: "❓ Неизвестно",
        }
        await ctx.send(f"Статус {member.mention}: **{statuses.get(member.status, '❓')}**")

    @bot.command(name="joined", description="Когда присоединился пользователь")
    async def joined(ctx, member: discord.Member = None):
        member = member or ctx.author
        if member.joined_at:
            await ctx.send(f"📅 {member.mention} присоединился **{member.joined_at.strftime('%d.%m.%Y %H:%M')}**")
        else:
            await ctx.send("❓ Неизвестно")

    @bot.command(name="dictionary", description="Значение слова (Wikipedia)")
    async def dictionary(ctx, *, word: str):
        try:
            async with bot.session.get("https://ru.wikipedia.org/api/rest_v1/page/summary/" + word.replace(" ", "_")) as resp:
                data = await resp.json()
            if "extract" in data:
                embed = discord.Embed(title=data.get("title", word), description=data["extract"][:1500], color=discord.Color.blurple())
                if data.get("thumbnail"):
                    embed.set_thumbnail(url=data["thumbnail"].get("source"))
                embed.set_footer(text="Источник: Wikipedia")
                await ctx.send(embed=embed)
            else:
                await ctx.send("❌ Слово не найдено", ephemeral=True)
        except Exception:
            await ctx.send("❌ Не удалось найти слово", ephemeral=True)