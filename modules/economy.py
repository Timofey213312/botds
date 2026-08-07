"""
Модуль экономики для Discord бота
Команды: balance, daily, pay, coinflip, work, leaderboard, shop, buy
Система XP, уровней, магазина и инвентаря
"""

import discord
from discord.ext import commands
from discord import app_commands
import asyncio
from datetime import datetime, timedelta
import logging
import random
import json
from typing import Optional

logger = logging.getLogger('discord_bot.economy')

class EconomySystem:
    """Класс для управления экономикой"""
    
    def __init__(self, bot):
        self.bot = bot
        self.default_items = [
            {"id": 1, "name": "🍎 Яблоко", "description": "Вкусное яблоко", "price": 50, "type": "food", "effect": "+10 XP"},
            {"id": 2, "name": "⚔️ Меч", "description": "Острый меч", "price": 200, "type": "weapon", "effect": "+20 сила"},
            {"id": 3, "name": "🛡️ Щит", "description": "Прочный щит", "price": 150, "type": "armor", "effect": "+15 защита"},
            {"id": 4, "name": "🧪 Зелье здоровья", "description": "Восстанавливает здоровье", "price": 100, "type": "potion", "effect": "+50 HP"},
            {"id": 5, "name": "🎩 Шляпа", "description": "Модная шляпа", "price": 75, "type": "cosmetic", "effect": "+5 харизма"},
            {"id": 6, "name": "💰 Золотой слиток", "description": "Ценный слиток", "price": 500, "type": "currency", "effect": "Инвестиции"},
            {"id": 7, "name": "📜 Свиток опыта", "description": "Дает опыт", "price": 300, "type": "xp", "effect": "+100 XP"},
            {"id": 8, "name": "🎫 Лотерейный билет", "description": "Шанс выиграть приз", "price": 25, "type": "gamble", "effect": "Розыгрыш"},
        ]
    
    async def get_user_data(self, user_id, guild_id):
        """Получить данные пользователя"""
        cursor = await self.bot.db.execute(
            "SELECT * FROM users WHERE user_id = ? AND guild_id = ?",
            (user_id, guild_id)
        )
        row = await cursor.fetchone()
        
        if not row:
            # Создаем нового пользователя
            await self.bot.db.execute(
                "INSERT INTO users (user_id, guild_id, balance, xp, level, created_at) VALUES (?, ?, 100, 0, 1, CURRENT_TIMESTAMP)",
                (user_id, guild_id)
            )
            await self.bot.db.commit()
            
            cursor = await self.bot.db.execute(
                "SELECT * FROM users WHERE user_id = ? AND guild_id = ?",
                (user_id, guild_id)
            )
            row = await cursor.fetchone()
        
        return {
            "user_id": row[0],
            "guild_id": row[1],
            "balance": row[2],
            "xp": row[3],
            "level": row[4],
            "daily_claimed": row[5],
            "work_cooldown": row[6],
            "inventory": json.loads(row[7] if row[7] else "[]"),
            "created_at": row[8]
        }
    
    async def update_balance(self, user_id, guild_id, amount):
        """Обновить баланс пользователя"""
        await self.bot.db.execute(
            "UPDATE users SET balance = balance + ? WHERE user_id = ? AND guild_id = ?",
            (amount, user_id, guild_id)
        )
        await self.bot.db.commit()
    
    async def add_xp(self, user_id, guild_id, xp_amount):
        """Добавить опыт пользователю"""
        await self.bot.db.execute(
            "UPDATE users SET xp = xp + ? WHERE user_id = ? AND guild_id = ?",
            (xp_amount, user_id, guild_id)
        )
        await self.bot.db.commit()
        
        # Проверка уровня
        data = await self.get_user_data(user_id, guild_id)
        current_xp = data["xp"]
        current_level = data["level"]
        
        xp_needed = current_level * 100
        
        if current_xp >= xp_needed:
            new_level = current_level + 1
            await self.bot.db.execute(
                "UPDATE users SET level = ?, xp = xp - ? WHERE user_id = ? AND guild_id = ?",
                (new_level, xp_needed, user_id, guild_id)
            )
            await self.bot.db.commit()
            return new_level
        
        return None
    
    async def get_leaderboard(self, guild_id, limit=10, type="balance"):
        """Получить таблицу лидеров"""
        if type == "balance":
            cursor = await self.bot.db.execute(
                "SELECT user_id, balance FROM users WHERE guild_id = ? ORDER BY balance DESC LIMIT ?",
                (guild_id, limit)
            )
        elif type == "level":
            cursor = await self.bot.db.execute(
                "SELECT user_id, level FROM users WHERE guild_id = ? ORDER BY level DESC, xp DESC LIMIT ?",
                (guild_id, limit)
            )
        else:
            return []
        
        rows = await cursor.fetchall()
        return rows
    
    async def init_shop_items(self):
        """Инициализировать товары в магазине"""
        for item in self.default_items:
            cursor = await self.bot.db.execute(
                "SELECT id FROM economy_items WHERE id = ?",
                (item["id"],)
            )
            if not await cursor.fetchone():
                await self.bot.db.execute(
                    "INSERT INTO economy_items (id, name, description, price, type, effect) VALUES (?, ?, ?, ?, ?, ?)",
                    (item["id"], item["name"], item["description"], item["price"], item["type"], item["effect"])
                )
        await self.bot.db.commit()

