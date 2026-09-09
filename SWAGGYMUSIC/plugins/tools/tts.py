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
from SWAGGYMUSIC.utils.database import (get_tts_duration, get_tts_text,
                                       is_tts_on, set_tts_duration,
                                       set_tts_text, tts_off, tts_on)
from SWAGGYMUSIC.utils.decorators.language import language
from config import BANNED_USERS, OWNER_ID


@app.on_message(filters.command(["tts"]) & filters.user(OWNER_ID) & ~BANNED_USERS)
@language
async def tts_status(client, message: Message, _):
    if len(message.command) != 2:
        mode = await is_tts_on()
        current = _["ST_B_5"] if mode else _["ST_B_6"]
        return await message.reply_text(_["tts_1"].format(current))

    state = message.command[1].lower()
    if state == "on":
        await tts_on()
        await message.reply_text(_["tts_2"])
    elif state == "off":
        await tts_off()
        await message.reply_text(_["tts_3"])
    else:
        await message.reply_text(_["tts_4"])


@app.on_message(filters.command(["ttsdur"]) & filters.user(OWNER_ID) & ~BANNED_USERS)
@language
async def tts_duration(client, message: Message, _):
    if len(message.command) != 2:
        current = await get_tts_duration()
        return await message.reply_text(_["tts_5"].format(current))

    try:
        duration = int(message.command[1])
    except:
        return await message.reply_text(_["tts_6"])

    if duration < 1 or duration > 15:
        return await message.reply_text(_["tts_7"])

    await set_tts_duration(duration)
    await message.reply_text(_["tts_8"].format(duration))


@app.on_message(filters.command(["ttstxt"]) & filters.user(OWNER_ID) & ~BANNED_USERS)
@language
async def tts_message(client, message: Message, _):
    if len(message.command) < 2:
        current = await get_tts_text()
        return await message.reply_text(_["tts_9"].format(current))

    text = message.text.split(None, 1)[1]
    if len(text) > 100:
        return await message.reply_text(_["tts_10"])

    await set_tts_text(text)
    await message.reply_text(_["tts_11"].format(text))
