"""
Модуль антирекламы с OCR-мониторингом изображений
Автоматически проверяет все текстовые каналы на фото с рекламой:
  - казино/ставки (1win, фонбет, депозит, фриспины и т.д.)
  - наркотики (мел, соль, меф и т.д.)
Распознавание текста на фото через Tesseract (OCR), плюс проверка текста/ссылок.
Бот логирует распознанный текст в канал логов для проверки работы OCR.
"""

import asyncio
import io
import json
import logging
import re

import discord
from discord.ext import commands
from discord import app_commands

try:
    from PIL import Image
    import pytesseract
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False

logger = logging.getLogger('discord_bot.antispam')

CASINO_WORDS = [
    "казин", "казик", "казіно", "ставк", "ставки", "бонус", "депозит", "фриспин",
    "фриспины", "1win", "1вин", "1xbet", "фонбет", "winline", "леон", "betboom",
    "букмекер", "букмекерск", "джекпот", "лотерея", "играть на деньги", "ставка",
    "казино онлайн", "csg", "bet", "win", "ставь", "прогноз", "экспресс ставк",
    "розыгрыш", "бесплатн", "кэшбэк", "официальн", "зеркал", "регистрац",
    "выигрыш", "лотере", "плей", "казна", "автомат", "слот", "тотализатор",
    "пари", "bet365", "betcity", "winner", "ligastavok", "marathon",
    "parimatch", "olimp", "mostbet", "pari", "fanbet", "zenitbet", "лотто",
    "фрибет", "бездеп", "бездепозит", "пополн", "вывод", "выплат", "рулетк",
    "блэкджек", "покер", "гембл", "casino", "азарт", "ставочк", "коэффициент",
    "тотал", "фору", "ординар", "ставки на спорт", "играть бесплатно",
    "демо счёт", "честное казино", "топ казино", "лучшее казино", "рабочее зеркал",
    "ставок", "бк", "выигрыш", "ставочка",
]

DRUG_WORDS = [
    "мел", "меф", "мет", "соль", "мука", "скорость", "амф", "спайс", "травк",
    "гашиш", "кока", "героин", "метадон", "экстази", "mdma", "lsd", "наркот",
    "нарко", "доз", "ширк", "мефедрон", "бошк", "план", "гандж", "анаш", "марихуан",
    "каннаб", "психотроп", "закадр", "соль для варк", "кури", "шишк", "солевар",
    "растам", "дурь", "колес", "гриб", "мухомор", "мелстрой", "мелстроев",
    "мелстрою", "мель", "сольвар", "варка", "варк", "варим", "порошок", "раствор",
    "шприц", "амфетамин", "метамфетамин", "первитин", "эфедрин", "бошки", "самокрутк",
    "косяк", "кокаин", "телеграм бот", "t.me", "закладк", "клад", "кладмен",
    "купить", "продам", "грамм", "грам", "vape", "жижа", "соль для ванн",
    "эйфор", "кайф", "ломк", "доза", "наркота", "наркоман", "солевар",
]

STRONG_WORDS = ["казино", "казик", "1win", "1вин", "фонбет", "1xbet", "мефедрон",
                "героин", "метадон", "спайс", "экстази", "мелстрой", "мистер бист",
                "mrbeast", "мефедрон"]

SPAM_WORDS = [
    "mebeast", "mrbeast", "@mebeast", "mr beast", "мистер бист", "мистербист",
    "mister beast", "misterbeast", "бист", "беаст", "мистербеаст", "@mrbeast",
    "beast", "beastbot", "beast giveaway", "розыгрыш от beast", "giveaway",
    "бесплатный айфон", "iphone бесплатно", "free iphone", "розыгрыш денег",
    "бесплатные деньги", "выиграй айфон", "подарок от", "1000$",
]

CASINO_DOMAINS = [
    "1win", "1xbet", "fonbet", "winline", "leon", "betboom", "parimatch",
    "ligastavok", "betfair", "marathonbet", "olimpbet", "pari", "winner",
    "mostbet", "betcity", "zenitbet", "fon.bet",
]

ACTIONS = ["delete", "timeout", "ban"]

