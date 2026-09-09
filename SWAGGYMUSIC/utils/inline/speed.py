#
# Copyright (C) 2021-2022 by TheAloneteam@Github, < https://github.com/TheAloneTeam >.
#
# This file is part of < https://github.com/TheAloneTeam/SWAGGYMUSIC > project,
# and is released under the "GNU v3.0 License Agreement".
# Please see < https://github.com/TheAloneTeam/SWAGGYMUSIC/blob/master/LICENSE >
#
# All rights reserved.

from pyrogram.enums import ButtonStyle
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def speed_markup(_, chat_id):
    upl = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    text="⌯ 🕒 0.5x ⌯",
                    callback_data=f"SpeedUP {chat_id}|0.5",
                    style=ButtonStyle.PRIMARY,
                ),
                InlineKeyboardButton(
                    text="⌯ 🕓 0.75x ⌯",
                    callback_data=f"SpeedUP {chat_id}|0.75",
                    style=ButtonStyle.PRIMARY,
                ),
            ],
            [
                InlineKeyboardButton(
                    text=_["P_B_4"],
                    callback_data=f"SpeedUP {chat_id}|1.0",
                    style=ButtonStyle.SUCCESS,
                ),
            ],
            [
                InlineKeyboardButton(
                    text="⌯ 🕤 1.5x ⌯",
                    callback_data=f"SpeedUP {chat_id}|1.5",
                    style=ButtonStyle.PRIMARY,
                ),
                InlineKeyboardButton(
                    text="⌯ 🕛 2.0x ⌯",
                    callback_data=f"SpeedUP {chat_id}|2.0",
                    style=ButtonStyle.PRIMARY,
                ),
            ],
            [
                InlineKeyboardButton(
                    text=_["CLOSE_BUTTON"],
                    callback_data="close",
                    style=ButtonStyle.DANGER,
                ),
            ],
        ]
    )
    return upl
