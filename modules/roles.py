"""
Модуль создания ролей для HvH клана
Команда: clanroles — создать все роли клана (название, цвет, права)
"""

import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime
import logging

logger = logging.getLogger('discord_bot.roles')

# Роли клана: (название, цвет, права, hex)
CLAN_ROLES = [
    ("Клан Владелец", 0x00FF00, discord.Permissions(administrator=True), "🟢"),
    ("Клан Со-Владелец", 0x00FF88, discord.Permissions(administrator=True), "🔶"),
    ("Клан Администратор", 0x00CCFF, discord.Permissions(administrator=True), "🔷"),
    ("Клан Модератор", 0x3399FF, discord.Permissions(manage_messages=True, kick_members=True, ban_members=True, mute_members=True, deafen_members=True, move_members=True, manage_nicknames=True, manage_roles=True, manage_channels=True), "🛡️"),
    ("Клан Лидер", 0xFFD700, discord.Permissions(manage_messages=True, kick_members=True, mute_members=True, move_members=True, manage_nicknames=True, mention_everyone=False), "👑"),
    ("Клан Заместитель", 0xFFAA00, discord.Permissions(manage_messages=True, mute_members=True, move_members=True, manage_nicknames=True), "🥈"),
    ("Клан Офицер", 0xFF8C00, discord.Permissions(manage_messages=True, move_members=True, manage_nicknames=True), "🥉"),
    ("Клан Тренер", 0xFF5500, discord.Permissions(manage_messages=True, move_members=True), "🎯"),
    ("Клан Ветеран", 0xFF3333, discord.Permissions(priority_speaker=True, stream=True), "🔥"),
    ("Клан Профи", 0xFF5555, discord.Permissions(priority_speaker=True), "⚡"),
    ("Клан Игрок", 0x66FF66, discord.Permissions(priority_speaker=False), "🎮"),
    ("Клан Рекрут", 0xAAAAAA, discord.Permissions(priority_speaker=False), "📝"),
    ("Клан Новичок", 0x888888, discord.Permissions(priority_speaker=False), "🐣"),
    ("Клан Триал", 0x999999, discord.Permissions(priority_speaker=False), "🧪"),
]

# Цвет по названию роли (для команды !clanrole)
COLOR_ALIASES = {
    "красный": 0xFF0000, "red": 0xFF0000,
    "оранжевый": 0xFF8C00, "orange": 0xFF8C00,
    "жёлтый": 0xFFFF00, "yellow": 0xFFFF00, "желтый": 0xFFFF00,
    "зелёный": 0x00FF00, "green": 0x00FF00, "зеленый": 0x00FF00,
    "голубой": 0x00FFFF, "cyan": 0x00FFFF,
    "синий": 0x0000FF, "blue": 0x0000FF,
    "фиолетовый": 0x8A2BE2, "purple": 0x8A2BE2,
    "розовый": 0xFF69B4, "pink": 0xFF69B4,
    "белый": 0xFFFFFF, "white": 0xFFFFFF,
    "чёрный": 0x000000, "black": 0x000000, "черный": 0x000000,
    "серый": 0x808080, "grey": 0x808080, "gray": 0x808080,
    "золотой": 0xFFD700, "gold": 0xFFD700,
    "коричневый": 0x8B4513, "brown": 0x8B4513,
}


def setup_roles(bot):
    """Настройка команд ролей"""

    @bot.hybrid_command(name="clanroles", description="Создать все роли для HvH клана")
    @commands.has_permissions(administrator=True)
    async def clanroles_cmd(ctx: commands.Context):
        """Создание всех ролей клана"""
        try:
            await ctx.defer()
            guild = ctx.guild

            existing = {r.name: r for r in guild.roles}
            created = []
            updated = []

            for name, color, perms, _emoji in CLAN_ROLES:
                try:
                    if name in existing:
                        role = existing[name]
                        await role.edit(color=discord.Color(color), permissions=perms, hoist=True)
                        updated.append(name)
                    else:
                        role = await guild.create_role(
                            name=name,
                            color=discord.Color(color),
                            permissions=perms,
                            hoist=True,
                            mentionable=False,
                            reason=f"Создано {ctx.author} через !clanroles"
                        )
                        created.append(name)
                except discord.Forbidden:
                    logger.error(f'Недостаточно прав для роли {name}')
                except Exception as e:
                    logger.error(f'Ошибка при создании роли {name}: {e}')

            embed = discord.Embed(
                title="🎯 Роли HvH клана",
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
            logger.info(f'{ctx.author} создал роли клана: {len(created)} новых, {len(updated)} обновлено')

        except Exception as e:
            await ctx.send(f"❌ Ошибка при создании ролей: {e}", ephemeral=True)
            logger.error(f'Ошибка clanroles: {e}')

    @bot.hybrid_command(name="clanrole", description="Создать одну роль для клана")
    @app_commands.describe(name="Название роли", color="Цвет (напр. красный, синий или HEX)", permissions="Права через запятую: kick, ban, mute, move, roles, channels, admin")
    @commands.has_permissions(administrator=True)
    async def clanrole_cmd(ctx: commands.Context, name: str, color: str = "серый", permissions: str = ""):
        """Создание одной роли клана"""
        try:
            guild = ctx.guild
            color_value = COLOR_ALIASES.get(color.lower(), 0x808080)
            if color.startswith("#") and len(color) == 7:
                try:
                    color_value = int(color[1:], 16)
                except ValueError:
                    color_value = 0x808080

            perms = discord.Permissions()
            if permissions:
                perm_map = {
                    "admin": {"administrator": True},
                    "administrator": {"administrator": True},
                    "kick": {"kick_members": True},
                    "ban": {"ban_members": True},
                    "mute": {"mute_members": True},
                    "deafen": {"deafen_members": True},
                    "move": {"move_members": True},
                    "roles": {"manage_roles": True},
                    "manage_roles": {"manage_roles": True},
                    "channels": {"manage_channels": True},
                    "manage_channels": {"manage_channels": True},
                    "messages": {"manage_messages": True},
                    "manage_messages": {"manage_messages": True},
                    "nicknames": {"manage_nicknames": True},
                    "manage_nicknames": {"manage_nicknames": True},
                    "stream": {"stream": True},
                }
                for p in permissions.lower().replace(" ", "").split(","):
                    if p in perm_map:
                        for k, v in perm_map[p].items():
                            setattr(perms, k, v)

            existing = discord.utils.get(guild.roles, name=name)
            if existing:
                await existing.edit(color=discord.Color(color_value), permissions=perms, hoist=True)
                await ctx.send(f"🔄 Роль **{name}** обновлена", ephemeral=True)
            else:
                await guild.create_role(
                    name=name,
                    color=discord.Color(color_value),
                    permissions=perms,
                    hoist=True,
                    mentionable=False,
                    reason=f"Создано {ctx.author} через !clanrole"
                )
                await ctx.send(f"✅ Роль **{name}** создана", ephemeral=True)

            logger.info(f'{ctx.author} создал/обновил роль {name}')
        except Exception as e:
            await ctx.send(f"❌ Ошибка при создании роли: {e}", ephemeral=True)
            logger.error(f'Ошибка clanrole: {e}')
