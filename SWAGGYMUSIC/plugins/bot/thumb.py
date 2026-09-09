#
# Copyright (C) 2021-2022 by TheAloneteam@Github, < https://github.com/TheAloneTeam >.
#
# This file is part of < https://github.com/TheAloneTeam/SWAGGYMUSIC > project,
# and is released under the "GNU v3.0 License Agreement".
# Please see < https://github.com/TheAloneTeam/SWAGGYMUSIC/blob/master/LICENSE >
#
# All rights reserved.

from pyrogram import filters
from pyrogram.enums import ButtonStyle
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

from SWAGGYMUSIC import app
from SWAGGYMUSIC.utils.database import is_thumb_on
from SWAGGYMUSIC.utils.decorators import language
from config import BANNED_USERS


@app.on_message(filters.command(["thumb", "thumbnail"]) & filters.group & ~BANNED_USERS)
@language
async def thumb_command(client, message: Message, _):
    thumb_state = await is_thumb_on(message.chat.id)
    # Dynamic style: when thumb is OFF (button says "ENABLE") -> Green (SUCCESS);
    # when thumb is ON (button says "DISABLE") -> Blue (PRIMARY).
    buttons = [
        [
            InlineKeyboardButton(
                text="⌯ єɴʌʙʟє ⌯" if not thumb_state else "⌯ ᴅɪsʌʙʟє ⌯",
                callback_data=f"THUMBNAILCHANGE",
                style=ButtonStyle.SUCCESS if not thumb_state else ButtonStyle.PRIMARY,
            ),
        ],
        [
            InlineKeyboardButton(
                text="⌯ ᴄʟᴏsє ⌯",
                callback_data="close",
                style=ButtonStyle.DANGER,
            ),
        ],
    ]
    return await message.reply_text(
        _["thumb_1"],
        reply_markup=InlineKeyboardMarkup(buttons),
    )
