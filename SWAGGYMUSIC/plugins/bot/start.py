#
# Copyright (C) 2021-2022 by Yuki77394@Github, < https://github.com/yuki77394 >.
# This file is part of < https://github.com/Yuki77394/SWAGGYMUSIC > project,
# and is released under the "GNU v3.0 License Agreement".
# Please see < https://github.com/Yuki77394/SWAGGYMUSIC/blob/master/LICENSE >
#
# All rights reserved.

import asyncio
import html
import json
import random
import re
import time

import aiohttp
from py_yt import VideosSearch
from pyrogram import filters
from pyrogram.enums import ButtonStyle, ChatMemberStatus, ChatType
from pyrogram.errors import (ChatAdminRequired, InviteRequestSent,
                             UserAlreadyParticipant)
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

import config
from SWAGGYMUSIC import app
from SWAGGYMUSIC.misc import _boot_
from SWAGGYMUSIC.plugins.sudo.sudoers import sudoers_list
from SWAGGYMUSIC.utils.database import (add_served_chat, add_served_user,
                                       blacklisted_chats, get_assistant,
                                       get_lang, is_banned_user, is_on_off)
from SWAGGYMUSIC.utils.decorators.language import LanguageStart
from SWAGGYMUSIC.utils.formatters import get_readable_time
from SWAGGYMUSIC.utils.inline import help_pannel, private_panel, start_panel
from config import BANNED_USERS
from strings import get_string

CELEBRATION_EFFECT_ID = 5046509860389126442  # 🎉 celebration/confetti effect

START_IMAGES = [
    "https://files.catbox.moe/jf0yqq.jpg",
    "https://files.catbox.moe/7w0ec2.jpg",
    "https://files.catbox.moe/dfj1l8.jpg",
    "https://files.catbox.moe/e7pbwj.jpg",
    "https://files.catbox.moe/bta4qz.jpg",
    "https://files.catbox.moe/1a1pu2.jpg",
    "https://files.catbox.moe/xvirq4.jpg",
    "https://files.catbox.moe/8dyj3u.jpg",
    "https://files.catbox.moe/x63yfj.jpg",
    "https://files.catbox.moe/3rtw9v.jpg",
    "https://files.catbox.moe/0u6db2.jpg",
]


def _escape_html_ampersands(text: str) -> str:
    """Escape literal ampersands without double-escaping HTML entities."""
    return re.sub(
        r"&(?!#(?:[0-9]+|x[0-9A-Fa-f]+);|[A-Za-z][A-Za-z0-9]+;)",
        "&amp;",
        text,
    )


def _build_start_caption(message: Message, template: str) -> str:
    """Build a Bot-API-safe HTML caption from the language template.

    The normal Kurigram ``mention`` strings are Telegram/MTProto formatted
    strings.  This private /start panel is sent through the Bot API instead,
    so construct the two placeholder mentions ourselves and HTML-escape only
    the user-controlled display names.
    """
    template = _escape_html_ampersands(template)

    user = message.from_user
    user_name = " ".join(
        part for part in (user.first_name, user.last_name) if part
    ).strip() or "User"
    safe_user_name = html.escape(user_name, quote=False)
    user_mention = (
        f'<a href="tg://user?id={int(user.id)}">{safe_user_name}</a>'
    )

    # ``app`` is the project's custom ``Alone`` client.  It exposes
    # ``name``, ``username`` and ``mention`` after startup, but it does NOT
    # expose ``first_name`` / ``last_name`` attributes.
    bot_username = getattr(app, "username", None)
    bot_name = getattr(app, "name", None) or bot_username or "Bot"
    safe_bot_name = html.escape(str(bot_name).strip(), quote=False)
    if bot_username:
        bot_mention = (
            f'<a href="https://t.me/{bot_username}">{safe_bot_name}</a>'
        )
    else:
        bot_mention = safe_bot_name

    return template.format(user_mention, bot_mention)


