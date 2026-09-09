#
# Copyright (C) 2021-2022 by TheAloneteam@Github, < https://github.com/TheAloneTeam >.
#
# This file is part of < https://github.com/TheAloneTeam/SWAGGYMUSIC > project,
# and is released under the "GNU v3.0 License Agreement".
# Please see < https://github.com/TheAloneTeam/SWAGGYMUSIC/blob/master/LICENSE >
#
# All rights reserved.
from time import time

from pyrogram import filters
from pyrogram.enums import ButtonStyle, ChatType
from pyrogram.errors import MessageNotModified
from pyrogram.types import (CallbackQuery, InlineKeyboardButton,InputMediaVideo,
                            InlineKeyboardMarkup, Message)

import config
from SWAGGYMUSIC import app
from SWAGGYMUSIC.utils.database import (add_nonadmin_chat, autoplay_off,
                                       autoplay_on, get_authuser,
                                       get_authuser_names, get_playmode,
                                       get_playtype, get_upvote_count,
                                       is_autoplay_on, is_nonadmin_chat,
                                       is_skipmode, is_thumb_on,
                                       remove_nonadmin_chat, set_playmode,
                                       set_playtype, set_upvotes, skip_off,
                                       skip_on, thumb_off, thumb_on)
from SWAGGYMUSIC.utils.decorators.admins import ActualAdminCB
from SWAGGYMUSIC.utils.decorators.language import language, languageCB
from SWAGGYMUSIC.utils.inline.settings import (auth_users_markup,
                                              playmode_users_markup,
                                              setting_markup, vote_mode_markup)
from SWAGGYMUSIC.utils.inline.start import private_panel
from config import BANNED_USERS, OWNER_ID


@app.on_message(
    filters.command(["settings", "setting"]) & filters.group & ~BANNED_USERS
)
@language
async def settings_mar(client, message: Message, _):
    buttons = setting_markup(_)
    await message.reply_text(
        _["setting_1"].format(app.mention, message.chat.id, message.chat.title),
        reply_markup=InlineKeyboardMarkup(buttons),
    )


@app.on_callback_query(filters.regex("gib_source"))
async def gib_repo_callback(_, callback_query):
    await callback_query.edit_message_media(
        media=InputMediaVideo(
            "https://telegra.ph/file/b1367262cdfbcd0b2af07.mp4",
            has_spoiler=True,
            caption=(
                "🎵 SWAGGYMUSIC Source Code🎵\n"
                "✨ Fast • Powerful • Smooth Music Bot\n"
                "➠ Play songs from YouTube instantly\n"
                "➠ High-quality audio & video streaming\n"
                "➠ Queue system with controls\n"
                "➠ 24/7 non-stop music in VC\n"
                "🚀 Fork the repo and deploy your own bot now!"
            ),
        ),
        reply_markup=InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        text="⌯ ғᴏʀᴋ ʀᴇᴘᴏ ⌯",
                        url="https://t.me/hot_dpz_stor",
                        style=ButtonStyle.PRIMARY,
                    ),
                    InlineKeyboardButton(
                        text="⌯ 💌 ʏᴛ-ʌᴘɪ ⌯",
                        callback_data="bot_info_data",
                        style=ButtonStyle.SUCCESS,
                    ),
                ],
                [
                    InlineKeyboardButton(
                        text="• ʙᴀᴄᴋ •",
                        callback_data="settingsback_helper",
                        style=ButtonStyle.PRIMARY,
                    ),
                    InlineKeyboardButton(
                        text="• ᴄʟᴏsᴇ •",
                        callback_data="close",
                        style=ButtonStyle.DANGER,
                    )
                ]
            ]
        ),
    )

