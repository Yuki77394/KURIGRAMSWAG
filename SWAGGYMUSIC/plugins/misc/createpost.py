"""
SWAGGYMUSIC - Interactive Post Creator

Command: /createpost

Flow:
1. Ask for target chat/channel ID.
2. Verify that the bot can access the chat and is an administrator.
3. Choose Format 1 or Format 2.
4. Ask for User ID.
5. Ask for button colour.
6. Ask for a photo (Telegram photo or direct URL).
7. Generate and send the selected template to the target chat.

The wizard is intentionally in-memory; unfinished sessions are cleared on restart.
"""

import asyncio
import re
from contextlib import suppress

from pyrogram import filters
from pyrogram.enums import ButtonStyle, ChatMemberStatus, ChatType
from pyrogram.errors import RPCError
from pyrogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from SWAGGYMUSIC import app

SESSIONS = {}
LOCK = asyncio.Lock()

PREFIX = "createpost"


def _key(user_id: int) -> str:
    return f"{PREFIX}:{user_id}"


def _format_menu():
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("📋 Fᴏʀᴍᴀᴛ 1", callback_data=f"{PREFIX}:format:1")],
            [InlineKeyboardButton("📋 Fᴏʀᴍᴀᴛ 2", callback_data=f"{PREFIX}:format:2")],
            [InlineKeyboardButton("❌ Cᴀɴᴄᴇʟ", callback_data=f"{PREFIX}:cancel")],
        ]
    )


def _colour_menu():
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("🔵 Bʟᴜᴇ", callback_data=f"{PREFIX}:color:blue"),
                InlineKeyboardButton("🟢 Gʀᴇᴇɴ", callback_data=f"{PREFIX}:color:green"),
            ],
            [
                InlineKeyboardButton("🔴 Rᴇᴅ", callback_data=f"{PREFIX}:color:red"),
                InlineKeyboardButton("⚪ Dᴇғᴀᴜʟᴛ", callback_data=f"{PREFIX}:color:default"),
            ],
            [InlineKeyboardButton("❌ Cᴀɴᴄᴇʟ", callback_data=f"{PREFIX}:cancel")],
        ]
    )


def _button_style(value):
    return {
        "blue": ButtonStyle.PRIMARY,
        "green": ButtonStyle.SUCCESS,
        "red": ButtonStyle.DANGER,
    }.get(value)


def _format_one(mention: str) -> str:
    return f"""<b>❖ ʜᴇʏ ᴇᴠᴇʀʏᴏɴᴇ 👋</b>\n\n<b>⊚ ɪꜰ ʏᴏᴜ ɴᴇᴇᴅ ᴀɴʏ ʜᴇʟᴘ • ꜱᴜᴘᴘᴏʀᴛ • ɢᴜɪᴅᴀɴᴄᴇ\nʏᴏᴜ ᴄᴀɴ ᴄᴏɴɴᴇᴄᴛ ᴅɪʀᴇᴄᴛʟʏ 💬✨</b>\n\n<b>✦ ᴄᴏᴍᴇ {mention}</b>\n<b>✦ ᴀʟᴡᴀʏꜱ ʜᴇʀᴇ ᴛᴏ ʜᴇʟᴘ 🤍</b>\n\n<b>•── ⋅ ⋅ ⋅ ───── ⋅ • ⋅ ───── ⋅ ⋅ ⋅ ──•</b>"""


def _format_two(mention: str) -> str:
    return f"""<b>Uꜱᴇʀɴᴀᴍᴇ Rᴇᴍᴏᴠᴇᴅ 🔄🔄</b>\n\n<b>Dᴍ Hᴇʀᴇ : {mention} 💗💗</b>\n\n<b>Aᴅᴅ Tᴏ Cᴏɴᴛᴀᴄᴛ Mᴇ Aʟᴡᴀʏꜱ 🚩💚</b>"""