async def _send_start_photo_with_effect(message: Message, photo: str, caption: str, out):
    """Send the private /start panel through Bot API so the message effect works.

    Kurigram 2.2.25's high-level Message.reply_photo() does not expose
    message_effect_id, while Telegram's Bot API does. This helper keeps the
    existing Kurigram handler and keyboard flow, but sends only this one
    effect-bearing photo through the official Bot API endpoint.
    """
    keyboard = []
    for row in out:
        buttons = []
        for button in row:
            item = {"text": button.text}

            if button.url:
                item["url"] = button.url
            elif button.callback_data is not None:
                item["callback_data"] = button.callback_data
            elif button.user_id:
                item["url"] = f"tg://user?id={button.user_id}"
            else:
                continue

            style = getattr(button, "style", None)
            if style == ButtonStyle.PRIMARY:
                item["style"] = "primary"
            elif style == ButtonStyle.SUCCESS:
                item["style"] = "success"
            elif style == ButtonStyle.DANGER:
                item["style"] = "danger"

            buttons.append(item)

        if buttons:
            keyboard.append(buttons)

    payload = {
        "chat_id": message.chat.id,
        "photo": photo,
        "caption": caption,
        "parse_mode": "HTML",
        "has_spoiler": True,
        "message_effect_id": str(CELEBRATION_EFFECT_ID),
        "reply_markup": json.dumps({"inline_keyboard": keyboard}),
        "reply_parameters": json.dumps({"message_id": message.id}),
    }

    url = f"https://api.telegram.org/bot{config.BOT_TOKEN}/sendPhoto"
    timeout = aiohttp.ClientTimeout(total=30)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.post(url, data=payload) as response:
            result = await response.json(content_type=None)
            if response.status != 200 or not result.get("ok"):
                raise RuntimeError(f"Telegram Bot API sendPhoto failed: {result}")
            return result


@app.on_message(filters.command(["start"]) & filters.private & ~BANNED_USERS)
@LanguageStart
async def start_pm(client, message: Message, _):
    await add_served_user(message.from_user.id)
    await message.react("❤️", big=True)
    if len(message.text.split()) > 1:
        name = message.text.split(None, 1)[1]
        if name[0:4] == "help":
            keyboard = help_pannel(_)
            return await message.reply_photo(
                photo=random.choice(START_IMAGES),
                has_spoiler=True,
                caption=_["help_1"].format(config.SUPPORT_CHAT),
                reply_markup=keyboard,
            )
        if name[0:3] == "sud":
            await sudoers_list(client=client, message=message, _=_)
            if await is_on_off(2):
                return await app.send_message(
                    chat_id=config.LOGGER_ID,
                    text=f"{message.from_user.mention} ᴊᴜsᴛ sᴛᴀʀᴛᴇᴅ ᴛʜᴇ ʙᴏᴛ ᴛᴏ ᴄʜᴇᴄᴋ <b>sᴜᴅᴏʟɪsᴛ</b>.\n\n<b>ᴜsᴇʀ ɪᴅ :</b> <code>{message.from_user.id}</code>\n<b>ᴜsᴇʀɴᴀᴍᴇ :</b> @{message.from_user.username}",
                )
            return
        if name[0:3] == "inf":
            m = await message.reply_text("🔎")
            query = (str(name)).replace("info_", "", 1)
            query = f"https://www.youtube.com/watch?v={query}"
            results = VideosSearch(query, limit=1)
            for result in (await results.next())["result"]:
                title = result["title"]
                duration = result["duration"]
                views = result["viewCount"]["short"]
                thumbnail = result["thumbnails"][0]["url"].split("?")[0]
                channellink = result["channel"]["link"]
                channel = result["channel"]["name"]
                link = result["link"]
                published = result["publishedTime"]
            searched_text = _["start_6"].format(
                title, duration, views, published, channellink, channel, app.mention
            )
            key = InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            text=_["S_B_8"],
                            url=link,
                            style=ButtonStyle.SUCCESS,
                        ),
                        InlineKeyboardButton(
                            text=_["S_B_9"],
                            url=config.SUPPORT_CHAT,
                            style=ButtonStyle.SUCCESS,
                        ),
                    ],
                ]
            )
            await m.delete()
            await app.send_photo(
                chat_id=message.chat.id,
                photo=thumbnail,
                has_spoiler=True,
                caption=searched_text,
                reply_markup=key,
            )
            if await is_on_off(2):
                return await app.send_message(
                    chat_id=config.LOGGER_ID,
                    text=f"{message.from_user.mention} ᴊᴜsᴛ sᴛᴀʀᴛᴇᴅ ᴛʜᴇ ʙᴏᴛ ᴛᴏ ᴄʜᴇᴄᴋ <b>ᴛʀᴀᴄᴋ ɪɴғᴏʀᴍᴀᴛɪᴏɴ</b>.\n\n<b>ᴜsᴇʀ ɪᴅ :</b> <code>{message.from_user.id}</code>\n<b>ᴜsᴇʀɴᴀᴍᴇ :</b> @{message.from_user.username}",
                )
    else:
        out = private_panel(_)
        await _send_start_photo_with_effect(
            message=message,
            photo=random.choice(START_IMAGES),
            caption=_build_start_caption(message, _["start_2"]),
            out=out,
        )
        if await is_on_off(2):
            return await app.send_message(
                chat_id=config.LOGGER_ID,
                text=f"{message.from_user.mention} ᴊᴜsᴛ sᴛᴀʀᴛᴇᴅ ᴛʜᴇ ʙᴏᴛ.\n\n<b>ᴜsᴇʀ ɪᴅ :</b> <code>{message.from_user.id}</code>\n<b>ᴜsᴇʀɴᴀᴍᴇ :</b> @{message.from_user.username}",
            )