def setup_economy(bot):
    """Настройка команд экономики"""
    
    economy = EconomySystem(bot)
    
    @bot.listen('on_ready')
    async def on_ready_init_shop():
        """Инициализация магазина при запуске"""
        await economy.init_shop_items()
    
    @bot.hybrid_command(name="balance", description="Показать баланс и уровень")
    @app_commands.describe(member="Участник для проверки баланса (опционально)")
    async def balance_cmd(ctx: commands.Context, member: Optional[discord.Member] = None):
        """Баланс и уровень пользователя"""
        try:
            target = member or ctx.author
            
            data = await economy.get_user_data(target.id, ctx.guild.id)
            
            embed = discord.Embed(
                title=f"💰 Баланс {target.name}",
                color=discord.Color.gold(),
                timestamp=datetime.now()
            )
            
            # Расчет XP для следующего уровня
            xp_needed = data["level"] * 100
            xp_progress = min(data["xp"], xp_needed)
            progress_percent = (xp_progress / xp_needed) * 100
            
            # Прогресс бар
            filled = int(progress_percent / 10)
            progress_bar = "█" * filled + "░" * (10 - filled)
            
            embed.add_field(name="Баланс", value=f"**{data['balance']}** 💰", inline=True)
            embed.add_field(name="Уровень", value=f"**{data['level']}** 📊", inline=True)
            embed.add_field(name="Опыт", value=f"**{data['xp']}/{xp_needed}** XP", inline=True)
            embed.add_field(name="Прогресс", value=f"```{progress_bar} {progress_percent:.1f}%```", inline=False)
            embed.add_field(name="В инвентаре", value=f"**{len(data['inventory'])}** предметов", inline=True)
            embed.add_field(name="Зарегистрирован", value=data["created_at"][:10], inline=True)
            
            embed.set_thumbnail(url=target.avatar.url if target.avatar else target.default_avatar.url)
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            await ctx.send(f"❌ Ошибка при проверке баланса: {e}", ephemeral=True)
            logger.error(f'Ошибка balance: {e}')
    
    @bot.hybrid_command(name="daily", description="Получить ежедневную награду (50-200 💰)")
    @commands.cooldown(1, 86400, commands.BucketType.user)  # 24 часа
    async def daily_cmd(ctx: commands.Context):
        """Ежедневная награда"""
        try:
            data = await economy.get_user_data(ctx.author.id, ctx.guild.id)
            
            # Проверка последнего получения
            if data["daily_claimed"]:
                last_claim = datetime.fromisoformat(data["daily_claimed"])
                if (datetime.now() - last_claim).total_seconds() < 86400:
                    await ctx.send("⏰ Вы уже получали ежедневную награду сегодня", ephemeral=True)
                    return
            
            # Случайная сумма от 50 до 200
            reward = random.randint(50, 200)
            
            # Бонус за уровень
            level_bonus = data["level"] * 5
            total_reward = reward + level_bonus
            
            # Добавляем деньги и опыт
            await economy.update_balance(ctx.author.id, ctx.guild.id, total_reward)
            level_up = await economy.add_xp(ctx.author.id, ctx.guild.id, 10)
            
            # Обновляем время получения
            await bot.db.execute(
                "UPDATE users SET daily_claimed = ? WHERE user_id = ? AND guild_id = ?",
                (datetime.now().isoformat(), ctx.author.id, ctx.guild.id)
            )
            await bot.db.commit()
            
            embed = discord.Embed(
                title="🎁 Ежедневная награда",
                description=f"Вы получили **{total_reward}** 💰",
                color=discord.Color.green(),
                timestamp=datetime.now()
            )
            embed.add_field(name="Базовая сумма", value=f"{reward} 💰", inline=True)
            embed.add_field(name="Бонус за уровень", value=f"+{level_bonus} 💰", inline=True)
            embed.add_field(name="Получено опыта", value="+10 XP", inline=True)
            
            if level_up:
                embed.add_field(name="🎉 Новый уровень!", value=f"Теперь у вас **{level_up}** уровень!", inline=False)
            
            embed.set_footer(text="Следующая награда через 24 часа")
            
            await ctx.send(embed=embed)
            logger.info(f'{ctx.author} получил daily: {total_reward} 💰')
            
        except Exception as e:
            await ctx.send(f"❌ Ошибка при получении награды: {e}", ephemeral=True)
            logger.error(f'Ошибка daily: {e}')
    
    @bot.hybrid_command(name="pay", description="Перевести деньги участнику")
    @app_commands.describe(member="Участник для перевода", amount="Сумма перевода")
    async def pay_cmd(ctx: commands.Context, member: discord.Member, amount: int):
        """Перевод денег"""
        try:
            if member == ctx.author:
                await ctx.send("❌ Нельзя перевести деньги самому себе", ephemeral=True)
                return
                
            if amount <= 0:
                await ctx.send("❌ Сумма должна быть положительной", ephemeral=True)
                return
                
            sender_data = await economy.get_user_data(ctx.author.id, ctx.guild.id)
            
            if sender_data["balance"] < amount:
                await ctx.send("❌ Недостаточно средств", ephemeral=True)
                return
            
            # Переводим деньги
            await economy.update_balance(ctx.author.id, ctx.guild.id, -amount)
            await economy.update_balance(member.id, ctx.guild.id, amount)
            
            # Добавляем опыт
            await economy.add_xp(ctx.author.id, ctx.guild.id, 5)
            await economy.add_xp(member.id, ctx.guild.id, 3)
            
            embed = discord.Embed(
                title="💸 Перевод выполнен",
                description=f"**{ctx.author.mention}** перевел **{amount}** 💰 **{member.mention}**",
                color=discord.Color.green(),
                timestamp=datetime.now()
            )
            embed.add_field(name="Новый баланс отправителя", value=f"{sender_data['balance'] - amount} 💰", inline=True)
            
            await ctx.send(embed=embed)
            logger.info(f'{ctx.author} перевел {amount} 💰 {member.name}')
            
        except Exception as e:
            await ctx.send(f"❌ Ошибка при переводе: {e}", ephemeral=True)
            logger.error(f'Ошибка pay: {e}')
    
    @bot.hybrid_command(name="coinflip", description="Подбросить монетку на деньги")
    @app_commands.describe(amount="Ставка", choice="Ваш выбор: орёл или решка")
    @commands.cooldown(1, 30, commands.BucketType.user)
    async def coinflip_cmd(ctx: commands.Context, amount: int, choice: str):
        """Игра в орёл/решка"""
        try:
            if amount <= 0:
                await ctx.send("❌ Ставка должна быть положительной", ephemeral=True)
                return
                
            if amount > 1000:
                await ctx.send("❌ Максимальная ставка: 1000 💰", ephemeral=True)
                return
                
            user_data = await economy.get_user_data(ctx.author.id, ctx.guild.id)
            
            if user_data["balance"] < amount:
                await ctx.send("❌ Недостаточно средств", ephemeral=True)
                return
            
            # Валидация выбора
            choice = choice.lower()
            if choice not in ["орёл", "орел", "решка"]:
                await ctx.send("❌ Выберите 'орёл' или 'решка'", ephemeral=True)
                return
            
            # Подбрасываем монетку
            result = random.choice(["орёл", "решка"])
            win = (choice == "орёл" or choice == "орел") and result == "орёл" or choice == "решка" and result == "решка"
            
            if win:
                win_amount = amount * 2
                await economy.update_balance(ctx.author.id, ctx.guild.id, win_amount)
                await economy.add_xp(ctx.author.id, ctx.guild.id, 15)
                
                embed = discord.Embed(
                    title="🎉 Поздравляем! Вы выиграли!",
                    description=f"Выпало: **{result}**\nВы выбрали: **{choice}**",
                    color=discord.Color.green(),
                    timestamp=datetime.now()
                )
                embed.add_field(name="Ставка", value=f"{amount} 💰", inline=True)
                embed.add_field(name="Выигрыш", value=f"{win_amount} 💰", inline=True)
                embed.add_field(name="Новый баланс", value=f"{user_data['balance'] + win_amount} 💰", inline=True)
                
                logger.info(f'{ctx.author} выиграл в coinflip: {win_amount} 💰')
            else:
                await economy.update_balance(ctx.author.id, ctx.guild.id, -amount)
                
                embed = discord.Embed(
                    title="😢 Вы проиграли",
                    description=f"Выпало: **{result}**\nВы выбрали: **{choice}**",
                    color=discord.Color.red(),
                    timestamp=datetime.now()
                )
                embed.add_field(name="Потеряно", value=f"{amount} 💰", inline=True)
                embed.add_field(name="Новый баланс", value=f"{user_data['balance'] - amount} 💰", inline=True)
                
                logger.info(f'{ctx.author} проиграл в coinflip: {amount} 💰')
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            await ctx.send(f"❌ Ошибка в игре: {e}", ephemeral=True)
            logger.error(f'Ошибка coinflip: {e}')
    
    @bot.hybrid_command(name="work", description="Заработать деньги (кулдаун 1 час)")
    @commands.cooldown(1, 3600, commands.BucketType.user)  # 1 час
    async def work_cmd(ctx: commands.Context):
        """Работа для заработка денег"""
        try:
            # Случайная работа и зарплата
            jobs = [
                {"name": "👨‍💻 Программист", "salary": (80, 150)},
                {"name": "👷‍♂️ Строитель", "salary": (50, 100)},
                {"name": "👨‍🍳 Повар", "salary": (40, 90)},
                {"name": "👨‍🏫 Учитель", "salary": (60, 110)},
                {"name": "🚚 Водитель", "salary": (45, 95)},
                {"name": "🛒 Продавец", "salary": (35, 85)},
            ]
            
            job = random.choice(jobs)
            salary = random.randint(job["salary"][0], job["salary"][1])
            
            # Бонус за уровень
            data = await economy.get_user_data(ctx.author.id, ctx.guild.id)
            level_bonus = data["level"] * 3
            total_salary = salary + level_bonus
            
            # Добавляем деньги и опыт
            await economy.update_balance(ctx.author.id, ctx.guild.id, total_salary)
            level_up = await economy.add_xp(ctx.author.id, ctx.guild.id, 20)
            
            embed = discord.Embed(
                title="💼 Работа выполнена",
                description=f"Вы поработали как **{job['name']}**",
                color=discord.Color.blue(),
                timestamp=datetime.now()
            )
            embed.add_field(name="Зарплата", value=f"{salary} 💰", inline=True)
            embed.add_field(name="Бонус за уровень", value=f"+{level_bonus} 💰", inline=True)
            embed.add_field(name="Всего заработано", value=f"**{total_salary}** 💰", inline=True)
            embed.add_field(name="Опыт", value="+20 XP", inline=True)
            
            if level_up:
                embed.add_field(name="🎉 Новый уровень!", value=f"Теперь у вас **{level_up}** уровень!", inline=False)
            
            embed.set_footer(text="Следующая работа через 1 час")
            
            await ctx.send(embed=embed)
            logger.info(f'{ctx.author} поработал: {total_salary} 💰')
            
        except Exception as e:
            await ctx.send(f"❌ Ошибка при работе: {e}", ephemeral=True)
            logger.error(f'Ошибка work: {e}')
    
    @bot.hybrid_command(name="leaderboard", description="Таблица лидеров по балансу или уровню")
    @app_commands.describe(type="Тип таблицы: balance или level")
    async def leaderboard_cmd(ctx: commands.Context, type: str = "balance"):
        """Таблица лидеров"""
        try:
            if type not in ["balance", "level"]:
                await ctx.send("❌ Доступные типы: balance, level", ephemeral=True)
                return
                
            leaderboard = await economy.get_leaderboard(ctx.guild.id, 10, type)
            
            if not leaderboard:
                await ctx.send("📭 Таблица лидеров пуста")
                return
            
            embed = discord.Embed(
                title=f"🏆 Таблица лидеров ({type})",
                color=discord.Color.gold(),
                timestamp=datetime.now()
            )
            
            medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
            
            for i, (user_id, value) in enumerate(leaderboard):
                try:
                    member = await ctx.guild.fetch_member(user_id)
                    name = member.display_name
                except:
                    name = f"User {user_id}"
                
                if type == "balance":
                    embed.add_field(
                        name=f"{medals[i] if i < len(medals) else f'{i+1}.'} {name}",
                        value=f"**{value}** 💰",
                        inline=False
                    )
                else:
                    embed.add_field(
                        name=f"{medals[i] if i < len(medals) else f'{i+1}.'} {name}",
                        value=f"Уровень **{value}**",
                        inline=False
                    )
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            await ctx.send(f"❌ Ошибка при показе таблицы: {e}", ephemeral=True)
            logger.error(f'Ошибка leaderboard: {e}')
    
    @bot.hybrid_command(name="shop", description="Показать магазин")
    async def shop_cmd(ctx: commands.Context):
        """Магазин предметов"""
        try:
            cursor = await bot.db.execute("SELECT * FROM economy_items")
            items = await cursor.fetchall()
            
            if not items:
                await ctx.send("🛒 Магазин пуст")
                return
            
            embed = discord.Embed(
                title="🛒 Магазин",
                description="Покупайте предметы командой `!buy <id>`",
                color=discord.Color.purple(),
                timestamp=datetime.now()
            )
            
            for item in items[:12]:  # Ограничиваем 12 предметами
                embed.add_field(
                    name=f"**{item[1]}** (ID: {item[0]})",
                    value=f"{item[2]}\nЦена: **{item[3]}** 💰\nТип: {item[4]} | Эффект: {item[5]}",
                    inline=True
                )
            
            embed.set_footer(text=f"Всего предметов: {len(items)}")
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            await ctx.send(f"❌ Ошибка при показе магазина: {e}", ephemeral=True)
            logger.error(f'Ошибка shop: {e}')
    
    @bot.hybrid_command(name="buy", description="Купить предмет из магазина")
    @app_commands.describe(item_id="ID предмета для покупки")
    async def buy_cmd(ctx: commands.Context, item_id: int):
        """Покупка предмета"""
        try:
            # Проверяем предмет
            cursor = await bot.db.execute(
                "SELECT * FROM economy_items WHERE id = ?",
                (item_id,)
            )
            item = await cursor.fetchone()
            
            if not item:
                await ctx.send("❌ Предмет не найден", ephemeral=True)
                return
            
            # Проверяем баланс
            user_data = await economy.get_user_data(ctx.author.id, ctx.guild.id)
            
            if user_data["balance"] < item[3]:
                await ctx.send("❌ Недостаточно средств", ephemeral=True)
                return
            
            # Покупаем предмет
            await economy.update_balance(ctx.author.id, ctx.guild.id, -item[3])
            
            # Добавляем в инвентарь
            inventory = user_data["inventory"]
            inventory.append({
                "id": item[0],
                "name": item[1],
                "description": item[2],
                "type": item[4],
                "effect": item[5],
                "bought_at": datetime.now().isoformat()
            })
            
            await bot.db.execute(
                "UPDATE users SET inventory = ? WHERE user_id = ? AND guild_id = ?",
                (json.dumps(inventory), ctx.author.id, ctx.guild.id)
            )
            await bot.db.commit()
            
            # Добавляем опыт
            await economy.add_xp(ctx.author.id, ctx.guild.id, 25)
            
            embed = discord.Embed(
                title="✅ Покупка успешна!",
                description=f"Вы купили **{item[1]}**",
                color=discord.Color.green(),
                timestamp=datetime.now()
            )
            embed.add_field(name="Описание", value=item[2], inline=False)
            embed.add_field(name="Цена", value=f"{item[3]} 💰", inline=True)
            embed.add_field(name="Тип", value=item[4], inline=True)
            embed.add_field(name="Эффект", value=item[5], inline=True)
            embed.add_field(name="Новый баланс", value=f"{user_data['balance'] - item[3]} 💰", inline=True)
            embed.add_field(name="В инвентаре", value=f"{len(inventory)} предметов", inline=True)
            
            await ctx.send(embed=embed)
            logger.info(f'{ctx.author} купил предмет {item[1]} за {item[3]} 💰')
            
        except Exception as e:
            await ctx.send(f"❌ Ошибка при покупке: {e}", ephemeral=True)
            logger.error(f'Ошибка buy: {e}')
    
    logger.info("Модуль экономики загружен")