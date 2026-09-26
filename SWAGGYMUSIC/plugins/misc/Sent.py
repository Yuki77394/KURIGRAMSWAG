"""
SWAGGYMUSIC - /sent
====================

SUDO-only Saved Messages feature.

Security:
- This module does NOT ask for or store Telegram OTP/2FA passwords.
- A separately authenticated Telegram user client must be registered with
  `register_authenticated_client()` by your secure/private authentication
  layer.
- The bot then uses that already-authenticated client to save the account's
  FIRST NAME as a clickable mention in its own Saved Messages.

Repo-specific:
- Uses SWAGGYMUSIC.misc.SUDOERS.
- Uses SWAGGYMUSIC.core.mongo.mongodb.
- PM-only.
- Uses a dedicated Mongo collection: `sent_accounts`.

Example secure integration:
    from SWAGGYMUSIC.plugins.misc.sent import register_authenticated_client

    register_authenticated_client(owner_id, authenticated_user_client)

Then `/sent` from that SUDO user performs the Saved Messages operation.
"""

from contextlib import suppress

from pyrogram import filters
from pyrogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)

from SWAGGYMUSIC import app
from SWAGGYMUSIC.misc import SUDOERS
from SWAGGYMUSIC.core.mongo import mongodb


sentdb = mongodb.sent_accounts

# In-memory registry. Authentication must happen outside the bot chat.
AUTHENTICATED_CLIENTS = {}


ACCESS_DENIED = """❌ <b>Access Denied</b>

You don't have permission to use this feature.

🔐 To request access, please contact one and Only @SexyProfessor"""


def register_authenticated_client(owner_id: int, user_client) -> None:
    """Register an already-authenticated Telegram user client."""
    AUTHENTICATED_CLIENTS[int(owner_id)] = user_client


def unregister_authenticated_client(owner_id: int):
    """Remove the in-memory client reference."""
    return AUTHENTICATED_CLIENTS.pop(int(owner_id), None)


def _logout_keyboard(owner_id: int):
    return InlineKeyboardMarkup(
        [[
            InlineKeyboardButton(
                "🚪 Logout Account",
                callback_data=f"sent:logout:{int(owner_id)}",
            )
        ]]
    )


async def _save_first_name(owner_id: int, user_client):
    """Save only the authenticated account's first name as a clickable mention."""
    me = await user_client.get_me()

    first_name = (getattr(me, "first_name", None) or "User").strip() or "User"
    account_id = int(me.id)

    # The URL is hidden behind the first-name text.
    mention = f'<a href="tg://user?id={account_id}">{first_name}</a>'

    await user_client.send_message(
        "me",
        mention,
        parse_mode="html",
    )

    await sentdb.update_one(
        {"owner_id": int(owner_id)},
        {
            "$set": {
                "owner_id": int(owner_id),
                "account_id": account_id,
                "first_name": first_name,
            }
        },
        upsert=True,
    )

    return first_name


@app.on_message(filters.private & filters.command("sent") & SUDOERS)
async def sent_command(client, message):
    owner_id = int(message.from_user.id)

    user_client = AUTHENTICATED_CLIENTS.get(owner_id)

    if user_client is None:
        await message.reply_text(
            "🔐 <b>Account Not Connected</b>\n\n"
            "Your Telegram user account is not connected to the "
            "secure /sent service yet."
        )
        return

    try:
        first_name = await _save_first_name(owner_id, user_client)

        await message.reply_text(
            "✅ <b>Successfully Saved</b>\n\n"
            f"Your first name <b>{first_name}</b> has been saved as a "
            "clickable mention in your Saved Messages.",
            reply_markup=_logout_keyboard(owner_id),
        )

    except Exception as exc:
        await message.reply_text(
            "❌ <b>Operation Failed</b>\n\n"
            "The authenticated account could not be used for Saved Messages."
        )


@app.on_message(filters.private & filters.command("sent"))
async def sent_denied(client, message):
    if message.from_user and message.from_user.id in SUDOERS:
        return

    await message.reply_text(ACCESS_DENIED)


@app.on_callback_query(filters.regex(r"^sent:logout:(\d+)$"))
async def sent_logout(client, callback_query: CallbackQuery):
    owner_id = int(callback_query.matches[0].group(1))

    if callback_query.from_user.id != owner_id:
        await callback_query.answer(
            "This logout button belongs to another user.",
            show_alert=True,
        )
        return

    if owner_id not in SUDOERS:
        await callback_query.answer(
            "You no longer have SUDO access.",
            show_alert=True,
        )
        return

    user_client = unregister_authenticated_client(owner_id)

    # If the external client exposes stop/disconnect, close it.
    if user_client is not None:
        try:
            disconnect = getattr(user_client, "disconnect", None)
            if disconnect:
                result = disconnect()
                if hasattr(result, "__await__"):
                    await result
        except Exception:
            pass

    # Delete ONLY this feature's record.
    await sentdb.delete_one({"owner_id": owner_id})

    with suppress(Exception):
        await callback_query.message.edit_text(
            "✅ <b>Account Logged Out</b>\n\n"
            "Your /sent feature data has been cleared."
        )

    await callback_query.answer("Logged out successfully.")


__all__ = [
    "register_authenticated_client",
    "unregister_authenticated_client",
]