@app.on_message(filters.command(["start"]) & filters.group & ~BANNED_USERS)
@LanguageStart
async def start_gp(client, message: Message, _):
    out = start_panel(_)
    uptime = int(time.time() - _boot_)
    await message.reply_photo(
        photo=random.choice(START_IMAGES),
        has_spoiler=True,
        caption=_["start_1"].format(app.mention, get_readable_time(uptime)),
        reply_markup=InlineKeyboardMarkup(out),
    )
    return await add_served_chat(message.chat.id)


@app.on_message(filters.new_chat_members, group=-1)
async def welcome(client, message: Message):
    for member in message.new_chat_members:
        try:
            language = await get_lang(message.chat.id)
            _ = get_string(language)
            if await is_banned_user(member.id):
                try:
                    await message.chat.ban_member(member.id)
                except:
                    pass
            if member.id == app.id:
                if message.chat.type != ChatType.SUPERGROUP:
                    await message.reply_text(_["start_4"])
                    return await app.leave_chat(message.chat.id)
                if message.chat.id in await blacklisted_chats():
                    await message.reply_text(
                        _["start_5"].format(
                            app.mention,
                            f"https://t.me/{app.username}?start=sudolist",
                            config.SUPPORT_CHAT,
                        ),
                        disable_web_page_preview=True,
                    )
                    return await app.leave_chat(message.chat.id)

                out = start_panel(_)
                await message.reply_photo(
                    photo=random.choice(START_IMAGES),
                    has_spoiler=True,
                    caption=_["start_3"].format(
                        message.from_user.first_name,
                        app.mention,
                        message.chat.title,
                        app.mention,
                    ),
                    reply_markup=InlineKeyboardMarkup(out),
                )
                await add_served_chat(message.chat.id)
                userbot = await get_assistant(message.chat.id)
                myu = await message.reply_text(_["call_4"].format(app.mention))
                try:
                    try:
                        get = await app.get_chat_member(message.chat.id, userbot.id)
                    except ChatAdminRequired:
                        return
                    if (
                        get.status == ChatMemberStatus.BANNED
                        or get.status == ChatMemberStatus.RESTRICTED
                    ):
                        try:
                            await app.unban_chat_member(message.chat.id, userbot.id)
                        except:
                            return
                except:
                    pass

                if message.chat.username:
                    invitelink = message.chat.username
                    try:
                        await userbot.resolve_peer(invitelink)
                    except:
                        pass
                else:
                    try:
                        invitelink = await app.export_chat_invite_link(message.chat.id)
                    except:
                        return

                if invitelink.startswith("https://t.me/+"):
                    invitelink = invitelink.replace(
                        "https://t.me/+", "https://t.me/joinchat/"
                    )
                try:
                    await asyncio.sleep(1)
                    await userbot.join_chat(invitelink)
                    await myu.edit(_["call_5"].format(app.mention))
                except InviteRequestSent:
                    try:
                        await app.approve_chat_join_request(
                            message.chat.id, userbot.id
                        )
                    except:
                        return
                except UserAlreadyParticipant:
                    pass
                except:
                    return

                try:
                    await userbot.resolve_peer(message.chat.id)
                except:
                    pass

                await message.stop_propagation()
        except Exception as ex:
            print(ex)
