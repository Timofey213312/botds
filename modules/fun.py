"""
Модуль развлекательных команд
Команды: игры, рандом, реакции, развлечения
"""

import asyncio
import logging
import random
import re
from datetime import datetime

import discord
from discord.ext import commands
from discord import app_commands

logger = logging.getLogger('discord_bot.fun')

EMOJIS = ['😀', '😂', '🤣', '😊', '😍', '🥰', '😎', '🤩', '🥳', '😇', '🙃', '😉', '😜', '🤪', '😝', '🤑', '🤓', '🥸', '🤔', '🤫', '🤭', '🤐', '😴', '🤤', '😶', '😐', '😑', '😬', '🙄', '😯', '😦', '😧', '😮', '😲', '🥱', '😣', '😖', '😫', '😩', '🥺', '😢', '😭', '😤', '😠', '😡', '🤬', '🤯', '😳', '🥵', '🥶', '😱']


def setup_fun(bot):
    """Настройка развлекательных команд"""

    @bot.command(name="8ball", description="Магический шар отвечает на вопрос")
    async def eightball(ctx, *, question: str):
        answers = [
            "Бесспорно", "Предрешено", "Никаких сомнений", "Определённо да", "Можешь быть уверен в этом",
            "Мне кажется — да", "Вероятнее всего", "Хорошие перспективы", "Знаки говорят — да", "Да",
            "Пока неясно, попробуй снова", "Спроси позже", "Лучше не рассказывать", "Сейчас нельзя предсказать",
            "Сконцентрируйся и спроси опять", "Даже не думай", "Мой ответ — нет", "По моим данным — нет",
            "Перспективы не очень хорошие", "Весьма сомнительно"
        ]
        embed = discord.Embed(title="🎱 Магический шар", color=discord.Color.purple())
        embed.add_field(name="Вопрос", value=question, inline=False)
        embed.add_field(name="Ответ", value=random.choice(answers), inline=False)
        await ctx.send(embed=embed)

    @bot.command(name="coin", description="Подбросить монетку")
    async def coin(ctx):
        result = random.choice(["Орёл", "Решка"])
        emoji = "🪙"
        embed = discord.Embed(title=f"{emoji} Монетка", description=f"Выпало: **{result}**", color=discord.Color.gold())
        await ctx.send(embed=embed)

    @bot.command(name="dice", description="Бросить кубик (1-6 или N граней)")
    async def dice(ctx, sides: int = 6):
        if sides < 2:
            await ctx.send("❌ Кубик должен иметь минимум 2 грани", ephemeral=True)
            return
        if sides > 1000000:
            sides = 1000000
        result = random.randint(1, sides)
        embed = discord.Embed(title=f"🎲 Кубик (d{sides})", description=f"Выпало: **{result}**", color=discord.Color.blurple())
        await ctx.send(embed=embed)

    @bot.command(name="rps", description="Камень-ножницы-бумага")
    async def rps(ctx, choice: str):
        choice = choice.lower()
        choices = ["камень", "ножницы", "бумага"]
        if choice not in choices:
            await ctx.send("❌ Выбери: камень / ножницы / бумага", ephemeral=True)
            return
        bot_choice = random.choice(choices)
        beats = {"камень": "ножницы", "ножницы": "бумага", "бумага": "камень"}
        if choice == bot_choice:
            result = "🤝 Ничья!"
        elif beats[choice] == bot_choice:
            result = "🏆 Ты выиграл!"
        else:
            result = "🤖 Бот выиграл!"
        embed = discord.Embed(title="✂️ Камень-ножницы-бумага", color=discord.Color.blurple())
        embed.add_field(name="Ты", value=choice, inline=True)
        embed.add_field(name="Бот", value=bot_choice, inline=True)
        embed.add_field(name="Итог", value=result, inline=False)
        await ctx.send(embed=embed)

    @bot.command(name="meme", description="Случайный мем")
    async def meme(ctx):
        try:
            async with bot.session.get("https://meme-api.com/gimme") as resp:
                data = await resp.json()
            embed = discord.Embed(title=data.get("title", "Мем"), color=discord.Color.orange())
            embed.set_image(url=data.get("url", ""))
            embed.set_footer(text=f"Автор: {data.get('author', 'unknown')} | {data.get('subreddit', '')}")
            await ctx.send(embed=embed)
        except Exception:
            memes = [
                "https://i.imgur.com/1kQYfQw.jpg", "https://i.imgur.com/6QZnZnc.jpg",
                "https://i.imgur.com/pT3XmJp.jpg", "https://i.imgur.com/2KxqxKq.jpg",
            ]
            embed = discord.Embed(title="Мем", color=discord.Color.orange())
            embed.set_image(url=random.choice(memes))
            await ctx.send(embed=embed)

    @bot.command(name="joke", description="Случайная шутка")
    async def joke(ctx):
        jokes = [
            "Программист — это человек, который решает проблемы, о существовании которых вы не знали, методами, которых вы не понимаете.",
            "У меня есть план побега. Он называется «закрыть вкладки с задачами».",
            "Идёт заяц по лесу, видит — сто рублей лежат. Наклонился поднять, а это клей.",
            "Лучший способ отпраздновать — это... подождать, я забыл.",
            "Почему программисты путают Хэллоуин и Рождество? Потому что OCT 31 == DEC 25.",
            "Сложность разработки: сначала казалось, что одна строка, потом оказалось, что весь файл.",
            "Я не ленивый, я в режиме энергосбережения.",
            "Воркаут: от слова «воркать» и «аут».",
        ]
        await ctx.send(random.choice(jokes))

    @bot.command(name="roast", description="Подколоть пользователя")
    async def roast(ctx, member: discord.Member = None):
        member = member or ctx.author
        roasts = [
            f"{member.mention} такой медленный, что на таймауте не замечают.",
            f"{member.mention} зашёл в голосовой канал, и там стало тише.",
            f"{member.mention} использует интернет через факс.",
            f"{member.mention} — живое доказательство того, что природа умеет ошибаться.",
            f"{member.mention}, твой Wi-Fi быстрее, чем твои мысли.",
            f"{member.mention} настолько токсичен, что после него чат нужно проветривать.",
            f"{member.mention} — единственный человек, который молчит громче всех.",
        ]
        await ctx.send(random.choice(roasts))

    @bot.command(name="compliment", description="Комплимент пользователю")
    async def compliment(ctx, member: discord.Member = None):
        member = member or ctx.author
        comps = [
            f"{member.mention}, ты прекрасен как код без багов!",
            f"{member.mention}, твоя энергия заряжает весь сервер!",
            f"{member.mention}, ты — MVP этого сервера.",
            f"{member.mention}, даже бот восхищается тобой.",
            f"{member.mention}, ты умеешь слушать — редкое качество.",
            f"{member.mention}, с тобой любой голосовой канал становится лучше.",
        ]
        await ctx.send(random.choice(comps))

    @bot.command(name="ship", description="Проверить совместимость двух людей")
    async def ship(ctx, member1: discord.Member, member2: discord.Member = None):
        member2 = member2 or ctx.author
        percent = random.randint(0, 100)
        bar = "❤️" * (percent // 10) + "🖤" * (10 - percent // 10)
        text = f"{member1.mention} + {member2.mention}"
        desc = f"Совместимость: **{percent}%**\n{bar}"
        if percent > 80:
            desc += "\n💞 Идеальная пара!"
        elif percent > 50:
            desc += "\n💕 Есть перспективы!"
        elif percent > 25:
            desc += "\n💔 Может, друзьями?"
        else:
            desc += "\n😬 Лучше не рисковать."
        embed = discord.Embed(title=f"💘 {text}", description=desc, color=discord.Color.pink())
        await ctx.send(embed=embed)

    @bot.command(name="rate", description="Оценить что-либо от 0 до 10")
    async def rate(ctx, *, item: str):
        percent = random.randint(0, 10)
        await ctx.send(f"⭐ **{item}** — {percent}/10")

    @bot.command(name="fortune", description="Предсказание судьбы")
    async def fortune(ctx):
        fates = [
            "Тебя ждёт великое открытие.", "Сегодня удачный день для решений.",
            "Не бойся перемен — они к лучшему.", "Скоро тебя ждёт приятный сюрприз.",
            "Твои усилия скоро окупятся.", "Впереди новая дружба.",
            "Берегись — всё слишком хорошо, чтобы быть правдой.", "Ты встретишь интересного человека.",
            "Удача на твоей стороне сегодня.", "Маленькие шаги ведут к большой цели.",
        ]
        embed = discord.Embed(title="🔮 Предсказание", description=random.choice(fates), color=discord.Color.purple())
        await ctx.send(embed=embed)

    @bot.command(name="emojify", description="Перевести текст в эмодзи")
    async def emojify(ctx, *, text: str):
        result = ""
        for ch in text.lower():
            if ch.isalpha():
                result += f":regional_indicator_{ch}: "
            elif ch == " ":
                result += "  "
            elif ch.isdigit():
                digits = {"0": "0️⃣", "1": "1️⃣", "2": "2️⃣", "3": "3️⃣", "4": "4️⃣", "5": "5️⃣", "6": "6️⃣", "7": "7️⃣", "8": "8️⃣", "9": "9️⃣"}
                result += digits[ch] + " "
            else:
                result += ch + " "
        await ctx.send(result[:2000] or "❌ Пустой результат")

    @bot.command(name="reverse", description="Перевернуть текст")
    async def reverse(ctx, *, text: str):
        await ctx.send(f"🔁 {text[::-1]}")

    @bot.command(name="uwu", description="Перевести текст в uwu-стиль")
    async def uwu(ctx, *, text: str):
        uwu_text = text.replace("л", "w").replace("Л", "W")
        uwu_text = uwu_text.replace("r", "w").replace("R", "W")
        uwu_text = uwu_text.replace("на", "ня").replace("На", "Ня")
        if random.random() < 0.5:
            uwu_text += " uwu"
        await ctx.send(f"💖 {uwu_text}")

    @bot.command(name="mock", description="Высмеять текст (перемешать регистры)")
    async def mock(ctx, *, text: str):
        result = "".join(c.upper() if i % 2 else c.lower() for i, c in enumerate(text))
        await ctx.send(f"🃏 {result}")

    @bot.command(name="slap", description="Дать пощёчину")
    async def slap(ctx, member: discord.Member = None):
        member = member or ctx.author
        await ctx.send(f"👋 {ctx.author.mention} дал пощёчину {member.mention}!")

    @bot.command(name="hug", description="Обнять")
    async def hug(ctx, member: discord.Member = None):
        member = member or ctx.author
        await ctx.send(f"🤗 {ctx.author.mention} обнял {member.mention}!")

    @bot.command(name="kiss", description="Поцеловать")
    async def kiss(ctx, member: discord.Member = None):
        member = member or ctx.author
        await ctx.send(f"😘 {ctx.author.mention} поцеловал {member.mention}!")

    @bot.command(name="punch", description="Ударить")
    async def punch(ctx, member: discord.Member = None):
        member = member or ctx.author
        await ctx.send(f"👊 {ctx.author.mention} ударил {member.mention}!")

    @bot.command(name="pat", description="Погладить")
    async def pat(ctx, member: discord.Member = None):
        member = member or ctx.author
        await ctx.send(f"🖐️ {ctx.author.mention} погладил {member.mention} по голове.")

    @bot.command(name="spank", description="Шлепнуть")
    async def spank(ctx, member: discord.Member = None):
        member = member or ctx.author
        await ctx.send(f"🍑 {ctx.author.mention} шлепнул {member.mention}!")

    @bot.command(name="cuddle", description="Потискать")
    async def cuddle(ctx, member: discord.Member = None):
        member = member or ctx.author
        await ctx.send(f"🥰 {ctx.author.mention} потискал {member.mention}.")

    @bot.command(name="highfive", description="Дай пять")
    async def highfive(ctx, member: discord.Member = None):
        member = member or ctx.author
        await ctx.send(f"✋ {ctx.author.mention} дал пять {member.mention}!")

    @bot.command(name="bite", description="Укусить")
    async def bite(ctx, member: discord.Member = None):
        member = member or ctx.author
        await ctx.send(f"🦷 {ctx.author.mention} укусил {member.mention}!")

    @bot.command(name="pet", description="Погладить (как pet)")
    async def pet(ctx, member: discord.Member = None):
        member = member or ctx.author
        await ctx.send(f"🐾 {ctx.author.mention} погладил {member.mention} как домашнего питомца.")

    @bot.command(name="random", description="Случайное число в диапазоне")
    async def random_cmd(ctx, minimum: int = 1, maximum: int = 100):
        if minimum > maximum:
            minimum, maximum = maximum, minimum
        if maximum - minimum > 1000000000:
            maximum = minimum + 1000000000
        await ctx.send(f"🎲 Случайное число: **{random.randint(minimum, maximum)}**")

    @bot.command(name="choose", description="Бот выберет один вариант")
    async def choose(ctx, *, options: str):
        parts = [p.strip() for p in re.split(r"[,|]", options) if p.strip()]
        if len(parts) < 2:
            await ctx.send("❌ Укажи минимум 2 варианта через запятую", ephemeral=True)
            return
        await ctx.send(f"🤔 Я выбираю: **{random.choice(parts)}**")

    @bot.command(name="spinner", description="Вращающийся выбор из вариантов")
    async def spinner(ctx, *, options: str):
        parts = [p.strip() for p in re.split(r"[,|]", options) if p.strip()]
        if len(parts) < 2:
            await ctx.send("❌ Укажи минимум 2 варианта", ephemeral=True)
            return
        message = await ctx.send("🌀 Крутится: ...")
        chosen = None
        for _ in range(10):
            chosen = random.choice(parts)
            await message.edit(content=f"🌀 Крутится: **{chosen}**")
            await asyncio.sleep(0.3)
        await message.edit(content=f"🎯 Выбор: **{chosen}**")

    @bot.command(name="iq", description="Замерить IQ")
    async def iq(ctx, member: discord.Member = None):
        member = member or ctx.author
        iq_value = random.randint(1, 200)
        await ctx.send(f"🧠 IQ пользователя {member.mention}: **{iq_value}**")

    @bot.command(name="gay", description="Измерить гей-метр")
    async def gay(ctx, member: discord.Member = None):
        member = member or ctx.author
        value = random.randint(0, 100)
        bar = "🏳️‍🌈" * (value // 10) + "⬜" * (10 - value // 10)
        await ctx.send(f"🏳️‍🌈 Гей-метр {member.mention}: **{value}%**\n{bar}")

    @bot.command(name="simp", description="Измерить симпатию")
    async def simp(ctx, member: discord.Member = None):
        member = member or ctx.author
        value = random.randint(0, 100)
        await ctx.send(f"💀 Симпатия {member.mention}: **{value}%**")

    @bot.command(name="topics", description="Случайная тема для разговора")
    async def topics(ctx):
        topics_list = [
            "Что бы ты делал с машиной времени?",
            "Твой идеальный отпуск — где и с кем?",
            "Какая суперспособность тебе нужна?",
            "Чему бы ты научился за месяц?",
            "Твоя любимая игра детства?",
            "Что бы ты сказал себе в прошлом?",
            "Какое место ты бы посетил прямо сейчас?",
            "Что тебя мотивирует больше всего?",
            "Какой предмет ты бы добавил в школу?",
            "Что делает человека интересным?",
        ]
        await ctx.send(f"💬 {random.choice(topics_list)}")

    @bot.command(name="wouldyou", description="Случайный вопрос «Что бы ты выбрал?»")
    async def wouldyou(ctx):
        questions = [
            "Никогда не пользоваться интернетом или никогда не есть вкусную еду?",
            "Быть всегда правым или всегда счастливым?",
            "Потерять все воспоминания или никогда не создавать новые?",
            "Уметь летать или быть невидимым?",
            "Говорить на всех языках или играть на всех инструментах?",
            "Жить на Луне или под водой?",
            "Иметь бесконечные деньги или бесконечное время?",
            "Быть известным сейчас или великим через 100 лет?",
        ]
        await ctx.send(f"🤔 {random.choice(questions)}")

    @bot.command(name="ascii", description="Случайный ASCII-арт")
    async def ascii(ctx):
        arts = [
            r"(-. )_( .-)",
            r"( •_•)",
            r"( •_•)>⌐■-■",
            r"(⌐■_■)",
            r"¯\_(ツ)_/¯",
            r"(╯°□°）╯︵ ┻━┻",
            r"(ノಠ益ಠ)ノ彡┻━┻",
            r"(づ｡◕‿‿◕｡)づ",
            r"( ◕‿◕)",
            r"[̲̅$̲̅(̲̅ ͡° ͜ʖ ͡°̲̅)̲̅$̲̅]",
        ]
        await ctx.send(f"```{random.choice(arts)}```")

    @bot.command(name="roll", description="Бросить несколько кубиков")
    async def roll(ctx, count: int = 2, sides: int = 6):
        if count > 50:
            count = 50
        results = [random.randint(1, sides) for _ in range(count)]
        total = sum(results)
        embed = discord.Embed(title=f"🎲 {count}d{sides}", color=discord.Color.blurple())
        embed.add_field(name="Результаты", value=", ".join(str(r) for r in results), inline=False)
        embed.add_field(name="Сумма", value=str(total), inline=False)
        await ctx.send(embed=embed)

    @bot.command(name="flip", description="Случайный флип слова")
    async def flip(ctx, *, text: str):
        flip_map = str.maketrans({
            "a": "ɐ", "b": "q", "c": "ɔ", "d": "p", "e": "ǝ", "f": "ɟ", "g": "ƃ",
            "h": "ɥ", "i": "ᴉ", "j": "ɾ", "k": "ʞ", "l": "l", "m": "ɯ", "n": "u",
            "o": "o", "p": "d", "q": "b", "r": "ɹ", "s": "s", "t": "ʇ", "u": "n",
            "v": "ʌ", "w": "ʍ", "x": "x", "y": "ʎ", "z": "z",
            "A": "∀", "B": "𐐒", "C": "Ɔ", "D": "ᗡ", "E": "Ǝ", "F": "Ⅎ", "G": "פ",
            "H": "H", "I": "I", "J": "ſ", "K": "ʞ", "L": "˥", "M": "W", "N": "N",
            "O": "O", "P": "Ԁ", "Q": "Q", "R": "ᴚ", "S": "S", "T": "⊥", "U": "∩",
            "V": "Λ", "W": "M", "X": "X", "Y": "⅄", "Z": "Z",
        })
        await ctx.send(f"🔄 {text.translate(flip_map)[::-1]}")

    @bot.command(name="zalgo", description="Проклятый текст")
    async def zalgo(ctx, *, text: str):
        marks = ["̷", "̸", "̶", "̵", "͜", "̆", "̑", "̇", "̣", "̈", "̊", "̋", "̌", "̍", "̎", "̏", "̐", "̑"]
        zalgo_text = ""
        for ch in text:
            zalgo_text += ch
            if ch != " ":
                zalgo_text += "".join(random.choice(marks) for _ in range(random.randint(1, 3)))
        await ctx.send(zalgo_text[:1900])

    @bot.command(name="murder", description="Криминальная история")
    async def murder(ctx):
        persons = ["Томас", "Виктор", "Максим", "Алекс", "Денис"]
        weapons = ["свечкой", "верёвкой", "карандашом", "гаечным ключом", "телефоном"]
        rooms = ["в библиотеке", "в подвале", "на кухне", "в гостиной", "на чердаке"]
        await ctx.send(
            f"🕵️ {ctx.author.mention}, в доме произошло преступление! "
            f"**{random.choice(persons)}** убит **{random.choice(weapons)}** {random.choice(rooms)}. "
            f"Подозреваемый: **{random.choice([p for p in persons if p != 'Томас'])}**."
        )

    @bot.command(name="dadjoke", description="Папина шутка")
    async def dadjoke(ctx):
        jokes = [
            "Я бы рассказал шутку про стул, но она кривовата.",
            "Почему осы жужжат? Потому что у них нет рук, чтобы писать.",
            "Как называют медведя без зубов? Желейный мишка.",
            "Что говорит один нос другому? Не суй свой нос в мои дела!",
            "Почему программист перепутал Рождество и Хэллоуин? OCT 31 = DEC 25.",
            "Какой любимый напиток программиста? Чай-ГПТ.",
        ]
        await ctx.send(random.choice(jokes))

    @bot.command(name="trump", description="Цитата Трампа")
    async def trump(ctx):
        quotes = [
            "У меня отличные слова. Лучшие слова.",
            "Мы сделаем это великим.",
            "Стройте стену!",
            "Никто не знает лучше, чем я.",
            "Фейковые новости!",
            "Это я придумал этот термин.",
        ]
        await ctx.send(f"🇺🇸 «{random.choice(quotes)}» — Д. Трамп")

    @bot.command(name="biden", description="Цитата Байдена")
    async def biden(ctx):
        quotes = [
            "Ну же, ребята, это же просто.",
            "Я шучу, конечно.",
            "Где я?.. А, точно.",
            "Мы справимся.",
            "Это всё про народ.",
        ]
        await ctx.send(f"🇺🇸 «{random.choice(quotes)}» — Дж. Байден")

    @bot.command(name="charinfo", description="Информация о символе/эмодзи")
    async def charinfo(ctx, *, char: str):
        if len(char) > 1:
            char = char[0]
        embed = discord.Embed(title=f"Символ: {char}", color=discord.Color.blurple())
        embed.add_field(name="Code point", value=f"U+{ord(char):04X}", inline=False)
        embed.add_field(name="Десятичный", value=str(ord(char)), inline=False)
        embed.add_field(name="Название", value=f"\\N{{{char}}}" if '\\N' else "-", inline=False)
        await ctx.send(embed=embed)

    @bot.command(name="cowsay", description="Корова говорит")
    async def cowsay(ctx, *, text: str):
        if len(text) > 40:
            text = text[:40] + "..."
        cow = f"┌─{'─' * (len(text) + 2)}─┐\n│ {text} │\n└─{'─' * (len(text) + 2)}─┘\n  \\   ^__^\n   \\  (oo)\\_______\n      (__)\\       )\\/\\\n          ||----w |\n          ||     ||"
        await ctx.send(f"```{cow}```")