"""channel/telegram.py -- Telegram channel using python-telegram-bot."""
from __future__ import annotations
import asyncio
import logging
from typing import Awaitable, Callable
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters
from mybot.channel.base import Channel, EventSource

logger = logging.getLogger(__name__)
MessageCallback = Callable[[str, EventSource], Awaitable[None]]


class TelegramChannel(Channel[EventSource]):
    """Telegram bot channel."""

    platform_name = "telegram"

    def __init__(self, token: str) -> None:
        self._token = token
        self._app: Application | None = None
        self._callback: MessageCallback | None = None

    async def run(self, on_message: MessageCallback) -> None:
        self._callback = on_message
        self._app = Application.builder().token(self._token).build()
        self._app.add_handler(CommandHandler("start", self._handle_start))
        self._app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_message))
        logger.info("TelegramChannel starting")
        await self._app.initialize()
        await self._app.start()
        await self._app.updater.start_polling(drop_pending_updates=True)
        # Block until stop() is called
        while self._app.updater.running:
            await asyncio.sleep(1)

    async def reply(self, content: str, source: EventSource) -> None:
        if not self._app:
            return
        # Split long messages (Telegram limit is 4096 chars)
        for chunk in _split_message(content, 4000):
            await self._app.bot.send_message(chat_id=source.chat_id, text=chunk)

    async def stop(self) -> None:
        if self._app:
            logger.info("TelegramChannel stopping")
            await self._app.updater.stop()
            await self._app.stop()
            await self._app.shutdown()

    async def _handle_start(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        await update.message.reply_text("Hello\! I'm your AI assistant. Start chatting\!")

    async def _handle_message(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.message or not update.message.text or not self._callback:
            return
        source = EventSource(
            platform="telegram",
            user_id=str(update.message.from_user.id),
            chat_id=str(update.message.chat_id),
        )
        await self._callback(update.message.text, source)


def _split_message(text: str, max_len: int) -> list[str]:
    if len(text) <= max_len:
        return [text]
    chunks = []
    while text:
        chunks.append(text[:max_len])
        text = text[max_len:]
    return chunks
