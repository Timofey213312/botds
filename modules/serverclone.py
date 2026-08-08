"""
Модуль копирования структуры сервера через шаблон (discord.new)
Команда: clone <ссылка шаблона или код> — копирует категории, каналы, роли в текущий сервер
Боту не нужно состоять на сервере-источнике: структура берётся из шаблона.
"""

import asyncio
import logging
import re

import aiohttp
import discord
from discord.ext import commands
from discord import app_commands

logger = logging.getLogger('discord_bot.serverclone')

BASE = 'https://discord.com/api'


def _parse_template_code(value):
    """Из ссылки (discord.new/XXX, discord.com/templates/XXX) или кода — вытаскиваем код"""
    value = (value or '').strip().strip('<>')
    m = re.search(r'(?:discord\.(?:com|new|gg)/(?:templates/)?)([A-Za-z0-9]+)', value)
    if m:
        return m.group(1)
    m = re.search(r'^([A-Za-z0-9]{6,})$', value)
    if m:
        return m.group(1)
    return None


def setup_serverclone(bot):
    """Настройка команды клонирования сервера"""

    @bot.hybrid_command(name="clone", description="Скопировать структуру сервера по шаблону discord.new (категории, каналы, роли)")
    @app_commands.describe(template="Ссылка шаблона (discord.new/XXX) или код шаблона")
    @commands.has_permissions(administrator=True)
    async def clone_cmd(ctx: commands.Context, *, template: str):
        """Копирование структуры сервера по шаблону"""
        code = _parse_template_code(template)
        if not code:
            await ctx.send(
                "❌ Не распознан шаблон. Используй ссылку вида `discord.new/XXXX` или код шаблона.\n"
                "Как создать шаблон: сервер → Настройки сервера → Шаблоны сервера → Сохранить шаблон.",
                ephemeral=True
            )
            return

        await ctx.defer()
        target = ctx.guild

        # 1. Получаем структуру шаблона
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f'{BASE}/guilds/templates/{code}',
                    headers={'Authorization': f'Bot {bot.http.token}'},
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as resp:
                    if resp.status == 404:
                        await ctx.send("❌ Шаблон не найден (код неверный или удалён)", ephemeral=True)
                        return
                    if resp.status != 200:
                        await ctx.send(f"❌ Ошибка получения шаблона: {resp.status}", ephemeral=True)
                        return
                    data = await resp.json()
        except Exception as e:
            await ctx.send(f"❌ Не удалось получить шаблон: {e}", ephemeral=True)
            return

        ssg = data.get('serialized_source_guild') or {}
        template_roles = [r for r in ssg.get('roles') or [] if r.get('name') not in ('@everyone',)]
        template_categories = ssg.get('categories') or []
        template_channels = ssg.get('channels') or []

        embed = discord.Embed(
            title="📋 Копирование сервера из шаблона",
            description=f"Шаблон: **{data.get('name') or 'без названия'}**\nЦель: **{target.name}**\n\n"
                        f"🎭 Ролей: **{len(template_roles)}**\n📁 Категорий: **{len(template_categories)}**\n"
                        f"📢 Каналов: **{len(template_channels)}**",
            color=discord.Color.orange()
        )
        msg = await ctx.send(embed=embed)

        stats = {"roles": 0, "categories": 0, "channels": 0, "skipped": []}

        # 2. Роли
        existing_names = {r.name for r in target.roles}
        role_map = {}  # id роли в шаблоне -> созданная роль
        # Сортируем по позиции (сверху вниз), чтобы проще было выставлять иерархию
        template_roles.sort(key=lambda r: r.get('position', 0), reverse=True)
        for role_data in template_roles:
            name = role_data.get('name', 'Роль')
            if name in existing_names:
                role_map[role_data['id']] = discord.utils.get(target.roles, name=name)
                continue
            try:
                perms = discord.Permissions(int(role_data.get('permissions', '0')))
                new_role = await target.create_role(
                    name=name,
                    permissions=perms,
                    colour=discord.Colour(role_data.get('color', 0)),
                    hoist=role_data.get('hoist', False),
                    mentionable=role_data.get('mentionable', False),
                    reason=f"Копирование из шаблона {code} ({ctx.author})"
                )
                role_map[role_data['id']] = new_role
                stats["roles"] += 1
                await asyncio.sleep(0.2)
            except Exception as e:
                stats["skipped"].append(name)
                logger.error(f'Ошибка копирования роли {name}: {e}')

        await msg.edit(embed=discord.Embed(
            title="📋 Копирование сервера из шаблона",
            description=f"Шаблон: **{data.get('name') or 'без названия'}**\n\n"
                        f"✅ Роли: **{stats['roles']}**\n🔄 Создаю категории...",
            color=discord.Color.orange()
        ))

        # 3. Категории
        cat_map = {}
        for cat in sorted(template_categories, key=lambda c: c.get('position', 0)):
            try:
                overwrites = _copy_overwrites(cat.get('permission_overwrites') or [], role_map, target)
                new_cat = await target.create_category(
                    name=cat.get('name', 'Категория'),
                    overwrites=overwrites,
                    position=cat.get('position', 0),
                    reason=f"Копирование из шаблона {code} ({ctx.author})"
                )
                cat_map[cat['id']] = new_cat
                stats["categories"] += 1
                await asyncio.sleep(0.2)
            except Exception as e:
                stats["skipped"].append(cat.get('name'))
                logger.error(f'Ошибка копирования категории {cat.get("name")}: {e}')

        # 4. Каналы
        for ch in sorted(template_channels, key=lambda c: c.get('position', 0)):
            ch_type = ch.get('type', 0)
            try:
                overwrites = _copy_overwrites(ch.get('permission_overwrites') or [], role_map, target)
                category = cat_map.get(ch.get('parent_id'))
                kwargs = dict(
                    name=ch.get('name', 'канал'),
                    category=category,
                    overwrites=overwrites,
                    position=ch.get('position', 0),
                    reason=f"Копирование из шаблона {code} ({ctx.author})"
                )
                if ch_type in (0, 5):  # текст / объявления
                    kwargs['topic'] = ch.get('topic') or None
                    kwargs['slowmode_delay'] = ch.get('rate_limit_per_user') or 0
                    kwargs['nsfw'] = ch.get('nsfw', False)
                    if ch_type == 5:
                        await target.create_news_channel(**kwargs)
                    else:
                        await target.create_text_channel(**kwargs)
                elif ch_type == 2:  # голосовой
                    kwargs['bitrate'] = min(ch.get('bitrate') or 64000, target.bitrate_limit or 96000)
                    kwargs['user_limit'] = ch.get('user_limit', 0)
                    await target.create_voice_channel(**kwargs)
                elif ch_type == 13:  # форум
                    await target.create_forum(**kwargs)
                elif ch_type == 15:  # сцена
                    await target.create_stage_channel(**kwargs)
                else:
                    continue
                stats["channels"] += 1
                await asyncio.sleep(0.2)
            except Exception as e:
                stats["skipped"].append(ch.get('name'))
                logger.error(f'Ошибка копирования канала {ch.get("name")}: {e}')

        # 5. Выставляем позиции ролей (иерархия как в источнике)
        try:
            ordered = sorted(template_roles, key=lambda r: r.get('position', 0), reverse=True)
            positions = {role_map[r['id']]: pos for pos, r in enumerate(ordered) if r['id'] in role_map}
            if positions:
                await target.edit_role_positions(positions)
        except Exception as e:
            logger.error(f'Ошибка выставления позиций ролей: {e}')

        finish = discord.Embed(
            title="✅ Копирование завершено",
            description=f"Шаблон: **{data.get('name') or 'без названия'}**\nЦель: **{target.name}**\n\n"
                        f"🎭 Роли: **{stats['roles']}**\n📁 Категории: **{stats['categories']}**\n"
                        f"📢 Каналы: **{stats['channels']}**",
            color=discord.Color.green()
        )
        if stats["skipped"]:
            finish.add_field(name="Пропущено (нет прав/ошибки)", value=", ".join(stats["skipped"][:20]), inline=False)
        await msg.edit(embed=finish)
        logger.info(f'{ctx.author} скопировал шаблон {code} в {target.name}')


def _copy_overwrites(overwrites, role_map, target):
    """Перенос прав доступа канала/категории из шаблона"""
    result = {}
    for ov in overwrites:
        if ov.get('type') == 0:  # роль
            role = role_map.get(ov.get('id'))
            if role is None:
                continue
            allow = discord.Permissions(int(ov.get('allow', '0')))
            deny = discord.Permissions(int(ov.get('deny', '0')))
            result[role] = discord.PermissionOverwrite.from_pair(allow=allow, deny=deny)
        elif ov.get('type') == 1:  # участник
            member = target.get_member(int(ov.get('id', 0)))
            if member:
                allow = discord.Permissions(int(ov.get('allow', '0')))
                deny = discord.Permissions(int(ov.get('deny', '0')))
                result[member] = discord.PermissionOverwrite.from_pair(allow=allow, deny=deny)
    return result