@app.on_callback_query(filters.regex("settings_helper") & ~BANNED_USERS)
@languageCB
async def settings_cb(client, CallbackQuery, _):
    try:
        await CallbackQuery.answer(_["set_cb_5"])
    except:
        pass
    buttons = setting_markup(_)
    return await CallbackQuery.edit_message_text(
        _["setting_1"].format(
            app.mention,
            CallbackQuery.message.chat.id,
            CallbackQuery.message.chat.title,
        ),
        reply_markup=InlineKeyboardMarkup(buttons),
    )


@app.on_callback_query(filters.regex("^bot_info_data$"))
async def show_bot_info(c: app, q: CallbackQuery):
    start = time()
    x = await c.send_message(q.message.chat.id, "ᴘɪɴɢ ᴘᴏɴɢ 💕..")
    delta_ping = time() - start
    await x.delete()
    txt = f"""💌 ᴘɪɴɢ ᴘᴏɴɢ ʙᴀʙʏ...

• ᴅᴀᴛᴀʙᴀsᴇ: ᴏɴʟɪɴᴇ
• ʏᴏᴜᴛᴜʙᴇ ᴀᴘɪ: ʀᴇsᴘᴏɴsɪᴠᴇ
• ʙᴏᴛ sᴇʀᴠᴇʀ: ʀᴜɴɴɪɴɢ sᴍᴏᴏᴛʜʟʏ
• ʀᴇsᴘᴏɴsᴇ ᴛɪᴍᴇ: ᴏᴘᴛɪᴍᴀʟ
• ᴀᴘɪ ᴘɪɴɢ: {delta_ping * 1000:.3f} ms   

• ᴇᴠᴇʀʏᴛʜɪɴɢ ʟᴏᴏᴋs ɢᴏᴏᴅ!
"""
    await q.answer(txt, show_alert=True)
    return


@app.on_callback_query(filters.regex("^SWAGGY_MUSIC$") & ~BANNED_USERS)
@languageCB
async def support(client, CallbackQuery, _):
    await CallbackQuery.edit_message_text(
        text=(
            "🎵 Welcome to SWAGGYMUSIC 🎵\n"
            "✨ Fast • Powerful • Smooth Music Experience\n"
            "➠ Play songs from YouTube instantly\n"
            "➠ High-quality audio & video streaming\n"
            "➠ Queue system with controls\n"
            "➠ 24/7 non-stop music in VC\n"
            "💡 Just send /play or .play and enjoy your favorite music anytime\n"
            "🚀 Made for speed, built for performance"
        ),
        reply_markup=InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        text="⌯ ᴏᴡɴᴇʀ ⌯",
                        user_id=config.OWNER_ID,
                        style=ButtonStyle.SUCCESS,
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="⌯ ʙᴀᴄᴋ ⌯",
                        callback_data="settingsback_helper",
                        style=ButtonStyle.PRIMARY,
                    )
                ],
            ]
        ),
        disable_web_page_preview=True
  )


@app.on_callback_query(filters.regex("settingsback_helper") & ~BANNED_USERS)
@languageCB
async def settings_back_markup(client, CallbackQuery: CallbackQuery, _):
    try:
        await CallbackQuery.answer()
    except:
        pass
    if CallbackQuery.message.chat.type == ChatType.PRIVATE:
        await app.resolve_peer(OWNER_ID)
        buttons = private_panel(_)
        return await CallbackQuery.edit_message_text(
            _["start_2"].format(CallbackQuery.from_user.mention, app.mention),
            reply_markup=InlineKeyboardMarkup(buttons),
        )
    else:
        buttons = setting_markup(_)
        return await CallbackQuery.edit_message_reply_markup(
            reply_markup=InlineKeyboardMarkup(buttons)
        )


