"""Telegram wiring. All chat decisions stay in ``handle_message``."""

from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from telegram import (
    BotCommand,
    BotCommandScopeAllGroupChats,
    BotCommandScopeAllPrivateChats,
    Update,
)
from telegram.ext import Application, ContextTypes, MessageHandler, filters

from tripbot.bot.core import handle_message, load_state, split_reply
from tripbot.config import load_config

logger = logging.getLogger(__name__)
ROOT = Path(__file__).resolve().parents[2]

_COMMANDS = [
    BotCommand("plan", "Make a plan from what the group said"),
    BotCommand("itinerary", "Make a plan from what the group said"),
    BotCommand("profiles", "Show the likes and budgets saved so far"),
    BotCommand("confirm", "Book the latest plan"),
]


async def deliver(
    message: Any,
    group_id: str,
    sender: str,
    text: str,
    config: dict[str, Any],
) -> None:
    """Pass one text message to the bot and send a reply when there is one."""
    try:
        reply = await asyncio.to_thread(handle_message, group_id, sender, text, config)
        if reply is None:
            return
        for part in split_reply(reply):
            await message.reply_text(part)
    except Exception:
        logger.exception("telegram update failed for group %s", group_id)


def build_application(token: str, config: dict[str, Any]) -> Application:
    """Register a single text handler. Commands are text and go through the same path."""
    # api.telegram.org can take longer than the library's 5 second default.
    application = (
        Application.builder()
        .token(token)
        .connect_timeout(30.0)
        .read_timeout(30.0)
        .write_timeout(30.0)
        .pool_timeout(5.0)
        .get_updates_connect_timeout(30.0)
        .get_updates_read_timeout(30.0)
        .get_updates_write_timeout(30.0)
        .get_updates_pool_timeout(5.0)
        .post_init(_register_commands)
        .build()
    )

    async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        incoming = update.effective_message
        if incoming is None or not incoming.text:
            return
        chat = update.effective_chat
        group_id = str(chat.id) if chat is not None else "unknown"
        await deliver(incoming, group_id, _sender(update.effective_user), incoming.text, config)

    application.add_handler(MessageHandler(filters.TEXT, on_text))
    return application


def main() -> None:
    """Start long polling. The token is ``TELEGRAM_BOT_TOKEN`` in ``.env``."""
    logging.basicConfig(level=logging.INFO)
    load_dotenv(ROOT / ".env")
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        print("Put TELEGRAM_BOT_TOKEN in .env (copy .env.example).")
        raise SystemExit(1)
    config = load_config(ROOT / "config.yaml", [])
    load_state(config)
    build_application(token, config).run_polling(
        allowed_updates=["message"],
        bootstrap_retries=3,
    )


async def _register_commands(application: Application) -> None:
    """Publish the slash menu for groups and private chats."""
    await application.bot.set_my_commands(_COMMANDS, scope=BotCommandScopeAllGroupChats())
    await application.bot.set_my_commands(_COMMANDS, scope=BotCommandScopeAllPrivateChats())


def _sender(user: Any) -> str:
    if user is None:
        return "unknown"
    username = getattr(user, "username", None)
    if username:
        return str(username)
    full_name = getattr(user, "full_name", None)
    return str(full_name) if full_name else "unknown"


if __name__ == "__main__":
    main()
