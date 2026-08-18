"""
Модуль математических команд
Команды: вычисления, конвертация, геометрия
"""

import logging
import math

import discord
from discord.ext import commands
from discord import app_commands

logger = logging.getLogger('discord_bot.math_tools')


def setup_math_tools(bot):
    """Настройка математических команд"""

    @bot.command(name="add", description="Сложение")
    async def add(ctx, a: float, b: float):
        await ctx.send(f"➕ {a} + {b} = **{a + b}**")

    @bot.command(name="sub", description="Вычитание")
    async def sub(ctx, a: float, b: float):
        await ctx.send(f"➖ {a} - {b} = **{a - b}**")

    @bot.command(name="mul", description="Умножение")
    async def mul(ctx, a: float, b: float):
        await ctx.send(f"✖️ {a} × {b} = **{a * b}**")

    @bot.command(name="div", description="Деление")
    async def div(ctx, a: float, b: float):
        if b == 0:
            await ctx.send("❌ Деление на ноль", ephemeral=True)
            return
        await ctx.send(f"➗ {a} ÷ {b} = **{a / b}**")

    @bot.command(name="pow", description="Возведение в степень")
    async def pow_cmd(ctx, base: float, exponent: float):
        try:
            result = base ** exponent
        except OverflowError:
            await ctx.send("❌ Слишком большое число", ephemeral=True)
            return
        await ctx.send(f"🔢 {base}^{exponent} = **{result:,.6f}**".rstrip("0").rstrip(",").rstrip(".") if isinstance(result, float) else f"🔢 {base}^{exponent} = **{result}**")

    @bot.command(name="sqrt", description="Квадратный корень")
    async def sqrt(ctx, number: float):
        if number < 0:
            await ctx.send("❌ Корень из отрицательного", ephemeral=True)
            return
        await ctx.send(f"√{number} = **{math.sqrt(number):.4f}**".rstrip("0").rstrip(".") if math.sqrt(number) % 1 else f"√{number} = **{int(math.sqrt(number))}**")

    @bot.command(name="cbrt", description="Кубический корень")
    async def cbrt(ctx, number: float):
        result = math.copysign(abs(number) ** (1/3), number)
        await ctx.send(f"∛{number} = **{result:.4f}**")

    @bot.command(name="sin", description="Синус")
    async def sin(ctx, number: float):
        await ctx.send(f"sin({number}) = **{math.sin(number):.6f}**")

    @bot.command(name="cos", description="Косинус")
    async def cos(ctx, number: float):
        await ctx.send(f"cos({number}) = **{math.cos(number):.6f}**")

    @bot.command(name="tan", description="Тангенс")
    async def tan(ctx, number: float):
        await ctx.send(f"tan({number}) = **{math.tan(number):.6f}**")

    @bot.command(name="log", description="Логарифм")
    async def log(ctx, number: float, base_: float = 10):
        if number <= 0 or base_ <= 0 or base_ == 1:
            await ctx.send("❌ Некорректные значения", ephemeral=True)
            return
        await ctx.send(f"log{base_}({number}) = **{math.log(number, base_):.6f}**")

    @bot.command(name="ln", description="Натуральный логарифм")
    async def ln(ctx, number: float):
        if number <= 0:
            await ctx.send("❌ Число должно быть > 0", ephemeral=True)
            return
        await ctx.send(f"ln({number}) = **{math.log(number):.6f}**")

    @bot.command(name="exp", description="Экспонента")
    async def exp(ctx, number: float):
        try:
            result = math.exp(number)
        except OverflowError:
            await ctx.send("❌ Слишком большое число", ephemeral=True)
            return
        await ctx.send(f"e^{number} = **{result:.6f}**")

    @bot.command(name="abs", description="Модуль числа")
    async def abs_cmd(ctx, number: float):
        await ctx.send(f"|{number}| = **{abs(number)}**")

    @bot.command(name="round", description="Округление")
    async def round_cmd(ctx, number: float, digits: int = 0):
        await ctx.send(f"🔘 {number} → **{round(number, digits)}**")

    @bot.command(name="floor", description="Округление вниз")
    async def floor(ctx, number: float):
        await ctx.send(f"⬇️ floor({number}) = **{math.floor(number)}**")

    @bot.command(name="ceil", description="Округление вверх")
    async def ceil(ctx, number: float):
        await ctx.send(f"⬆️ ceil({number}) = **{math.ceil(number)}**")

    @bot.command(name="factorial", description="Факториал")
    async def factorial(ctx, number: int):
        if number < 0 or number > 100:
            await ctx.send("❌ Число от 0 до 100", ephemeral=True)
            return
        await ctx.send(f"❗ {number}! = **{math.factorial(number):,}**".replace(",", " "))

    @bot.command(name="fib", description="Число Фибоначчи")
    async def fib(ctx, number: int):
        if number < 0 or number > 1000:
            await ctx.send("❌ Индекс от 0 до 1000", ephemeral=True)
            return
        a, b = 0, 1
        for _ in range(number):
            a, b = b, a + b
        await ctx.send(f"🔢 F({number}) = **{a}**")

    @bot.command(name="prime", description="Проверить простоту числа")
    async def prime(ctx, number: int):
        if number < 2:
            await ctx.send(f"🔍 {number} — не простое")
            return
        for i in range(2, int(math.sqrt(number)) + 1):
            if number % i == 0:
                await ctx.send(f"🔍 {number} — не простое (делится на {i})")
                return
        await ctx.send(f"🔍 {number} — простое число")

    @bot.command(name="divisors", description="Делители числа")
    async def divisors(ctx, number: int):
        if number <= 0 or number > 10000000:
            await ctx.send("❌ Число от 1 до 10 000 000", ephemeral=True)
            return
        divs = [i for i in range(1, number + 1) if number % i == 0]
        text = ", ".join(str(d) for d in divs[:40])
        if len(divs) > 40:
            text += f" ... (+{len(divs) - 40} ещё)"
        await ctx.send(f"🔍 Делители {number} ({len(divs)}):\n{text}")

    @bot.command(name="gcd", description="НОД двух чисел")
    async def gcd(ctx, a: int, b: int):
        await ctx.send(f"🔢 НОД({a}, {b}) = **{math.gcd(a, b)}**")

    @bot.command(name="lcm", description="НОК двух чисел")
    async def lcm(ctx, a: int, b: int):
        if a == 0 or b == 0:
            await ctx.send("❌ Ноль не подходит", ephemeral=True)
            return
        result = abs(a * b) // math.gcd(a, b)
        await ctx.send(f"🔢 НОК({a}, {b}) = **{result}**")

    @bot.command(name="percent", description="Процент от числа")
    async def percent(ctx, percent: float, number: float):
        result = number * percent / 100
        await ctx.send(f"💯 {percent}% от {number} = **{result}**")

    @bot.command(name="convert", description="Конвертация единиц")
    async def convert(ctx, value: float, from_unit: str, to_unit: str):
        units = {
            "km": 1000, "m": 1, "cm": 0.01, "mm": 0.001,
            "kg": 1000, "g": 1, "mg": 0.001,
            "h": 3600, "min": 60, "s": 1,
            "kmh": 0.2778, "ms": 1,
        }
        f, t = from_unit.lower(), to_unit.lower()
        if f in units and t in units:
            result = value * units[f] / units[t]
            await ctx.send(f"🔄 {value} {f} = **{result:,.6f}** {t}".rstrip("0").rstrip(".") if result % 1 == 0 else f"🔄 {value} {f} = **{result:,.4f}** {t}")
        else:
            await ctx.send(f"❌ Неизвестные единицы. Доступны: {', '.join(units)}", ephemeral=True)

    @bot.command(name="temp", description="Конвертация температуры")
    async def temp(ctx, value: float, from_unit: str, to_unit: str):
        f, t = from_unit.upper(), to_unit.upper()
        if f == "C":
            kelvin = value + 273.15
        elif f == "F":
            kelvin = (value - 32) * 5/9 + 273.15
        elif f == "K":
            kelvin = value
        else:
            await ctx.send("❌ Используй C / F / K", ephemeral=True)
            return
        if t == "C":
            result = kelvin - 273.15
        elif t == "F":
            result = (kelvin - 273.15) * 9/5 + 32
        elif t == "K":
            result = kelvin
        else:
            await ctx.send("❌ Используй C / F / K", ephemeral=True)
            return
        await ctx.send(f"🌡️ {value}°{f} = **{result:.2f}°{t}**")

    @bot.command(name="average", description="Среднее арифметическое")
    async def average(ctx, *, numbers: str):
        try:
            nums = [float(x) for x in numbers.split()]
        except ValueError:
            await ctx.send("❌ Введи числа через пробел", ephemeral=True)
            return
        if not nums:
            await ctx.send("❌ Пустой ввод", ephemeral=True)
            return
        avg = sum(nums) / len(nums)
        await ctx.send(f"📊 Среднее: **{avg:,.4f}**".rstrip("0").rstrip(".") if avg % 1 == 0 else f"📊 Среднее: **{avg:.4f}**")

    @bot.command(name="minmax", description="Минимум и максимум")
    async def minmax(ctx, *, numbers: str):
        try:
            nums = [float(x) for x in numbers.split()]
        except ValueError:
            await ctx.send("❌ Введи числа через пробел", ephemeral=True)
            return
        if not nums:
            await ctx.send("❌ Пустой ввод", ephemeral=True)
            return
        await ctx.send(f"📊 Минимум: **{min(nums)}**\n📊 Максимум: **{max(nums)}**")

    @bot.command(name="area", description="Площадь фигуры")
    async def area(ctx, shape: str, param1: float, param2: float = 0):
        shape = shape.lower()
        if shape in ("круг", "circle"):
            result = math.pi * param1 ** 2
            label = f"Площадь круга (r={param1})"
        elif shape in ("квадрат", "square"):
            result = param1 ** 2
            label = f"Площадь квадрата (a={param1})"
        elif shape in ("треугольник", "triangle"):
            result = 0.5 * param1 * param2
            label = f"Площадь треугольника (b={param1}, h={param2})"
        elif shape in ("прямоугольник", "rectangle"):
            result = param1 * param2
            label = f"Площадь прямоугольника ({param1}×{param2})"
        else:
            await ctx.send("❌ Фигуры: круг, квадрат, треугольник, прямоугольник", ephemeral=True)
            return
        await ctx.send(f"📐 {label} = **{result:,.4f}**")

    @bot.command(name="distance", description="Расстояние между точками")
    async def distance(ctx, x1: float, y1: float, x2: float, y2: float):
        result = math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)
        await ctx.send(f"📏 Расстояние = **{result:,.4f}**")