@app.on_callback_query(
    filters.regex(
        pattern=r"^(SEARCHANSWER|PLAYMODEANSWER|PLAYTYPEANSWER|AUTOPLAYANSWER|THUMBNAILANSWER|AUTHANSWER|ANSWERVOMODE|VOTEANSWER|PM|AU|VM)$"
    )
    & ~BANNED_USERS
)
@languageCB
async def without_Admin_rights(client, CallbackQuery, _):
    command = CallbackQuery.matches[0].group(1)
    if command == "SEARCHANSWER":
        try:
            return await CallbackQuery.answer(_["setting_2"], show_alert=True)
        except:
            return
    if command == "PLAYMODEANSWER":
        try:
            return await CallbackQuery.answer(_["setting_5"], show_alert=True)
        except:
            return
    if command == "PLAYTYPEANSWER":
        try:
            return await CallbackQuery.answer(_["setting_6"], show_alert=True)
        except:
            return
    if command == "AUTHANSWER":
        try:
            return await CallbackQuery.answer(_["setting_3"], show_alert=True)
        except:
            return
    if command == "VOTEANSWER":
        try:
            return await CallbackQuery.answer(
                _["setting_8"],
                show_alert=True,
            )
        except:
            return
    if command == "THUMBNAILANSWER":
        try:
            return await CallbackQuery.answer("» ᴛᴏɢɢʟє ʌʟʙᴜϻ ʌʀᴛ ᴅɪsᴘʟʌʏ. ᴅɪsʌʙʟɪɴɢ ɪᴛ ʀєᴅᴜᴄєs ᴅʌᴛʌ ʟᴏʌᴅ ʌɴᴅ ϻʌɪɴᴛʌɪɴs ʌ ϻɪɴɪϻʌʟɪsᴛ ᴄʜʌᴛ ʟᴏᴏᴋ.",
                show_alert=True,
            )
        except:
            return
    if command == "AUTOPLAYANSWER":
        try:
            return await CallbackQuery.answer("» ᴡʜєɴ єɴʌʙʟєᴅ, ᴛʜє ʙᴏᴛ ᴡɪʟʟ ʌᴜᴛᴏϻʌᴛɪᴄʌʟʟʏ ᴘʟʌʏ ʀєʟʌᴛєᴅ sᴏɴɢs ᴡʜєɴ ᴛʜє ǫᴜєᴜє ɪs єϻᴘᴛʏ.",
                show_alert=True,
            )
        except:
            return
    if command == "ANSWERVOMODE":
        current = await get_upvote_count(CallbackQuery.message.chat.id)
        try:
            return await CallbackQuery.answer(
                _["setting_9"].format(current),
                show_alert=True,
            )
        except:
            return
    if command == "PM":
        try:
            await CallbackQuery.answer(_["set_cb_2"], show_alert=True)
        except:
            pass
        playmode = await get_playmode(CallbackQuery.message.chat.id)
        if playmode == "Direct":
            Direct = True
        else:
            Direct = None
        is_non_admin = await is_nonadmin_chat(CallbackQuery.message.chat.id)
        if not is_non_admin:
            Group = True
        else:
            Group = None
        playty = await get_playtype(CallbackQuery.message.chat.id)
        if playty == "Everyone":
            Playtype = None
        else:
            Playtype = True
        Autoplay = await is_autoplay_on(CallbackQuery.message.chat.id)
        Thumbnail = await is_thumb_on(CallbackQuery.message.chat.id)
        buttons = playmode_users_markup(_, Direct, Group, Playtype, Autoplay, Thumbnail)
    if command == "AU":
        try:
            await CallbackQuery.answer(_["set_cb_1"], show_alert=True)
        except:
            pass
        is_non_admin = await is_nonadmin_chat(CallbackQuery.message.chat.id)
        if not is_non_admin:
            buttons = auth_users_markup(_, True)
        else:
            buttons = auth_users_markup(_)
    if command == "VM":
        mode = await is_skipmode(CallbackQuery.message.chat.id)
        current = await get_upvote_count(CallbackQuery.message.chat.id)
        buttons = vote_mode_markup(_, current, mode)
    try:
        return await CallbackQuery.edit_message_reply_markup(
            reply_markup=InlineKeyboardMarkup(buttons)
        )
    except MessageNotModified:
        return


