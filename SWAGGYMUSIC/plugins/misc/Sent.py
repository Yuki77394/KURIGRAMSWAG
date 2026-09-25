from contextlib import suppress
from pyrogram import filters
from pyrogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from SWAGGYMUSIC import app
from SWAGGYMUSIC.misc import SUDOERS
from SWAGGYMUSIC.core.mongo import mongodb

sentdb = mongodb.sent_accounts

ACCESS_DENIED = """❌ <b>Access Denied</b>

You don't have permission to use this feature.

🔐 To request access, please contact one and Only @SexyProfessor"""


def logout_markup(owner_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton(
            "🚪 Logout Account",
            callback_data=f"sent:logout:{owner_id}",
        )]]
    )


async def _sudo_ids() -> set[int]:
    try:
        doc = await mongodb.sudoers.find_one({"sudo": "sudo"})
        return {int(x) for x in (doc or {}).get("sudoers", [])}
    except Exception:
        return set()


async def is_sudo(user_id: int) -> bool:
    return user_id in await _sudo_ids()


async def save_first_name_to_saved_messages(user_client, owner_id: int) -> str:
    """
    user_client must already be securely authenticated outside the bot.
    No OTP or 2FA password is collected by this module.
    """
    me = await user_client.get_me()
    first_name = (me.first_name or "User").strip() or "User"
    mention = f'<a href="tg://user?id={int(me.id)}">{first_name}</a>'

    await user_client.send_message("me", mention, parse_mode="html")

    await sentdb.update_one(
        {"owner_id": int(owner_id)},
        {"$set": {
            "owner_id": int(owner_id),
            "account_id": int(me.id),
            "first_name": first_name,
        }},
        upsert=True,
    )
    return first_name


@app.on_message(filters.private & filters.command("sent") & SUDOERS)
async def sent_sudo_entry(client, message):
    await message.reply_text(
        "🔐 <b>Secure Account Connection Required</b>\n\n"
        "Your Telegram user account must be authenticated through a "
        "secure/private login flow before it can be connected to this feature."
    )


@app.on_message(filters.private & filters.command("sent"))
async def sent_non_sudo(client, message):
    if await is_sudo(message.from_user.id):
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

    if not await is_sudo(owner_id):
        await callback_query.answer(
            "You no longer have SUDO access.",
            show_alert=True,
        )
        return

    await sentdb.delete_one({"owner_id": owner_id})

    with suppress(Exception):
        await callback_query.message.edit_text(
            "✅ <b>Account logged out successfully.</b>\n\n"
            "Your /sent feature data has been cleared."
        )

    await callback_query.answer("Logged out successfully.")


__all__ = ["save_first_name_to_saved_messages", "logout_markup"]
