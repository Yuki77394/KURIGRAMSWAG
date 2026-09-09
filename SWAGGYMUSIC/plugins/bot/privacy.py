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
from SWAGGYMUSIC.utils.decorators.language import language
from config import BANNED_USERS, PRIVACY_LINK

@app.on_message(filters.command("privacy") & ~BANNED_USERS)
@language
async def privacy_policy(client, message: Message, _):
    buttons = [
        [
            InlineKeyboardButton(
                text=_["PRIVACY_BUTTON"],
                url=config.PRIVACY_LINK,
                style=ButtonStyle.PRIMARY,
            ),
        ],
    ]
    await message.reply_text(
        _["privacy_1"],
        reply_markup=InlineKeyboardMarkup(buttons),
    )
