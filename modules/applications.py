"""
Модуль системы подачи заявок на роли
- !apply-setup <название> <роль> [канал] — создать/обновить заявку
- !apply-panel [канал] — панель выбора заявки (select-меню)
- !apply-list — список заявок
- !apply-remove <название> — удалить заявку
- Пользователь выбирает заявку → модальное окно → заявка в канале
- Админы принимают (выдаётся роль) / отклоняют
"""

import logging
import re
from datetime import datetime

import discord
from discord import app_commands
from discord.ext import commands

logger = logging.getLogger('discord_bot.applications')

EMBED_COLOR = 0x9000FF
STATUS_PENDING = '📝 На рассмотрении'
STATUS_ACCEPTED = '✅ Принято'
STATUS_REJECTED = '❌ Отклонено'


async def _get_applications(bot, guild_id):
    cursor = await bot.db.execute(
        "SELECT id, name, role_id, channel_id FROM applications WHERE guild_id = ? ORDER BY id",
        (guild_id,)
    )
    rows = await cursor.fetchall()
    return [{'id': r[0], 'name': r[1], 'role_id': r[2], 'channel_id': r[3]} for r in rows]


async def _get_application(bot, app_id):
    cursor = await bot.db.execute(
        "SELECT id, name, role_id, channel_id FROM applications WHERE id = ?",
        (app_id,)
    )
    row = await cursor.fetchone()
    if not row:
        return None
    return {'id': row[0], 'name': row[1], 'role_id': row[2], 'channel_id': row[3]}


async def _is_staff(member):
    return bool(member.guild_permissions.manage_roles or member.guild_permissions.administrator)


class ApplyModal(discord.ui.Modal, title="📝 Подача заявки"):
    """Модальное окно анкеты заявки"""

    about = discord.ui.TextInput(
        label="Расскажи о себе",
        placeholder="Почему ты хочешь получить эту роль?",
        style=discord.TextStyle.paragraph,
        max_length=1500,
        required=True,
    )

    def __init__(self, app_info):
        super().__init__()
        self.app_info = app_info

    async def on_submit(self, interaction):
        guild = interaction.guild
        channel = guild.get_channel(self.app_info['channel_id'])
        if channel is None:
            await interaction.response.send_message(
                "❌ Канал приёма заявок не найден. Обратись к администрации.", ephemeral=True
            )
            return

        embed = discord.Embed(
            title=f"📝 Заявка на роль: {self.app_info['name']}",
            description=self.about.value,
            color=EMBED_COLOR,
            timestamp=datetime.now(),
        )
        embed.set_author(name=f"От {interaction.user.display_name}", icon_url=interaction.user.display_avatar.url)
        embed.add_field(name="Статус", value=STATUS_PENDING, inline=False)
        embed.set_footer(text=f"ID: {interaction.user.id} • {datetime.now().strftime('%d.%m.%Y %H:%M')}")

        msg = await channel.send(embed=embed, view=ApplyModerationView())
        await msg.add_reaction('👍')
        await msg.add_reaction('👎')

        cursor = await interaction.client.db.execute(
            "INSERT INTO apply_submissions (message_id, user_id, guild_id, application_id) VALUES (?, ?, ?, ?)",
            (msg.id, interaction.user.id, guild.id, self.app_info['id'])
        )
        await interaction.client.db.commit()

        await interaction.response.send_message(
            "📨 Ваша заявка отправлена. Ожидайте, пока администрация рассмотрит её.", ephemeral=True
        )
        logger.info(f'{interaction.user} подал заявку на {self.app_info["name"]}')


