"""
SWAGGYMUSIC - Channel Auto Delete

Install path:
    SWAGGYMUSIC/plugins/misc/autodelete.py

Supported commands (CHANNEL ONLY):
    /setdelay 5s
    /setdelay 30s
    /setdelay 1m
    /setdelay 1h
    /setdelay 3600s
    /setdelay off

`/setdelay on` is intentionally invalid, matching the requested behavior.

Limits:
    minimum 3 seconds
    maximum 24 hours

Uses the existing SWAGGYMUSIC MongoDB connection. No config.py change is
required because plugins are auto-discovered by SWAGGYMUSIC/plugins/__init__.py.
"""

import asyncio
import re
import time
from contextlib import suppress

from pyrogram import filters
from pyrogram.enums import ChatMemberStatus, ChatType
from pyrogram.types import Message

from SWAGGYMUSIC import app
from SWAGGYMUSIC.core.mongo import mongodb
from SWAGGYMUSIC.logging import LOGGER

log = LOGGER(__name__)

# Existing MongoDB connection is reused.
settings_db = mongodb.autodelete_settings
jobs_db = mongodb.autodelete_jobs

MIN_SECONDS = 3
MAX_SECONDS = 24 * 60 * 60

_DURATION_RE = re.compile(r"^\s*(\d+)\s*([smh])\s*$", re.IGNORECASE)


async def _ensure_indexes():
    with suppress(Exception):
        await settings_db.create_index("chat_id", unique=True)
    with suppress(Exception):
        await jobs_db.create_index([("delete_at", 1)])
    with suppress(Exception):
        await jobs_db.create_index([("chat_id", 1), ("message_id", 1)], unique=True)


async def _get_setting(chat_id: int):
    return await settings_db.find_one({"chat_id": chat_id})


def _parse_delay(value: str):
    match = _DURATION_RE.fullmatch(value or "")
    if not match:
        return None

    amount = int(match.group(1))
    unit = match.group(2).lower()
    seconds = amount * {"s": 1, "m": 60, "h": 3600}[unit]

    if seconds < MIN_SECONDS or seconds > MAX_SECONDS:
        return None
    return seconds


async def _bot_can_delete(chat_id: int) -> bool:
    """Return whether the bot has permission to delete channel posts."""
    try:
        member = await app.get_chat_member(chat_id, app.id)
        if member.status == ChatMemberStatus.OWNER:
            return True
        privileges = member.privileges
        return bool(privileges and privileges.can_delete_messages)
    except Exception:
        return False


async def _queue_delete(chat_id: int, message_id: int, delay: int):
    delete_at = int(time.time()) + delay
    await jobs_db.update_one(
        {"chat_id": chat_id, "message_id": message_id},
        {
            "$set": {
                "chat_id": chat_id,
                "message_id": message_id,
                "delete_at": delete_at,
            }
        },
        upsert=True,
    )


async def _delete_worker():
    await _ensure_indexes()

    while True:
        try:
            now = int(time.time())
            cursor = (
                jobs_db.find(
                    {"delete_at": {"$lte": now}},
                    {"chat_id": 1, "message_id": 1},
                )
                .sort("delete_at", 1)
                .limit(100)
            )
            jobs = await cursor.to_list(length=100)

            for job in jobs:
                job_id = job["_id"]
                chat_id = job["chat_id"]
                message_id = job["message_id"]

                try:
                    await app.delete_messages(chat_id, message_id)
                except Exception as exc:
                    # The message may already have been removed or become
                    # unavailable. Do not let one failed job stop the worker.
                    log.debug(
                        "Channel auto-delete failed for %s/%s: %s",
                        chat_id,
                        message_id,
                        type(exc).__name__,
                    )

                with suppress(Exception):
                    await jobs_db.delete_one({"_id": job_id})

        except asyncio.CancelledError:
            raise
        except Exception as exc:
            log.warning(
                "Channel auto-delete worker error: %s: %s",
                type(exc).__name__,
                exc,
            )

        await asyncio.sleep(1)


