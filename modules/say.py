"""
Модуль публикации сообщений от имени бота
- !say /say — отправить стилизованное сообщение (embed) от лица бота
  • text   — текст сообщения (поддерживает переносы строк)
  • title  — необязательный заголовок
  • color  — необязательный цвет (HEX #5865F2 или 0x5865F2)
"""

import logging

import discord
from discord import app_commands
from discord.ext import commands

logger = logging.getLogger('discord_bot.say')


def setup_say(bot):
    @bot.hybrid_command(name="say", description="Опубликовать красивое сообщение от имени бота")
    @app_commands.describe(
        text="Текст сообщения (можно с переносами строк)",
        title="Заголовок (необязательно)",
        color="Цвет HEX, напр. #5865F2 или 0x5865F2 (необязательно)",
    )
    async def say_cmd(ctx: commands.Context, text: str, title: str = None, color: str = None):
        try:
            embed = discord.Embed(title=title or discord.Embed.Empty, description=text)
            if color:
                try:
                    col = color.strip()
                    if col.startswith('#'):
                        embed.color = discord.Color.from_str(col)
                    else:
                        embed.color = discord.Color(int(col, 0))
                except Exception:
                    logger.warning(f'Некорректный цвет для say: {color}')

            # для префикс-команды прячем сообщение с командой
            if ctx.message and getattr(ctx.message, 'author', None) == ctx.author:
                try:
                    await ctx.message.delete()
                except Exception:
                    pass

            await ctx.send(embed=embed)
            logger.info(f'{ctx.author} опубликовал сообщение от бота (say)')
        except Exception as e:
            await ctx.send(f"❌ Ошибка: {e}", ephemeral=True)
            logger.error(f'Ошибка say: {e}')
