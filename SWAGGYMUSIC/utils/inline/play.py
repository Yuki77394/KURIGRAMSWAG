#
# Copyright (C) 2021-2022 by TheAloneteam@Github, < https://github.com/TheAloneTeam >.
#
# This file is part of < https://github.com/TheAloneTeam/SWAGGYMUSIC > project,
# and is released under the "GNU v3.0 License Agreement".
# Please see < https://github.com/TheAloneTeam/SWAGGYMUSIC/blob/master/LICENSE >
#
# All rights reserved.

import math
from typing import Union

from pyrogram.enums import ButtonStyle
from pyrogram.types import InlineKeyboardButton

from SWAGGYMUSIC import app
from SWAGGYMUSIC.utils.formatters import time_to_seconds


def track_markup(_, videoid, user_id, channel, fplay, thumb: Union[bool, str] = None):
    buttons = [
        [
            InlineKeyboardButton(
                text="🎵",
                callback_data=f"MusicStream {videoid}|{user_id}|a|{channel}|{fplay}",
                style=ButtonStyle.PRIMARY,
            ),
            InlineKeyboardButton(
                text="🎥",
                callback_data=f"MusicStream {videoid}|{user_id}|v|{channel}|{fplay}",
                style=ButtonStyle.PRIMARY,
            ),
        ],
        [
            InlineKeyboardButton(
                text="⎘",
                callback_data=f"MusicThumb {videoid}|{user_id}|{channel}|{fplay}",
                style=ButtonStyle.SUCCESS,
            ),
            InlineKeyboardButton(
                text="⌯✖",
                callback_data=f"forceclose {videoid}|{user_id}",
                style=ButtonStyle.DANGER,
            ),
        ],
    ]
    return buttons


def stream_markup_timer(
    _,
    chat_id,
    played,
    dur,
    autoplay: Union[bool, str] = None,
    thumb: Union[bool, str] = None,
    chat_filter: Union[bool, str] = None,
    more: bool = False,
):
    played_sec = time_to_seconds(played)
    duration_sec = time_to_seconds(dur)

    remaining_sec = duration_sec - played_sec

    if remaining_sec < 0:
        remaining_sec = 0

    rem_min = remaining_sec // 60
    rem_sec = remaining_sec % 60
    remaining = f"{rem_min:02d}:{rem_sec:02d}"

    percentage = (
        (played_sec / duration_sec) * 100
        if duration_sec
        else 0
    )

    umm = math.floor(percentage)

    if 0 < umm <= 10:
        bar = "|♬—————————|"
    elif 10 < umm < 20:
        bar = "|—♬————————|"
    elif 20 <= umm < 30:
        bar = "|——♬———————|"
    elif 30 <= umm < 40:
        bar = "|———♬——————|"
    elif 40 <= umm < 50:
        bar = "|————♬—————|"
    elif 50 <= umm < 60:
        bar = "|—————♬————|"
    elif 60 <= umm < 70:
        bar = "|——————♬———|"
    elif 70 <= umm < 80:
        bar = "|———————♬——|"
    elif 80 <= umm < 95:
        bar = "|————————♬—|"
    else:
        bar = "|—————————♬|"

    if not more:
        buttons = [
            [
                InlineKeyboardButton(
                    text="▷",
                    callback_data=f"ADMIN Resume|{chat_id}",
                    style=ButtonStyle.PRIMARY,
                ),
                InlineKeyboardButton(
                    text="II",
                    callback_data=f"ADMIN Pause|{chat_id}",
                    style=ButtonStyle.PRIMARY,
                ),
                InlineKeyboardButton(
                    text="‣‣I",
                    callback_data=f"ADMIN Skip|{chat_id}",
                    style=ButtonStyle.PRIMARY,
                ),
                InlineKeyboardButton(
                    text="↻",
                    callback_data=f"ADMIN Replay|{chat_id}",
                    style=ButtonStyle.PRIMARY,
                ),
                InlineKeyboardButton(
                    text="▢",
                    callback_data=f"ADMIN Stop|{chat_id}",
                    style=ButtonStyle.PRIMARY,
                ),
            ],
            [
                InlineKeyboardButton(
                    text="☰ ᴍᴏʀᴇ",
                    callback_data=f"ADMIN More|{chat_id}",
                    style=ButtonStyle.SUCCESS,
                ),
                InlineKeyboardButton(
                    text="🗑",
                    callback_data="close",
                    style=ButtonStyle.DANGER,
                ),
            ],
        ]

    else:

        buttons = [
            [
                InlineKeyboardButton(
                    text="▷",
                    callback_data=f"ADMIN Resume|{chat_id}",
                    style=ButtonStyle.PRIMARY,
                ),
                InlineKeyboardButton(
                    text="II",
                    callback_data=f"ADMIN Pause|{chat_id}",
                    style=ButtonStyle.PRIMARY,
                ),
                InlineKeyboardButton(
                    text="‣‣I",
                    callback_data=f"ADMIN Skip|{chat_id}",
                    style=ButtonStyle.PRIMARY,
                ),
                InlineKeyboardButton(
                    text="↻",
                    callback_data=f"ADMIN Replay|{chat_id}",
                    style=ButtonStyle.PRIMARY,
                ),
                InlineKeyboardButton(
                    text="▢",
                    callback_data=f"ADMIN Stop|{chat_id}",
                    style=ButtonStyle.PRIMARY,
                ),
            ],
            [
                InlineKeyboardButton(
                    text="Autoplay",
                    callback_data=f"ADMIN Autoplay|{chat_id}",
                    style=ButtonStyle.PRIMARY,
                ),
                InlineKeyboardButton(
                    text="Thumb",
                    callback_data=f"ADMIN Thumb|{chat_id}",
                    style=ButtonStyle.PRIMARY,
                ),
            ],
            [
                InlineKeyboardButton(
                    text="⟵ ʙᴀᴄᴋ",
                    callback_data=f"ADMIN Back|{chat_id}",
                    style=ButtonStyle.SUCCESS,
                ),
                InlineKeyboardButton(
                    text="🗑",
                    callback_data="close",
                    style=ButtonStyle.DANGER,
                ),
            ],
        ]

    return buttons


