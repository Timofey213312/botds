"""
Модуль экономики
Команды: баланс, работа, ежедневная награда, игры на деньги, магазин
"""

import asyncio
import json
import logging
import random
from datetime import datetime, timedelta

import discord
from discord.ext import commands
from discord import app_commands

logger = logging.getLogger('discord_bot.economy')

DAILY_AMOUNT = 200
WORK_MIN = 50
WORK_MAX = 200
START_BALANCE = 100

SHOP_ITEMS = {
    "🎁": {"name": "Таинственный подарок", "price": 250, "desc": "Случайный приз"},
    "🎩": {"name": "Шляпа джентльмена", "price": 500, "desc": "Статусный аксессуар"},
    "🏆": {"name": "Трофей", "price": 1000, "desc": "Доказательство богатства"},
    "💎": {"name": "Алмаз", "price": 2000, "desc": "Дорогой камень"},
    "🛡️": {"name": "Щит", "price": 1500, "desc": "Защита от ограблений (50%)"},
    "🎣": {"name": "Удочка", "price": 300, "desc": "Можно рыбачить"},
}


def setup_economy(bot):
    """Настройка команд экономики"""

    async def _get_user(user_id, guild_id):
        cursor = await bot.db.execute(
            "SELECT balance, xp, level, daily_claimed, work_cooldown, inventory FROM users WHERE user_id = ? AND guild_id = ?",
            (user_id, guild_id)
        )
        row = await cursor.fetchone()
        if row is None:
            await bot.db.execute(
                "INSERT INTO users (user_id, guild_id, balance, xp, level, inventory) VALUES (?, ?, ?, 1, 1, '[]')",
                (user_id, guild_id, START_BALANCE)
            )
            await bot.db.commit()
            return {"balance": START_BALANCE, "xp": 0, "level": 1, "daily_claimed": None, "work_cooldown": None, "inventory": "[]"}
        return {"balance": row[0], "xp": row[1], "level": row[2], "daily_claimed": row[3], "work_cooldown": row[4], "inventory": row[5]}

    async def _update_balance(user_id, guild_id, amount):
        cursor = await bot.db.execute(
            "UPDATE users SET balance = balance + ? WHERE user_id = ? AND guild_id = ?",
            (amount, user_id, guild_id)
        )
        await bot.db.commit()

    @bot.command(name="balance", description="Показать баланс")
    async def balance(ctx, member: discord.Member = None):
        member = member or ctx.author
        user = await _get_user(member.id, ctx.guild.id)
        embed = discord.Embed(title=f"💰 Баланс: {member.display_name}", color=discord.Color.gold())
        embed.add_field(name="Баланс", value=f"**{user['balance']:,}** монет".replace(",", " "), inline=True)
        embed.add_field(name="Уровень", value=str(user["level"]), inline=True)
        embed.add_field(name="XP", value=str(user["xp"]), inline=True)
        await ctx.send(embed=embed)

    @bot.command(name="bal", description="Алиас для баланса")
    async def bal(ctx, member: discord.Member = None):
        await balance.callback(ctx, member=member)

    @bot.command(name="daily", description="Ежедневная награда")
    async def daily(ctx):
        user = await _get_user(ctx.author.id, ctx.guild.id)
        if user["daily_claimed"]:
            last = datetime.fromisoformat(user["daily_claimed"])
            next_time = last + timedelta(hours=24)
            if datetime.now() < next_time:
                remaining = next_time - datetime.now()
                hours = int(remaining.seconds // 3600)
                minutes = int((remaining.seconds % 3600) // 60)
                await ctx.send(f"⏰ Ежедневная награда уже получена! Следующая через **{hours} ч {minutes} мин**.", ephemeral=True)
                return
        await _update_balance(ctx.author.id, ctx.guild.id, DAILY_AMOUNT)
        await bot.db.execute(
            "UPDATE users SET daily_claimed = ? WHERE user_id = ? AND guild_id = ?",
            (datetime.now().isoformat(), ctx.author.id, ctx.guild.id)
        )
        await bot.db.commit()
        embed = discord.Embed(title="📅 Ежедневная награда", color=discord.Color.green())
        embed.add_field(name="Получено", value=f"+{DAILY_AMOUNT} монет", inline=False)
        await ctx.send(embed=embed)

    @bot.command(name="work", description="Поработать и заработать")
    async def work(ctx):
        user = await _get_user(ctx.author.id, ctx.guild.id)
        if user["work_cooldown"]:
            last = datetime.fromisoformat(user["work_cooldown"])
            next_time = last + timedelta(minutes=15)
            if datetime.now() < next_time:
                remaining = next_time - datetime.now()
                minutes = int(remaining.seconds // 60)
                await ctx.send(f"💼 Устал! Следующая работа через **{minutes} мин**.", ephemeral=True)
                return
        amount = random.randint(WORK_MIN, WORK_MAX)
        await _update_balance(ctx.author.id, ctx.guild.id, amount)
        await bot.db.execute(
            "UPDATE users SET work_cooldown = ? WHERE user_id = ? AND guild_id = ?",
            (datetime.now().isoformat(), ctx.author.id, ctx.guild.id)
        )
        await bot.db.commit()
        jobs = [
            "разгрузил грузовик", "помогал в офисе", "чинил забор", "продал старый компьютер",
            "разносил почту", "кодил для бота", "помыл машину", "работал курьером",
        ]
        embed = discord.Embed(title="💼 Работа", color=discord.Color.green())
        embed.add_field(name="Ты " + random.choice(jobs), value=f"+{amount} монет", inline=False)
        await ctx.send(embed=embed)

    @bot.command(name="gamble", description="Сыграть в рулетку на деньги")
    async def gamble(ctx, amount: int):
        if amount <= 0:
            await ctx.send("❌ Ставка должна быть положительной", ephemeral=True)
            return
        user = await _get_user(ctx.author.id, ctx.guild.id)
        if user["balance"] < amount:
            await ctx.send(f"❌ Недостаточно монет. У тебя **{user['balance']:,}**".replace(",", " "), ephemeral=True)
            return
        number = random.randint(1, 100)
        if number <= 45:
            win = round(amount * 1.8)
            await _update_balance(ctx.author.id, ctx.guild.id, win - amount)
            embed = discord.Embed(title="🎰 Рулетка", description=f"Победил! Выпало **{number}**", color=discord.Color.green())
            embed.add_field(name="Выигрыш", value=f"+{win - amount} монет")
        else:
            await _update_balance(ctx.author.id, ctx.guild.id, -amount)
            embed = discord.Embed(title="🎰 Рулетка", description=f"Проиграл... Выпало **{number}**", color=discord.Color.red())
            embed.add_field(name="Потеряно", value=f"-{amount} монет")
        await ctx.send(embed=embed)

    @bot.command(name="slots", description="Игровой автомат")
    async def slots(ctx, bet: int = 10):
        if bet <= 0:
            await ctx.send("❌ Ставка должна быть положительной", ephemeral=True)
            return
        user = await _get_user(ctx.author.id, ctx.guild.id)
        if user["balance"] < bet:
            await ctx.send(f"❌ Недостаточно монет. У тебя **{user['balance']:,}**".replace(",", " "), ephemeral=True)
            return
        symbols = ["🍒", "🍋", "🍀", "💎", "7️⃣", "💰"]
        result = [random.choice(symbols) for _ in range(3)]
        line = " | ".join(result)
        if result[0] == result[1] == result[2]:
            win = bet * 10
            await _update_balance(ctx.author.id, ctx.guild.id, win - bet)
            text = f"🎰 {line}\n\n🎉 ДЖЕКПОТ! +{win - bet}"
        elif result[0] == result[1] or result[1] == result[2] or result[0] == result[2]:
            win = bet * 2
            await _update_balance(ctx.author.id, ctx.guild.id, win - bet)
            text = f"🎰 {line}\n\n🎉 Пара! +{win - bet}"
        else:
            await _update_balance(ctx.author.id, ctx.guild.id, -bet)
            text = f"🎰 {line}\n\n😢 Проигрыш: -{bet}"
        embed = discord.Embed(title="🎰 Слоты", description=text, color=discord.Color.blurple())
        await ctx.send(embed=embed)

    @bot.command(name="give", description="Передать монеты другому")
    async def give(ctx, member: discord.Member, amount: int):
        if member == ctx.author:
            await ctx.send("❌ Нельзя передать самому себе", ephemeral=True)
            return
        if amount <= 0:
            await ctx.send("❌ Сумма должна быть положительной", ephemeral=True)
            return
        user = await _get_user(ctx.author.id, ctx.guild.id)
        if user["balance"] < amount:
            await ctx.send(f"❌ Недостаточно монет. У тебя **{user['balance']:,}**".replace(",", " "), ephemeral=True)
            return
        await _update_balance(ctx.author.id, ctx.guild.id, -amount)
        await _get_user(member.id, ctx.guild.id)
        await _update_balance(member.id, ctx.guild.id, amount)
        embed = discord.Embed(title="💸 Перевод", color=discord.Color.green())
        embed.add_field(name="Отправитель", value=ctx.author.mention, inline=True)
        embed.add_field(name="Получатель", value=member.mention, inline=True)
        embed.add_field(name="Сумма", value=f"{amount} монет", inline=True)
        await ctx.send(embed=embed)

    @bot.command(name="pay", description="Алиас для передачи монет")
    async def pay(ctx, member: discord.Member, amount: int):
        await give.callback(ctx, member=member, amount=amount)

    @bot.command(name="rob", description="Попробовать ограбить (шанс провала)")
    async def rob(ctx, member: discord.Member):
        if member == ctx.author:
            await ctx.send("❌ Нельзя ограбить себя", ephemeral=True)
            return
        victim = await _get_user(member.id, ctx.guild.id)
        robber = await _get_user(ctx.author.id, ctx.guild.id)
        if victim["balance"] < 10:
            await ctx.send(f"❌ У {member.mention} нет денег на ограбление", ephemeral=True)
            return
        if random.random() < 0.5:
            stole = random.randint(10, min(100, victim["balance"]))
            await _update_balance(ctx.author.id, ctx.guild.id, stole)
            await _update_balance(member.id, ctx.guild.id, -stole)
            await ctx.send(f"🦹 {ctx.author.mention} ограбил {member.mention} на **{stole}** монет!")
        else:
            fine = random.randint(10, 50)
            await _update_balance(ctx.author.id, ctx.guild.id, -min(fine, robber["balance"]))
            await ctx.send(f"🚨 {ctx.author.mention} попался! Заплатил штраф **{fine}** монет.")

    @bot.command(name="leaderboard", description="Топ самых богатых")
    async def leaderboard(ctx):
        cursor = await bot.db.execute(
            "SELECT user_id, balance FROM users WHERE guild_id = ? ORDER BY balance DESC LIMIT 10",
            (ctx.guild.id,)
        )
        rows = await cursor.fetchall()
        if not rows:
            await ctx.send("📭 Пока нет данных для топ-листа", ephemeral=True)
            return
        embed = discord.Embed(title="🏆 Топ богачей", color=discord.Color.gold())
        medals = ["🥇", "🥈", "🥉"]
        for i, (user_id, balance) in enumerate(rows):
            member = ctx.guild.get_member(user_id)
            name = member.display_name if member else f"<@{user_id}>"
            prefix = medals[i] if i < 3 else f"{i+1}."
            embed.add_field(name=f"{prefix} {name}", value=f"{balance:,} монет".replace(",", " "), inline=False)
        await ctx.send(embed=embed)

    @bot.command(name="rich", description="Топ богачей")
    async def rich(ctx):
        await leaderboard.callback(ctx)

    @bot.command(name="shop", description="Магазин")
    async def shop(ctx):
        embed = discord.Embed(title="🛒 Магазин", color=discord.Color.blurple())
        for emoji, item in SHOP_ITEMS.items():
            embed.add_field(
                name=f"{emoji} {item['name']} — {item['price']} монет",
                value=item["desc"],
                inline=False
            )
        embed.set_footer(text="Используй !buy <название>")
        await ctx.send(embed=embed)

    @bot.command(name="buy", description="Купить предмет")
    async def buy(ctx, *, item: str):
        user = await _get_user(ctx.author.id, ctx.guild.id)
        found = None
        for emoji, shop_item in SHOP_ITEMS.items():
            if item.lower() in shop_item["name"].lower():
                found = (emoji, shop_item)
                break
        if not found:
            await ctx.send("❌ Предмет не найден в магазине", ephemeral=True)
            return
        emoji, shop_item = found
        if user["balance"] < shop_item["price"]:
            await ctx.send(f"❌ Недостаточно монет: нужно {shop_item['price']}, у тебя {user['balance']}", ephemeral=True)
            return
        inventory = json.loads(user["inventory"] or "[]")
        inventory.append(f"{emoji} {shop_item['name']}")
        await _update_balance(ctx.author.id, ctx.guild.id, -shop_item["price"])
        await bot.db.execute(
            "UPDATE users SET inventory = ? WHERE user_id = ? AND guild_id = ?",
            (json.dumps(inventory, ensure_ascii=False), ctx.author.id, ctx.guild.id)
        )
        await bot.db.commit()
        await ctx.send(f"✅ Куплено: {emoji} **{shop_item['name']}** за {shop_item['price']} монет!")

    @bot.command(name="inventory", description="Инвентарь")
    async def inventory(ctx, member: discord.Member = None):
        member = member or ctx.author
        user = await _get_user(member.id, ctx.guild.id)
        items = json.loads(user["inventory"] or "[]")
        if not items:
            await ctx.send(f"🎒 У {member.mention} пустой инвентарь", ephemeral=True)
            return
        embed = discord.Embed(title=f"🎒 Инвентарь: {member.display_name}", color=discord.Color.blurple())
        embed.description = "\n".join(items)
        await ctx.send(embed=embed)

    @bot.command(name="inv", description="Алиас инвентаря")
    async def inv(ctx, member: discord.Member = None):
        await inventory.callback(ctx, member=member)

    @bot.command(name="fish", description="Рыбалка (нужна удочка)")
    async def fish(ctx):
        user = await _get_user(ctx.author.id, ctx.guild.id)
        inventory = json.loads(user["inventory"] or "[]")
        has_rod = any("Удочка" in i for i in inventory)
        if not has_rod:
            await ctx.send("❌ Нужна удочка! Купи в магазине: `!buy удочка`", ephemeral=True)
            return
        catches = [
            ("🐟", "рыбу", random.randint(5, 20)),
            ("🐠", "золотую рыбку", random.randint(20, 50)),
            ("🐡", "рыбу-шар", random.randint(15, 40)),
            ("🦐", "креветку", random.randint(5, 15)),
            ("🐙", "осьминога", random.randint(30, 60)),
            ("👢", "старый сапог", 0),
        ]
        emoji, name, amount = random.choice(catches)
        if amount:
            await _update_balance(ctx.author.id, ctx.guild.id, amount)
            await ctx.send(f"🎣 {ctx.author.mention} поймал {emoji} **{name}**! Продал за {amount} монет.")
        else:
            await ctx.send(f"🎣 {ctx.author.mention} поймал {emoji} **{name}**. Выбросил обратно.")

    @bot.command(name="level", description="Твой уровень")
    async def level(ctx, member: discord.Member = None):
        member = member or ctx.author
        user = await _get_user(member.id, ctx.guild.id)
        next_xp = user["level"] * 100
        embed = discord.Embed(title=f"📈 Уровень: {member.display_name}", color=discord.Color.green())
        embed.add_field(name="Уровень", value=str(user["level"]), inline=True)
        embed.add_field(name="XP", value=f"{user['xp']} / {next_xp}", inline=True)
        await ctx.send(embed=embed)

    @bot.command(name="xp", description="Показать XP")
    async def xp_cmd(ctx, member: discord.Member = None):
        await level.callback(ctx, member=member)