async def _bot_admin_status(chat_id: int):
    """Return (ok, reason). For channels, require posting permission."""
    try:
        chat = await app.get_chat(chat_id)
        member = await app.get_chat_member(chat_id, app.id)
    except Exception as exc:
        return False, f"❌ I can't access that chat.\n<code>{type(exc).__name__}</code>"

    if member.status not in (ChatMemberStatus.OWNER, ChatMemberStatus.ADMINISTRATOR):
        return False, "❌ I am not an administrator in that chat. Please promote me and try again."

    privileges = member.privileges
    if chat.type == ChatType.CHANNEL:
        if not privileges or not privileges.can_post_messages:
            return False, "❌ I am an admin, but I don't have permission to post messages in this channel."

    return True, None


async def _send_step(message: Message, text: str, reply_markup=None):
    with suppress(Exception):
        await message.reply_text(text, reply_markup=reply_markup)


@app.on_message(filters.command("createpost") & ~filters.edited)
async def createpost_start(_, message: Message):
    if not message.from_user:
        return

    user_id = message.from_user.id
    async with LOCK:
        SESSIONS[user_id] = {"step": "chat_id"}

    await message.reply_text(
        "<b>🛠 Pᴏsᴛ Cʀᴇᴀᴛᴏʀ</b>\n\n"
        "<b>⚠️ Bᴇғᴏʀᴇ ᴜsɪɴɢ ᴛʜɪs ғᴇᴀᴛᴜʀᴇ:</b>\n"
        "Tʜᴇ ʙᴏᴛ ᴍᴜsᴛ ʙᴇ ᴀɴ <b>ᴀᴅᴍɪɴ</b> ɪɴ ʏᴏᴜʀ ɢʀᴏᴜᴘ/ᴄʜᴀɴɴᴇʟ.\n\n"
        "📌 Sᴇɴᴅ ᴛʜᴇ <b>Cʜᴀᴛ ID</b> ᴡʜᴇʀᴇ ʏᴏᴜ ᴡᴀɴᴛ ᴛʜᴇ ᴘᴏsᴛ ᴛᴏ ʙᴇ sᴇɴᴛ.\n\n"
        "<i>Example: -1001234567890</i>\n\n"
        "Send /cancel anytime to stop."
    )


@app.on_message(filters.command("cancel") & ~filters.edited)
async def createpost_cancel(_, message: Message):
    if message.from_user:
        SESSIONS.pop(message.from_user.id, None)
    await message.reply_text("❌ <b>Pᴏsᴛ Cʀᴇᴀᴛᴏʀ ᴄᴀɴᴄᴇʟʟᴇᴅ.</b>")


@app.on_callback_query(filters.regex(rf"^{PREFIX}:"))
async def createpost_callbacks(_, query: CallbackQuery):
    if not query.from_user:
        return await query.answer("Not available.", show_alert=True)

    user_id = query.from_user.id
    session = SESSIONS.get(user_id)

    if not session:
        return await query.answer("This setup has expired. Use /createpost again.", show_alert=True)

    data = query.data

    if data == f"{PREFIX}:cancel":
        SESSIONS.pop(user_id, None)
        await query.answer("Cancelled")
        with suppress(Exception):
            await query.message.edit_text("❌ <b>Pᴏsᴛ Cʀᴇᴀᴛᴏʀ ᴄᴀɴᴄᴇʟʟᴇᴅ.</b>")
        return

    if data.startswith(f"{PREFIX}:format:"):
        if session.get("step") != "format":
            return await query.answer("Please follow the current step.", show_alert=True)

        session["format"] = data.rsplit(":", 1)[1]
        session["step"] = "user_id"
        await query.answer("Format selected")
        await query.message.edit_text(
            "<b>2/4 — Sᴇɴᴅ Uꜱᴇʀ ID</b>\n\n"
            "Send the Telegram User ID whose name and mention should appear in the post."
        )
        return

    if data.startswith(f"{PREFIX}:color:"):
        if session.get("step") != "color":
            return await query.answer("Please follow the current step.", show_alert=True)

        session["color"] = data.rsplit(":", 1)[1]
        session["step"] = "photo"
        await query.answer("Colour selected")
        await query.message.edit_text(
            "<b>4/5 — Sᴇɴᴅ Pʜᴏᴛᴏ</b>\n\n"
            "Send the image as a Telegram photo, or send a direct image URL."
        )
        return

    await query.answer("Unknown option.", show_alert=True)