def stream_markup(
    _,
    chat_id,
    autoplay: Union[bool, str] = None,
    thumb: Union[bool, str] = None,
    chat_filter: Union[bool, str] = None,
    more: bool = False,
):
    if not more:
        buttons = [
            [
                InlineKeyboardButton(
                    text="▷",
                    callback_data=f"ADMIN Resume|{chat_id}",
                    style=ButtonStyle.PRIMARY,
                ),
                InlineKeyboardButton(
                    text="II",
                    callback_data=f"ADMIN Pause|{chat_id}",
                    style=ButtonStyle.PRIMARY,
                ),
                InlineKeyboardButton(
                    text="‣‣I",
                    callback_data=f"ADMIN Skip|{chat_id}",
                    style=ButtonStyle.PRIMARY,
                ),
                InlineKeyboardButton(
                    text="↻",
                    callback_data=f"ADMIN Replay|{chat_id}",
                    style=ButtonStyle.PRIMARY,
                ),
                InlineKeyboardButton(
                    text="▢",
                    callback_data=f"ADMIN Stop|{chat_id}",
                    style=ButtonStyle.PRIMARY,
                ),
            ],
            [
                InlineKeyboardButton(
                    text="☰ ᴍᴏʀᴇ",
                    callback_data=f"ADMIN More|{chat_id}",
                    style=ButtonStyle.SUCCESS,
                ),
                InlineKeyboardButton(
                    text="🗑",
                    callback_data="close",
                    style=ButtonStyle.DANGER,
                ),
            ],
        ]

    else:

        buttons = [
            [
                InlineKeyboardButton(
                    text="▷",
                    callback_data=f"ADMIN Resume|{chat_id}",
                    style=ButtonStyle.PRIMARY,
                ),
                InlineKeyboardButton(
                    text="II",
                    callback_data=f"ADMIN Pause|{chat_id}",
                    style=ButtonStyle.PRIMARY,
                ),
                InlineKeyboardButton(
                    text="‣‣I",
                    callback_data=f"ADMIN Skip|{chat_id}",
                    style=ButtonStyle.PRIMARY,
                ),
                InlineKeyboardButton(
                    text="↻",
                    callback_data=f"ADMIN Replay|{chat_id}",
                    style=ButtonStyle.PRIMARY,
                ),
                InlineKeyboardButton(
                    text="▢",
                    callback_data=f"ADMIN Stop|{chat_id}",
                    style=ButtonStyle.PRIMARY,
                ),
            ],
            [
                InlineKeyboardButton(
                    text="♫",
                    callback_data=f"ADMIN Autoplay|{chat_id}",
                    style=ButtonStyle.PRIMARY,
                ),
                InlineKeyboardButton(
                    text="⎘",
                    callback_data=f"ADMIN Thumb|{chat_id}",
                    style=ButtonStyle.PRIMARY,
                ),
            ],
            [
                InlineKeyboardButton(
                    text="⟵ ʙᴀᴄᴋ",
                    callback_data=f"ADMIN Back|{chat_id}",
                    style=ButtonStyle.SUCCESS,
                ),
                InlineKeyboardButton(
                    text="🗑",
                    callback_data="close",
                    style=ButtonStyle.DANGER,
                ),
            ],
        ]

    return buttons