@app.on_callback_query(filters.regex("FERRARIUDTI") & ~BANNED_USERS)
@ActualAdminCB
async def addition(client, CallbackQuery, _):
    callback_data = CallbackQuery.data.strip()
    mode = callback_data.split(None, 1)[1]
    if not await is_skipmode(CallbackQuery.message.chat.id):
        return await CallbackQuery.answer(_["setting_10"], show_alert=True)
    current = await get_upvote_count(CallbackQuery.message.chat.id)
    if mode == "M":
        final = current - 2
        print(final)
        if final == 0:
            return await CallbackQuery.answer(
                _["setting_11"],
                show_alert=True,
            )
        if final <= 2:
            final = 2
        await set_upvotes(CallbackQuery.message.chat.id, final)
    else:
        final = current + 2
        print(final)
        if final == 17:
            return await CallbackQuery.answer(
                _["setting_12"],
                show_alert=True,
            )
        if final >= 15:
            final = 15
        await set_upvotes(CallbackQuery.message.chat.id, final)
    buttons = vote_mode_markup(_, final, True)
    try:
        return await CallbackQuery.edit_message_reply_markup(
            reply_markup=InlineKeyboardMarkup(buttons)
        )
    except MessageNotModified:
        return


@app.on_callback_query(
    filters.regex(pattern=r"^(MODECHANGE|CHANNELMODECHANGE|PLAYTYPECHANGE|AUTOPLAYCHANGE|THUMBNAILCHANGE)$")
    & ~BANNED_USERS
)
@ActualAdminCB
async def playmode_ans(client, CallbackQuery, _):
    command = CallbackQuery.matches[0].group(1)
    if command == "CHANNELMODECHANGE":
        is_non_admin = await is_nonadmin_chat(CallbackQuery.message.chat.id)
        if not is_non_admin:
            await add_nonadmin_chat(CallbackQuery.message.chat.id)
        else:
            await remove_nonadmin_chat(CallbackQuery.message.chat.id)
    elif command == "MODECHANGE":
        try:
            await CallbackQuery.answer(_["set_cb_3"], show_alert=True)
        except:
            pass
        playmode = await get_playmode(CallbackQuery.message.chat.id)
        if playmode == "Direct":
            await set_playmode(CallbackQuery.message.chat.id, "Inline")
        else:
            await set_playmode(CallbackQuery.message.chat.id, "Direct")
    elif command == "PLAYTYPECHANGE":
        try:
            await CallbackQuery.answer(_["set_cb_3"], show_alert=True)
        except:
            pass
        playty = await get_playtype(CallbackQuery.message.chat.id)
        if playty == "Everyone":
            await set_playtype(CallbackQuery.message.chat.id, "Admin")
        else:
            await set_playtype(CallbackQuery.message.chat.id, "Everyone")
    elif command == "AUTOPLAYCHANGE":
        try:
            await CallbackQuery.answer(_["set_cb_3"], show_alert=True)
        except:
            pass
        if await is_autoplay_on(CallbackQuery.message.chat.id):
            await autoplay_off(CallbackQuery.message.chat.id)
        else:
            await autoplay_on(CallbackQuery.message.chat.id)
    elif command == "THUMBNAILCHANGE":
        try:
            await CallbackQuery.answer(_["set_cb_3"], show_alert=True)
        except:
            pass
        if await is_thumb_on(CallbackQuery.message.chat.id):
            await thumb_off(CallbackQuery.message.chat.id)
        else:
            await thumb_on(CallbackQuery.message.chat.id)

    # Fetch updated states
    playmode = await get_playmode(CallbackQuery.message.chat.id)
    Direct = True if playmode == "Direct" else None
    is_non_admin = await is_nonadmin_chat(CallbackQuery.message.chat.id)
    Group = True if not is_non_admin else None
    playty = await get_playtype(CallbackQuery.message.chat.id)
    Playtype = None if playty == "Everyone" else True
    Autoplay = await is_autoplay_on(CallbackQuery.message.chat.id)
    Thumbnail = await is_thumb_on(CallbackQuery.message.chat.id)

    buttons = playmode_users_markup(_, Direct, Group, Playtype, Autoplay, Thumbnail)
    try:
        return await CallbackQuery.edit_message_reply_markup(
            reply_markup=InlineKeyboardMarkup(buttons)
        )
    except MessageNotModified:
        return


