#
# Copyright (C) 2021-2022 by TheAloneteam@Github, < https://github.com/TheAloneTeam >.
#
# This file is part of < https://github.com/TheAloneTeam/SWAGGYMUSIC > project,
# and is released under the "GNU v3.0 License Agreement".
# Please see < https://github.com/TheAloneTeam/SWAGGYMUSIC/blob/master/LICENSE >
#
# All rights reserved.

"""Welcome system — adapted from the autoplaysty reference repository.

This module implements the complete welcome feature:
  - Persistent per-chat enable/disable flag (MongoDB-backed, restart-safe)
  - /welcome command (admins only) showing current status with toggle buttons
  - Inline callback handler for the enable/disable buttons
  - Dual event detection for new members:
      * Primary: on_chat_member_updated (group=-3)
      * Backup: on_message(filters.new_chat_members) (group=-5)
        — uses a non-conflicting group number; existing handlers in
        start.py (group=-1) and logs.py (default group=0) are unaffected.
  - Welcome image generation: wel2.png template + circular profile pic
    overlay + user_id + username text rendering via PIL
  - Auto-delete previous welcome message per chat (in-memory dict, since
    it only tracks ephemeral message handles that wouldn't survive restart
    anyway)
  - Auto-delete the welcome message itself after 3 minutes
  - Comprehensive try/except around every step so a single failure can
    never crash the bot or block other plugins

Persistence model:
  - MongoDB collection `welcome_toggle` stores one document per chat:
        { "_id": ObjectId(...), "chat_id": <int>, "welcome": <bool> }
  - An in-memory cache (welcomem dict in utils/database.py) mirrors the
    DB row to avoid a Mongo round-trip on every new-member join event,
    which fires frequently and is latency-sensitive.
"""

import asyncio
import os

