#
# Copyright (C) 2021-2022 by TheAloneteam@Github, < https://github.com/TheAloneTeam >.
#
# This file is part of < https://github.com/TheAloneTeam/SWAGGYMUSIC > project,
# and is released under the "GNU v3.0 License Agreement".
# Please see < https://github.com/TheAloneTeam/SWAGGYMUSIC/blob/master/LICENSE >
#
# All rights reserved.

# ─── Button color policy (per project-wide spec) ────────────────────────────
# The buttons below follow a consistent color convention:
#   - PRIMARY  (blue)   → primary/enable/info buttons (left column of sub-menus)
#   - SUCCESS  (green)  → toggle/confirmation buttons (right column of sub-menus)
#   - DANGER   (red)     → close / delete buttons
#
# These are applied ONLY to InlineKeyboardButton's `style=` attribute — the
# button text, callback_data, and layout are 100% unchanged from the original
# behaviour, so all existing callback handlers continue to work identically.

from typing import Union

from pyrogram.enums import ButtonStyle
from pyrogram.types import InlineKeyboardButton


def setting_markup(_):
    """Main settings panel — AUTO USERS, LANGUAGE, PLAY MODE, VOTING MODE, CLOSE.

    Color mapping (per spec rule 5):
      AUTO USERS    → Blue   (PRIMARY)
      LANGUAGE      → Blue   (PRIMARY)
      PLAY MODE     → Green  (SUCCESS)
      VOTING MODE   → Green  (SUCCESS)
      CLOSE (🗑)    → Red    (DANGER)
    """
    buttons = [
        [
            InlineKeyboardButton(
                text=_["ST_B_1"],
                callback_data="AU",
                style=ButtonStyle.PRIMARY,
            ),
            InlineKeyboardButton(
                text=_["ST_B_3"],
                callback_data="LG",
                style=ButtonStyle.PRIMARY,
            ),
        ],
        [
            InlineKeyboardButton(
                text=_["ST_B_2"],
                callback_data="PM",
                style=ButtonStyle.SUCCESS,
            ),
        ],
        [
            InlineKeyboardButton(
                text=_["ST_B_4"],
                callback_data="VM",
                style=ButtonStyle.SUCCESS,
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
    return buttons


def vote_mode_markup(_, current, mode: Union[bool, str] = None):
    """Voting-mode sub-menu — left column (info), right column (toggle),
    plus a BACK + CLOSE row.

    Color mapping (per spec rule 2):
      Left column (info / state labels)   → Blue   (PRIMARY)
      Right column (toggle buttons)       → Green  (SUCCESS)
      BACK (⟵)                           → Blue   (PRIMARY)
      CLOSE (🗑)                          → Red    (DANGER)
    """
    buttons = [
        [
            InlineKeyboardButton(
                text="⌯ ᴠᴏᴛɪɴɢ ϻᴏᴅє ➜ ⌯",
                callback_data="VOTEANSWER",
                style=ButtonStyle.PRIMARY,
            ),
            InlineKeyboardButton(
                text=_["ST_B_5"] if mode else _["ST_B_6"],
                callback_data="VOMODECHANGE",
                style=ButtonStyle.SUCCESS,
            ),
        ],
        [
            InlineKeyboardButton(
                text="⌯ -2 ⌯",
                callback_data="FERRARIUDTI M",
                style=ButtonStyle.PRIMARY,
            ),
            InlineKeyboardButton(
                text=f"⌯ ᴄᴜʀʀєɴᴛ : {current} ⌯",
                callback_data="ANSWERVOMODE",
                style=ButtonStyle.PRIMARY,
            ),
            InlineKeyboardButton(
                text="⌯ +2 ⌯",
                callback_data="FERRARIUDTI A",
                style=ButtonStyle.SUCCESS,
            ),
        ],
        [
            InlineKeyboardButton(
                text=_["BACK_BUTTON"],
                callback_data="settings_helper",
                style=ButtonStyle.PRIMARY,
            ),
            InlineKeyboardButton(
                text=_["CLOSE_BUTTON"],
                callback_data="close",
                style=ButtonStyle.DANGER,
            ),
        ],
    ]
    return buttons


def auth_users_markup(_, status: Union[bool, str] = None):
    """Authorized-users sub-menu — left column (info), right column (toggle),
    plus an AUTHLIST row and a BACK + CLOSE row.

    Color mapping (per spec rule 2):
      Left column (info / state labels)   → Blue   (PRIMARY)
      Right column (toggle buttons)        → Green  (SUCCESS)
      AUTHLIST row                        → Blue   (PRIMARY)
      BACK (⟵)                            → Blue   (PRIMARY)
      CLOSE (🗑)                           → Red    (DANGER)
    """
    buttons = [
        [
            InlineKeyboardButton(
                text=_["ST_B_7"],
                callback_data="AUTHANSWER",
                style=ButtonStyle.PRIMARY,
            ),
            InlineKeyboardButton(
                text=_["ST_B_8"] if status else _["ST_B_9"],
                callback_data="AUTH",
                style=ButtonStyle.SUCCESS,
            ),
        ],
        [
            InlineKeyboardButton(
                text=_["ST_B_1"],
                callback_data="AUTHLIST",
                style=ButtonStyle.PRIMARY,
            ),
        ],
        [
            InlineKeyboardButton(
                text=_["BACK_BUTTON"],
                callback_data="settings_helper",
                style=ButtonStyle.PRIMARY,
            ),
            InlineKeyboardButton(
                text=_["CLOSE_BUTTON"],
                callback_data="close",
                style=ButtonStyle.DANGER,
            ),
        ],
    ]
    return buttons


def playmode_users_markup(
    _,
    Direct: Union[bool, str] = None,
    Group: Union[bool, str] = None,
    Playtype: Union[bool, str] = None,
    Autoplay: Union[bool, str] = None,
    Thumbnail: Union[bool, str] = None,
):
    """Play-mode / autoplay / search-mode sub-menu — left column (info labels)
    and right column (toggle buttons), plus a BACK + CLOSE row.

    Color mapping (per spec rule 2):
      Left column (info / state labels)   → Blue   (PRIMARY)
      Right column (toggle buttons)        → Green  (SUCCESS)
      BACK (⟵)                            → Blue   (PRIMARY)
      CLOSE (🗑)                           → Red    (DANGER)
    """
    buttons = [
        [
            InlineKeyboardButton(
                text=_["ST_B_10"],
                callback_data="SEARCHANSWER",
                style=ButtonStyle.PRIMARY,
            ),
            InlineKeyboardButton(
                text=_["ST_B_11"] if Direct else _["ST_B_12"],
                callback_data="MODECHANGE",
                style=ButtonStyle.SUCCESS,
            ),
        ],
        [
            InlineKeyboardButton(
                text=_["ST_B_15"],
                callback_data="AUTOPLAYANSWER",
                style=ButtonStyle.PRIMARY,
            ),
            InlineKeyboardButton(
                text=_["ST_B_5"] if Autoplay else _["ST_B_6"],
                callback_data="AUTOPLAYCHANGE",
                style=ButtonStyle.SUCCESS,
            ),
        ],
        [
            InlineKeyboardButton(
                text=_["ST_B_13"],
                callback_data="AUTHANSWER",
                style=ButtonStyle.PRIMARY,
            ),
            InlineKeyboardButton(
                text=_["ST_B_8"] if Group else _["ST_B_9"],
                callback_data="CHANNELMODECHANGE",
                style=ButtonStyle.SUCCESS,
            ),
        ],
        [
            InlineKeyboardButton(
                text=_["ST_B_14"],
                callback_data="PLAYTYPEANSWER",
                style=ButtonStyle.PRIMARY,
            ),
            InlineKeyboardButton(
                text=_["ST_B_8"] if Playtype else _["ST_B_9"],
                callback_data="PLAYTYPECHANGE",
                style=ButtonStyle.SUCCESS,
            ),
        ],
        [
            InlineKeyboardButton(
                text=_["ST_B_16"],
                callback_data="THUMBNAILANSWER",
                style=ButtonStyle.PRIMARY,
            ),
            InlineKeyboardButton(
                text=_["ST_B_5"] if Thumbnail else _["ST_B_6"],
                callback_data="THUMBNAILCHANGE",
                style=ButtonStyle.SUCCESS,
            ),
        ],
        [
            InlineKeyboardButton(
                text=_["BACK_BUTTON"],
                callback_data="settings_helper",
                style=ButtonStyle.PRIMARY,
            ),
            InlineKeyboardButton(
                text=_["CLOSE_BUTTON"],
                callback_data="close",
                style=ButtonStyle.DANGER,
            ),
        ],
    ]
    return buttons
