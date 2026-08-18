"""
Модуль текстовых инструментов
Команды: преобразования текста, кодировки, генерация
"""

import base64
import binascii
import hashlib
import logging
import random
import string

import discord
from discord.ext import commands
from discord import app_commands

logger = logging.getLogger('discord_bot.text')


def setup_text(bot):
    """Настройка текстовых команд"""

    @bot.command(name="upper", description="Текст ВЕРХНИМ РЕГИСТРОМ")
    async def upper(ctx, *, text: str):
        await ctx.send(f"🔠 {text.upper()}")

    @bot.command(name="lower", description="Текст нижним регистром")
    async def lower(ctx, *, text: str):
        await ctx.send(f"🔡 {text.lower()}")

    @bot.command(name="capitalize", description="С заглавной буквы")
    async def capitalize(ctx, *, text: str):
        await ctx.send(f"✨ {text.capitalize()}")

    @bot.command(name="title", description="Каждое слово с заглавной")
    async def title(ctx, *, text: str):
        await ctx.send(f"📝 {text.title()}")

    @bot.command(name="len", description="Длина текста")
    async def length(ctx, *, text: str):
        await ctx.send(f"📏 Длина: **{len(text)}** символов")

    @bot.command(name="words", description="Количество слов")
    async def words(ctx, *, text: str):
        count = len(text.split())
        await ctx.send(f"📖 Слов: **{count}**")

    @bot.command(name="binary", description="Текст в двоичный код")
    async def binary(ctx, *, text: str):
        result = " ".join(format(ord(c), "08b") for c in text)
        await ctx.send(f"🔢 {result}")

    @bot.command(name="unbinary", description="Двоичный код в текст")
    async def unbinary(ctx, *, text: str):
        parts = text.replace(" ", "").strip()
        if len(parts) % 8 != 0:
            await ctx.send("❌ Неверный двоичный код", ephemeral=True)
            return
        result = ""
        try:
            for i in range(0, len(parts), 8):
                result += chr(int(parts[i:i+8], 2))
        except ValueError:
            await ctx.send("❌ Неверный двоичный код", ephemeral=True)
            return
        await ctx.send(f"📄 {result}")

    @bot.command(name="hex", description="Текст в HEX")
    async def hex_cmd(ctx, *, text: str):
        result = text.encode().hex()
        await ctx.send(f"🟥 {result}")

    @bot.command(name="unhex", description="HEX в текст")
    async def unhex(ctx, *, text: str):
        try:
            result = bytes.fromhex(text.replace(" ", "")).decode()
        except (ValueError, UnicodeDecodeError):
            await ctx.send("❌ Неверный HEX", ephemeral=True)
            return
        await ctx.send(f"📄 {result}")

    @bot.command(name="base64", description="Кодировать в Base64")
    async def base64_cmd(ctx, *, text: str):
        result = base64.b64encode(text.encode()).decode()
        await ctx.send(f"🔐 {result}")

    @bot.command(name="unbase64", description="Декодировать Base64")
    async def unbase64(ctx, *, text: str):
        try:
            result = base64.b64decode(text).decode()
        except (binascii.Error, UnicodeDecodeError):
            await ctx.send("❌ Неверный Base64", ephemeral=True)
            return
        await ctx.send(f"📄 {result}")

    @bot.command(name="md5", description="MD5 хеш текста")
    async def md5(ctx, *, text: str):
        await ctx.send(f"#️⃣ MD5: **{hashlib.md5(text.encode()).hexdigest()}**")

    @bot.command(name="sha256", description="SHA-256 хеш текста")
    async def sha256(ctx, *, text: str):
        await ctx.send(f"#️⃣ SHA-256: **{hashlib.sha256(text.encode()).hexdigest()}**")

    @bot.command(name="sha1", description="SHA-1 хеш текста")
    async def sha1(ctx, *, text: str):
        await ctx.send(f"#️⃣ SHA-1: **{hashlib.sha1(text.encode()).hexdigest()}**")

    @bot.command(name="password", description="Сгенерировать пароль")
    async def password(ctx, length: int = 16):
        if length < 4 or length > 128:
            await ctx.send("❌ Длина от 4 до 128", ephemeral=True)
            return
        chars = string.ascii_letters + string.digits + "!@#$%^&*"
        pwd = "".join(random.choice(chars) for _ in range(length))
        await ctx.send(f"🔑 Пароль: `{pwd}`")

    @bot.command(name="snake", description="Текст snake_case")
    async def snake(ctx, *, text: str):
        result = "_".join(text.lower().split())
        await ctx.send(f"🐍 {result}")

    @bot.command(name="kebab", description="Текст kebab-case")
    async def kebab(ctx, *, text: str):
        result = "-".join(text.lower().split())
        await ctx.send(f"🥖 {result}")

    @bot.command(name="camel", description="Текст camelCase")
    async def camel(ctx, *, text: str):
        parts = text.lower().split()
        if not parts:
            await ctx.send("❌ Пустой ввод", ephemeral=True)
            return
        result = parts[0] + "".join(p.capitalize() for p in parts[1:])
        await ctx.send(f"🐫 {result}")

    @bot.command(name="leet", description="Текст в leet (1337)")
    async def leet(ctx, *, text: str):
        table = str.maketrans({
            "а": "4", "е": "3", "о": "0", "с": "5", "т": "7", "з": "3",
            "a": "4", "e": "3", "o": "0", "s": "5", "t": "7", "i": "1", "g": "9",
            "А": "4", "Е": "3", "О": "0", "С": "5", "Т": "7",
            "A": "4", "E": "3", "O": "0", "S": "5", "T": "7", "I": "1", "G": "9",
        })
        await ctx.send(f"👾 {text.translate(table)}")

    @bot.command(name="small", description="Текст маленькими буквами")
    async def small(ctx, *, text: str):
        small_map = str.maketrans("абвгдеёжзийклмнопрстуфхцчшщъыьэюяabcdefghijklmnopqrstuvwxyz",
                                  "ᵃᵇᵛᵍᵈᵉᵉᶣᶻᶦᶦᵏˡᵐⁿᵒᵖʳˢᵗᵘᶠᵘᵛᶻᶜᶜᵗʷᵗᵗᵉᵘʸᵃᵇᶜᵈᵉᶠᵍʰᶦʲᵏˡᵐⁿᵒᵖᑫʳˢᵗᵘᵛʷˣʸᶻ")
        result = text.translate(small_map)
        await ctx.send(f"🔤 {result}")

    @bot.command(name="bold", description="Жирный текст")
    async def bold(ctx, *, text: str):
        await ctx.send(f"**{text}**")

    @bot.command(name="italic", description="Курсив")
    async def italic(ctx, *, text: str):
        await ctx.send(f"*{text}*")

    @bot.command(name="underline", description="Подчёркнутый текст")
    async def underline(ctx, *, text: str):
        await ctx.send(f"__{text}__")

    @bot.command(name="spoiler", description="Спойлер")
    async def spoiler(ctx, *, text: str):
        await ctx.send(f"||{text}||")

    @bot.command(name="strike", description="Зачёркнутый текст")
    async def strike(ctx, *, text: str):
        await ctx.send(f"~~{text}~~")

    @bot.command(name="box", description="Текст в рамке")
    async def box(ctx, *, text: str):
        await ctx.send(f"```{text}```")

    @bot.command(name="randomtext", description="Случайный текст")
    async def randomtext(ctx, length: int = 30):
        if length > 1000:
            length = 1000
        words = ["кот", "собака", "дом", "лес", "река", "звезда", "луна", "солнце", "ветер", "дождь"]
        result = " ".join(random.choice(words) for _ in range(length // 5 + 1))
        await ctx.send(f"🎲 {result}")

    @bot.command(name="lorem", description="Текст lorem ipsum")
    async def lorem(ctx, paragraphs: int = 1):
        if paragraphs > 5:
            paragraphs = 5
        words = "lorem ipsum dolor sit amet consectetur adipiscing elit sed do eiusmod tempor incididunt ut labore et dolore magna aliqua"
        result = "\n\n".join(
            " ".join(random.choice(words.split()) for _ in range(30))
            for _ in range(paragraphs)
        )
        await ctx.send(result[:1900])

    @bot.command(name="abbreviation", description="Аббревиатура из фразы")
    async def abbreviation(ctx, *, text: str):
        abbr = "".join(word[0].upper() for word in text.split() if word[0].isalpha())
        await ctx.send(f"🔤 {text} → **{abbr}**")