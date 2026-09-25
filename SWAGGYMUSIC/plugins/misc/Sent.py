"""
SWAGGYMUSIC - /sent feature
--------------------------------
SUDO-only Saved Messages helper.

Important:
This module deliberately does NOT collect Telegram OTPs or 2FA passwords
through the bot chat. A Telegram user-account client must be authenticated
through a secure/private flow outside the bot and then supplied to
`save_first_name_to_saved_messages()`.

What this module provides:
- /sent is SUDO-only.
- Non-SUDO users receive the requested English access-denied message.
- Saves ONLY the authenticated account's FIRST NAME as a clickable
  `tg://user?id=...` mention to Saved Messages.
- Provides a Logout Account button.
- Keeps feature-specific MongoDB state isolated.
- Logout callback deletes only this feature's MongoDB record.

Integration point:
An authenticated user client can be wired into
`save_first_name_to_saved_messages()` without touching the rest of the bot.
"""

from contextlib import suppress

from pyrogram import filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery

from SWAGGYMUSIC import app
from SWAGGYMUSIC.misc import SUDOERS
from SWAGGYMUSIC.core.mongo import mongodb


# Dedicated collection: never touch the bot's normal user/music collections.
sentdb = mongodb.sent_accounts


ACCESS_DENIED = """❌ <b>Access Denied</b>

You don't have permission to use this feature.

🔐 To request access, please contact one and Only @SexyProfessor"""


def _logout_keyboard(owner_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[
            InlineKeyboardButton(
                "🚪 Logout Account",
                callback_data=f"sent:logout:{owner_id}",
            )
        ]]
    )


async def _is_sudo(user_id: int) -> bool:
    # SUDOERS is a Pyrogram user filter object in this repo, so use the
    # database-backed sudo list as the authoritative source.
    try:
        sudo_doc = await mongodb.sudoers.find_one({"sudo": "sudo"})
        sudo_ids = set((sudo_doc or {}).get("sudoers", []))
        return user_id in sudo_ids
    except Exception:
        return False


async def _save_feature_state(owner_id: int, account_id: int, first_name: str):
    await sentdb.update_one(
        {"owner_id": owner_id},
        {
            "$set": {
                "owner_id": owner_id,
                "account_id": account_id,
                "first_name": first_name,
            }
        },
        upsert=True,
    )


async def _delete_feature_state(owner_id: int):
    await sentdb.delete_one({"owner_id": owner_id})


async def save_first_name_to_saved_messages(
    user_client,
    owner_id: int,
) -> str:
    """
    Save the authenticated Telegram account's first name as a clickable
    profile mention in its own Saved Messages.

    `user_client` must already be securely authenticated outside the bot.
    """
    me = await user_client.get_me()

    first_name = (me.first_name or "User").strip() or "User"

    # Telegram's user mention deep-link.
    html = f'<a href="tg://user?id={me.id}">{first_name}</a>'

    await user_client.send_message(
        "me",
        html,
        parse_mode="html",
    )

    await _save_feature_state(
        owner_id=owner_id,
        account_id=int(me.id),
        first_name=first_name,
    )

    return first_name


@app.on_message(filters.command("sent") & SUDOERS)
async def sent_command(client, message):
    """
    SUDO-only entry point.

    The actual account-authentication step is intentionally not performed
    inside the bot chat. Wire a securely authenticated user client into
    save_first_name_to_saved_messages().
    """
    user_id = message.from_user.id

    await message.reply_text(
        "🔐 <b>Secure Account Login Required</b>\n\n"
        "Authenticate your Telegram account through a secure/private "
        "user-account login flow, then connect the authenticated client "
        "to this feature."
    )


@app.on_message(filters.command("sent"))
async def sent_non_sudo(client, message):
    """Catch /sent from users who are not SUDO."""
    user_id = message.from_user.id

    if await _is_sudo(user_id):
        # The SUDO-filtered handler above handles authorized users.
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

    if not await _is_sudo(owner_id):
        await callback_query.answer(
            "You no longer have SUDO access.",
            show_alert=True,
        )
        with suppress(Exception):
            await callback_query.message.edit_reply_markup(None)
        return

    # IMPORTANT:
    # The actual authenticated user-client logout/revoke must be performed
    # by the integration that owns that client. This module only removes
    # this feature's MongoDB state.
    await _delete_feature_state(owner_id)

    with suppress(Exception):
        await callback_query.message.edit_text(
            "✅ <b>Account logged out successfully.</b>\n\n"
            "Your /sent feature data has been cleared from the database."
        )

    await callback_query.answer("Logged out successfully.")


__all__ = [
    "save_first_name_to_saved_messages",
]
