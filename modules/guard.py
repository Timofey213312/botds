"""
Модуль защиты сервера (Server Guard)
Автоматически откатывает изменения каналов/ролей, сделанные не владельцем Discord сервера.
Владелец сервера может одобрять или отклонять изменения через кнопки.
"""

import discord
import asyncio
import logging
from datetime import datetime

logger = logging.getLogger('discord_bot.guard')

PENDING_CHANGES = {}  # change_id -> dict (change data, pending approval)
_change_counter = 0


def setup_guard(bot):
    """Настройка модуля защиты сервера"""

    DEFAULT_MODLOG_CHANNEL_ID = "1535655890982801438"  # 🔨-логи

    async def _get_guard_channel(guild):
        cid = DEFAULT_MODLOG_CHANNEL_ID
        try:
            ch = guild.get_channel(int(cid)) or bot.get_channel(int(cid))
            if not ch:
                ch = await bot.fetch_channel(int(cid))
            return ch
        except Exception:
            return None

    async def _guard_log(guild, title, color, fields, ping_owner=False):
        ch = await _get_guard_channel(guild)
        if not ch:
            return
        embed = discord.Embed(title=title, color=color, timestamp=datetime.now())
        for name, value in fields:
            embed.add_field(name=name, value=value, inline=False)
        embed.set_footer(text="Vector.prod • Защита сервера")
        content = None
        if ping_owner and guild.owner:
            content = f"{guild.owner.mention}, требуется ваше действие!"
        try:
            await ch.send(content=content, embed=embed)
        except Exception:
            pass

    async def _check_audit_log(guild, action, target_id, within=30):
        try:
            if not guild.me.guild_permissions.view_audit_log:
                logger.warning(f'Guard: нет прав на View Audit Log в {guild.name}')
                return None
            async for entry in guild.audit_logs(limit=10, action=action):
                if getattr(entry.target, 'id', None) == target_id:
                    now = discord.utils.utcnow()
                    elapsed = (now - entry.created_at).total_seconds()
                    if elapsed <= within:
                        return entry
        except Exception as e:
            logger.error(f'Ошибка чтения журнала аудита: {e}')
        return None

    def _is_owner(user):
        if hasattr(user, 'guild'):
            return user.guild.owner_id == user.id
        return False

    async def _send_approval_request(guild, change_id, change_data, action_str, target_str, moderator, extra=""):
        global PENDING_CHANGES
        owner = guild.owner
        if not owner:
            return

        view = GuardApprovalView(change_id)

        embed = discord.Embed(
            title="⚠️ Обнаружено несанкционированное изменение",
            color=discord.Color.orange(),
            timestamp=datetime.now())
        embed.add_field(name="Действие", value=action_str, inline=True)
        embed.add_field(name="Объект", value=target_str, inline=True)
        embed.add_field(name="Кто изменил", value=f"{moderator.mention} (`{moderator.id}`)", inline=True)
        embed.add_field(name="Сервер", value=guild.name, inline=True)
        if extra:
            embed.add_field(name="Детали", value=extra, inline=False)
        embed.set_footer(text=f"Change ID: {change_id} • Vector.prod • Защита сервера")

        log_channel = await _get_guard_channel(guild)
        log_msg = None
        if log_channel:
            try:
                log_msg = await log_channel.send(embed=embed)
                PENDING_CHANGES[change_id]["log_channel_id"] = log_channel.id
                PENDING_CHANGES[change_id]["log_message_id"] = log_msg.id
            except Exception as e:
                logger.error(f'Ошибка отправки лога guard: {e}')

        try:
            dm = await owner.create_dm()
            msg = await dm.send(embed=embed, view=view)
            PENDING_CHANGES[change_id]["message_id"] = msg.id
            PENDING_CHANGES[change_id]["channel_id"] = dm.id
        except discord.Forbidden:
            if log_channel:
                try:
                    await log_msg.edit(
                        content=f"{owner.mention} **В ЛС ЗАКРЫТЫ!** Нужно открыть ЛС!",
                        view=view)
                except Exception:
                    pass
        except Exception as e:
            logger.error(f'Ошибка отправки в ЛС владельца: {e}')

        ch = await _get_guard_channel(guild)
        if ch:
            log_embed = discord.Embed(
                title=f"🛡️ Guard: {action_str}",
                color=discord.Color.orange(),
                timestamp=datetime.now())
            log_embed.add_field(name="Объект", value=target_str, inline=True)
            log_embed.add_field(name="Кто изменил", value=moderator.mention, inline=True)
            if extra:
                log_embed.add_field(name="Детали", value=extra[:1024], inline=False)
            log_embed.set_footer(text=f"Change ID: {change_id} • Vector.prod • Защита сервера")
            try:
                await ch.send(embed=log_embed)
            except Exception:
                pass

    async def _try_revert_guild_channel_create(guild, entry, channel):
        try:
            await channel.delete(reason="Guard: несанкционированное создание канала")
            await _guard_log(guild, "🔄 Откат: канал удалён", discord.Color.green(), [
                ("Канал", f"#{channel.name} (`{channel.id}`)"),
                ("Создал", entry.user.mention if entry.user else "Неизвестно"),
                ("Причина отката", "Несанкционированное создание"),
            ])
            return True
        except Exception as e:
            logger.error(f'Ошибка отката создания канала: {e}')
            return False

    async def _try_revert_guild_channel_delete(guild, entry, channel_data):
        try:
            overwrites = {}
            for target_id, overwrite in channel_data.get("overwrites", {}).items():
                obj = guild.get_role(target_id) or guild.get_member(target_id)
                if obj:
                    overwrites[obj] = overwrite
            new_ch = await guild.create_text_channel(
                channel_data["name"],
                category=guild.get_channel(channel_data.get("category_id")),
                topic=channel_data.get("topic"),
                overwrites=overwrites,
                reason="Guard: откат удаления канала")
            await _guard_log(guild, "🔄 Откат: канал восстановлен", discord.Color.green(), [
                ("Канал", f"#{new_ch.mention} (`{new_ch.id}`)"),
                ("Удалил", entry.user.mention if entry.user else "Неизвестно"),
                ("Причина отката", "Восстановление удалённого канала"),
            ])
            return True
        except Exception as e:
            logger.error(f'Ошибка отката удаления канала: {e}')
            return False

    async def _try_revert_guild_role_create(guild, entry, role):
        try:
            await role.delete(reason="Guard: несанкционированное создание роли")
            await _guard_log(guild, "🔄 Откат: роль удалена", discord.Color.green(), [
                ("Роль", f"{role.mention} (`{role.id}`)"),
                ("Создал", entry.user.mention if entry.user else "Неизвестно"),
                ("Причина отката", "Несанкционированное создание"),
            ])
            return True
        except Exception as e:
            logger.error(f'Ошибка отката создания роли: {e}')
            return False

    async def _try_revert_guild_role_delete(guild, entry, role_data):
        try:
            perms = discord.Permissions(role_data["permissions"])
            new_role = await guild.create_role(
                name=role_data["name"],
                color=discord.Color(role_data["color"]),
                hoist=role_data["hoist"],
                mentionable=role_data["mentionable"],
                permissions=perms,
                reason="Guard: откат удаления роли")
            members = []
            for m in guild.members:
                for r in m.roles:
                    if r.id == role_data["id"]:
                        members.append(m)
                        break
            if members:
                await new_role.edit(members=members, reason="Guard: восстановление участников")
            await _guard_log(guild, "🔄 Откат: роль восстановлена", discord.Color.green(), [
                ("Роль", f"{new_role.mention} (`{new_role.id}`)"),
                ("Удалил", entry.user.mention if entry.user else "Неизвестно"),
                ("Причина отката", "Восстановление удалённой роли"),
            ])
            return True
        except Exception as e:
            logger.error(f'Ошибка отката удаления роли: {e}')
            return False

    @bot.listen('on_guild_channel_create')
    async def guard_channel_create(channel):
        try:
            if not isinstance(channel.guild, discord.Guild):
                return
            guild = channel.guild
            entry = await _check_audit_log(guild, discord.AuditLogAction.channel_create, channel.id)
            if not entry:
                return
            if entry.user == guild.me:
                return
            if _is_owner(entry.user):
                return
            global _change_counter
            _change_counter += 1
            cid = f"gc_{_change_counter}"
            PENDING_CHANGES[cid] = {"type": "channel_create", "channel_id": channel.id}
            await _send_approval_request(
                guild, cid, PENDING_CHANGES[cid],
                "Создание канала",
                f"#{channel.name} (`{channel.id}`)",
                entry.user,
                f"Тип: {channel.type}")
        except Exception as e:
            logger.error(f'Ошибка guard_channel_create: {e}')

    @bot.listen('on_guild_channel_delete')
    async def guard_channel_delete(channel):
        try:
            if not isinstance(channel.guild, discord.Guild):
                return
            guild = channel.guild
            entry = await _check_audit_log(guild, discord.AuditLogAction.channel_delete, channel.id)
            if not entry:
                return
            if entry.user == guild.me:
                return
            if _is_owner(entry.user):
                return
            overwrites = {}
            for target, overwrite in channel.overwrites.items():
                overwrites[target.id] = overwrite
            channel_data = {
                "name": channel.name,
                "id": channel.id,
                "type": str(channel.type),
                "topic": getattr(channel, "topic", None),
                "category_id": channel.category_id,
                "overwrites": overwrites,
            }
            success = await _try_revert_guild_channel_delete(guild, entry, channel_data)
            global _change_counter
            _change_counter += 1
            cid = f"gc_del_{_change_counter}"
            PENDING_CHANGES[cid] = {"type": "channel_delete", "channel_data": channel_data}
            if not success:
                await _send_approval_request(
                    guild, cid, PENDING_CHANGES[cid],
                    "Удаление канала (откат не удался)",
                    f"#{channel.name} (`{channel.id}`)",
                    entry.user,
                    "Канал не удалось восстановить автоматически")
        except Exception as e:
            logger.error(f'Ошибка guard_channel_delete: {e}')

    @bot.listen('on_guild_channel_update')
    async def guard_channel_update(before, after):
        try:
            if not isinstance(before.guild, discord.Guild):
                return
            guild = before.guild
            entry = await _check_audit_log(guild, discord.AuditLogAction.channel_update, after.id)
            if not entry:
                return
            if entry.user == guild.me:
                return
            if _is_owner(entry.user):
                return

            changes = []
            if before.name != after.name:
                changes.append(f"Название: `{before.name}` → `{after.name}`")
            if getattr(before, 'topic', None) != getattr(after, 'topic', None):
                changes.append(f"Тема: `{getattr(before, 'topic', None)}` → `{getattr(after, 'topic', None)}`")
            if before.overwrites != after.overwrites:
                changes.append("Изменены разрешения канала")

            if changes:
                global _change_counter
                _change_counter += 1
                cid = f"gc_upd_{_change_counter}"
                PENDING_CHANGES[cid] = {"type": "channel_update", "channel_id": after.id}
                await _send_approval_request(
                    guild, cid, PENDING_CHANGES[cid],
                    "Изменение канала",
                    f"#{after.name} (`{after.id}`)",
                    entry.user,
                    "\n".join(changes))
        except Exception as e:
            logger.error(f'Ошибка guard_channel_update: {e}')

    @bot.listen('on_guild_role_create')
    async def guard_role_create(role):
        try:
            if not isinstance(role.guild, discord.Guild):
                return
            guild = role.guild
            entry = await _check_audit_log(guild, discord.AuditLogAction.role_create, role.id)
            if not entry:
                return
            if entry.user == guild.me:
                return
            if _is_owner(entry.user):
                return
            global _change_counter
            _change_counter += 1
            cid = f"gr_{_change_counter}"
            PENDING_CHANGES[cid] = {"type": "role_create", "role_id": role.id}
            await _send_approval_request(
                guild, cid, PENDING_CHANGES[cid],
                "Создание роли",
                f"{role.mention} (`{role.id}`)",
                entry.user,
                f"Цвет: {role.color}\nПрава: {role.permissions}")
        except Exception as e:
            logger.error(f'Ошибка guard_role_create: {e}')

    @bot.listen('on_guild_role_delete')
    async def guard_role_delete(role):
        try:
            if not isinstance(role.guild, discord.Guild):
                return
            guild = role.guild
            entry = await _check_audit_log(guild, discord.AuditLogAction.role_delete, role.id)
            if not entry:
                return
            if entry.user == guild.me:
                return
            if _is_owner(entry.user):
                return
            role_data = {
                "name": role.name,
                "id": role.id,
                "color": role.color.value,
                "hoist": role.hoist,
                "mentionable": role.mentionable,
                "permissions": role.permissions.value,
            }
            success = await _try_revert_guild_role_delete(guild, entry, role_data)
            global _change_counter
            _change_counter += 1
            cid = f"gr_del_{_change_counter}"
            PENDING_CHANGES[cid] = {"type": "role_delete", "role_data": role_data}
            if not success:
                await _send_approval_request(
                    guild, cid, PENDING_CHANGES[cid],
                    "Удаление роли (откат не удался)",
                    f"`{role.name}` (`{role.id}`)",
                    entry.user,
                    "Роль не удалось восстановить автоматически")
        except Exception as e:
            logger.error(f'Ошибка guard_role_delete: {e}')

    @bot.listen('on_guild_role_update')
    async def guard_role_update(before, after):
        try:
            if not isinstance(before.guild, discord.Guild):
                return
            guild = before.guild
            entry = await _check_audit_log(guild, discord.AuditLogAction.role_update, after.id)
            if not entry:
                return
            if entry.user == guild.me:
                return
            if _is_owner(entry.user):
                return

            changes = []
            if before.name != after.name:
                changes.append(f"Название: `{before.name}` → `{after.name}`")
            if before.color != after.color:
                changes.append(f"Цвет: `{before.color}` → `{after.color}`")
            if before.permissions != after.permissions:
                changes.append("Изменены разрешения роли")
            if before.hoist != after.hoist:
                changes.append(f"Отображение: `{before.hoist}` → `{after.hoist}`")
            if before.mentionable != after.mentionable:
                changes.append(f"Упоминаемость: `{before.mentionable}` → `{after.mentionable}`")
            if before.position != after.position:
                changes.append(f"Позиция: `{before.position}` → `{after.position}`")

            if changes:
                global _change_counter
                _change_counter += 1
                cid = f"gr_upd_{_change_counter}"
                PENDING_CHANGES[cid] = {"type": "role_update", "role_id": after.id}
                await _send_approval_request(
                    guild, cid, PENDING_CHANGES[cid],
                    "Изменение роли",
                    f"{after.mention} (`{after.id}`)",
                    entry.user,
                    "\n".join(changes))
        except Exception as e:
            logger.error(f'Ошибка guard_role_update: {e}')

    @bot.listen('on_guild_update')
    async def guard_guild_update(before, after):
        try:
            if not isinstance(before, discord.Guild):
                return
            entry = await _check_audit_log(after, discord.AuditLogAction.guild_update, after.id)
            if not entry:
                return
            if entry.user == after.me:
                return
            if _is_owner(entry.user):
                return

            changes = []
            if before.name != after.name:
                changes.append(f"Название сервера: `{before.name}` → `{after.name}`")
            if before.icon != after.icon:
                changes.append("Иконка сервера изменена")
            if before.splash != after.splash:
                changes.append("Фон сервера изменён")
            if before.verification_level != after.verification_level:
                changes.append(f"Уровень верификации: `{before.verification_level}` → `{after.verification_level}`")
            if before.default_notifications != after.default_notifications:
                changes.append(f"Уведомления по умолчанию: `{before.default_notifications}` → `{after.default_notifications}`")
            if before.mfa_level != after.mfa_level:
                changes.append(f"Уровень 2FA: `{before.mfa_level}` → `{after.mfa_level}`")
            if before.vanity_url_code != after.vanity_url_code:
                changes.append(f"Vanity URL: `{before.vanity_url_code}` → `{after.vanity_url_code}`")
            if before.system_channel != after.system_channel:
                changes.append("Системный канал изменён")
            if before.rules_channel != after.rules_channel:
                changes.append("Канал правил изменён")

            if changes:
                global _change_counter
                _change_counter += 1
                cid = f"gu_{_change_counter}"
                PENDING_CHANGES[cid] = {"type": "guild_update", "guild_id": after.id}
                await _send_approval_request(
                    after, cid, PENDING_CHANGES[cid],
                    "Изменение сервера",
                    f"`{after.name}` (`{after.id}`)",
                    entry.user,
                    "\n".join(changes))
        except Exception as e:
            logger.error(f'Ошибка guard_guild_update: {e}')

    @bot.listen('on_member_update')
    async def guard_member_update(before, after):
        try:
            if not isinstance(before.guild, discord.Guild):
                return
            guild = before.guild
            if before.roles == after.roles:
                return
            entry = await _check_audit_log(guild, discord.AuditLogAction.member_role_update, after.id)
            if not entry:
                return
            if entry.user == guild.me:
                return
            if _is_owner(entry.user):
                return

            added = set(after.roles) - set(before.roles)
            removed = set(before.roles) - set(after.roles)

            changes = []
            for r in added:
                if r.name != "@everyone":
                    changes.append(f"+{r.mention}")
            for r in removed:
                if r.name != "@everyone":
                    changes.append(f"-{r.mention}")

            if changes:
                global _change_counter
                _change_counter += 1
                cid = f"mu_{_change_counter}"
                PENDING_CHANGES[cid] = {"type": "member_role_update", "member_id": after.id}
                await _send_approval_request(
                    guild, cid, PENDING_CHANGES[cid],
                    "Изменение ролей участника",
                    f"{after.mention} (`{after.id}`)",
                    entry.user,
                    "\n".join(changes))
        except Exception as e:
            logger.error(f'Ошибка guard_member_update: {e}')

    class GuardApprovalView(discord.ui.View):
        def __init__(self, change_id):
            super().__init__(timeout=None)
            self.change_id = change_id

        @discord.ui.button(label="✅ Одобрить", style=discord.ButtonStyle.success, custom_id="guard_approve")
        async def approve(self, interaction, button):
            if interaction.user.id != interaction.guild.owner_id:
                await interaction.response.send_message("❌ Только владелец сервера может одобрять.", ephemeral=True)
                return
            await interaction.response.send_message("✅ Изменение одобрено.", ephemeral=True)
            data = PENDING_CHANGES.get(self.change_id)
            if data:
                log_ch_id = data.get("log_channel_id")
                log_msg_id = data.get("log_message_id")
                if log_ch_id and log_msg_id:
                    try:
                        ch = interaction.client.get_channel(log_ch_id) or await interaction.client.fetch_channel(log_ch_id)
                        msg = await ch.fetch_message(log_msg_id)
                        await msg.delete()
                    except Exception:
                        pass
                del PENDING_CHANGES[self.change_id]
            for child in self.children:
                child.disabled = True
            try:
                await interaction.edit_original_response(view=self)
            except Exception:
                pass

        @discord.ui.button(label="❌ Отклонить", style=discord.ButtonStyle.danger, custom_id="guard_deny")
        async def deny(self, interaction, button):
            if interaction.user.id != interaction.guild.owner_id:
                await interaction.response.send_message("❌ Только владелец сервера может отклонять.", ephemeral=True)
                return
            await interaction.response.send_message("❌ Изменение отклонено.", ephemeral=True)
            data = PENDING_CHANGES.get(self.change_id)
            if data:
                log_ch_id = data.get("log_channel_id")
                log_msg_id = data.get("log_message_id")
                if log_ch_id and log_msg_id:
                    try:
                        ch = interaction.client.get_channel(log_ch_id) or await interaction.client.fetch_channel(log_ch_id)
                        msg = await ch.fetch_message(log_msg_id)
                        await msg.delete()
                    except Exception:
                        pass
                del PENDING_CHANGES[self.change_id]
            for child in self.children:
                child.disabled = True
            try:
                await interaction.edit_original_response(view=self)
            except Exception:
                pass

    bot.add_view(GuardApprovalView(0))

    logger.info("Модуль защиты сервера (guard) загружен")