_worker_task = None


async def _start_worker():
    global _worker_task
    if _worker_task is None or _worker_task.done():
        await _ensure_indexes()
        _worker_task = asyncio.create_task(_delete_worker())


INVALID_TEXT = (
    "Invalid time selected!\n"
    "Should be under 24 hours or off!\n\n"
    "Use like this:\n"
    "/setdelay 1m or 5s or 22h or off (To turn off.)\n\n"
    "Maximum is 24 hours and minimum is 3 seconds."
)


# ---------------------------------------------------------------------------
# /setdelay — CHANNEL ONLY
# ---------------------------------------------------------------------------

@app.on_message(
    filters.channel & filters.regex(r"(?i)^/setdelay(?:@\w+)?(?:\s+(.+?))?\s*$"),
    group=-20,
)
async def setdelay_handler(_, message: Message):
    await _start_worker()

    # This guard makes the scope explicit even if Pyrogram filter behavior
    # changes in a future release.
    if message.chat.type != ChatType.CHANNEL:
        return

    # Channel posts have no normal from_user. Telegram only allows channel
    # members with posting rights/admins to publish, so this command is usable
    # by channel admins who can post. The bot's own post is not an incoming
    # command in the normal update flow.
    if not await _bot_can_delete(message.chat.id):
        with suppress(Exception):
            await message.reply_text(
                "I need <b>Delete Messages</b> admin permission to work here."
            )
        return

    text = message.text or message.caption or ""
    parts = text.split(maxsplit=1)
    value = parts[1].strip() if len(parts) == 2 else ""

    # `/setdelay on` is intentionally invalid.
    if value.lower() == "on":
        with suppress(Exception):
            await message.reply_text(INVALID_TEXT)
        return

    if value.lower() == "off":
        await settings_db.update_one(
            {"chat_id": message.chat.id},
            {
                "$set": {
                    "chat_id": message.chat.id,
                    "enabled": False,
                }
            },
            upsert=True,
        )
        with suppress(Exception):
            await message.reply_text("Turned off for new messages!")
        return

    seconds = _parse_delay(value)
    if seconds is None:
        with suppress(Exception):
            await message.reply_text(INVALID_TEXT)
        return

    await settings_db.update_one(
        {"chat_id": message.chat.id},
        {
            "$set": {
                "chat_id": message.chat.id,
                "delay": seconds,
                "enabled": True,
            }
        },
        upsert=True,
    )

    with suppress(Exception):
        await message.reply_text(f"Successfully updated to {value.lower()}!")


# ---------------------------------------------------------------------------
# Delete NEW CHANNEL POSTS according to that channel's saved setting.
# ---------------------------------------------------------------------------

@app.on_message(filters.channel & filters.incoming, group=0)
async def autodelete_new_channel_post(_, message: Message):
    try:
        # Hard channel-only guard.
        if message.chat.type != ChatType.CHANNEL:
            return

        setting = await _get_setting(message.chat.id)
        if not setting or not setting.get("enabled"):
            return

        delay = int(setting.get("delay") or 0)
        if delay < MIN_SECONDS or delay > MAX_SECONDS:
            return

        if not await _bot_can_delete(message.chat.id):
            return

        # Do not delete the command itself immediately; it is a command post.
        # The requested behavior concerns new channel messages after the
        # delay setting is active.
        text = message.text or message.caption or ""
        if re.match(r"(?i)^/setdelay(?:@\w+)?(?:\s+.+?)?\s*$", text):
            return

        await _queue_delete(message.chat.id, message.id, delay)
    except Exception as exc:
        log.debug(
            "Channel auto-delete handler failed: %s: %s",
            type(exc).__name__,
            exc,
        )


async def _bootstrap():
    await _start_worker()


# Plugins are imported from an already-running event loop by __main__.py.
# Start the persistent worker without requiring any edit to another file.
try:
    asyncio.get_running_loop().create_task(_bootstrap())
except RuntimeError:
    pass