class ApplyModerationView(discord.ui.View):
    """Кнопки одобрения/отклонения заявки (данные берём из БД по message_id)"""

    def __init__(self):
        super().__init__(timeout=None)

    async def _get_submission_app(self, interaction):
        """Достаёт application по message_id заявки"""
        cursor = await interaction.client.db.execute(
            "SELECT application_id, user_id FROM apply_submissions WHERE message_id = ?",
            (interaction.message.id,)
        )
        row = await cursor.fetchone()
        if not row:
            return None, None
        app = await _get_application(interaction.client, row[0])
        return app, row[1]

    async def _resolve(self, interaction, accepted):
        if not await _is_staff(interaction.user):
            await interaction.response.send_message(
                "❌ Только администрация может рассматривать заявки.", ephemeral=True
            )
            return

        app_info, author_id = await _get_submission_app(interaction)
        if app_info is None:
            await interaction.response.send_message(
                "❌ Не удалось найти данные заявки.", ephemeral=True
            )
            return

        embed = interaction.message.embeds[0]
        status = STATUS_ACCEPTED if accepted else STATUS_REJECTED
        color = discord.Color.green() if accepted else discord.Color.red()
        embed.color = color
        embed.set_field_at(0, name="Статус", value=status, inline=False)
        embed.set_footer(
            text=f"{embed.footer.text if embed.footer.text else ''} • {interaction.user.display_name}"
        )
        await interaction.response.edit_message(embed=embed, view=None)

        try:
            await interaction.client.db.execute(
                "UPDATE apply_submissions SET status = ? WHERE message_id = ?",
                (status, interaction.message.id)
            )
            await interaction.client.db.commit()
        except Exception as e:
            logger.error(f'Ошибка обновления статуса заявки: {e}')

        role = interaction.guild.get_role(app_info['role_id'])
        author = interaction.guild.get_member(author_id) if author_id else None

        # Выдаём роль автору при принятии
        if author and accepted and role:
            try:
                await author.add_roles(role, reason=f"Заявка одобрена {interaction.user}")
            except Exception as e:
                logger.error(f'Ошибка выдачи роли: {e}')

        # Уведомляем автора
        if author:
            try:
                msg = discord.Embed(
                    title=f"📝 Статус вашей заявки: {app_info['name']}",
                    description=f"Ваша заявка: **{status}**",
                    color=color,
                )
                if role and accepted:
                    msg.add_field(name="Выдана роль", value=role.mention, inline=False)
                msg.set_footer(text=interaction.guild.name)
                await author.send(embed=msg)
            except discord.Forbidden:
                pass
            except Exception as e:
                logger.error(f'Ошибка уведомления автора заявки: {e}')

        logger.info(f'{interaction.user} {status} заявку {app_info["name"]}')

    @discord.ui.button(label="✅ Принять", style=discord.ButtonStyle.success, custom_id="apply_approve")
    async def accept(self, interaction, button):
        await self._resolve(interaction, True)

    @discord.ui.button(label="❌ Отклонить", style=discord.ButtonStyle.danger, custom_id="apply_reject")
    async def reject(self, interaction, button):
        await self._resolve(interaction, False)


class ApplySelect(discord.ui.Select):
    """Select-меню выбора заявки на панели"""

    def __init__(self, apps=None):
        if apps:
            options = [
                discord.SelectOption(label=app['name'][:80], value=str(app['id']))
                for app in apps[:25]
            ]
        else:
            options = [discord.SelectOption(label="Заявки не настроены", value="0")]
        super().__init__(
            placeholder="Выбери заявку...",
            options=options,
            custom_id="apply_select",
        )

    async def callback(self, interaction):
        try:
            app_id = int(self.values[0])
        except (ValueError, IndexError):
            await interaction.response.send_message("❌ Заявки ещё не настроены.", ephemeral=True)
            return
        app_info = await _get_application(interaction.client, app_id)
        if app_info is None:
            await interaction.response.send_message("❌ Заявка больше не существует.", ephemeral=True)
            return
        await interaction.response.send_modal(ApplyModal(app_info))


class ApplyPanelView(discord.ui.View):
    """Панель с select-меню подачи заявки"""

    def __init__(self, apps=None):
        super().__init__(timeout=None)
        self.add_item(ApplySelect(apps))


