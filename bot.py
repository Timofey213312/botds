@bot.hybrid_command(name="mute", description="Выдать мут участнику (роль)")
@app_commands.describe(member="Участник для мута", minutes="Длительность мута в минутах", reason="Причина мута")
@commands.has_permissions(manage_roles=True)
async def mute(ctx: commands.Context, member: discord.Member, minutes: int = 10, *, reason: str = "Не указана"):
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
            # Создаем роль с ограничениями
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
            title="Участнику выдан мут",
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
        await asyncio.sleep(minutes * 60)
        if muted_role in member.roles:
            await member.remove_roles(muted_role, reason="Автоматическое снятие мута")
            await member.send(f"Ваш мут на сервере {ctx.guild.name} истёк.")
            logger.info(f'Мут снят с {member.name}')
        
    except Exception as e:
        await ctx.send(f"❌ Ошибка при выдаче мута: {e}", ephemeral=True)
        logger.error(f'Ошибка мута: {e}')

@bot.hybrid_command(name="timeout", description="Выдать таймаут участнику (Discord)")
@app_commands.describe(member="Участник для таймаута", minutes="Длительность таймаута в минутах (1-40320)", reason="Причина таймаута")
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