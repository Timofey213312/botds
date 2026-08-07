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
                    await ctx.send("✅ Жалоба отправлена модераторам", ephemeral=True)
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
    
    logger.info("Модуль модерации загружен")