from PIL import Image, ImageDraw, ImageEnhance, ImageFont
from pyrogram import enums, filters
from pyrogram.enums import ButtonStyle, ParseMode
from pyrogram.types import (
    ChatMemberUpdated,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from SWAGGYMUSIC import app
from SWAGGYMUSIC.logging import LOGGER
from SWAGGYMUSIC.utils.database import (
    disable_welcome,
    enable_welcome,
    is_welcome_enabled,
)
from config import BANNED_USERS
from strings import get_string

_log = LOGGER(__name__)

# ─── Parse mode rationale ────────────────────────────────────────────────────
# The target repo's Pyrogram client (core/bot.py) sets a global
# `parse_mode=ParseMode.HTML`. This means by default Pyrogram will:
#   - Parse <b>bold</b>, <u>underline</u>, <code>...</code> etc. as HTML
#   - Send Markdown syntax like **bold** as LITERAL TEXT (no parsing)
#
# The welcome caption (welcome_caption in en.yml) contains BOTH:
#   - Markdown:  **⏤͟͟͞͞★ ʜᴇʟʟᴏ ᴅᴇᴀʀ...**  and  **➻ ɴᴀᴍᴇ »**
#   - HTML:      <u>**❖ ᴜsᴇʀ sʜᴏʀᴛ ɪɴꜰᴏ**</u>
#
# The autoplaysty source repo (Pyrogram 2.0.106, no global parse_mode) lets
# Pyrogram default to ParseMode.DEFAULT which parses BOTH Markdown and HTML
# simultaneously. That is why `**bold**` renders as actual bold in the source
# bot but shows up as literal `**` characters in the target bot.
#
# Fix: explicitly pass `parse_mode=ParseMode.DEFAULT` to every welcome
# message-sending call. DEFAULT mode is "combined Markdown+HTML", which
# correctly parses BOTH `**bold**` AND `<u>underline</u>` in the same text.
#
# We do NOT change the global parse_mode (would break the HTML-only
# convention used by hundreds of other strings in en.yml like call_10,
# general_2, tg_1, etc.). The fix is scoped to welcome messages only.
#
# A safe fallback is included: if DEFAULT parsing fails on malformed
# input (e.g. unmatched `**` or invalid HTML), we retry with HTML-only
# parsing, then as a last resort plain text. This ensures the welcome
# message is always delivered even if the caption is malformed.

# ─── In-memory store for auto-deleting previous welcome messages ────────────
# Only tracks message *handles* (not settings) — these are inherently
# ephemeral and would not survive a bot restart anyway, so a dict is fine.
# Persistent state lives in MongoDB via the helpers above.


class _WelcomeTemp:
    PREV_MSG = {}


_temp = _WelcomeTemp()


# ─── Asset paths ─────────────────────────────────────────────────────────────
# wel2.png was copied from the autoplaysty reference repo. Target already
# had upic.png (fallback profile pic) and font2.ttf, so those are reused.

_WEL2_BG = os.path.join("SWAGGYMUSIC", "assets", "wel2.png")
_FALLBACK_PIC = os.path.join("SWAGGYMUSIC", "assets", "upic.png")
_FONT_PATH = os.path.join("SWAGGYMUSIC", "assets", "font2.ttf")
_DOWNLOADS_DIR = "downloads"


# ─── Image-rendering parameters ──────────────────────────────────────────────
# The reference template (wel2.png) is 1734×907. These coordinates are
# tuned for that exact resolution. If the asset is ever replaced with a
# different-size template, the values below must be recalibrated.

_CIRCLE_SIZE = (354, 354)
_CIRCLE_PASTE_POS = (280, 232)

_TEXT_FONT_SIZE = 53
_TEXT_COLOR = (225, 200, 145)  # gold/tan, matching template labels
_UID_DRAW_POS = (1020, 712)
_UNAME_DRAW_POS = (1020, 786)
_MAX_TEXT_X = 1680  # right boundary for text truncation


# ─── Image helpers ───────────────────────────────────────────────────────────


def _circle(pfp, size=None, brightness_factor=1.4):
    """Crop profile photo to a centered square, resize, brighten, and
    apply a circular alpha mask so it can be pasted onto the template."""
    if size is None:
        size = _CIRCLE_SIZE
    # Center-crop to square first so rectangular photos aren't stretched
    w, h = pfp.size
    min_dim = min(w, h)
    left = (w - min_dim) // 2
    top = (h - min_dim) // 2
    pfp = pfp.crop((left, top, left + min_dim, top + min_dim))
    pfp = pfp.resize(size).convert("RGBA")
    pfp = ImageEnhance.Brightness(pfp).enhance(brightness_factor)
    mask = Image.new("L", size, 0)
    draw = ImageDraw.Draw(mask)
    draw.ellipse((0, 0, size[0], size[1]), fill=255)
    pfp.putalpha(mask)
    return pfp


def _generate_welcome_image(pic_path, user_id, username):
    """Render the welcome image by overlaying the profile photo and the
    user's ID/username onto the wel2.png template. Returns the output path."""
    background = Image.open(_WEL2_BG).convert("RGBA")
    pfp = Image.open(pic_path).convert("RGBA")
    pfp = _circle(pfp, size=_CIRCLE_SIZE, brightness_factor=1.3)
    background.paste(pfp, _CIRCLE_PASTE_POS, pfp)

    draw = ImageDraw.Draw(background)
    font = ImageFont.truetype(_FONT_PATH, _TEXT_FONT_SIZE)

    username_text = f"@{username}" if username else "Not Set"

    # Truncate long usernames to stay within _MAX_TEXT_X
    try:
        uname_val_w = font.getbbox(username_text)[2]
    except Exception:
        uname_val_w = 0
    if _UNAME_DRAW_POS[0] + uname_val_w > _MAX_TEXT_X:
        while len(username_text) > 3:
            test = username_text + "..."
            try:
                test_w = font.getbbox(test)[2]
            except Exception:
                test_w = 0
            if test_w + _UNAME_DRAW_POS[0] <= _MAX_TEXT_X:
                username_text = test
                break
            username_text = username_text[:-1]
        else:
            username_text += "..."

    draw.text(_UID_DRAW_POS, str(user_id), font=font, fill=_TEXT_COLOR)
    draw.text(_UNAME_DRAW_POS, username_text, font=font, fill=_TEXT_COLOR)

    os.makedirs(_DOWNLOADS_DIR, exist_ok=True)
    output_path = os.path.join(_DOWNLOADS_DIR, f"welcome_{user_id}.png")
    background.save(output_path)
    return output_path


# ─── Shared send-welcome logic ──────────────────────────────────────────────
# Factored out so the primary ChatMemberUpdated handler and the backup
# new_chat_members handler share identical behaviour — avoiding drift.


async def _safe_send_photo(client, chat_id, photo, caption, reply_markup=None):
    """Send a photo with combined Markdown+HTML parsing, with safe fallback.

    Tries ParseMode.DEFAULT (combined Markdown+HTML) first — this matches
    the autoplaysty source repo's default Pyrogram 2.0.106 behavior.
    If that fails (malformed markup), retries with HTML-only parsing
    (strips any unmatched `**` markers from the rendered text). If that
    also fails, retries with DISABLED parse mode (sends raw text).
    Never raises — returns the Message on success or None on total failure.
    """
    attempts = [
        (ParseMode.DEFAULT, "DEFAULT (Markdown+HTML combined)"),
        (ParseMode.HTML, "HTML only"),
        (ParseMode.DISABLED, "DISABLED (plain text)"),
    ]
    for mode, label in attempts:
        try:
            return await client.send_photo(
                chat_id=chat_id,
                photo=photo,
                caption=caption,
                parse_mode=mode,
                reply_markup=reply_markup,
            )
        except Exception as e:
            _log.warning(
                f"welcome send_photo failed with parse_mode={label}: {e}"
            )
            if mode == ParseMode.DISABLED:
                # Last resort also failed — give up entirely.
                return None
    return None


async def _safe_reply_text(message, text, reply_markup=None):
    """Reply with text using combined Markdown+HTML parsing, with fallback.

    Same fallback ladder as _safe_send_photo: DEFAULT → HTML → DISABLED.
    """
    attempts = [
        (ParseMode.DEFAULT, "DEFAULT (Markdown+HTML combined)"),
        (ParseMode.HTML, "HTML only"),
        (ParseMode.DISABLED, "DISABLED (plain text)"),
    ]
    for mode, label in attempts:
        try:
            return await message.reply_text(
                text=text,
                parse_mode=mode,
                reply_markup=reply_markup,
            )
        except Exception as e:
            _log.warning(
                f"welcome reply_text failed with parse_mode={label}: {e}"
            )
            if mode == ParseMode.DISABLED:
                return None
    return None


async def _safe_edit_text(message, text, reply_markup=None, disable_preview=True):
    """Edit message text using combined Markdown+HTML parsing, with fallback.

    Same fallback ladder as _safe_send_photo: DEFAULT → HTML → DISABLED.
    """
    attempts = [
        (ParseMode.DEFAULT, "DEFAULT (Markdown+HTML combined)"),
        (ParseMode.HTML, "HTML only"),
        (ParseMode.DISABLED, "DISABLED (plain text)"),
    ]
    for mode, label in attempts:
        try:
            return await message.edit_text(
                text=text,
                parse_mode=mode,
                disable_web_page_preview=disable_preview,
                reply_markup=reply_markup,
            )
        except Exception as e:
            _log.warning(
                f"welcome edit_text failed with parse_mode={label}: {e}"
            )
            if mode == ParseMode.DISABLED:
                return None
    return None


async def _send_welcome(client, chat_id, chat_title, user):
    """Generate the welcome image and send the welcome message.

    Designed to swallow all exceptions internally so that a failure here
    can never propagate up and break the calling event handler (which
    would block subsequent handlers from running).
    """
    # ── Download profile photo with fallback ──
    pic_path = _FALLBACK_PIC
    downloaded_pic = None
    try:
        if user.photo and user.photo.big_file_id:
            downloaded_pic = os.path.join(_DOWNLOADS_DIR, f"pp{user.id}.png")
            await client.download_media(
                user.photo.big_file_id, file_name=downloaded_pic
            )
            pic_path = downloaded_pic
    except Exception as e:
        _log.warning(f"welcome pfp download failed for {user.id}: {e}")

    # ── Delete previous welcome message for this chat ──
    old_msg = _temp.PREV_MSG.get(f"welcome-{chat_id}")
    if old_msg:
        try:
            await old_msg.delete()
        except Exception:
            pass

    # ── Generate welcome image ──
    welcome_img_path = None
    try:
        welcome_img_path = _generate_welcome_image(pic_path, user.id, user.username)
    except Exception as e:
        _log.error(f"welcome image generation failed for {user.id}: {e}")
        if downloaded_pic and os.path.exists(downloaded_pic):
            try:
                os.remove(downloaded_pic)
            except Exception:
                pass
        return

    # ── Send welcome message ──
    try:
        username_display = f"@{user.username}" if user.username else "No Username"
        try:
            mention = user.mention
        except Exception:
            # user.mention can fail in some edge cases; build a manual mention
            mention = f"<a href='tg://user?id={user.id}'>{user.first_name or 'User'}</a>"

        try:
            language = await _get_chat_lang(chat_id)
            _ = get_string(language)
            caption = _["welcome_caption"].format(
                chat_title or "this group",
                mention,
                user.id,
                username_display,
            )
        except Exception:
            # If language lookup fails, fall back to a minimal hardcoded caption
            caption = (
                f"**⏤͟͟͞͞★ ʜᴇʟʟᴏ ᴅᴇᴀʀ ᴡᴇʟᴄᴏᴍᴇ ᴛᴏ : {chat_title or 'this group'}**\n\n"
                f"**➻ ɴᴀᴍᴇ »** {mention}\n"
                f"**➻ ᴜsᴇʀ_ɪᴅ »** `{user.id}`\n"
                f"**➻ ᴜ_ɴᴀᴍᴇ »** {username_display}\n"
            )

        msg = await _safe_send_photo(
            client,
            chat_id=chat_id,
            photo=welcome_img_path,
            caption=caption,
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "ᴀᴅᴅ ᴍᴇ ɪɴ ʏᴏᴜʀ ɢʀᴏᴜᴘ",
                            url=f"https://t.me/{client.username}?startgroup=true",
                            style=ButtonStyle.PRIMARY,
                        )
                    ]
                ]
            ),
        )

        # If all parse_mode fallbacks failed, give up — log the failure
        # and clear any stale PREV_MSG entry for this chat. There is no
        # message to schedule for deletion in this case.
        if msg is None:
            _log.error(
                f"welcome: all parse_mode fallbacks failed for chat {chat_id}, user {user.id}"
            )
            stale_key = f"welcome-{chat_id}"
            if stale_key in _temp.PREV_MSG:
                try:
                    del _temp.PREV_MSG[stale_key]
                except Exception:
                    pass
        else:
            # ── Schedule auto-delete after 3 minutes (180 seconds) ──
            async def _delete_welcome():
                await asyncio.sleep(180)
                try:
                    await msg.delete()
                except Exception:
                    pass
                key = f"welcome-{chat_id}"
                if key in _temp.PREV_MSG:
                    try:
                        del _temp.PREV_MSG[key]
                    except Exception:
                        pass

            asyncio.create_task(_delete_welcome())
            _temp.PREV_MSG[f"welcome-{chat_id}"] = msg

    except Exception as e:
        _log.error(f"welcome failed to send message: {e}")

    finally:
        # Clean up the downloaded profile pic (the welcome image is kept
        # only for the 3-minute auto-delete window — it gets removed by the
        # caller's cleanup or by the OS temp cleanup; we explicitly remove
        # the source pfp here).
        if downloaded_pic and os.path.exists(downloaded_pic):
            try:
                os.remove(downloaded_pic)
            except Exception:
                pass