@app.on_message(filters.incoming & ~filters.service & ~filters.command("createpost") & ~filters.command("cancel"))
async def createpost_input(_, message: Message):
    if not message.from_user:
        return

    user_id = message.from_user.id
    session = SESSIONS.get(user_id)
    if not session:
        return

    step = session.get("step")
    raw = (message.text or message.caption or "").strip()

    if step == "chat_id":
        try:
            chat_id = int(raw)
        except ValueError:
            return await message.reply_text("❌ Send a valid numeric Chat ID, e.g. <code>-1001234567890</code>.")

        ok, reason = await _bot_admin_status(chat_id)
        if not ok:
            return await message.reply_text(reason)

        session["chat_id"] = chat_id
        session["step"] = "format"
        await message.reply_text(
            "<b>✅ Bᴏᴛ ᴀᴅᴍɪɴ ᴠᴇʀɪғɪᴇᴅ.</b>\n\n"
            "<b>1/4 — Cʜᴏᴏsᴇ Pᴏsᴛ Fᴏʀᴍᴀᴛ</b>",
            reply_markup=_format_menu(),
        )
        return

    if step == "user_id":
        try:
            target_user_id = int(raw)
            target_user = await app.get_users(target_user_id)
        except (ValueError, RPCError):
            return await message.reply_text("❌ Invalid or inaccessible User ID. Send a valid Telegram User ID.")
        except Exception:
            return await message.reply_text("❌ I couldn't fetch that user. Please check the User ID and try again.")

        session["user"] = target_user
        session["step"] = "color"
        await message.reply_text(
            f"<b>✅ User:</b> <a href='tg://user?id={target_user.id}'>{target_user.first_name or 'User'}</a>\n\n"
            "<b>3/4 — Cʜᴏᴏsᴇ Bᴜᴛᴛᴏɴ Cᴏʟᴏᴜʀ</b>",
            reply_markup=_colour_menu(),
        )
        return

    if step == "photo":
        photo = None
        if message.photo:
            photo = message.photo.file_id
        elif raw:
            if not re.match(r"^https?://\S+$", raw, re.IGNORECASE):
                return await message.reply_text("❌ Send a valid direct image URL or upload the image as a Telegram photo.")
            photo = raw

        if not photo:
            return await message.reply_text("❌ Please send a photo or a direct image URL.")

        session["photo"] = photo
        session["step"] = "sending"
        await message.reply_text("⏳ <b>Cʀᴇᴀᴛɪɴɢ ʏᴏᴜʀ ᴘᴏsᴛ...</b>")

        try:
            target_user = session["user"]
            name = target_user.first_name or "User"
            mention = f'<a href="tg://user?id={target_user.id}">{name}</a>'

            if session["format"] == "1":
                caption = _format_one(mention)
            else:
                caption = _format_two(mention)

            style = _button_style(session.get("color"))
            button_kwargs = {"text": name, "user_id": target_user.id}
            if style is not None:
                button_kwargs["style"] = style

            keyboard = InlineKeyboardMarkup([[InlineKeyboardButton(**button_kwargs)]])

            await app.send_photo(
                chat_id=session["chat_id"],
                photo=photo,
                caption=caption,
                reply_markup=keyboard,
            )

            with suppress(Exception):
                await message.reply_text("✅ <b>Pᴏsᴛ ᴄʀᴇᴀᴛᴇᴅ sᴜᴄᴄᴇssғᴜʟʟʏ.</b>")
        except Exception as exc:
            await message.reply_text(
                "❌ <b>Fᴀɪʟᴇᴅ ᴛᴏ ᴄʀᴇᴀᴛᴇ ᴛʜᴇ ᴘᴏsᴛ.</b>\n\n"
                f"<code>{type(exc).__name__}: {str(exc)[:500]}</code>"
            )
        finally:
            SESSIONS.pop(user_id, None)