def setup_applications(bot):
    """Настройка системы подачи заявок"""

    @bot.hybrid_command(name="apply-setup", description="Создать/обновить заявку на роль")
    @app_commands.describe(name="Название заявки (например: media, клан)", role="Роль, которая выдаётся", channel="Канал приёма заявок (по умолчанию текущий)")
    @commands.has_permissions(manage_roles=True)
    async def apply_setup_cmd(ctx: commands.Context, name: str, role: discord.Role, channel: discord.TextChannel = None):
        """Настройка заявки"""
        try:
            channel = channel or ctx.channel
            name_lower = name.lower()
            cursor = await bot.db.execute(
                "SELECT id FROM applications WHERE guild_id = ? AND name = ?",
                (ctx.guild.id, name_lower)
            )
            existing = await cursor.fetchone()
            if existing:
                await bot.db.execute(
                    "UPDATE applications SET role_id = ?, channel_id = ? WHERE id = ?",
                    (role.id, channel.id, existing[0])
                )
                await bot.db.commit()
                await ctx.send(f"✅ Заявка **{name}** обновлена (роль {role.mention}, канал {channel.mention}).", ephemeral=True)
            else:
                await bot.db.execute(
                    "INSERT INTO applications (guild_id, name, role_id, channel_id) VALUES (?, ?, ?, ?)",
                    (ctx.guild.id, name_lower, role.id, channel.id)
                )
                await bot.db.commit()
                await ctx.send(f"✅ Заявка **{name}** создана (роль {role.mention}, канал {channel.mention}).", ephemeral=True)
            logger.info(f'{ctx.author} настроил заявку {name} (роль {role.name})')
        except Exception as e:
            await ctx.send(f"❌ Ошибка: {e}", ephemeral=True)
            logger.error(f'Ошибка apply-setup: {e}')

    @bot.hybrid_command(name="apply-panel", description="Разместить панель подачи заявок в канале")
    @app_commands.describe(channel="Канал для панели (по умолчанию текущий)")
    @commands.has_permissions(manage_roles=True)
    async def apply_panel_cmd(ctx: commands.Context, channel: discord.TextChannel = None):
        """Размещение панели"""
        try:
            channel = channel or ctx.channel
            apps = await _get_applications(bot, ctx.guild.id)
            if not apps:
                await ctx.send(
                    "❌ Заявок нет. Сначала настрой: `!apply-setup <название> @роль #канал`.",
                    ephemeral=True
                )
                return

            # Удаляем старые панели в канале
            try:
                async for old in channel.history(limit=50):
                    if old.author.id == bot.user.id and old.embeds and old.embeds[0].title == "📝 Подача заявки":
                        await old.delete()
            except Exception:
                pass

            embed = discord.Embed(
                title="📝 Подача заявки",
                description="Выбери заявку в меню ниже, чтобы подать анкету.\n"
                            "Администрация рассмотрит её и выдаст роль в случае одобрения.",
                color=EMBED_COLOR,
            )
            await channel.send(embed=embed, view=ApplyPanelView(apps))
            await ctx.send(f"✅ Панель заявок размещена в {channel.mention}.", ephemeral=True)
            logger.info(f'{ctx.author} разместил панель заявок в {channel.name}')
        except Exception as e:
            await ctx.send(f"❌ Ошибка: {e}", ephemeral=True)
            logger.error(f'Ошибка apply-panel: {e}')

    @bot.hybrid_command(name="apply-list", description="Список заявок на роли")
    @commands.has_permissions(manage_roles=True)
    async def apply_list_cmd(ctx: commands.Context):
        """Список заявок"""
        try:
            apps = await _get_applications(bot, ctx.guild.id)
            embed = discord.Embed(
                title="📝 Заявки на роли",
                color=EMBED_COLOR,
                timestamp=datetime.now()
            )
            if not apps:
                embed.description = "Заявок нет. Настрой через `!apply-setup`."
            else:
                for a in apps:
                    role = ctx.guild.get_role(a['role_id'])
                    chan = ctx.guild.get_channel(a['channel_id'])
                    embed.add_field(
                        name=f"**{a['name']}**",
                        value=f"Роль: {role.mention if role else '❓'} | Канал: {chan.mention if chan else '❓'}",
                        inline=False
                    )
            await ctx.send(embed=embed, ephemeral=True)
        except Exception as e:
            await ctx.send(f"❌ Ошибка: {e}", ephemeral=True)
            logger.error(f'Ошибка apply-list: {e}')

    @bot.hybrid_command(name="apply-remove", description="Удалить заявку")
    @app_commands.describe(name="Название заявки")
    @commands.has_permissions(manage_roles=True)
    async def apply_remove_cmd(ctx: commands.Context, name: str):
        """Удаление заявки"""
        try:
            cursor = await bot.db.execute(
                "DELETE FROM applications WHERE guild_id = ? AND name = ?",
                (ctx.guild.id, name.lower())
            )
            await bot.db.commit()
            if cursor.rowcount:
                await ctx.send(f"✅ Заявка **{name}** удалена.", ephemeral=True)
            else:
                await ctx.send(f"❌ Заявка **{name}** не найдена.", ephemeral=True)
        except Exception as e:
            await ctx.send(f"❌ Ошибка: {e}", ephemeral=True)
            logger.error(f'Ошибка apply-remove: {e}')

    # Persistent views: select на панели и кнопки модерации
    bot.add_view(ApplyModerationView())
    bot.add_view(ApplyPanelView())
    logger.info('Модуль подачи заявок загружен (persistent views: apply_select, apply_approve, apply_reject)')