async def _get_chat_lang(chat_id: int) -> str:
    """Wrapper around the target repo's get_lang that never raises —
    returns 'en' on any error so the welcome message still goes out."""
    try:
        from SWAGGYMUSIC.utils.database import get_lang
        return await get_lang(chat_id) or "en"
    except Exception:
        return "en"


# ─── Admin permission check (inline, not via AdminRightsCheck) ──────────────
# AdminRightsCheck is music-specific (checks is_active_chat, video-chat
# perms, etc.) and doesn't fit a non-music feature. The source repo's
# welcome.py uses an inline check, which we mirror here.


async def _is_chat_admin(client, chat_id: int, user_id: int) -> bool:
    """Return True if user_id is an admin or owner of chat_id.
    Never raises — returns False on any error."""
    try:
        member = await client.get_chat_member(chat_id, user_id)
        return member.status in (
            enums.ChatMemberStatus.ADMINISTRATOR,
            enums.ChatMemberStatus.OWNER,
        )
    except Exception as e:
        _log.error(f"welcome admin check error for {chat_id}/{user_id}: {e}")
        return False


# ─── /welcome command ──────────────────────────────────────────────────────


@app.on_message(
    filters.command("welcome") & filters.group & ~BANNED_USERS
)
async def welcome_cmd(client, message: Message):
    chat = message.chat
    chat_id = chat.id

    # Anonymous-admin shortcut: sender_chat means the message came from
    # the group itself (anonymous admin). Treat as admin and proceed.
    if not message.from_user and message.sender_chat:
        pass
    else:
        if not message.from_user:
            return
        if not await _is_chat_admin(client, chat_id, message.from_user.id):
            try:
                language = await _get_chat_lang(chat_id)
                _ = get_string(language)
                return await _safe_reply_text(message, _["welcome_5"])
            except Exception:
                return await _safe_reply_text(
                    message,
                    "**» ᴏɴʟʏ ᴀᴅᴍɪɴs ᴄᴀɴ ʜᴀɴᴅʟᴇ ᴡᴇʟᴄᴏᴍᴇ sʏsᴛᴇᴍ**"
                )

    try:
        state = await is_welcome_enabled(chat_id)
    except Exception as e:
        _log.error(f"welcome is_welcome_enabled error: {e}")
        state = True

    try:
        language = await _get_chat_lang(chat_id)
        _ = get_string(language)
    except Exception:
        _ = get_string("en")

    status = _["welcome_2"] if state else _["welcome_3"]

    btn = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "ᴇɴᴀʙʟᴇ",
                    callback_data=f"wlc_on_{chat_id}",
                    style=ButtonStyle.PRIMARY,
                ),
                InlineKeyboardButton(
                    "ᴅɪsᴀʙʟᴇ",
                    callback_data=f"wlc_off_{chat_id}",
                    style=ButtonStyle.SUCCESS,
                ),
            ]
        ]
    )

    try:
        await _safe_reply_text(
            message,
            _["welcome_1"].format(status, chat.title or "this group"),
            reply_markup=btn,
        )
    except Exception as e:
        _log.error(f"welcome cmd failed to send reply: {e}")


