"""
Модуль модерации для Discord бота
Команды: clear, kick, ban, mute, timeout, untimeout, report
"""

import discord
from discord.ext import commands
from discord import app_commands
import asyncio
from datetime import datetime, timedelta
import logging

logger = logging.getLogger('discord_bot.moderation')

def setup_moderation(bot):
    """Настройка команд модерации"""
    
    @bot.hybrid_command(name="clear", description="Очистить сообщения в канале (1-100)")
    @app_commands.describe(amount="Количество сообщений для очистки (1-100)")
    @commands.has_permissions(manage_messages=True)
    async def clear_cmd(ctx: commands.Context, amount: int = 10):
        """Очистка сообщений в канале"""
        try:
            if amount < 1 or amount > 100:
                await ctx.send("❌ Количество сообщений должно быть от 1 до 100", ephemeral=True)
                return
                
            # Удаляем сообщения
            try:
                deleted = await ctx.channel.purge(limit=amount + 1)  # +1 для команды
            except discord.NotFound:
                # Некоторые сообщения уже были удалены - попытка всё равно удалась частично
                deleted = []
            
            embed = discord.Embed(
                title="✅ Очистка сообщений",
                description=f"Удалено **{len(deleted)-1 if deleted else 0}** сообщений",
                color=discord.Color.green(),
                timestamp=datetime.now()
            )
            embed.set_footer(text=f"Модератор: {ctx.author.name}")
            
            msg = await ctx.send(embed=embed)
            await asyncio.sleep(5)
            try:
                await msg.delete()
            except discord.NotFound:
                pass
            
            logger.info(f'{ctx.author} очистил {amount} сообщений в {ctx.channel.name}')
            
        except Exception as e:
            await ctx.send(f"❌ Ошибка при очистке: {e}", ephemeral=True)
            logger.error(f'Ошибка очистки: {e}')
    
    @bot.hybrid_command(name="kick", description="Кикнуть участника с сервера")
    @app_commands.describe(member="Участник для кика", reason="Причина кика")
    @commands.has_permissions(kick_members=True)
    async def kick_cmd(ctx: commands.Context, member: discord.Member, *, reason: str = "Не указана"):
        """Кик участника"""
        try:
            if member == ctx.author:
                await ctx.send("❌ Нельзя кикнуть самого себя", ephemeral=True)
                return
                
            if member.top_role >= ctx.author.top_role:
                await ctx.send("❌ Нельзя кикнуть участника с равной или высшей ролью", ephemeral=True)
                return
                
            await member.kick(reason=reason)
            
            embed = discord.Embed(
                title="🚪 Участник кикнут",
                color=discord.Color.red(),
                timestamp=datetime.now()
            )
            embed.add_field(name="Участник", value=f"{member.mention} ({member.name})", inline=True)
            embed.add_field(name="Модератор", value=ctx.author.mention, inline=True)
            embed.add_field(name="Причина", value=reason, inline=False)
            
            await ctx.send(embed=embed)

            # Лог в канал логов
            mod_log = getattr(bot, 'mod_log', None)
            if mod_log:
                try:
                    await mod_log(bot, ctx.guild, "Кик", "👢 Участник кикнут", 0xE67E22, member, ctx.author, reason)
                except Exception as e:
                    logger.error(f'Ошибка лога кика: {e}')
            
            # Уведомляем участника
            try:
                await member.send(f"Вы были кикнуты с сервера **{ctx.guild.name}**\n**Причина:** {reason}")
            except:
                pass
                
            logger.info(f'{ctx.author} кикнул {member.name} по причине: {reason}')
            
        except Exception as e:
            await ctx.send(f"❌ Ошибка при кике: {e}", ephemeral=True)
            logger.error(f'Ошибка кика: {e}')
    
    @bot.hybrid_command(name="ban", description="Забанить участника на сервере")
    @app_commands.describe(member="Участник для бана", reason="Причина бана")
    @commands.has_permissions(ban_members=True)
    async def ban_cmd(ctx: commands.Context, member: discord.Member, *, reason: str = "Не указана"):
        """Бан участника"""
        try:
            if member == ctx.author:
                await ctx.send("❌ Нельзя забанить самого себя", ephemeral=True)
                return
                
            if member.top_role >= ctx.author.top_role:
                await ctx.send("❌ Нельзя забанить участника с равной или высшей ролью", ephemeral=True)
                return
                
            await member.ban(reason=reason, delete_message_days=7)
            
            embed = discord.Embed(
                title="🔨 Участник забанен",
                color=discord.Color.dark_red(),
                timestamp=datetime.now()
            )
            embed.add_field(name="Участник", value=f"{member.mention} ({member.name})", inline=True)
            embed.add_field(name="Модератор", value=ctx.author.mention, inline=True)
            embed.add_field(name="Причина", value=reason, inline=False)
            
            await ctx.send(embed=embed)

            # Лог в канал логов
            mod_log = getattr(bot, 'mod_log', None)
            if mod_log:
                try:
                    await mod_log(bot, ctx.guild, "Бан", "🔨 Участник забанен", 0xE74C3C, member, ctx.author, reason)
                except Exception as e:
                    logger.error(f'Ошибка лога бана: {e}')
            
            # Уведомляем участника
            try:
                await member.send(f"Вы были забанены на сервере **{ctx.guild.name}**\n**Причина:** {reason}")
            except:
                pass
                
            logger.info(f'{ctx.author} забанил {member.name} по причине: {reason}')
            
        except Exception as e:
            await ctx.send(f"❌ Ошибка при бане: {e}", ephemeral=True)
            logger.error(f'Ошибка бана: {e}')
    
    @bot.hybrid_command(name="mute", description="Выдать мут участнику (роль)")
    @app_commands.describe(member="Участник для мута", minutes="Длительность мута в минутах", reason="Причина мута")
    @commands.has_permissions(manage_roles=True)
    async def mute_cmd(ctx: commands.Context, member: discord.Member, minutes: int = 10, *, reason: str = "Не указана"):
        """Мут участника (через роль)"""
        try:
            if member == ctx.author:
                await ctx.send("❌ Нельзя выдать мут самому себе", ephemeral=True)
                return
            
            if member.top_role >= ctx.author.top_role:
                await ctx.send("❌ Нельзя выдать мут участнику с равной или высшей ролью", ephemeral=True)
                return
            
            # Поиск или создание роли "Muted"
            muted_role = discord.utils.get(ctx.guild.roles, name="Muted")
            if not muted_role:
                muted_role = await ctx.guild.create_role(
                    name="Muted",
                    color=discord.Color.dark_gray(),
                    reason="Роль для мута участников"
                )
                
                # Настройка прав для роли
                for channel in ctx.guild.channels:
                    await channel.set_permissions(muted_role,
                        send_messages=False,
                        add_reactions=False,
                        speak=False
                    )
            
            await member.add_roles(muted_role, reason=reason)
            
            embed = discord.Embed(
                title="🔇 Участнику выдан мут",
                color=discord.Color.dark_gray(),
                timestamp=datetime.now()
            )
            embed.add_field(name="Участник", value=member.mention, inline=True)
            embed.add_field(name="Модератор", value=ctx.author.mention, inline=True)
            embed.add_field(name="Длительность", value=f"{minutes} минут", inline=True)
            embed.add_field(name="Причина", value=reason, inline=False)
            
            await ctx.send(embed=embed)
            logger.info(f'{ctx.author} выдал мут {member.name} на {minutes} минут по причине: {reason}')

            # Лог в канал логов
            mod_log = getattr(bot, 'mod_log', None)
            if mod_log:
                try:
                    await mod_log(bot, ctx.guild, f"Мут ({minutes} мин)", "🔇 Участник замучен", 0x9B59B6, member, ctx.author, reason)
                except Exception as e:
                    logger.error(f'Ошибка лога мута: {e}')
            
            # Автоматическое снятие мута
            async def remove_mute_after_time():
                await asyncio.sleep(minutes * 60)
                try:
                    member_obj = ctx.guild.get_member(member.id)
                    if member_obj and muted_role in member_obj.roles:
                        await member_obj.remove_roles(muted_role, reason="Автоматическое снятие мута")
                        try:
                            await member_obj.send(f"Ваш мут на сервере {ctx.guild.name} истёк.")
                        except:
                            pass
                        logger.info(f'Мут снят с {member.name}')
                except Exception as e:
                    logger.error(f'Ошибка при автоматическом снятии мута: {e}')
            
            bot.loop.create_task(remove_mute_after_time())
            
        except Exception as e:
            await ctx.send(f"❌ Ошибка при выдаче мута: {e}", ephemeral=True)
            logger.error(f'Ошибка мута: {e}')
    
    @bot.hybrid_command(name="timeout", description="Выдать таймаут участнику (Discord)")
    @app_commands.describe(member="Участник для таймаута", minutes="Длительность таймаута (1-40320)", reason="Причина таймаута")
    @commands.has_permissions(moderate_members=True)
    async def timeout_cmd(ctx: commands.Context, member: discord.Member, minutes: int = 10, *, reason: str = "Не указана"):
        """Таймаут участника (нативный Discord)"""
        try:
            if member == ctx.author:
                await ctx.send("❌ Нельзя выдать таймаут самому себе", ephemeral=True)
                return
            
            if member.top_role >= ctx.author.top_role:
                await ctx.send("❌ Нельзя выдать таймаут участнику с равной или высшей ролью", ephemeral=True)
                return
            
            if minutes < 1 or minutes > 40320:
                await ctx.send("❌ Длительность таймаута должна быть от 1 до 40320 минут (макс. 28 дней)", ephemeral=True)
                return
            
            # Выдаем таймаут
            timeout_until = datetime.now() + timedelta(minutes=minutes)
            await member.timeout(timeout_until, reason=reason)
            
            embed = discord.Embed(
                title="⏸️ Участнику выдан таймаут",
                color=discord.Color.orange(),
                timestamp=datetime.now()
            )
            embed.add_field(name="Участник", value=member.mention, inline=True)
            embed.add_field(name="Модератор", value=ctx.author.mention, inline=True)
            embed.add_field(name="Длительность", value=f"{minutes} минут", inline=True)
            embed.add_field(name="Истекает", value=timeout_until.strftime("%d.%m.%Y %H:%M"), inline=True)
            embed.add_field(name="Причина", value=reason, inline=False)
            
            await ctx.send(embed=embed)
            logger.info(f'{ctx.author} выдал таймаут {member.name} на {minutes} минут по причине: {reason}')

            # Лог в канал логов
            mod_log = getattr(bot, 'mod_log', None)
            if mod_log:
                try:
                    await mod_log(bot, ctx.guild, f"Тайм-аут ({minutes} мин)", "🔇 Участник в тайм-ауте", 0x9B59B6, member, ctx.author, reason)
                except Exception as e:
                    logger.error(f'Ошибка лога таймаута: {e}')
            
        except Exception as e:
            await ctx.send(f"❌ Ошибка при выдаче таймаута: {e}", ephemeral=True)
            logger.error(f'Ошибка таймаута: {e}')
    
    @bot.hybrid_command(name="untimeout", description="Снять таймаут с участника")
    @app_commands.describe(member="Участник для снятия таймаута", reason="Причина снятия")
    @commands.has_permissions(moderate_members=True)
    async def untimeout_cmd(ctx: commands.Context, member: discord.Member, *, reason: str = "Не указана"):
        """Снятие таймаута с участника"""
        try:
            if not member.is_timed_out():
                await ctx.send("❌ У участника нет активного таймаута", ephemeral=True)
                return
            
            await member.timeout(None, reason=reason)
            
            embed = discord.Embed(
                title="✅ Таймаут снят",
                color=discord.Color.green(),
                timestamp=datetime.now()
            )
            embed.add_field(name="Участник", value=member.mention, inline=True)
            embed.add_field(name="Модератор", value=ctx.author.mention, inline=True)
            embed.add_field(name="Причина", value=reason, inline=False)
            
            await ctx.send(embed=embed)
            logger.info(f'{ctx.author} снял таймаут с {member.name} по причине: {reason}')

            # Лог в канал логов
            mod_log = getattr(bot, 'mod_log', None)
            if mod_log:
                try:
                    await mod_log(bot, ctx.guild, "Снят тайм-аут", "🔓 Тайм-аут снят", 0x1ABC9C, member, ctx.author, reason)
                except Exception as e:
                    logger.error(f'Ошибка лога снятия таймаута: {e}')
            
        except Exception as e:
            await ctx.send(f"❌ Ошибка при снятии таймаута: {e}", ephemeral=True)
            logger.error(f'Ошибка снятия таймаута: {e}')
    
    @bot.hybrid_command(name="report", description="Отправить жалобу на участника")
    @app_commands.describe(member="Участник для жалобы", reason="Причина жалобы")
    async def report_cmd(ctx: commands.Context, member: discord.Member, *, reason: str):
        """Жалоба на участника"""
        try:
            # Ищем текстовый канал для жалоб по ключевым словам
            report_channel = None
            for channel in ctx.guild.text_channels:
                name = (channel.name or '').lower()
                if any(kw in name for kw in ('жалоб', 'report')):
                    report_channel = channel
                    break

            embed = discord.Embed(
                title="🚨 Новая жалоба",
                color=discord.Color.red(),
                timestamp=datetime.now()
            )
            embed.add_field(name="Жалобщик", value=ctx.author.mention, inline=True)
            embed.add_field(name="Нарушитель", value=member.mention, inline=True)
            embed.add_field(name="Канал", value=ctx.channel.mention, inline=True)
            embed.add_field(name="Причина", value=reason, inline=False)
            embed.set_footer(text=f"ID жалобщика: {ctx.author.id} | ID нарушителя: {member.id}")

            if report_channel:
                try:
                    await report_channel.send(
                        f"<@&{ctx.guild.default_role.id}>",
                        embed=embed,
                        allowed_mentions=discord.AllowedMentions(roles=True)
                    )
                except discord.Forbidden:
                    # Нет прав писать в канал жалоб — отправляем лично
                    try:
                        await ctx.author.send("🚨 Ваша жалоба не была доставлена: у бота нет прав в канале жалоб.", embed=embed)
                        await ctx.send("⚠️ Жалоба не доставлена: у бота нет прав в канале жалоб.", ephemeral=True)
                    except discord.Forbidden:
                        await ctx.send("⚠️ Не удалось отправить жалобу: бот не может писать в канал жалоб и в личные сообщения.", ephemeral=True)
                logger.info(f'{ctx.author} пожаловался на {member.name}: {reason}')
                return

            # Канал жалоб не найден
            try:
                await ctx.author.send(
                    "⚠️ Канал для жалоб не настроен на сервере. "
                    "Создайте текстовый канал с названием, содержащим «жалоб» или «report», "
                    "например #жалобы.", embed=embed
                )
                await ctx.send("⚠️ Канал для жалоб не найден на сервере. Жалоба отправлена вам в личные сообщения.", ephemeral=True)
            except discord.Forbidden:
                await ctx.send("⚠️ Канал для жалоб не найден. Создайте канал #жалобы, чтобы жалобы уходили модераторам.", ephemeral=True)
            logger.info(f'{ctx.author} попытался пожаловаться на {member.name}, но канал жалоб не найден')

        except Exception as e:
            await ctx.send(f"❌ Ошибка при отправке жалобы: {e}", ephemeral=True)
            logger.error(f'Ошибка жалобы: {e}')
    
    @bot.hybrid_command(name="unban", description="Разбанить участника по ID или имени")
    @app_commands.describe(user="ID или имя участника", reason="Причина разбана")
    @commands.has_permissions(ban_members=True)
    async def unban_cmd(ctx: commands.Context, user: str, *, reason: str = "Не указана"):
        """Разбан участника"""
        try:
            banned = [entry async for entry in ctx.guild.bans()]
            target = None
            for entry in banned:
                u = entry.user
                if str(u.id) == user or u.name.lower() == user.lower() or str(u).lower() == user.lower():
                    target = u
                    break

            if target is None:
                await ctx.send("❌ Участник не найден в списке банов. Укажи ID или имя (например, `!unban 1234567890`).", ephemeral=True)
                return

            await ctx.guild.unban(target, reason=reason)
            embed = discord.Embed(
                title="✅ Участник разбанен",
                color=discord.Color.green(),
                timestamp=datetime.now()
            )
            embed.add_field(name="Участник", value=f"{target.mention} ({target.name})", inline=True)
            embed.add_field(name="Модератор", value=ctx.author.mention, inline=True)
            embed.add_field(name="Причина", value=reason, inline=False)
            await ctx.send(embed=embed)
            logger.info(f'{ctx.author} разбанил {target.name} по причине: {reason}')

            # Лог в канал логов
            mod_log = getattr(bot, 'mod_log', None)
            if mod_log:
                try:
                    await mod_log(bot, ctx.guild, "Разбан", "⚖️ Снят бан", 0x2ECC71, target, ctx.author, reason)
                except Exception as e:
                    logger.error(f'Ошибка лога разбана: {e}')
        except Exception as e:
            await ctx.send(f"❌ Ошибка при разбане: {e}", ephemeral=True)
            logger.error(f'Ошибка разбана: {e}')

    @bot.hybrid_command(name="warn", description="Выдать предупреждение участнику")
    @app_commands.describe(member="Участник для предупреждения", reason="Причина предупреждения")
    @commands.has_permissions(manage_messages=True)
    async def warn_cmd(ctx: commands.Context, member: discord.Member, *, reason: str = "Не указана"):
        """Выдать предупреждение"""
        try:
            if member == ctx.author:
                await ctx.send("❌ Нельзя выдать предупреждение самому себе", ephemeral=True)
                return
            if member.top_role >= ctx.author.top_role:
                await ctx.send("❌ Нельзя выдать предупреждение участнику с равной или высшей ролью", ephemeral=True)
                return

            cursor = await bot.db.execute(
                "INSERT INTO warnings (user_id, guild_id, moderator_id, reason) VALUES (?, ?, ?, ?)",
                (member.id, ctx.guild.id, ctx.author.id, reason)
            )
            await bot.db.commit()
            warn_id = cursor.lastrowid

            # Получаем текущее количество предупреждений
            cursor = await bot.db.execute(
                "SELECT COUNT(*) FROM warnings WHERE user_id = ? AND guild_id = ?",
                (member.id, ctx.guild.id)
            )
            count = (await cursor.fetchone())[0]

            embed = discord.Embed(
                title=f"⚠️ Предупреждение #{warn_id}",
                color=discord.Color.orange(),
                timestamp=datetime.now()
            )
            embed.add_field(name="Участник", value=member.mention, inline=True)
            embed.add_field(name="Модератор", value=ctx.author.mention, inline=True)
            embed.add_field(name="Всего предупреждений", value=str(count), inline=True)
            embed.add_field(name="Причина", value=reason, inline=False)

            await ctx.send(embed=embed)

            try:
                await member.send(f"⚠️ Вы получили предупреждение на сервере **{ctx.guild.name}**\n**Причина:** {reason}\n**Всего предупреждений:** {count}")
            except:
                pass

            logger.info(f'{ctx.author} выдал предупреждение {member.name} (#{warn_id}): {reason}')
        except Exception as e:
            await ctx.send(f"❌ Ошибка при выдаче предупреждения: {e}", ephemeral=True)
            logger.error(f'Ошибка warn: {e}')

    @bot.hybrid_command(name="warnings", description="Показать предупреждения участника")
    @app_commands.describe(member="Участник для просмотра предупреждений")
    async def warnings_cmd(ctx: commands.Context, member: discord.Member = None):
        """Список предупреждений участника"""
        try:
            member = member or ctx.author
            cursor = await bot.db.execute(
                "SELECT id, moderator_id, reason, created_at FROM warnings WHERE user_id = ? AND guild_id = ? ORDER BY id DESC",
                (member.id, ctx.guild.id)
            )
            rows = await cursor.fetchall()

            embed = discord.Embed(
                title=f"⚠️ Предупреждения: {member.display_name}",
                color=discord.Color.orange() if rows else discord.Color.green(),
                timestamp=datetime.now()
            )
            if not rows:
                embed.description = "🎉 У этого участника нет предупреждений."
            else:
                embed.description = f"Всего: **{len(rows)}**"
                for warn_id, mod_id, reason, created in rows[:15]:
                    mod = ctx.guild.get_member(mod_id)
                    embed.add_field(
                        name=f"#{warn_id} • {created[:16]}",
                        value=f"**Причина:** {reason}\n**Модератор:** {mod.mention if mod else 'Неизвестен'}",
                        inline=False
                    )
            await ctx.send(embed=embed)
        except Exception as e:
            await ctx.send(f"❌ Ошибка при просмотре предупреждений: {e}", ephemeral=True)
            logger.error(f'Ошибка warnings: {e}')

    @bot.hybrid_command(name="unwarn", description="Снять предупреждение с участника")
    @app_commands.describe(member="Участник для снятия предупреждения", warn_id="Номер предупреждения (из !warnings)")
    @commands.has_permissions(manage_messages=True)
    async def unwarn_cmd(ctx: commands.Context, member: discord.Member, warn_id: int = None):
        """Снятие предупреждения"""
        try:
            if warn_id is None:
                cursor = await bot.db.execute(
                    "SELECT id FROM warnings WHERE user_id = ? AND guild_id = ? ORDER BY id DESC LIMIT 1",
                    (member.id, ctx.guild.id)
                )
                row = await cursor.fetchone()
                if row is None:
                    await ctx.send(f"❌ У участника **{member.display_name}** нет предупреждений.", ephemeral=True)
                    return
                warn_id = row[0]

            cursor = await bot.db.execute(
                "DELETE FROM warnings WHERE id = ? AND guild_id = ?",
                (warn_id, ctx.guild.id)
            )
            await bot.db.commit()
            if cursor.rowcount == 0:
                await ctx.send(f"❌ Предупреждение #{warn_id} не найдено.", ephemeral=True)
                return

            embed = discord.Embed(
                title=f"✅ Предупреждение #{warn_id} снято",
                description=f"У **{member.mention}** снято предупреждение.",
                color=discord.Color.green(),
                timestamp=datetime.now()
            )
            embed.add_field(name="Модератор", value=ctx.author.mention, inline=False)
            await ctx.send(embed=embed)
            logger.info(f'{ctx.author} снял предупреждение #{warn_id} с {member.name}')
        except Exception as e:
            await ctx.send(f"❌ Ошибка при снятии предупреждения: {e}", ephemeral=True)
            logger.error(f'Ошибка unwarn: {e}')

    @bot.hybrid_command(name="slowmode", description="Установить медленный режим канала")
    @app_commands.describe(seconds="Задержка в секундах (0 = выключить)", channel="Канал для настройки")
    @commands.has_permissions(manage_channels=True)
    async def slowmode_cmd(ctx: commands.Context, seconds: int = 5, channel: discord.TextChannel = None):
        """Установить slowmode в канале"""
        try:
            if seconds < 0 or seconds > 21600:
                await ctx.send("❌ Задержка должна быть от 0 до 21600 секунд (6 часов).", ephemeral=True)
                return
            channel = channel or ctx.channel
            await channel.edit(slowmode_delay=seconds)
            text = "выключен" if seconds == 0 else f"**{seconds}** секунд"
            await ctx.send(f"⏳ Медленный режим в {channel.mention}: {text}.", ephemeral=True)
            logger.info(f'{ctx.author} установил slowmode {seconds}с в {channel.name}')
        except Exception as e:
            await ctx.send(f"❌ Ошибка при установке slowmode: {e}", ephemeral=True)
            logger.error(f'Ошибка slowmode: {e}')

    @bot.hybrid_command(name="lock", description="Закрыть канал для участников")
    @app_commands.describe(channel="Канал для блокировки", reason="Причина блокировки")
    @commands.has_permissions(manage_channels=True)
    async def lock_cmd(ctx: commands.Context, channel: discord.TextChannel = None, *, reason: str = "Не указана"):
        """Закрыть канал (запретить писать @everyone)"""
        try:
            channel = channel or ctx.channel
            overwrite = channel.overwrites_for(channel.guild.default_role)
            if overwrite.send_messages is False:
                await ctx.send(f"🔒 Канал {channel.mention} уже закрыт.", ephemeral=True)
                return
            overwrite.send_messages = False
            await channel.set_permissions(channel.guild.default_role, overwrite=overwrite, reason=reason)
            await ctx.send(f"🔒 Канал {channel.mention} закрыт.\n**Причина:** {reason}", ephemeral=True)
            logger.info(f'{ctx.author} закрыл {channel.name}: {reason}')
        except Exception as e:
            await ctx.send(f"❌ Ошибка при закрытии канала: {e}", ephemeral=True)
            logger.error(f'Ошибка lock: {e}')

    @bot.hybrid_command(name="unlock", description="Открыть канал для участников")
    @app_commands.describe(channel="Канал для разблокировки")
    @commands.has_permissions(manage_channels=True)
    async def unlock_cmd(ctx: commands.Context, channel: discord.TextChannel = None):
        """Открыть канал"""
        try:
            channel = channel or ctx.channel
            overwrite = channel.overwrites_for(channel.guild.default_role)
            if overwrite.send_messages is None or overwrite.send_messages is True:
                await ctx.send(f"🔓 Канал {channel.mention} уже открыт.", ephemeral=True)
                return
            overwrite.send_messages = None
            await channel.set_permissions(channel.guild.default_role, overwrite=overwrite)
            await ctx.send(f"🔓 Канал {channel.mention} открыт.", ephemeral=True)
            logger.info(f'{ctx.author} открыл {channel.name}')
        except Exception as e:
            await ctx.send(f"❌ Ошибка при открытии канала: {e}", ephemeral=True)
            logger.error(f'Ошибка unlock: {e}')

    @bot.hybrid_command(name="nick", description="Изменить никнейм участника")
    @app_commands.describe(member="Участник для смены ника", nickname="Новый никнейм (без указания = сброс)")
    @commands.has_permissions(manage_nicknames=True)
    async def nick_cmd(ctx: commands.Context, member: discord.Member, *, nickname: str = None):
        """Смена никнейма участника"""
        try:
            if member.top_role >= ctx.author.top_role:
                await ctx.send("❌ Нельзя изменить ник участника с равной или высшей ролью", ephemeral=True)
                return
            await member.edit(nick=nickname, reason=f"Смена ника модератором {ctx.author}")
            if nickname:
                await ctx.send(f"✏️ Никнейм **{member.display_name}** изменён на `{nickname}`.", ephemeral=True)
            else:
                await ctx.send(f"✏️ Никнейм **{member.display_name}** сброшен.", ephemeral=True)
            logger.info(f'{ctx.author} сменил ник {member.name} на {nickname}')
        except Exception as e:
            await ctx.send(f"❌ Ошибка при смене ника: {e}", ephemeral=True)
            logger.error(f'Ошибка nick: {e}')

    @bot.hybrid_command(name="voicekick", description="Отключить участника от голосового канала")
    @app_commands.describe(member="Участник для отключения", reason="Причина")
    @commands.has_permissions(move_members=True)
    async def voicekick_cmd(ctx: commands.Context, member: discord.Member, *, reason: str = "Не указана"):
        """Отключение участника от голосового канала"""
        try:
            if not member.voice or not member.voice.channel:
                await ctx.send(f"❌ **{member.display_name}** не находится в голосовом канале.", ephemeral=True)
                return
            channel = member.voice.channel
            await member.move_to(None, reason=reason)
            await ctx.send(f"🚪 **{member.display_name}** отключён от **{channel.name}**.\n**Причина:** {reason}", ephemeral=True)
            logger.info(f'{ctx.author} отключил {member.name} от {channel.name}: {reason}')
        except Exception as e:
            await ctx.send(f"❌ Ошибка при отключении: {e}", ephemeral=True)
            logger.error(f'Ошибка voicekick: {e}')

    @bot.hybrid_command(name="moveall", description="Переместить всех участников из голосового канала")
    @app_commands.describe(from_channel="Откуда переместить", to_channel="Куда переместить")
    @commands.has_permissions(move_members=True)
    async def moveall_cmd(ctx: commands.Context, from_channel: discord.VoiceChannel, to_channel: discord.VoiceChannel):
        """Перемещение всех участников между голосовыми каналами"""
        try:
            members = [m for m in from_channel.members]
            if not members:
                await ctx.send(f"❌ В канале **{from_channel.name}** нет участников.", ephemeral=True)
                return
            for m in members:
                try:
                    await m.move_to(to_channel, reason=f"Перемещение модератором {ctx.author}")
                except Exception:
                    pass
            await ctx.send(f"🔀 Перемещено **{len(members)}** участников из **{from_channel.name}** в **{to_channel.name}**.", ephemeral=True)
            logger.info(f'{ctx.author} переместил {len(members)} участников из {from_channel.name} в {to_channel.name}')
        except Exception as e:
            await ctx.send(f"❌ Ошибка при перемещении: {e}", ephemeral=True)
            logger.error(f'Ошибка moveall: {e}')

    @bot.hybrid_command(name="purge", description="Удалить сообщения конкретного пользователя в канале")
    @app_commands.describe(member="Участник, чьи сообщения удалить", amount="Количество сообщений (1-100)")
    @commands.has_permissions(manage_messages=True)
    async def purge_cmd(ctx: commands.Context, member: discord.Member, amount: int = 10):
        """Удаление сообщений конкретного пользователя"""
        try:
            if amount < 1 or amount > 100:
                await ctx.send("❌ Количество должно быть от 1 до 100", ephemeral=True)
                return
            deleted = await ctx.channel.purge(
                limit=100, check=lambda m: m.author.id == member.id, before=ctx.message
            )
            count = len(deleted)
            msg = await ctx.send(f"🧹 Удалено **{count}** сообщений от **{member.display_name}**.", ephemeral=True)
            logger.info(f'{ctx.author} удалил {count} сообщений от {member.name} в {ctx.channel.name}')
        except Exception as e:
            await ctx.send(f"❌ Ошибка: {e}", ephemeral=True)
            logger.error(f'Ошибка purge: {e}')

    @bot.hybrid_command(name="softban", description="Кикнуть с очисткой сообщений (бан + мгновенный разбан)")
    @app_commands.describe(member="Участник для soft-бана", days="Сколько дней сообщений удалить (0-7)", reason="Причина")
    @commands.has_permissions(ban_members=True)
    async def softban_cmd(ctx: commands.Context, member: discord.Member, days: int = 1, *, reason: str = "Не указана"):
        """Soft-бан: баним, чистим сообщения, сразу разбаниваем"""
        try:
            if member == ctx.author:
                await ctx.send("❌ Нельзя применить к себе", ephemeral=True)
                return
            if member.top_role >= ctx.author.top_role:
                await ctx.send("❌ Роль выше или равна вашей", ephemeral=True)
                return
            days = max(0, min(7, days))
            await member.ban(reason=f"Soft-ban: {reason}", delete_message_days=days)
            await ctx.guild.unban(member, reason=f"Soft-ban завершён: {reason}")
            embed = discord.Embed(
                title="🛡️ Soft-ban применён",
                description=f"**{member.mention}** кикнут, удалено сообщений за {days} дн.",
                color=discord.Color.orange(),
                timestamp=datetime.now()
            )
            embed.add_field(name="Причина", value=reason, inline=False)
            await ctx.send(embed=embed)
            logger.info(f'{ctx.author} применил soft-ban к {member.name}: {reason}')
        except Exception as e:
            await ctx.send(f"❌ Ошибка: {e}", ephemeral=True)
            logger.error(f'Ошибка softban: {e}')

    @bot.hybrid_command(name="hackban", description="Забанить по ID (пользователя не на сервере)")
    @app_commands.describe(user_id="ID пользователя", reason="Причина")
    @commands.has_permissions(ban_members=True)
    async def hackban_cmd(ctx: commands.Context, user_id: str, *, reason: str = "Не указана"):
        """Бан по ID без необходимости, чтобы пользователь был на сервере"""
        try:
            uid = int(user_id)
            user = await bot.fetch_user(uid)
            await ctx.guild.ban(discord.Object(id=uid), reason=reason, delete_message_days=0)
            embed = discord.Embed(
                title="🔨 Hackban",
                description=f"**{user}** (ID: {uid}) забанен.",
                color=discord.Color.dark_red(),
                timestamp=datetime.now()
            )
            embed.add_field(name="Причина", value=reason, inline=False)
            await ctx.send(embed=embed)
            logger.info(f'{ctx.author} забанил по ID {uid} ({user}): {reason}')
        except ValueError:
            await ctx.send("❌ ID должен быть числом.", ephemeral=True)
        except discord.NotFound:
            await ctx.send("❌ Пользователь с таким ID не найден.", ephemeral=True)
        except Exception as e:
            await ctx.send(f"❌ Ошибка: {e}", ephemeral=True)
            logger.error(f'Ошибка hackban: {e}')

    @bot.hybrid_command(name="banlist", description="Список забаненных участников")
    @commands.has_permissions(ban_members=True)
    async def banlist_cmd(ctx: commands.Context):
        """Показать всех забаненных"""
        try:
            banned = [entry async for entry in ctx.guild.bans()]
            embed = discord.Embed(
                title=f"🔨 Забаненные ({len(banned)})",
                color=discord.Color.red(),
                timestamp=datetime.now()
            )
            if not banned:
                embed.description = "Нет забаненных."
            else:
                lines = []
                for entry in banned[:25]:
                    lines.append(f"• **{entry.user}** (`{entry.user.id}`) — {entry.reason or 'без причины'}")
                embed.description = "\n".join(lines)
            await ctx.send(embed=embed)
            logger.info(f'{ctx.author} запросил список банов')
        except Exception as e:
            await ctx.send(f"❌ Ошибка: {e}", ephemeral=True)
            logger.error(f'Ошибка banlist: {e}')

    @bot.hybrid_command(name="role", description="Выдать роль участнику")
    @app_commands.describe(member="Участник", role="Роль", reason="Причина")
    @commands.has_permissions(manage_roles=True)
    async def role_cmd(ctx: commands.Context, member: discord.Member, role: discord.Role, *, reason: str = "Не указана"):
        """Выдать роль участнику"""
        try:
            if role >= ctx.author.top_role and ctx.author != ctx.guild.owner:
                await ctx.send("❌ Роль выше или равна вашей высшей роли", ephemeral=True)
                return
            if role in member.roles:
                await ctx.send(f"❌ У **{member.display_name}** уже есть роль **{role.name}**.", ephemeral=True)
                return
            await member.add_roles(role, reason=reason)
            await ctx.send(f"✅ **{member.mention}** выдана роль **{role.mention}**.", ephemeral=True)
            logger.info(f'{ctx.author} выдал роль {role.name} участнику {member.name}: {reason}')
        except Exception as e:
            await ctx.send(f"❌ Ошибка: {e}", ephemeral=True)
            logger.error(f'Ошибка role: {e}')

    @bot.hybrid_command(name="unrole", description="Снять роль у участника")
    @app_commands.describe(member="Участник", role="Роль", reason="Причина")
    @commands.has_permissions(manage_roles=True)
    async def unrole_cmd(ctx: commands.Context, member: discord.Member, role: discord.Role, *, reason: str = "Не указана"):
        """Снять роль с участника"""
        try:
            if role >= ctx.author.top_role and ctx.author != ctx.guild.owner:
                await ctx.send("❌ Роль выше или равна вашей высшей роли", ephemeral=True)
                return
            if role not in member.roles:
                await ctx.send(f"❌ У **{member.display_name}** нет роли **{role.name}**.", ephemeral=True)
                return
            await member.remove_roles(role, reason=reason)
            await ctx.send(f"✅ У **{member.mention}** снята роль **{role.mention}**.", ephemeral=True)
            logger.info(f'{ctx.author} снял роль {role.name} с {member.name}: {reason}')
        except Exception as e:
            await ctx.send(f"❌ Ошибка: {e}", ephemeral=True)
            logger.error(f'Ошибка unrole: {e}')

    @bot.hybrid_command(name="nuke", description="Полностью очистить канал (удалить и пересоздать)")
    @app_commands.describe(channel="Канал для очистки", reason="Причина")
    @commands.has_permissions(manage_channels=True)
    async def nuke_cmd(ctx: commands.Context, channel: discord.TextChannel = None, *, reason: str = "Не указана"):
        """Удаление канала и создание нового на его месте"""
        try:
            channel = channel or ctx.channel
            pos = channel.position
            category = channel.category
            name = channel.name
            topic = channel.topic

            new_channel = await channel.clone(reason=f"Nuke: {reason}")
            await channel.delete(reason=f"Nuke: {reason}")
            await new_channel.edit(position=pos, topic=topic)
            await new_channel.send(f"🧨 Канал пересоздан. **Причина:** {reason}")
            logger.info(f'{ctx.author} пересоздал канал {name}: {reason}')
        except Exception as e:
            await ctx.send(f"❌ Ошибка: {e}", ephemeral=True)
            logger.error(f'Ошибка nuke: {e}')

    @bot.hybrid_command(name="voicemute", description="Заглушить участника в голосовом канале")
    @app_commands.describe(member="Участник", reason="Причина")
    @commands.has_permissions(mute_members=True)
    async def voicemute_cmd(ctx: commands.Context, member: discord.Member, *, reason: str = "Не указана"):
        """Включить мут в голосовом канале"""
        try:
            if not member.voice or not member.voice.channel:
                await ctx.send(f"❌ **{member.display_name}** не в голосовом канале.", ephemeral=True)
                return
            await member.edit(mute=True, reason=reason)
            await ctx.send(f"🔇 **{member.display_name}** заглушен в **{member.voice.channel.name}**.", ephemeral=True)
            logger.info(f'{ctx.author} заглушил {member.name}: {reason}')
        except Exception as e:
            await ctx.send(f"❌ Ошибка: {e}", ephemeral=True)
            logger.error(f'Ошибка voicemute: {e}')

    @bot.hybrid_command(name="voiceunmute", description="Включить звук участнику в голосовом канале")
    @app_commands.describe(member="Участник", reason="Причина")
    @commands.has_permissions(mute_members=True)
    async def voiceunmute_cmd(ctx: commands.Context, member: discord.Member, *, reason: str = "Не указана"):
        """Снять мут в голосовом канале"""
        try:
            await member.edit(mute=False, reason=reason)
            await ctx.send(f"🔊 **{member.display_name}** больше не заглушен.", ephemeral=True)
            logger.info(f'{ctx.author} снял заглушку с {member.name}: {reason}')
        except Exception as e:
            await ctx.send(f"❌ Ошибка: {e}", ephemeral=True)
            logger.error(f'Ошибка voiceunmute: {e}')

    @bot.hybrid_command(name="lockall", description="Закрыть все текстовые каналы сервера")
    @app_commands.describe(reason="Причина")
    @commands.has_permissions(manage_channels=True)
    async def lockall_cmd(ctx: commands.Context, *, reason: str = "Не указана"):
        """Закрыть все текстовые каналы для @everyone"""
        try:
            closed = 0
            for channel in ctx.guild.text_channels:
                overwrite = channel.overwrites_for(ctx.guild.default_role)
                overwrite.send_messages = False
                await channel.set_permissions(ctx.guild.default_role, overwrite=overwrite, reason=f"Lockall: {reason}")
                closed += 1
            await ctx.send(f"🔒 Закрыто **{closed}** текстовых каналов.\n**Причина:** {reason}", ephemeral=True)
            logger.info(f'{ctx.author} закрыл все каналы: {reason}')
        except Exception as e:
            await ctx.send(f"❌ Ошибка: {e}", ephemeral=True)
            logger.error(f'Ошибка lockall: {e}')

    @bot.hybrid_command(name="unlockall", description="Открыть все текстовые каналы сервера")
    @app_commands.describe(reason="Причина")
    @commands.has_permissions(manage_channels=True)
    async def unlockall_cmd(ctx: commands.Context, *, reason: str = "Не указана"):
        """Открыть все текстовые каналы для @everyone"""
        try:
            opened = 0
            for channel in ctx.guild.text_channels:
                overwrite = channel.overwrites_for(ctx.guild.default_role)
                overwrite.send_messages = None
                await channel.set_permissions(ctx.guild.default_role, overwrite=overwrite, reason=f"Unlockall: {reason}")
                opened += 1
            await ctx.send(f"🔓 Открыто **{opened}** текстовых каналов.\n**Причина:** {reason}", ephemeral=True)
            logger.info(f'{ctx.author} открыл все каналы: {reason}')
        except Exception as e:
            await ctx.send(f"❌ Ошибка: {e}", ephemeral=True)
            logger.error(f'Ошибка unlockall: {e}')

    @bot.hybrid_command(name="clearwarn", description="Очистить все предупреждения участника")
    @app_commands.describe(member="Участник")
    @commands.has_permissions(manage_messages=True)
    async def clearwarn_cmd(ctx: commands.Context, member: discord.Member):
        """Удалить все предупреждения участника"""
        try:
            cursor = await bot.db.execute(
                "DELETE FROM warnings WHERE user_id = ? AND guild_id = ?",
                (member.id, ctx.guild.id)
            )
            await bot.db.commit()
            count = cursor.rowcount
            await ctx.send(f"🧹 У **{member.mention}** удалено предупреждений: **{count}**.", ephemeral=True)
            logger.info(f'{ctx.author} очистил {count} предупреждений у {member.name}')
        except Exception as e:
            await ctx.send(f"❌ Ошибка: {e}", ephemeral=True)
            logger.error(f'Ошибка clearwarn: {e}')

    logger.info("Модуль модерации загружен")