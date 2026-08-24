"""
Модуль антирекламы с OCR-мониторингом изображений
Автоматически проверяет все текстовые каналы на фото с рекламой:
   - казино/ставки (1win, фонбет, депозит, фриспины и т.д.)
   - спам/раздачи (Мистер Бист, giveaway и т.д.)
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
    "блэкджек", "покер", "гембл", "casino", "азарт", "azart", "bonuses", "ставочк", "коэффициент",
    "тотал", "фору", "ординар", "ставки на спорт", "играть бесплатно",
    "демо счёт", "честное казино", "топ казино", "лучшее казино", "рабочее зеркал",
    "ставок", "выигрыш", "ставочка",
    "drgn43.casino", "деньги поступают сразу", "на баланс", "сразу на баланс",
    "меллстрой", "казино", "регистрации",
]

STRONG_WORDS = ["казино", "казик", "1win", "1вин", "фонбет", "1xbet", "меллстрой",
                "мистер бист", "mrbeast", "drgn43.casino"]

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
    "mostbet", "betcity", "zenitbet", "fon.bet", "mellacasino", "drgn43.casino",
]

ACTIONS = ["delete", "timeout", "ban", "kick"]

ANTISPAM_VERSION = "2.4 (без пропуска модераторов/спамеров с правами)"

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
                "INSERT INTO antispam_settings (guild_id, enabled, log_channel, action, timeout_minutes, whitelist) VALUES (?, 1, NULL, 'kick', 10, '[]')",
                (guild_id,))
            await bot.db.commit()
            return {"enabled": True, "log_channel": None, "action": "kick",
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

    CYR_TRANSLIT = {
        'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'e',
        'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'i', 'к': 'k', 'л': 'l', 'м': 'm',
        'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 'c', 'т': 't', 'у': 'u',
        'ф': 'f', 'х': 'h', 'ц': 'c', 'ч': 'ch', 'ш': 'sh', 'щ': 'sch',
        'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya',
    }

    def _transliterate(text):
        text = text or ""
        text = ''.join(CYR_TRANSLIT.get(ch, ch) for ch in text)
        return text.lower()

    def _scan_text(text):
        norm = _normalize(text)
        trans = _transliterate(text)
        found = []
        score = 0
        for w in CASINO_WORDS:
            if w in norm or w in trans:
                found.append(("казино", w))
                score += 2 if w in STRONG_WORDS else 1
        for w in SPAM_WORDS:
            if w in norm or w in trans:
                found.append(("спам", w))
                score += 3
        for d in CASINO_DOMAINS:
            if d in norm or d in trans:
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
        img_ext = (".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp")
        for att in message.attachments:
            is_img = (att.content_type and att.content_type.startswith("image/")) or \
                      (att.filename and att.filename.lower().endswith(img_ext))
            if is_img and att.size <= 15 * 1024 * 1024:
                try:
                    images.append(await att.read())
                except Exception:
                    pass
        for emb in message.embeds:
            url = emb.image.url or emb.thumbnail.url or (emb.url if emb.url else None)
            if url and str(url).lower().endswith(img_ext):
                try:
                    async with bot.session.get(str(url)) as resp:
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
            elif action == "kick":
                if guild.me.guild_permissions.kick_members:
                    await member.kick(reason=reason)
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
        try:
            if message.author == bot.user:
                return
            if not message.guild:
                return
            if not isinstance(message.channel, (discord.TextChannel, discord.Thread)):
                return

            # Не сканируем приватные каналы тикетов/заявок (topic содержит owner:)
            _topic = ""
            if isinstance(message.channel, discord.TextChannel):
                _topic = message.channel.topic or ""
            elif isinstance(message.channel, discord.Thread):
                _topic = getattr(message.channel.parent, 'topic', '') or ""
            if "owner:" in _topic:
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
                if any(f[0] == "казино" for f in best_words):
                    category = "казино/ставки"
                elif any(f[0] == "спам" for f in best_words):
                    category = "спам (Мистер Бист/раздачи)"
                else:
                    category = "реклама"
                extra = ""
                can_delete = message.channel.permissions_for(message.guild.me).manage_messages
                if not can_delete:
                    extra = "НЕТ ПРАВ НА УДАЛЕНИЕ (нужен Manage Messages в канале)"
                else:
                    try:
                        await message.delete()
                        try:
                            await message.channel.send(f"БРУХ НЕ ПОЛУЧИЛОСЬ ANTISPAM DETECT {message.author.mention}")
                        except Exception:
                            pass
                    except discord.Forbidden:
                        extra = "НЕТ ПРАВ НА УДАЛЕНИЕ (Manage Messages запрещён ролью/иерархией)"
                    except Exception as e:
                        extra = f"Ошибка удаления: {e}"
                await _punish(message.guild, message.author, settings, f"Антиреклама: {category}")
                await _log(message.guild, message.author, category, best_words, ocr_text, extra=extra)
                logger.info(f'Антиреклама: реклама от {message.author} ({category}) | {extra or "удалено"}')
        except Exception as e:
            logger.error(f'ОШИБКА antispam_listener: {e}', exc_info=True)
            try:
                await _log(message.guild, message.author, "ОШИБКА МОДУЛЯ", [], str(message.content), extra=f"antispam_listener упал: {e}")
            except Exception:
                pass

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
            embed.add_field(name="Версия модуля", value=ANTISPAM_VERSION, inline=False)
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
                await ctx.send("Действие должно быть: delete / timeout / ban / kick")
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

    # ===================== БЕЗОПАСНОСТЬ: капча, антирейд, антиспам =====================
    DEFAULT_MODLOG_CHANNEL_ID = "1535655890982801438"

    _spam_cache = {}
    _join_times = {}

    async def _get_security(guild_id):
        await bot.db.execute('''
            CREATE TABLE IF NOT EXISTS security_settings (
                guild_id INTEGER PRIMARY KEY,
                captcha_enabled INTEGER DEFAULT 0,
                captcha_role_id INTEGER DEFAULT NULL,
                verify_channel_id INTEGER DEFAULT NULL,
                mass_mention INTEGER DEFAULT 1,
                mass_mention_limit INTEGER DEFAULT 5,
                spam INTEGER DEFAULT 1,
                spam_limit INTEGER DEFAULT 4,
                spam_window INTEGER DEFAULT 10,
                join_raid INTEGER DEFAULT 1,
                join_raid_limit INTEGER DEFAULT 8,
                join_raid_window INTEGER DEFAULT 20,
                join_raid_action_min INTEGER DEFAULT 10,
                log_channel INTEGER DEFAULT NULL
            )
        ''')
        await bot.db.commit()
        cursor = await bot.db.execute(
            "SELECT captcha_enabled, captcha_role_id, verify_channel_id, mass_mention, "
            "mass_mention_limit, spam, spam_limit, spam_window, join_raid, join_raid_limit, "
            "join_raid_window, join_raid_action_min, log_channel FROM security_settings WHERE guild_id=?",
            (guild_id,))
        row = await cursor.fetchone()
        if row is None:
            await bot.db.execute("INSERT INTO security_settings (guild_id) VALUES (?)", (guild_id,))
            await bot.db.commit()
            row = (0, None, None, 1, 5, 1, 4, 10, 1, 8, 20, 10, None)
        keys = ["captcha_enabled", "captcha_role_id", "verify_channel_id", "mass_mention",
                "mass_mention_limit", "spam", "spam_limit", "spam_window", "join_raid",
                "join_raid_limit", "join_raid_window", "join_raid_action_min", "log_channel"]
        return dict(zip(keys, row))

    async def _security_log(guild, title, color, fields):
        try:
            settings = await _get_security(guild.id)
            cid = settings.get("log_channel") or (await _get_settings(guild.id)).get("log_channel")
            if not cid:
                cid = DEFAULT_MODLOG_CHANNEL_ID
            ch = guild.get_channel(int(cid)) or bot.get_channel(int(cid))
            if not ch:
                ch = await bot.fetch_channel(int(cid))
            if not ch or not hasattr(ch, "send"):
                return
            embed = discord.Embed(title=title, color=color, timestamp=discord.utils.utcnow())
            for name, value in fields:
                embed.add_field(name=name, value=value, inline=False)
            embed.set_footer(text="Vector.prod • Безопасность")
            await ch.send(embed=embed)
        except Exception as e:
            logger.error(f'Ошибка лога безопасности: {e}')

    async def _security_action(message, settings, *, reason, title):
        guild = message.guild
        member = message.author
        try:
            perms = message.channel.permissions_for(guild.me)
            if perms.manage_messages:
                try:
                    await message.delete()
                except Exception:
                    pass
            if guild.me.guild_permissions.moderate_members and isinstance(member, discord.Member):
                try:
                    await member.timeout(
                        discord.utils.utcnow() + discord.timedelta(minutes=settings.get("join_raid_action_min", 10)),
                        reason=reason)
                except Exception as e:
                    logger.error(f'Ошибка таймаута безопасности: {e}')
            ch_mention = message.channel.mention if hasattr(message.channel, "mention") else str(message.channel)
            await _security_log(guild, title, discord.Color.red(), [
                ("Участник", f"{member.mention} (`{member.id}`)"),
                ("Причина", reason),
                ("Действие", "Удаление + таймаут"),
                ("Канал", ch_mention),
            ])
        except Exception as e:
            logger.error(f'Ошибка _security_action: {e}')

    @bot.listen('on_message')
    async def security_listener(message):
        try:
            if message.author == bot.user:
                return
            if not message.guild:
                return
            if not isinstance(message.channel, (discord.TextChannel, discord.Thread)):
                return
            _topic = ""
            if isinstance(message.channel, discord.TextChannel):
                _topic = message.channel.topic or ""
            elif isinstance(message.channel, discord.Thread):
                _topic = getattr(message.channel.parent, 'topic', '') or ""
            if "owner:" in _topic:
                return
            author = message.author
            if author.guild_permissions.manage_messages or author.guild_permissions.administrator:
                return
            settings = await _get_security(message.guild.id)
            if settings["mass_mention"]:
                limit = settings["mass_mention_limit"]
                mention_count = len(message.mentions) + len(message.role_mentions)
                if message.mention_everyone:
                    mention_count += 2
                if mention_count >= limit:
                    await _security_action(message, settings,
                                          reason=f"Массовые упоминания ({mention_count})",
                                          title="🚨 Массовые упоминания")
                    return
            if settings["spam"]:
                await _spam_check(message, settings)
        except Exception as e:
            logger.error(f'ОШИБКА security_listener: {e}')

    async def _spam_check(message, settings):
        content = (message.content or "").strip().lower()
        if len(content) < 3:
            return
        limit = settings["spam_limit"]
        window = settings["spam_window"]
        now = discord.utils.utcnow().timestamp()
        user_id = message.author.id
        h = hash(content)
        lst = _spam_cache.setdefault(user_id, [])
        lst.append((now, h))
        lst[:] = [(t, hh) for (t, hh) in lst if now - t <= window]
        count = sum(1 for (t, hh) in lst if hh == h)
        if count >= limit:
            _spam_cache[user_id] = []
            await _security_action(message, settings,
                                  reason="Спам/повторяющиеся сообщения",
                                  title="🚨 Спам сообщений")

    @bot.listen('on_member_join')
    async def security_join_listener(member):
        try:
            if member.bot:
                return
            guild = member.guild
            settings = await _get_security(guild.id)
            if settings["captcha_enabled"] and settings["captcha_role_id"]:
                role = guild.get_role(settings["captcha_role_id"])
                if role:
                    try:
                        await member.add_roles(role, reason="Капча: требуется верификация")
                    except Exception as e:
                        logger.error(f'Ошибка выдачи роли капчи: {e}')
                    vch = guild.get_channel(settings["verify_channel_id"]) if settings["verify_channel_id"] else None
                    view = CaptchaView()
                    if vch:
                        try:
                            await vch.send(f"{member.mention}, добро пожаловать! Нажми кнопку ниже для верификации.",
                                           view=view)
                        except Exception:
                            pass
                    else:
                        try:
                            await member.send("Нажми кнопку для верификации на сервере.", view=view)
                        except Exception:
                            pass
            if settings["join_raid"]:
                now = discord.utils.utcnow().timestamp()
                window = settings["join_raid_window"]
                lst = _join_times.setdefault(guild.id, [])
                lst.append((now, member))
                lst[:] = [(t, m) for (t, m) in lst if now - t <= window]
                if len(lst) >= settings["join_raid_limit"]:
                    if guild.me.guild_permissions.moderate_members:
                        mins = settings["join_raid_action_min"]
                        until = discord.utils.utcnow() + discord.timedelta(minutes=mins)
                        for (t, m) in lst:
                            try:
                                if isinstance(m, discord.Member):
                                    await m.timeout(until, reason="Антирейд: массовые заходы")
                            except Exception:
                                pass
                    await _security_log(guild, "🚨 Обнаружен рейд (массовые заходы)", discord.Color.dark_red(), [
                        ("Событие", f"Зашло {len(lst)} участников за {window} сек"),
                        ("Действие", f"Таймаут новых участников на {settings['join_raid_action_min']} мин"),
                        ("Последний участник", f"{member.mention} (`{member.id}`)"),
                    ])
                    _join_times[guild.id] = []
        except Exception as e:
            logger.error(f'ОШИБКА security_join_listener: {e}')

    class CaptchaView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=None)

        @discord.ui.button(label="✅ Я не бот", style=discord.ButtonStyle.success, custom_id="sec_captcha")
        async def verify(self, interaction, button):
            settings = await _get_security(interaction.guild.id)
            role_id = settings.get("captcha_role_id")
            if role_id:
                role = interaction.guild.get_role(role_id)
                if role and role in interaction.user.roles:
                    try:
                        await interaction.user.remove_roles(role, reason="Капча пройдена")
                    except Exception:
                        pass
                    await interaction.response.send_message(
                        "✅ Верификация пройдена! Добро пожаловать.", ephemeral=True)
                    await _security_log(interaction.guild, "✅ Капча пройдена", discord.Color.green(), [
                        ("Участник", f"{interaction.user.mention} (`{interaction.user.id}`)"),
                    ])
                    return
            await interaction.response.send_message("✅ Вы уже верифицированы.", ephemeral=True)

    async def _setup_captcha_role(guild, verify_channel_id):
        settings = await _get_security(guild.id)
        role = None
        if settings.get("captcha_role_id"):
            role = guild.get_role(settings["captcha_role_id"])
        if not role:
            role = discord.utils.get(guild.roles, name="Капча")
        if not role:
            role = await guild.create_role(name="Капча", reason="Антирейд: капча")
        for ch in guild.channels:
            try:
                if ch.id == verify_channel_id:
                    await ch.set_permissions(role, view_channel=True, send_messages=False, add_reactions=False)
                else:
                    await ch.set_permissions(role, view_channel=False)
            except discord.Forbidden:
                continue
            except Exception:
                continue
            await asyncio.sleep(0.05)
        return role

    @bot.hybrid_command(name="security", description="Настройки безопасности: капча, антирейд, антиспам")
    @commands.has_permissions(administrator=True)
    async def security_cmd(ctx, action: str = "status", value: str = None):
        settings = await _get_security(ctx.guild.id)
        action = (action or "status").lower()
        if action == "status":
            embed = discord.Embed(title="🛡️ Безопасность", color=discord.Color.blue())
            embed.add_field(name="Капча", value="Да" if settings["captcha_enabled"] else "Нет", inline=True)
            embed.add_field(name="Масс-упоминания", value=(f"Да (лимит {settings['mass_mention_limit']})" if settings["mass_mention"] else "Нет"), inline=True)
            embed.add_field(name="Спам", value=(f"Да ({settings['spam_limit']} за {settings['spam_window']}с)" if settings["spam"] else "Нет"), inline=True)
            embed.add_field(name="Антирейд", value=(f"Да ({settings['join_raid_limit']} за {settings['join_raid_window']}с, {settings['join_raid_action_min']} мин)" if settings["join_raid"] else "Нет"), inline=True)
            log_ch = ctx.guild.get_channel(settings["log_channel"]) if settings["log_channel"] else None
            embed.add_field(name="Канал логов", value=(log_ch.mention if log_ch else "По умолчанию 🔨-логи"), inline=False)
            await ctx.send(embed=embed)
            return
        if action == "logchannel":
            cid = int(value.strip().replace("<#", "").replace(">", ""))
            await bot.db.execute("UPDATE security_settings SET log_channel=? WHERE guild_id=?", (cid, ctx.guild.id))
            await bot.db.commit()
            await ctx.send(f"Канал логов безопасности: {ctx.guild.get_channel(cid).mention}")
            return
        if action == "verifychannel":
            cid = int(value.strip().replace("<#", "").replace(">", ""))
            await bot.db.execute("UPDATE security_settings SET verify_channel_id=? WHERE guild_id=?", (cid, ctx.guild.id))
            await bot.db.commit()
            await ctx.send("Канал верификации указан.")
            return
        if action == "captcharole":
            if not value:
                await ctx.send("Укажите роль: `!security captcharole @Unverified`")
                return
            vid = None
            v = value.strip().replace("<@&", "").replace(">", "")
            try:
                vid = int(v)
            except ValueError:
                vid = None
            role = ctx.guild.get_role(vid) if vid else discord.utils.get(ctx.guild.roles, name=value.strip())
            if not role:
                await ctx.send("Роль не найдена на сервере.")
                return
            if role.position >= ctx.guild.me.top_role.position:
                await ctx.send("Эта роль выше моей — я не смогу выдавать/снимать её. Перенесите роль ниже моей роли.")
                return
            await bot.db.execute("UPDATE security_settings SET captcha_role_id=? WHERE guild_id=?", (role.id, ctx.guild.id))
            await bot.db.commit()
            await ctx.send(f"Роль капчи установлена: {role.mention}. Затем выполните `!security captcha on` (применит права к каналам).")
            return
        if action == "captcha":
            if value == "on":
                if not settings["verify_channel_id"]:
                    await ctx.send("Сначала укажите канал верификации: `!security verifychannel #канал`")
                    return
                await ctx.send("Настраиваю права роли капчи (может занять минуту)...")
                role = await _setup_captcha_role(ctx.guild, settings["verify_channel_id"])
                await bot.db.execute("UPDATE security_settings SET captcha_enabled=1, captcha_role_id=? WHERE guild_id=?", (role.id, ctx.guild.id))
                await bot.db.commit()
                await ctx.send("✅ Капча включена. Неверифицированные видят только канал верификации и нажимают кнопку.")
                return
            elif value == "off":
                role_id = settings["captcha_role_id"]
                if role_id:
                    role = ctx.guild.get_role(role_id)
                    if role:
                        for m in ctx.guild.members:
                            if role in m.roles:
                                try:
                                    await m.remove_roles(role, reason="Капча выключена")
                                except Exception:
                                    pass
                                await asyncio.sleep(0.05)
                await bot.db.execute("UPDATE security_settings SET captcha_enabled=0 WHERE guild_id=?", (ctx.guild.id,))
                await bot.db.commit()
                await ctx.send("Капча выключена, роль снята с участников.")
                return
            else:
                await ctx.send("Используйте: `!security captcha on` / `off`")
                return
        if action == "massmention":
            if value == "on":
                await bot.db.execute("UPDATE security_settings SET mass_mention=1 WHERE guild_id=?", (ctx.guild.id,)); await bot.db.commit(); await ctx.send("Масс-упоминания: вкл")
            elif value == "off":
                await bot.db.execute("UPDATE security_settings SET mass_mention=0 WHERE guild_id=?", (ctx.guild.id,)); await bot.db.commit(); await ctx.send("Масс-упоминания: выкл")
            elif value and value.isdigit():
                await bot.db.execute("UPDATE security_settings SET mass_mention_limit=? WHERE guild_id=?", (int(value), ctx.guild.id)); await bot.db.commit(); await ctx.send(f"Лимит упоминаний: {value}")
            else:
                await ctx.send("Используйте: `!security massmention on` / `off` / `<число>`")
            return
        if action == "spam":
            if value == "on":
                await bot.db.execute("UPDATE security_settings SET spam=1 WHERE guild_id=?", (ctx.guild.id,)); await bot.db.commit(); await ctx.send("Спам-фильтр: вкл")
            elif value == "off":
                await bot.db.execute("UPDATE security_settings SET spam=0 WHERE guild_id=?", (ctx.guild.id,)); await bot.db.commit(); await ctx.send("Спам-фильтр: выкл")
            elif value and value.isdigit():
                await bot.db.execute("UPDATE security_settings SET spam_limit=? WHERE guild_id=?", (int(value), ctx.guild.id)); await bot.db.commit(); await ctx.send(f"Лимит повторов: {value}")
            else:
                await ctx.send("Используйте: `!security spam on` / `off` / `<число>`")
            return
        if action == "raid":
            if value == "on":
                await bot.db.execute("UPDATE security_settings SET join_raid=1 WHERE guild_id=?", (ctx.guild.id,)); await bot.db.commit(); await ctx.send("Антирейд: вкл")
            elif value == "off":
                await bot.db.execute("UPDATE security_settings SET join_raid=0 WHERE guild_id=?", (ctx.guild.id,)); await bot.db.commit(); await ctx.send("Антирейд: выкл")
            elif value and value.isdigit():
                await bot.db.execute("UPDATE security_settings SET join_raid_limit=? WHERE guild_id=?", (int(value), ctx.guild.id)); await bot.db.commit(); await ctx.send(f"Лимит заходов: {value}")
            else:
                await ctx.send("Используйте: `!security raid on` / `off` / `<число>`")
            return
        await ctx.send("Неизвестное действие. `!security` — статус.")

    bot.add_view(CaptchaView())