# ─── Callback handler for enable/disable buttons ────────────────────────────
# Prefix `wlc_` is unique across the entire target codebase — verified
# via grep, no collisions with existing callback_data patterns.


@app.on_callback_query(filters.regex(r"^wlc_") & ~BANNED_USERS)
async def welcome_toggle(client, query):
    try:
        data = query.data.split("_")
        action = data[1]
        chat_id = int(data[2])
    except (IndexError, ValueError):
        try:
            await query.answer("Invalid callback data", show_alert=True)
        except Exception:
            pass
        return

    # Admin check — only admins/owners can toggle welcome
    if not await _is_chat_admin(client, chat_id, query.from_user.id):
        try:
            language = await _get_chat_lang(chat_id)
            _ = get_string(language)
            return await query.answer(_["welcome_6"], show_alert=True)
        except Exception:
            return await query.answer(
                "ʏᴏᴜ ᴀʀᴇ ɴᴏᴛ ᴀᴅᴍɪɴ ʙᴀʙʏ 🥺", show_alert=True
            )

    if action == "on":
        await enable_welcome(chat_id)
        new_status_key = "welcome_2"
    else:
        await disable_welcome(chat_id)
        new_status_key = "welcome_3"

    try:
        chat = await client.get_chat(chat_id)
        chat_title = chat.title or "this group"
    except Exception:
        chat_title = "this group"

    try:
        language = await _get_chat_lang(chat_id)
        _ = get_string(language)
    except Exception:
        _ = get_string("en")

    try:
        await _safe_edit_text(
            query.message,
            _["welcome_4"].format(
                _[new_status_key],
                chat_title,
                query.from_user.mention,
            )
        )
    except Exception as e:
        _log.error(f"welcome toggle edit error: {e}")

    try:
        await query.answer()
    except Exception:
        pass


