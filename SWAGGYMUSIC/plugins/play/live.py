#
# Copyright (C) 2021-2022 by TheAloneteam@Github, < https://github.com/TheAloneTeam >.
#
# This file is part of < https://github.com/TheAloneTeam/SWAGGYMUSIC > project,
# and is released under the "GNU v3.0 License Agreement".
# Please see < https://github.com/TheAloneTeam/SWAGGYMUSIC/blob/master/LICENSE >
#
# All rights reserved.

from pyrogram import filters
from pyrogram.types import InputMediaPhoto

import config
from SWAGGYMUSIC import YouTube, app
from SWAGGYMUSIC.utils.channelplay import get_channeplayCB
from SWAGGYMUSIC.utils.decorators.language import languageCB
from SWAGGYMUSIC.utils.stream.stream import stream
from config import BANNED_USERS


@app.on_callback_query(filters.regex("LiveStream") & ~BANNED_USERS)
@languageCB
async def play_live_stream(client, CallbackQuery, _):
    callback_data = CallbackQuery.data.strip()
    callback_request = callback_data.split(None, 1)[1]
    vidid, user_id, mode, cplay, fplay = callback_request.split("|")
    if CallbackQuery.from_user.id != int(user_id):
        try:
            return await CallbackQuery.answer(_["playcb_1"], show_alert=True)
        except:
            return
    try:
        chat_id, channel = await get_channeplayCB(_, cplay, CallbackQuery)
    except:
        return
    video = True if mode == "v" else None
    user_name = CallbackQuery.from_user.first_name
    try:
        await CallbackQuery.answer()
    except:
        pass

    from SWAGGYMUSIC.utils.database import is_thumb_on
    if await is_thumb_on(chat_id):
        try:
            mystic = await CallbackQuery.edit_message_media(
                media=InputMediaPhoto(
                    config.STREAM_IMG_URL,
                    caption=_["play_2"].format(channel) if channel else _["play_1"],
                ),
            )
        except Exception:
            mystic = await CallbackQuery.message.reply_photo(
                photo=config.STREAM_IMG_URL,
                caption=_["play_2"].format(channel) if channel else _["play_1"],
            )
    else:
        try:
            mystic = await CallbackQuery.edit_message_text(
                _["play_2"].format(channel) if channel else _["play_1"]
            )
        except Exception:
            mystic = await CallbackQuery.message.reply_text(
                _["play_2"].format(channel) if channel else _["play_1"]
            )
    try:
        details, track_id = await YouTube.track(vidid, True)
    except:
        try:
            return await mystic.edit_caption(_["play_3"])
        except:
            return await mystic.edit_text(_["play_3"])
    ffplay = True if fplay == "f" else None
    if not details["duration_min"]:
        try:
            await stream(
                _,
                mystic,
                user_id,
                details,
                chat_id,
                user_name,
                CallbackQuery.message.chat.id,
                video,
                streamtype="live",
                forceplay=ffplay,
            )
        except Exception as e:
            ex_type = type(e).__name__
            err = e if ex_type == "AssistantErr" else _["general_2"].format(ex_type)
            try:
                return await mystic.edit_caption(err)
            except:
                return await mystic.edit_text(err)
    else:
        try:
            return await mystic.edit_caption("» ɴᴏᴛ ᴀ ʟɪᴠᴇ sᴛʀᴇᴀᴍ.")
        except:
            return await mystic.edit_text("» ɴᴏᴛ ʌ ʟɪᴠє sᴛʀєʌϻ.")
