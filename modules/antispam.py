"""
Модуль антиспама с OCR-мониторингом изображений
Автоматически проверяет все текстовые каналы на фото с рекламой:
  - казино/ставки (1win, фонбет, депозит, фриспины и т.д.)
  - наркотики (мел, соль, меф, спайс и т.д.)
Распознавание текста на фото через Tesseract (OCR), плюс проверка текста сообщения.
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

# Ключевые слова: казино/ставки/букмекеры
CASINO_WORDS = [
    "казино", "казик", "казіно", "ставк", "ставки", "бонус", "депозит", "фриспин",
    "фриспины", "1win", "1вин", "1xbet", "фонбет", "winline", "леон", "betboom",
    "букмекер", "букмекерск", "джекпот", "лотерея", "играть на деньги", "ставка",
    "казино онлайн", "csg", "bet", "win", "ставь", "прогноз", "экспресс ставк",
    "розыгрыш", "бесплатн", "кэшбэк",
]

# Ключевые слова: наркотики (мел, соль, меф и т.д.)
DRUG_WORDS = [
    "мел", "меф", "мет", "соль", "мука", "скорость", "амф", "спайс", "травк",
    "гашиш", "кока", "героин", "метадон", "экстази", "mdma", "lsd", "наркот",
    "нарко", "доз", "ширк", "мефедрон", "бошк", "план", "гандж", "анаш", "марихуан",
    "каннаб", "психотроп", "закадр", "соль для варк", "кури", "шишк", "солевар",
]

# Штрафные слова (высокий вес, достаточно одного совпадения)
STRONG_WORDS = ["казино", "казик", "1win", "1вин", "фонбет", "1xbet", "мефедрон", "героин", "метадон", "спайс", "экстази"]

ACTIONS = ["delete", "timeout", "ban"]


def setup_antispam(bot):
    """Настройка антиспама с OCR"""

    # Инициализация таблицы настроек (создаётся при первом обращении)
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
            (guild_id,)
        )
        row = await cursor.fetchone()
        if row is None:
            await bot.db.execute(
                "INSERT INTO antispam_settings (guild_id, enabled, log_channel, action, timeout_minutes, whitelist) VALUES (?, 1, NULL, 'timeout', 10, '[]')",
                (guild_id,)
            )
            await bot.db.commit()
            return {"enabled": True, "log_channel": None, "action": "timeout", "timeout_minutes": 10, "whitelist": "[]"}
        return {"enabled": bool(row[0]), "log_channel": row[1], "action": row[2],
                "timeout_minutes": row[3], "whitelist": row[4]}

    def _normalize(text):
        text = (text or "").lower()
        text = re.sub(r'[^a-zа-яё0-9\s]', ' ', text)
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
        return score, found

    async def _ocr_image(data: bytes):
        if not OCR_AVAILABLE:
            return ""
        try:
            image = Image.open(io.BytesIO(data))
            # Уменьшаем для ускорения
            if max(image.size) > 2000:
                image.thumbnail((2000, 2000))
            text = await asyncio.to_thread(pytesseract.image_to_string, image, lang='rus+eng')
            return text or ""
        except Exception as e:
            logger.error(f'Ошибка OCR: {e}')
            return ""

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

    async def _log(guild, message, member, category, words, ocr_text):
        settings = await _get_settings(guild.id)
        if not settings["log_channel"]:
            return
        channel = guild.get_channel(settings["log_channel"])
        if not channel:
            return
        embed = discord.Embed(
            title="🚨 Обнаружена реклама",
            color=discord.Color.red(),
            timestamp=discord.utils.utcnow()
        )
        embed.add_field(name="Автор", value=member.mention, inline=True)
        embed.add_field(name="Канал", value=message.channel.mention, inline=True)
        embed.add_field(name="Категория", value=category, inline=True)
        embed.add_field(name="Ключевые слова", value=", ".join(w[1] for w in words), inline=False)
        embed.add_field(name="Текст (OCR/сообщение)", value=(ocr_text or "—")[:1000], inline=False)
        try:
            await channel.send(embed=embed)
        except Exception:
            pass

    @bot.listen('on_message')
    async def antispam_listener(message: discord.Message):
        if message.author.bot:
            return
        if not message.guild:
            return
        if not isinstance(message.channel, discord.TextChannel):
            return

        settings = await _get_settings(message.guild.id)
        if not settings["enabled"]:
            return

        # Белый список каналов
        whitelist = []
        try:
            whitelist = json.loads(settings["whitelist"] or "[]")
        except Exception:
            whitelist = []
        if message.channel.id in whitelist:
            return

        # Проверяем права: не трогать админов/модераторов
        if message.author.guild_permissions.manage_messages:
            return

        # Проверка текста сообщения
        text_score, text_found = _scan_text(message.content)
        best_category = None
        best_words = text_found
        best_score = text_score
        ocr_text = message.content

        # Проверка изображений (вложения + эмбеды)
        image_bytes_list = []
        for att in message.attachments:
            if att.content_type and att.content_type.startswith("image/"):
                if att.size <= 15 * 1024 * 1024:
                    try:
                        image_bytes_list.append(await att.read())
                    except Exception:
                        pass
        for emb in message.embeds:
            if emb.image and emb.image.url:
                try:
                    async with bot.session.get(emb.image.url) as resp:
                        if resp.status == 200:
                            data = await resp.read()
                            if len(data) <= 15 * 1024 * 1024:
                                image_bytes_list.append(data)
                except Exception:
                    pass

        for img_data in image_bytes_list:
            ocr = await _ocr_image(img_data)
            if ocr:
                ocr_text = ocr
                score, found = _scan_text(ocr)
                if score > best_score:
                    best_score = score
                    best_category = None
                    best_words = found

        # Решение о блокировке
        if best_score >= 3:
            category = "казино/ставки" if any(f[0] == "казино" for f in best_words) else "наркотики"
            try:
                if message.channel.permissions_for(message.guild.me).manage_messages:
                    await message.delete()
            except Exception:
                pass
            await _punish(message.guild, message.author, settings, f"Антиспам: реклама ({category})")
            await _log(message.guild, message, message.author, category, best_words, ocr_text)
            logger.info(f'Антиспам: удалена реклама от {message.author} ({category})')

    # Команды управления
    @bot.hybrid_command(name="antispam", description="Настройки антиспама (OCR-мониторинг фото)")
    @app_commands.describe(action="Что сделать", value="Значение (для toggle/logchannel/action/whitelist)")
    @commands.has_permissions(administrator=True)
    async def antispam_cmd(ctx: commands.Context, action: str = "status", value: str = None):
        settings = await _get_settings(ctx.guild.id)
        action = action.lower()

        if action == "status":
            embed = discord.Embed(title="🛡️ Антиспам (OCR)", color=discord.Color.blue())
            embed.add_field(name="Включён", value="✅ Да" if settings["enabled"] else "❌ Нет", inline=True)
            embed.add_field(name="Действие", value=settings["action"], inline=True)
            log_ch = ctx.guild.get_channel(settings["log_channel"]) if settings["log_channel"] else None
            embed.add_field(name="Канал логов", value=log_ch.mention if log_ch else "Не задан", inline=True)
            embed.add_field(name="Таймаут (мин)", value=str(settings["timeout_minutes"]), inline=True)
            embed.add_field(name="OCR доступен", value="✅ Да" if OCR_AVAILABLE else "❌ Нет (установи tesseract)", inline=True)
            embed.add_field(name="Белый список", value=", ".join(f"<#{c}>" for c in (json.loads(settings["whitelist"] or "[]") if settings["whitelist"] else [])) or "Пусто", inline=False)
            embed.set_footer(text="Мониторит все текстовые каналы на фото с рекламой казино и наркотиков")
            await ctx.send(embed=embed, ephemeral=True)

        elif action == "toggle":
            new_val = 0 if settings["enabled"] else 1
            await bot.db.execute("UPDATE antispam_settings SET enabled = ? WHERE guild_id = ?", (new_val, ctx.guild.id))
            await bot.db.commit()
            await ctx.send(f"✅ Антиспам {'включён' if new_val else 'выключен'}", ephemeral=True)

        elif action == "logchannel":
            if not value:
                await ctx.send("❌ Укажи канал: `!antispam logchannel #канал`", ephemeral=True)
                return
            ch = ctx.channel_mentions[0] if ctx.channel_mentions else None
            if not ch:
                await ctx.send("❌ Канал не найден", ephemeral=True)
                return
            await bot.db.execute("UPDATE antispam_settings SET log_channel = ? WHERE guild_id = ?", (ch.id, ctx.guild.id))
            await bot.db.commit()
            await ctx.send(f"✅ Канал логов: {ch.mention}", ephemeral=True)

        elif action == "action":
            if value not in ACTIONS:
                await ctx.send(f"❌ Действие должно быть: {', '.join(ACTIONS)}", ephemeral=True)
                return
            await bot.db.execute("UPDATE antispam_settings SET action = ? WHERE guild_id = ?", (value, ctx.guild.id))
            await bot.db.commit()
            await ctx.send(f"✅ Действие при обнаружении: **{value}**", ephemeral=True)

        elif action == "timeout":
            if not value or not value.isdigit():
                await ctx.send("❌ Укажи минуты: `!antispam timeout 10`", ephemeral=True)
                return
            await bot.db.execute("UPDATE antispam_settings SET timeout_minutes = ? WHERE guild_id = ?", (int(value), ctx.guild.id))
            await bot.db.commit()
            await ctx.send(f"✅ Таймаут: {value} минут", ephemeral=True)

        elif action == "whitelist":
            if not value:
                await ctx.send("❌ Укажи: `!antispam whitelist add #канал` или `remove`", ephemeral=True)
                return
            parts = value.split()
            mode = parts[0].lower()
            wl = json.loads(settings["whitelist"] or "[]") if settings["whitelist"] else []
            if mode == "add" and ctx.channel_mentions:
                cid = ctx.channel_mentions[0].id
                if cid not in wl:
                    wl.append(cid)
            elif mode == "remove" and ctx.channel_mentions:
                cid = ctx.channel_mentions[0].id
                wl = [c for c in wl if c != cid]
            else:
                await ctx.send("❌ Формат: `!antispam whitelist add #канал`", ephemeral=True)
                return
            await bot.db.execute("UPDATE antispam_settings SET whitelist = ? WHERE guild_id = ?", (json.dumps(wl), ctx.guild.id))
            await bot.db.commit()
            await ctx.send(f"✅ Белый список обновлён ({len(wl)} каналов)", ephemeral=True)

        else:
            await ctx.send("❌ Неизвестное действие. Доступно: status, toggle, logchannel, action, timeout, whitelist", ephemeral=True)