# ─── Primary handler: on_chat_member_updated ────────────────────────────────
# Fires when a user's chat-member status changes. We detect actual joins:
# status went from LEFT/BANNED → MEMBER/ADMINISTRATOR/RESTRICTED.
#
# group=-3 is chosen to be lower than start.py's group=-1 (which handles
# the bot being added to a chat) and lower than the default group=0
# (where logs.py runs). This handler runs *before* those, but since it
# only acts on non-bot user joins, there is no overlap.
#
# NOTE: No filters.group here — we check chat type inside the handler.
# This avoids subtle compatibility issues between filters.group and
# ChatMemberUpdated objects across Pyrogram versions.


@app.on_chat_member_updated(group=-3)
async def greet_new_member(client, member: ChatMemberUpdated):
    chat_id = member.chat.id

    # Only process supergroups and basic groups
    if member.chat.type not in (enums.ChatType.SUPERGROUP, enums.ChatType.GROUP):
        return

    # Check if welcome is enabled for this chat
    try:
        is_enabled = await is_welcome_enabled(chat_id)
    except Exception as e:
        _log.error(f"welcome is_welcome_enabled error: {e}")
        is_enabled = True

    if not is_enabled:
        return

    new_cm = member.new_chat_member
    old_cm = member.old_chat_member

    if not new_cm or not new_cm.user:
        return

    # ── Member-join detection ──
    # If old_cm is None, we can't reliably determine this is a fresh join
    # (it could be the initial state sync). Skip in that case — the
    # backup new_chat_members handler will catch actual joins.
    if old_cm is None:
        return

    try:
        old_status_val = old_cm.status
        new_status_val = new_cm.status

        is_join = (
            new_status_val
            in (
                enums.ChatMemberStatus.MEMBER,
                enums.ChatMemberStatus.ADMINISTRATOR,
                enums.ChatMemberStatus.RESTRICTED,
            )
            and old_status_val
            in (
                enums.ChatMemberStatus.LEFT,
                enums.ChatMemberStatus.BANNED,
            )
        )

        if not is_join:
            return
    except Exception as e:
        _log.error(f"welcome status check error: {e}")
        return

    user = new_cm.user

    # Skip if the joining entity is the bot itself — handled elsewhere
    if user.id == client.id:
        return

    try:
        await _send_welcome(client, chat_id, member.chat.title, user)
    except Exception as e:
        _log.error(f"welcome greet_new_member uncaught error: {e}")