def setup_antispam(bot):
    """Настройка антирекламы с OCR"""

    async def _get_settings(guild_id):
        await bot.db.execute('''
            CREATE TABLE IF NOT EXISTS antispam_settings (
                guild_id INTEGER PRIMARY KEY,
                enabled INTEGER DEFAULT 1,
                log_channel INTEGER DEFAULT NULL,
                action TEXT DEFAULT 'timeout',
                timeout_minutes INTEGER DEFAULT 10,
                whitelist TEXT DEFAULT '[]'
            )
        ''')
        await bot.db.commit()
        cursor = await bot.db.execute(
            "SELECT enabled, log_channel, action, timeout_minutes, whitelist FROM antispam_settings WHERE guild_id = ?",
            (guild_id,))
        row = await cursor.fetchone()
        if row is None:
            await bot.db.execute(
                "INSERT INTO antispam_settings (guild_id, enabled, log_channel, action, timeout_minutes, whitelist) VALUES (?, 1, NULL, 'delete', 10, '[]')",
                (guild_id,))
            await bot.db.commit()
            return {"enabled": True, "log_channel": None, "action": "delete",
                    "timeout_minutes": 10, "whitelist": "[]"}
        return {"enabled": bool(row[0]), "log_channel": row[1], "action": row[2],
                "timeout_minutes": row[3], "whitelist": row[4]}

    # Двойники букв (homoglyphs), которыми спамеры обходят фильтры
    HOMOGLYPHS = {
        'а': 'a', 'А': 'a', 'а': 'a', 'е': 'e', 'Е': 'e', 'ё': 'e', 'Ё': 'e',
        'с': 'c', 'С': 'c', 'о': 'o', 'О': 'o', 'р': 'p', 'Р': 'p', 'у': 'y',
        'У': 'y', 'х': 'x', 'Х': 'x', 'і': 'i', 'І': 'i', 'ѕ': 's', 'ѕ': 's',
        'в': 'b', 'В': 'b', 'к': 'k', 'К': 'k', 'м': 'm', 'М': 'm', 'н': 'h',
        'Н': 'h', 'т': 't', 'Т': 't', 'ь': '', 'ъ': '',
        'ᴀ': 'a', 'ᴁ': 'a', 'ᴂ': 'ae', 'ᴃ': 'b', 'ᴄ': 'c', 'ᴅ': 'd', 'ᴇ': 'e',
        'ᴈ': 'e', 'ᴉ': 'i', 'ᴊ': 'j', 'ᴋ': 'k', 'ᴌ': 'l', 'ᴍ': 'm', 'ᴎ': 'n',
        'ᴏ': 'o', 'ᴐ': 'o', 'ᴘ': 'p', 'ᴙ': 'r', 'ᴚ': 'r', 'ᴛ': 't', 'ᴜ': 'u',
        'ᴠ': 'v', 'ᴡ': 'w', 'ᴢ': 'z', 'ꜱ': 's', 'ᴮ': 'b', 'ꓐ': 'p', 'ꓑ': 'p',
        'ɑ': 'a', 'ɓ': 'b', 'ϲ': 'c', 'ԁ': 'd', 'е': 'e', 'ҽ': 'e', 'ƒ': 'f',
        'ց': 'g', 'հ': 'h', 'ɨ': 'i', 'պ': 'p', 'գ': 'q', 'ɾ': 'r', 'ѕ': 's',
        '𝑡': 't', 'υ': 'u', 'ν': 'v', 'ա': 'w', 'х': 'x', 'γ': 'y', 'զ': 'z',
        '0': 'o', '1': 'i', '!': 'i', '@': 'a', '$': 's', '5': 's', '8': 'b',
    }

    def _normalize(text):
        text = text or ""
        text = ''.join(HOMOGLYPHS.get(ch, ch) for ch in text)
        text = text.lower()
        text = re.sub(r'[^a-zа-яё0-9\s]', ' ', text)
        text = re.sub(r'\s+', ' ', text).strip()
        return text

    def _scan_text(text):
        norm = _normalize(text)
        found = []
        score = 0
        for w in CASINO_WORDS:
            if w in norm:
                found.append(("казино", w))
                score += 2 if w in STRONG_WORDS else 1
        for w in DRUG_WORDS:
            if w in norm:
                found.append(("наркотики", w))
                score += 3 if w in STRONG_WORDS else 1
        for w in SPAM_WORDS:
            if w in norm:
                found.append(("спам", w))
                score += 3
        for d in CASINO_DOMAINS:
            if d in norm:
                found.append(("казино", d))
                score += 3
        return score, found

    async def _ocr_image(data):
        if not OCR_AVAILABLE:
            return ""
        try:
            image = Image.open(io.BytesIO(data)).convert("RGB")
            if max(image.size) > 2000:
                image.thumbnail((2000, 2000))
            # Предобработка: ч/б + порог для лучшего распознавания стилизованного текста
            gray = image.convert("L")
            bw = gray.point(lambda p: 255 if p > 140 else 0)
            results = []
            for img in (bw, gray):
                try:
                    results.append(await asyncio.to_thread(pytesseract.image_to_string, img, lang='rus+eng'))
                except Exception:
                    pass
            text = "\n".join(r for r in results if r) or ""
            return text or ""
        except Exception as e:
            logger.error(f'Ошибка OCR: {e}')
            return ""

    async def _extract_images(message):
        images = []
        for att in message.attachments:
            if att.content_type and att.content_type.startswith("image/"):
                if att.size <= 15 * 1024 * 1024:
                    try:
                        images.append(await att.read())
                    except Exception:
                        pass
        for emb in message.embeds:
            url = emb.image.url or (emb.thumbnail.url if emb.thumbnail else None)
            if url:
                try:
                    async with bot.session.get(url) as resp:
                        if resp.status == 200:
                            data = await resp.read()
                            if len(data) <= 15 * 1024 * 1024:
                                images.append(data)
                except Exception:
                    pass
        return images

    async def _punish(guild, member, settings, reason):
        action = settings.get("action", "timeout")
        try:
            if action == "delete":
                return
            elif action == "timeout":
                minutes = settings.get("timeout_minutes", 10)
                if guild.me.guild_permissions.moderate_members:
                    await member.timeout(discord.utils.utcnow() + discord.timedelta(minutes=minutes), reason=reason)
            elif action == "ban":
                if guild.me.guild_permissions.ban_members:
                    await member.ban(reason=reason)
        except Exception as e:
            logger.error(f'Ошибка наказания: {e}')

    async def _log(guild, member, category, words, ocr_text, extra=""):
        settings = await _get_settings(guild.id)
        if not settings["log_channel"]:
            return
        channel = guild.get_channel(settings["log_channel"])
        if not channel:
            return
        embed = discord.Embed(
            title="Обнаружена реклама",
            color=discord.Color.red(),
            timestamp=discord.utils.utcnow())
        embed.add_field(name="Автор", value=member.mention, inline=True)
        embed.add_field(name="Категория", value=category, inline=True)
        embed.add_field(name="Ключевые слова", value=", ".join(w[1] for w in words) or "—", inline=False)
        embed.add_field(name="Распознанный текст (OCR/сообщение)", value=(ocr_text or "—")[:1000], inline=False)
        if extra:
            embed.add_field(name="Заметка", value=extra, inline=False)
        try:
            await channel.send(embed=embed)
        except Exception:
            pass

    @bot.listen('on_message')
    async def antispam_listener(message):
        if message.author.bot:
            return
        if not message.guild:
            return
        if not isinstance(message.channel, discord.TextChannel):
            return

        settings = await _get_settings(message.guild.id)
        if not settings["enabled"]:
            return

        whitelist = []
        try:
            whitelist = json.loads(settings["whitelist"] or "[]")
        except Exception:
            whitelist = []
        if message.channel.id in whitelist:
            return
        if message.author.guild_permissions.manage_messages:
            return

        text_score, text_found = _scan_text(message.content)
        best_score = text_score
        best_words = text_found
        ocr_text = message.content

        images = await _extract_images(message)
        for img_data in images:
            ocr = await _ocr_image(img_data)
            if ocr:
                ocr_text = ocr
                score, found = _scan_text(ocr)
                if score > best_score:
                    best_score = score
                    best_words = found

        if best_score >= 3:
            category = "казино/ставки" if any(f[0] == "казино" for f in best_words) else "наркотики"
            try:
                if message.channel.permissions_for(message.guild.me).manage_messages:
                    await message.delete()
            except Exception:
                pass
            await _punish(message.guild, message.author, settings, f"Антиреклама: {category}")
            await _log(message.guild, message.author, category, best_words, ocr_text)
            logger.info(f'Антиреклама: удалена реклама от {message.author} ({category})')

    @bot.hybrid_command(name="antispam", description="Настройки антирекламы (OCR-мониторинг фото)")
    @app_commands.describe(action="Что сделать", value="Значение")
    @commands.has_permissions(administrator=True)
    async def antispam_cmd(ctx, action: str = "status", value: str = None):
        settings = await _get_settings(ctx.guild.id)
        action = action.lower()

        if action == "status":
            embed = discord.Embed(title="Антиреклама (OCR)", color=discord.Color.blue())
            embed.add_field(name="Включён", value="Да" if settings["enabled"] else "Нет", inline=True)
            embed.add_field(name="Действие", value=settings["action"], inline=True)
            log_ch = ctx.guild.get_channel(settings["log_channel"]) if settings["log_channel"] else None
            embed.add_field(name="Канал логов", value=log_ch.mention if log_ch else "Не задан", inline=True)
            embed.add_field(name="Таймаут (мин)", value=str(settings["timeout_minutes"]), inline=True)
            embed.add_field(name="OCR доступен", value="Да" if OCR_AVAILABLE else "Нет (tesseract не установлен)", inline=True)
            embed.add_field(name="Команды", value="on / off / logchannel #канал / action delete|timeout|ban / timeout <мин> / whitelist add|remove #канал / test", inline=False)
            await ctx.send(embed=embed)
            return

        if action == "on":
            await bot.db.execute("UPDATE antispam_settings SET enabled = 1 WHERE guild_id = ?", (ctx.guild.id,))
            await bot.db.commit()
            await ctx.send("Антиреклама включена.")
            return

        if action == "off":
            await bot.db.execute("UPDATE antispam_settings SET enabled = 0 WHERE guild_id = ?", (ctx.guild.id,))
            await bot.db.commit()
            await ctx.send("Антиреклама выключена.")
            return

        if action == "logchannel":
            if value is None:
                await ctx.send("Укажите канал: `!antispam logchannel #канал`")
                return
            cid = int(value.strip().replace("<#", "").replace(">", ""))
            await bot.db.execute("UPDATE antispam_settings SET log_channel = ? WHERE guild_id = ?", (cid, ctx.guild.id))
            await bot.db.commit()
            await ctx.send(f"Канал логов установлен: {ctx.guild.get_channel(cid).mention}")
            return

        if action == "action":
            if value not in ACTIONS:
                await ctx.send("Действие должно быть: delete / timeout / ban")
                return
            await bot.db.execute("UPDATE antispam_settings SET action = ? WHERE guild_id = ?", (value, ctx.guild.id))
            await bot.db.commit()
            await ctx.send(f"Действие при рекламе: {value}")
            return

        if action == "timeout":
            try:
                minutes = int(value)
            except (TypeError, ValueError):
                await ctx.send("Укажите число минут: `!antispam timeout 15`")
                return
            await bot.db.execute("UPDATE antispam_settings SET timeout_minutes = ? WHERE guild_id = ?", (minutes, ctx.guild.id))
            await bot.db.commit()
            await ctx.send(f"Таймаут: {minutes} мин")
            return

        if action == "whitelist":
            if value is None:
                await ctx.send("Используйте: `!antispam whitelist add #канал` или `remove`")
                return
            parts = value.split()
            mode = parts[0]
            cid = int(parts[1].strip().replace("<#", "").replace(">", ""))
            wl = []
            try:
                wl = json.loads(settings["whitelist"] or "[]")
            except Exception:
                wl = []
            if mode == "add" and cid not in wl:
                wl.append(cid)
            elif mode == "remove" and cid in wl:
                wl.remove(cid)
            await bot.db.execute("UPDATE antispam_settings SET whitelist = ? WHERE guild_id = ?", (json.dumps(wl), ctx.guild.id))
            await bot.db.commit()
            await ctx.send(f"Белый список каналов: {len(wl)}")
            return

        if action == "test":
            images = await _extract_images(ctx.message)
            if not images:
                await ctx.send("Прикрепите фото к команде, чтобы проверить OCR.")
                return
            ocr = await _ocr_image(images[0])
            score, found = _scan_text(ocr)
            result = f"OCR доступен: {'Да' if OCR_AVAILABLE else 'Нет'}\n"
            result += f"Распознанный текст:\n```\n{(ocr or '—')[:1500]}\n```\n"
            result += f"Нормализованный (двойники->ascii):\n```\n{(_normalize(ocr) or '—')[:1500]}\n```\n"
            result += f"Оценка рекламы: {score} (порог 3)\n"
            result += f"Найдено: {', '.join(w[1] for w in found) or '—'}"
            await ctx.send(result)
            return

        await ctx.send("Неизвестное действие. Используйте `!antispam` для списка команд.")


