#
# Copyright (C) 2021-2022 by TheAloneteam@Github, < https://github.com/TheAloneTeam >.
#
# This file is part of < https://github.com/TheAloneTeam/SWAGGYMUSIC > project,
# and is released under the "GNU v3.0 License Agreement".
# Please see < https://github.com/TheAloneTeam/SWAGGYMUSIC/blob/master/LICENSE >
#
# All rights reserved.

from pyrogram import filters
from pyrogram.types import Message

from SWAGGYMUSIC import app
from SWAGGYMUSIC.core.call import Alone
from SWAGGYMUSIC.misc import db
from SWAGGYMUSIC.utils.decorators import AdminRightsCheck
from SWAGGYMUSIC.utils.inline import close_markup
from config import BANNED_USERS

@app.on_message(
    filters.command(["bass", "echo", "slowed", "nightcore", "normal"])
    & filters.group
    & ~BANNED_USERS
)
@AdminRightsCheck
async def apply_audio_filters(cli, message: Message, _, chat_id):
    playing = db.get(chat_id)
    if not playing:
        return await message.reply_text(_["queue_2"])

    duration_seconds = int(playing[0]["seconds"])
    if duration_seconds == 0:
        return await message.reply_text("» ʟɪᴠє sᴛʀєʌϻs ᴄʌɴ'ᴛ ʙє ғɪʟᴛєʀєᴅ.")

    file_path = playing[0]["file"]
    if "downloads" not in file_path:
        return await message.reply_text("» ᴏɴʟʏ ᴅᴏᴡɴʟᴏʌᴅєᴅ ᴛʀʌᴄᴋs ᴄʌɴ ʙє ғɪʟᴛєʀєᴅ.")

    command = message.command[0].lower()

    # Map command to filter type
    if command == "bass":
        filter_type = "bass"
    elif command == "echo":
        filter_type = "echo"
    elif command == "slowed":
        filter_type = "slowed"
    elif command == "nightcore":
        filter_type = "nightcore"
    else:
        filter_type = "normal"

    mystic = await message.reply_text(f"» ᴀᴘᴘʟʏɪɴɢ **{filter_type.upper()}** ғɪʟᴛᴇʀ...")

    try:
        await Alone.apply_filter(chat_id, file_path, filter_type, playing)
    except Exception as e:
        return await mystic.edit_text(f"» ғᴀɪʟᴇᴅ ᴛᴏ ᴀᴘᴘʟʏ ғɪʟᴛᴇʀ.\n\nᴇʀʀᴏʀ: {e}")

    await mystic.edit_text(
        text=f"➻ **{filter_type.upper()}** ғɪʟᴛᴇʀ ᴀᴘᴘʟɪᴇᴅ sᴜᴄᴄᴇssғᴜʟʟʏ 🎄\n│ \n└ʙʏ : {message.from_user.mention} 🥀",
        reply_markup=close_markup(_)
    )