# ─── Backup handler: on_message(new_chat_members) ───────────────────────────
# In some Pyrogram/Telegram API versions, on_chat_member_updated may not
# fire reliably for supergroups. This backup catches the service message
# that Telegram sends when members join.
#
# group=-5 is lower than start.py's group=-1. The start.py handler calls
# message.stop_propagation() only when `member.id == app.id`, so for
# regular user joins, start.py doesn't stop propagation — but it's in
# group=-1 which runs *after* this handler in group=-5. Either way, this
# handler explicitly skips `member.id == app.id` to avoid double-handling.
#
# Note: Pyrogram fires handlers in ascending group order, so group=-5
# runs *before* group=-1. This is fine — we don't call stop_propagation,
# so start.py and logs.py still get a chance to run their own logic.


@app.on_message(filters.new_chat_members, group=-5)
async def welcome_backup(client, message: Message):
    for new_user in message.new_chat_members:
        # Skip the bot itself (handled by start.py + logs.py)
        if new_user.id == app.id:
            continue

        chat_id = message.chat.id

        try:
            is_enabled = await is_welcome_enabled(chat_id)
        except Exception as e:
            _log.error(f"welcome backup is_welcome_enabled error: {e}")
            is_enabled = True

        if not is_enabled:
            continue

        try:
            await _send_welcome(client, chat_id, message.chat.title, new_user)
        except Exception as e:
            _log.error(f"welcome_backup _send_welcome error: {e}")
