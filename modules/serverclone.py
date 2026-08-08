"""
Модуль копирования структуры сервера
Команда: clone <ID сервера> — копирует категории, каналы, роли с другого сервера (где состоит бот)
"""

import asyncio
import logging

import discord
from discord.ext import commands

logger = logging.getLogger('discord_bot.serverclone')


def setup_serverclone(bot):
    """Настройка команды клонирования сервера"""

    @bot.hybrid_command(name="clone", description="Скопировать структуру сервера (категории, каналы, роли)")
    @commands.has_permissions(administrator=True)
    async def clone_cmd(ctx: commands.Context, server_id: int):
        """Копирование структуры сервера по ID"""
        try:
            source = bot.get_guild(server_id)
            if source is None:
                await ctx.send(f"❌ Сервер с ID **{server_id}** не найден. Бот должен быть участником этого сервера.", ephemeral=True)
                return
            if source.id == ctx.guild.id:
                await ctx.send("❌ Нельзя копировать сервер сам в себя", ephemeral=True)
                return

            await ctx.defer()

            target = ctx.guild
            embed = discord.Embed(
                title="📋 Копирование сервера",
                description=f"Источник: **{source.name}**\nЦель: **{target.name}**",
                color=discord.Color.orange()
            )
            msg = await ctx.send(embed=embed)

            stats = {"roles": 0, "categories": 0, "channels": 0}

            # 1. Роли (кроме @everyone и роли бота)
            source_roles = sorted(
                [r for r in source.roles if r.name != '@everyone' and not r.is_bot_managed() and not r.is_premium_subscriber()],
                key=lambda r: r.position, reverse=True
            )
            existing_names = {r.name for r in target.roles}
            created_roles = {}
            for role in source_roles:
                if role.name in existing_names:
                    created_roles[role.id] = discord.utils.get(target.roles, name=role.name)
                    continue
                try:
                    new_role = await target.create_role(
                        name=role.name,
                        permissions=role.permissions,
                        colour=role.colour,
                        hoist=role.hoist,
                        mentionable=role.mentionable,
                        reason=f"Копирование с сервера {source.name} ({ctx.author})"
                    )
                    created_roles[role.id] = new_role
                    stats["roles"] += 1
                    await asyncio.sleep(0.3)
                except Exception as e:
                    logger.error(f'Ошибка копирования роли {role.name}: {e}')

            await msg.edit(embed=discord.Embed(
                title="📋 Копирование сервера",
                description=f"Источник: **{source.name}**\nЦель: **{target.name}**\n\n"
                            f"✅ Роли: **{stats['roles']}** создано\n🔄 Создаю каналы...",
                color=discord.Color.orange()
            ))

            # 2. Категории
            source_categories = sorted(source.categories, key=lambda c: c.position)
            created_categories = {}
            for cat in source_categories:
                try:
                    new_cat = await target.create_category(
                        name=cat.name,
                        overwrites=_copy_overwrites(cat.overwrites, created_roles, target),
                        position=cat.position,
                        reason=f"Копирование с сервера {source.name} ({ctx.author})"
                    )
                    created_categories[cat.id] = new_cat
                    stats["categories"] += 1
                    await asyncio.sleep(0.2)
                except Exception as e:
                    logger.error(f'Ошибка копирования категории {cat.name}: {e}')

            # 3. Каналы
            source_channels = sorted(
                source.channels,
                key=lambda ch: (ch.category.position if ch.category else -1, ch.position)
            )
            for ch in source_channels:
                try:
                    overwrites = _copy_overwrites(ch.overwrites, created_roles, target)
                    category = created_categories.get(ch.category_id)
                    if isinstance(ch, discord.TextChannel):
                        new_ch = await target.create_text_channel(
                            name=ch.name,
                            category=category,
                            overwrites=overwrites,
                            topic=ch.topic,
                            slowmode_delay=ch.slowmode_delay,
                            nsfw=ch.nsfw,
                            position=ch.position,
                            reason=f"Копирование с сервера {source.name} ({ctx.author})"
                        )
                    elif isinstance(ch, discord.VoiceChannel):
                        new_ch = await target.create_voice_channel(
                            name=ch.name,
                            category=category,
                            overwrites=overwrites,
                            bitrate=min(ch.bitrate, target.bitrate_limit or ch.bitrate),
                            user_limit=ch.user_limit,
                            position=ch.position,
                            reason=f"Копирование с сервера {source.name} ({ctx.author})"
                        )
                    elif isinstance(ch, discord.ForumChannel):
                        new_ch = await target.create_forum(
                            name=ch.name,
                            category=category,
                            overwrites=overwrites,
                            position=ch.position,
                            reason=f"Копирование с сервера {source.name} ({ctx.author})"
                        )
                    else:
                        continue
                    stats["channels"] += 1
                    await asyncio.sleep(0.2)
                except Exception as e:
                    logger.error(f'Ошибка копирования канала {ch.name}: {e}')

            await msg.edit(embed=discord.Embed(
                title="✅ Копирование завершено",
                description=f"Источник: **{source.name}**\nЦель: **{target.name}**\n\n"
                            f"🎭 Роли: **{stats['roles']}**\n"
                            f"📁 Категории: **{stats['categories']}**\n"
                            f"📢 Каналы: **{stats['channels']}**",
                color=discord.Color.green()
            ))
            logger.info(f'{ctx.author} скопировал структуру сервера {source.name} в {target.name}')

        except Exception as e:
            await ctx.send(f"❌ Ошибка при копировании: {e}", ephemeral=True)
            logger.error(f'Ошибка clone: {e}')


def _copy_overwrites(overwrites, created_roles, target):
    """Перенос прав доступа канала/категории (только роли, которые удалось создать/найти)"""
    result = {}
    for target_obj, perms in overwrites.items():
        if isinstance(target_obj, discord.Role):
            if target_obj.id in created_roles:
                result[created_roles[target_obj.id]] = perms
            elif target_obj.id == target.id:
                result[target.default_role] = perms
        elif isinstance(target_obj, discord.Member):
            member = target.get_member(target_obj.id)
            if member:
                result[member] = perms
    return result