def playlist_markup(
    _,
    videoid,
    user_id,
    ptype,
    channel,
    fplay,
    thumb: Union[bool, str] = None,
):
    buttons = [
        [
            InlineKeyboardButton(
                text="🎵",
                callback_data=(
                    f"AlonePlaylists "
                    f"{videoid}|{user_id}|{ptype}|a|{channel}|{fplay}"
                ),
                style=ButtonStyle.PRIMARY,
            ),
            InlineKeyboardButton(
                text="🎥",
                callback_data=(
                    f"AlonePlaylists "
                    f"{videoid}|{user_id}|{ptype}|v|{channel}|{fplay}"
                ),
                style=ButtonStyle.PRIMARY,
            ),
        ],
        [
            InlineKeyboardButton(
                text="⎘",
                callback_data=(
                    f"PlaylistThumb "
                    f"{videoid}|{user_id}|{ptype}|{channel}|{fplay}"
                ),
                style=ButtonStyle.SUCCESS,
            ),
            InlineKeyboardButton(
                text="✖",
                callback_data=f"forceclose {videoid}|{user_id}",
                style=ButtonStyle.DANGER,
            ),
        ],
    ]

    return buttons


def livestream_markup(
    _,
    videoid,
    user_id,
    mode,
    channel,
    fplay,
    thumb: Union[bool, str] = None,
):
    buttons = [
        [
            InlineKeyboardButton(
                text="🎬",
                callback_data=(
                    f"LiveStream "
                    f"{videoid}|{user_id}|{mode}|{channel}|{fplay}"
                ),
                style=ButtonStyle.PRIMARY,
            ),
        ],
        [
            InlineKeyboardButton(
                text="⎘",
                callback_data=(
                    f"LiveThumb "
                    f"{videoid}|{user_id}|{mode}|{channel}|{fplay}"
                ),
                style=ButtonStyle.SUCCESS,
            ),
            InlineKeyboardButton(
                text="✖",
                callback_data=f"forceclose {videoid}|{user_id}",
                style=ButtonStyle.DANGER,
            ),
        ],
    ]

    return buttons


def slider_markup(
    _,
    videoid,
    user_id,
    query,
    query_type,
    channel,
    fplay,
    thumb: Union[bool, str] = None,
):
    query = f"{query[:20]}"

    buttons = [
        [
            InlineKeyboardButton(
                text="🎵",
                callback_data=(
                    f"MusicStream "
                    f"{videoid}|{user_id}|a|{channel}|{fplay}"
                ),
                style=ButtonStyle.PRIMARY,
            ),
            InlineKeyboardButton(
                text="🎥",
                callback_data=(
                    f"MusicStream "
                    f"{videoid}|{user_id}|v|{channel}|{fplay}"
                ),
                style=ButtonStyle.PRIMARY,
            ),
        ],
        [
            InlineKeyboardButton(
                text="◁",
                callback_data=(
                    f"slider B|{query_type}|{query}|"
                    f"{user_id}|{channel}|{fplay}"
                ),
                style=ButtonStyle.SUCCESS,
            ),
            InlineKeyboardButton(
                text="⎘",
                callback_data=(
                    f"SliderThumb "
                    f"{videoid}|{user_id}|{query}|{query_type}|"
                    f"{channel}|{fplay}"
                ),
                style=ButtonStyle.SUCCESS,
            ),
            InlineKeyboardButton(
                text="▷",
                callback_data=(
                    f"slider F|{query_type}|{query}|"
                    f"{user_id}|{channel}|{fplay}"
                ),
                style=ButtonStyle.SUCCESS,
            ),
        ],
        [
            InlineKeyboardButton(
                text="✖",
                callback_data=f"forceclose {query}|{user_id}",
                style=ButtonStyle.DANGER,
            ),
        ],
    ]

    return buttons
    
