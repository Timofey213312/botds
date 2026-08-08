"""
Модуль создания ролей сервера по готовому пресету (HvH клан)
Команда: setup_roles — создать все роли с указанными правами
"""

import asyncio
import logging
from datetime import datetime

import discord
from discord.ext import commands

logger = logging.getLogger('discord_bot.roles')


def _perms(**kwargs):
    """Создание Permissions с указанными правами"""
    p = discord.Permissions()
    for name, value in kwargs.items():
        if hasattr(p, name):
            setattr(p, name, bool(value))
    return p


# (название, цвет, права, hoist)
ROLE_PRESET = [
    # Администраторские роли
    ("👑 || ᴅᴇᴠ", 0xFFFFFF, _perms(administrator=True), True),
    ("👑 || ᴄᴇᴏ", 0xFFD700, _perms(administrator=True), True),
    ("👑 || ᴄᴏᴏ", 0xC0C0C0, _perms(administrator=True), True),
    ("👑 || ᴀᴅᴍɪɴ", 0xFF0000, _perms(
        administrator=True,
    ), True),
    # Модерация
    ("🛎️ || ᴢᴀᴍ.ᴀᴅᴍɪɴ", 0xFF8C00, _perms(
        kick_members=True,
        manage_messages=True,
        mute_members=True,
        deafen_members=True,
        move_members=True,
        manage_nicknames=True,
        mention_everyone=True,
        priority_speaker=True,
        create_instant_invite=True,
    ), True),
    ("🛡️ || ɢʟ ᴍᴏᴅᴇʀ", 0xFFAA00, _perms(
        manage_messages=True,
        mute_members=True,
        deafen_members=True,
        move_members=True,
        mention_everyone=True,
        priority_speaker=True,
        create_instant_invite=True,
    ), True),
    ("🛡️ || ɢᴜᴀʀᴅ ʙᴏᴛ", 0x00CCFF, _perms(
        manage_messages=True,
        mute_members=True,
        manage_nicknames=True,
        read_message_history=True,
        send_messages=True,
        embed_links=True,
        add_reactions=True,
    ), True),
    ("🛡️ || ᴍᴏᴅᴇʀ", 0x00FF88, _perms(
        manage_messages=True,
        mute_members=True,
        priority_speaker=True,
    ), True),
    # Командные/контентные роли
    ("🎬 || ᴍᴇᴅɪᴀ", 0xFF69B4, _perms(
        attach_files=True,
        embed_links=True,
        mention_everyone=True,
        create_polls=True,
        priority_speaker=True,
        connect=True,
        create_instant_invite=True,
    ), False),
    ("🤝 || ᴘᴀʀᴛɴᴇʀ", 0x8A2BE2, _perms(
        embed_links=True,
        attach_files=True,
        priority_speaker=True,
        create_instant_invite=True,
    ), False),
    ("🤖 || ʙᴏᴛs", 0x808080, _perms(
        read_message_history=True,
        send_messages=True,
        embed_links=True,
        add_reactions=True,
        priority_speaker=True,
    ), False),
    ("❤️ || ꜰʀɪᴇɴᴅ", 0xFF66B2, _perms(
        priority_speaker=True,
        connect=True,
        attach_files=True,
        create_instant_invite=True,
        change_nickname=True,
    ), False),
    ("🪄 || ᴅᴏᴠᴇʀᴇɴɴʏ", 0x00BFFF, _perms(
        change_nickname=True,
        attach_files=True,
        embed_links=True,
        create_instant_invite=True,
        add_reactions=True,
    ), False),
    # Основные роли
    ("⚔️ || ʏчᴀсник клᴀннᴀ", 0x4C9EFF, _perms(
        read_message_history=True,
        send_messages=True,
        connect=True,
        add_reactions=True,
        create_instant_invite=True,
    ), True),
    ("🎮 || иrᴘок", 0x3A6BFF, _perms(
        read_message_history=True,
        send_messages=True,
        connect=True,
        add_reactions=True,
        change_nickname=True,
        create_instant_invite=True,
    ), True),
]


def setup_roles(bot):
    """Настройка команды создания ролей"""

    @bot.hybrid_command(name="setup_roles", description="Создать все роли сервера по пресету (с правами)")
    @commands.has_permissions(administrator=True)
    async def setup_roles_cmd(ctx: commands.Context):
        """Создание всех ролей по пресету"""
        try:
            await ctx.defer()
            guild = ctx.guild

            existing = {r.name: r for r in guild.roles}
            created = []
            updated = []

            for name, color, perms, hoist in ROLE_PRESET:
                try:
                    if name in existing:
                        role = existing[name]
                        await role.edit(color=discord.Color(color), permissions=perms, hoist=hoist)
                        updated.append(name)
                    else:
                        role = await guild.create_role(
                            name=name,
                            color=discord.Color(color),
                            permissions=perms,
                            hoist=hoist,
                            mentionable=False,
                            reason=f"Создано {ctx.author} через !setup_roles"
                        )
                        created.append(name)
                    await asyncio.sleep(0.2)
                except discord.Forbidden:
                    logger.error(f'Недостаточно прав для роли {name}')
                except Exception as e:
                    logger.error(f'Ошибка при создании роли {name}: {e}')

            embed = discord.Embed(
                title="🎯 Роли сервера",
                color=discord.Color.green(),
                timestamp=datetime.now()
            )
            embed.add_field(
                name=f"Создано: {len(created)}",
                value="\n".join(f"✅ {r}" for r in created) if created else "—",
                inline=False
            )
            embed.add_field(
                name=f"Обновлено: {len(updated)}",
                value="\n".join(f"🔄 {r}" for r in updated) if updated else "—",
                inline=False
            )
            embed.set_footer(text=f"{ctx.author}", icon_url=ctx.author.display_avatar.url)

            await ctx.send(embed=embed)
            logger.info(f'{ctx.author} создал роли по пресету: {len(created)} новых, {len(updated)} обновлено')

        except Exception as e:
            await ctx.send(f"❌ Ошибка при создании ролей: {e}", ephemeral=True)
            logger.error(f'Ошибка setup_roles: {e}')