@app.on_callback_query(filters.regex(pattern=r"^(AUTH|AUTHLIST)$") & ~BANNED_USERS)
@ActualAdminCB
async def authusers_mar(client, CallbackQuery, _):
    command = CallbackQuery.matches[0].group(1)
    if command == "AUTHLIST":
        _authusers = await get_authuser_names(CallbackQuery.message.chat.id)
        if not _authusers:
            try:
                return await CallbackQuery.answer(_["setting_4"], show_alert=True)
            except:
                return
        else:
            try:
                await CallbackQuery.answer(_["set_cb_4"], show_alert=True)
            except:
                pass
            j = 0
            await CallbackQuery.edit_message_text(_["auth_6"])
            msg = _["auth_7"].format(CallbackQuery.message.chat.title)
            for note in _authusers:
                _note = await get_authuser(CallbackQuery.message.chat.id, note)
                user_id = _note["auth_user_id"]
                admin_id = _note["admin_id"]
                admin_name = _note["admin_name"]
                try:
                    user = await app.get_users(user_id)
                    user = user.first_name
                    j += 1
                except:
                    continue
                msg += f"{j}➤ {user}[<code>{user_id}</code>]\n"
                msg += f"   {_['auth_8']} {admin_name}[<code>{admin_id}</code>]\n\n"
            upl = InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            text=_["BACK_BUTTON"],
                            callback_data="AU",
                            style=ButtonStyle.PRIMARY,
                        ),
                        InlineKeyboardButton(
                            text=_["CLOSE_BUTTON"],
                            callback_data="close",
                            style=ButtonStyle.DANGER,
                        ),
                    ]
                ]
            )
            try:
                return await CallbackQuery.edit_message_text(msg, reply_markup=upl)
            except MessageNotModified:
                return
    try:
        await CallbackQuery.answer(_["set_cb_3"], show_alert=True)
    except:
        pass
    if command == "AUTH":
        is_non_admin = await is_nonadmin_chat(CallbackQuery.message.chat.id)
        if not is_non_admin:
            await add_nonadmin_chat(CallbackQuery.message.chat.id)
            buttons = auth_users_markup(_)
        else:
            await remove_nonadmin_chat(CallbackQuery.message.chat.id)
            buttons = auth_users_markup(_, True)
    try:
        return await CallbackQuery.edit_message_reply_markup(
            reply_markup=InlineKeyboardMarkup(buttons)
        )
    except MessageNotModified:
        return


@app.on_callback_query(filters.regex("VOMODECHANGE") & ~BANNED_USERS)
@ActualAdminCB
async def vote_change(client, CallbackQuery, _):
    CallbackQuery.matches[0].group(1)
    try:
        await CallbackQuery.answer(_["set_cb_3"], show_alert=True)
    except:
        pass
    mod = None
    if await is_skipmode(CallbackQuery.message.chat.id):
        await skip_off(CallbackQuery.message.chat.id)
    else:
        mod = True
        await skip_on(CallbackQuery.message.chat.id)
    current = await get_upvote_count(CallbackQuery.message.chat.id)
    buttons = vote_mode_markup(_, current, mod)

    try:
        return await CallbackQuery.edit_message_reply_markup(
            reply_markup=InlineKeyboardMarkup(buttons)
        )
    except MessageNotModified:
        return
