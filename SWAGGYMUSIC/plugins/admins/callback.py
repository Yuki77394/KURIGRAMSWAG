##
# Copyright (C) 2021-2022 by TheAloneteam@Github, < https://github.com/TheAloneTeam >.
#
# This file is part of < https://github.com/TheAloneTeam/SWAGGYMUSIC > project,
# and is released under the "GNU v3.0 License Agreement".
# Please see < https://github.com/TheAloneTeam/SWAGGYMUSIC/blob/master/LICENSE >
#
# All rights reserved.

import asyncio

from pyrogram import filters
from pyrogram.enums import ButtonStyle
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto

import config
from SWAGGYMUSIC import YouTube, app
from SWAGGYMUSIC.core.call import Alone
from SWAGGYMUSIC.misc import SUDOERS, db
from SWAGGYMUSIC.utils.database import (autoplay_off, autoplay_on,
                                       get_active_chats, get_lang,
                                       get_filter, set_filter,
                                       get_upvote_count, is_active_chat,
                                       is_autoplay_on, is_music_playing,
                                       is_nonadmin_chat, is_thumb_on,
                                       music_off, music_on, set_loop)
from SWAGGYMUSIC.utils.decorators.language import languageCB
from SWAGGYMUSIC.utils.formatters import seconds_to_min
from SWAGGYMUSIC.utils.inline import (close_markup, stream_markup,
                                     stream_markup_timer)
from SWAGGYMUSIC.utils.stream.autoclear import auto_clean
from SWAGGYMUSIC.utils.thumbnails import get_thumb
from config import (BANNED_USERS, adminlist, confirmer, votemode)
from strings import get_string

checker = {}
upvoters = {}


@app.on_callback_query(filters.regex("ADMIN") & ~BANNED_USERS)
@languageCB
async def del_back_playlist(client, CallbackQuery, _):
    callback_data = CallbackQuery.data.strip()
    callback_request = callback_data.split(None, 1)[1]
    command, chat = callback_request.split("|")
    if "_" in str(chat):
        bet = chat.split("_")
        chat = bet[0]
        counter = bet[1]
    chat_id = int(chat)
    if not await is_active_chat(chat_id):
        return await CallbackQuery.answer(_["general_5"], show_alert=True)
    mention = CallbackQuery.from_user.mention
    if command == "UpVote":
        if chat_id not in votemode:
            votemode[chat_id] = {}
        if chat_id not in upvoters:
            upvoters[chat_id] = {}

        voters = (upvoters[chat_id]).get(CallbackQuery.message.id)
        if not voters:
            upvoters[chat_id][CallbackQuery.message.id] = []

        vote = (votemode[chat_id]).get(CallbackQuery.message.id)
        if not vote:
            votemode[chat_id][CallbackQuery.message.id] = 0

        if CallbackQuery.from_user.id in upvoters[chat_id][CallbackQuery.message.id]:
            (upvoters[chat_id][CallbackQuery.message.id]).remove(
                CallbackQuery.from_user.id
            )
            votemode[chat_id][CallbackQuery.message.id] -= 1
        else:
            (upvoters[chat_id][CallbackQuery.message.id]).append(
                CallbackQuery.from_user.id
            )
            votemode[chat_id][CallbackQuery.message.id] += 1
        upvote = await get_upvote_count(chat_id)
        get_upvotes = int(votemode[chat_id][CallbackQuery.message.id])
        if get_upvotes >= upvote:
            votemode[chat_id][CallbackQuery.message.id] = upvote
            try:
                exists = confirmer[chat_id][CallbackQuery.message.id]
                current = db[chat_id][0]
            except:
                return await CallbackQuery.edit_message_text("ғᴀɪʟᴇᴅ.")
            try:
                if current["vidid"] != exists["vidid"]:
                    return await CallbackQuery.edit_message.text(_["admin_35"])
                if current["file"] != exists["file"]:
                    return await CallbackQuery.edit_message.text(_["admin_35"])
            except:
                return await CallbackQuery.edit_message_text(_["admin_36"])
            try:
                await CallbackQuery.edit_message_text(_["admin_37"].format(upvote))
            except:
                pass
            command = counter
            mention = "ᴜᴘᴠᴏᴛᴇs"
        else:
            if (
                CallbackQuery.from_user.id
                in upvoters[chat_id][CallbackQuery.message.id]
            ):
                await CallbackQuery.answer(_["admin_38"], show_alert=True)
            else:
                await CallbackQuery.answer(_["admin_39"], show_alert=True)
            upl = InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            text=f"👍 {get_upvotes}",
                            callback_data=f"ADMIN  UpVote|{chat_id}_{counter}",
                            style=ButtonStyle.SUCCESS,
                        )
                    ]
                ]
            )
            await CallbackQuery.answer(_["admin_40"], show_alert=True)
            return await CallbackQuery.edit_message_reply_markup(reply_markup=upl)
    else:
        is_non_admin = await is_nonadmin_chat(CallbackQuery.message.chat.id)
        if not is_non_admin:
            if CallbackQuery.from_user.id not in SUDOERS:
                admins = adminlist.get(CallbackQuery.message.chat.id)
                if not admins:
                    return await CallbackQuery.answer(_["admin_13"], show_alert=True)
                else:
                    if CallbackQuery.from_user.id not in admins:
                        return await CallbackQuery.answer(
                            _["admin_14"], show_alert=True
                        )
    if command == "Pause":
        if not await is_music_playing(chat_id):
            return await CallbackQuery.answer(_["admin_1"], show_alert=True)
        await CallbackQuery.answer()
        await music_off(chat_id)
        await Alone.pause_stream(chat_id)
        await CallbackQuery.message.reply_text(
            _["admin_2"].format(mention), reply_markup=close_markup(_)
        )
    elif command == "Resume":
        if await is_music_playing(chat_id):
            return await CallbackQuery.answer(_["admin_3"], show_alert=True)
        await CallbackQuery.answer()
        await music_on(chat_id)
        await Alone.resume_stream(chat_id)
        await CallbackQuery.message.reply_text(
            _["admin_4"].format(mention), reply_markup=close_markup(_)
        )
    elif command == "Stop" or command == "End":
        await CallbackQuery.answer()
        await Alone.stop_stream(chat_id)
        await set_loop(chat_id, 0)
        await CallbackQuery.message.reply_text(
            _["admin_5"].format(mention), reply_markup=close_markup(_)
        )
        await CallbackQuery.message.delete()
    elif command == "Autoplay":
        if await is_autoplay_on(chat_id):
            await autoplay_off(chat_id)
            await CallbackQuery.answer("» ʌᴜᴛᴏᴘʟʌʏ ᴅɪsʌʙʟєᴅ.", show_alert=True)
        else:
            await autoplay_on(chat_id)
            await CallbackQuery.answer("» ʌᴜᴛᴏᴘʟʌʏ єɴʌʙʟєᴅ.", show_alert=True)
        try:
            playing = db.get(chat_id)
            if not playing:
                return
            try:
                duration_seconds = int(playing[0]["seconds"])
            except:
                duration_seconds = 0

            more = playing[0].get("more", False)
            if duration_seconds == 0:
                buttons = stream_markup(
                    _, chat_id, await is_autoplay_on(chat_id), await is_thumb_on(chat_id), await get_filter(chat_id), more=more
                )
            else:
                buttons = stream_markup_timer(
                    _,
                    chat_id,
                    seconds_to_min(playing[0]["played"]),
                    playing[0]["dur"],
                    await is_autoplay_on(chat_id),
                    await is_thumb_on(chat_id),
                    await get_filter(chat_id),
                    more=more
                )
            await CallbackQuery.edit_message_reply_markup(
                reply_markup=InlineKeyboardMarkup(buttons)
            )
        except:
            pass
    elif command == "Thumb":
        from SWAGGYMUSIC.utils.database import thumb_off, thumb_on

        if await is_thumb_on(chat_id):
            await thumb_off(chat_id)
            await CallbackQuery.answer("» ᴛʜᴜϻʙɴʌɪʟ ᴅɪsʌʙʟєᴅ.", show_alert=True)
        else:
            await thumb_on(chat_id)
            await CallbackQuery.answer("» ᴛʜᴜϻʙɴʌɪʟ єɴʌʙʟєᴅ.", show_alert=True)
        try:
            playing = db.get(chat_id)
            if not playing:
                return
            try:
                duration_seconds = int(playing[0]["seconds"])
            except:
                duration_seconds = 0

            more = playing[0].get("more", False)
            if duration_seconds == 0:
                buttons = stream_markup(
                    _, chat_id, await is_autoplay_on(chat_id), await is_thumb_on(chat_id), await get_filter(chat_id), more=more
                )
            else:
                buttons = stream_markup_timer(
                    _,
                    chat_id,
                    seconds_to_min(playing[0]["played"]),
                    playing[0]["dur"],
                    await is_autoplay_on(chat_id),
                    await is_thumb_on(chat_id),
                    await get_filter(chat_id),
                    more=more
                )
            await CallbackQuery.edit_message_reply_markup(
                reply_markup=InlineKeyboardMarkup(buttons)
            )
        except:
            pass
    elif command == "More":
        await CallbackQuery.answer()
        try:
            db[chat_id][0]["more"] = True
            playing = db.get(chat_id)
            if not playing:
                return
            try:
                duration_seconds = int(playing[0]["seconds"])
            except:
                duration_seconds = 0
            if duration_seconds == 0:
                buttons = stream_markup(
                    _, chat_id, await is_autoplay_on(chat_id), await is_thumb_on(chat_id), await get_filter(chat_id), more=True
                )
            else:
                buttons = stream_markup_timer(
                    _,
                    chat_id,
                    seconds_to_min(playing[0]["played"]),
                    playing[0]["dur"],
                    await is_autoplay_on(chat_id),
                    await is_thumb_on(chat_id),
                    await get_filter(chat_id),
                    more=True
                )
            await CallbackQuery.edit_message_reply_markup(
                reply_markup=InlineKeyboardMarkup(buttons)
            )
        except:
            pass
    elif command == "Back":
        await CallbackQuery.answer()
        try:
            db[chat_id][0]["more"] = False
            playing = db.get(chat_id)
            if not playing:
                return
            try:
                duration_seconds = int(playing[0]["seconds"])
            except:
                duration_seconds = 0
            if duration_seconds == 0:
                buttons = stream_markup(
                    _, chat_id, await is_autoplay_on(chat_id), await is_thumb_on(chat_id), await get_filter(chat_id), more=False
                )
            else:
                buttons = stream_markup_timer(
                    _,
                    chat_id,
                    seconds_to_min(playing[0]["played"]),
                    playing[0]["dur"],
                    await is_autoplay_on(chat_id),
                    await is_thumb_on(chat_id),
                    await get_filter(chat_id),
                    more=False
                )
            await CallbackQuery.edit_message_reply_markup(
                reply_markup=InlineKeyboardMarkup(buttons)
            )
        except:
            pass
    elif command == "Filter":
        playing = db.get(chat_id)
        if not playing:
            return await CallbackQuery.answer(_["queue_2"], show_alert=True)

        try:
            duration_seconds = int(playing[0]["seconds"])
        except:
            duration_seconds = 0

        file_path = playing[0]["file"]
        current_filter = await get_filter(chat_id)
        filters_list = ["Normal", "Bass", "Echo", "Slowed", "Nightcore"]

        if current_filter not in filters_list:
            next_filter = "Normal"
        else:
            idx = filters_list.index(current_filter)
            next_filter = filters_list[(idx + 1) % len(filters_list)]

        await set_filter(chat_id, next_filter)
        await CallbackQuery.answer(f"» ᴀᴘᴘʟʏɪɴɢ {next_filter.upper()} ғɪʟᴛᴇʀ...", show_alert=True)

        try:
            await Alone.apply_filter(chat_id, file_path, next_filter.lower(), playing)
        except Exception as e:
            return await CallbackQuery.message.reply_text(f"» ғᴀɪʟᴇᴅ ᴛᴏ ᴀᴘᴘʟʏ ғɪʟᴛᴇʀ.\n\nᴇʀʀᴏʀ: {e}")

        try:
            more = playing[0].get("more", False)
            if duration_seconds == 0:
                buttons = stream_markup(
                    _, chat_id, await is_autoplay_on(chat_id), await is_thumb_on(chat_id), next_filter, more=more
                )
            else:
                buttons = stream_markup_timer(
                    _,
                    chat_id,
                    seconds_to_min(playing[0]["played"]),
                    playing[0]["dur"],
                    await is_autoplay_on(chat_id),
                    await is_thumb_on(chat_id),
                    next_filter,
                    more=more
                )
            await CallbackQuery.edit_message_reply_markup(
                reply_markup=InlineKeyboardMarkup(buttons)
            )
        except:
            pass
    elif command == "Skip" or command == "Replay":
        check = db.get(chat_id)
        if command == "Skip":
            txt = f"➻ sᴛʀᴇᴀᴍ sᴋɪᴩᴩᴇᴅ 🎄\n│ \n└ʙʏ : {mention} 🥀"
            popped = None
            try:
                popped = check.pop(0)
                if popped:
                    await auto_clean(popped)
                if not check:
                    await CallbackQuery.edit_message_text(
                        f"➻ sᴛʀᴇᴀᴍ sᴋɪᴩᴩᴇᴅ 🎄\n│ \n└ʙʏ : {mention} 🥀"
                    )
                    await CallbackQuery.message.reply_text(
                        text=_["admin_6"].format(
                            mention, CallbackQuery.message.chat.title
                        ),
                        reply_markup=close_markup(_),
                    )
                    try:
                        return await Alone.stop_stream(chat_id)
                    except:
                        return
            except:
                try:
                    await CallbackQuery.edit_message_text(
                        f"➻ sᴛʀᴇᴀᴍ sᴋɪᴩᴩᴇᴅ 🎄\n│ \n└ʙʏ : {mention} 🥀"
                    )
                    await CallbackQuery.message.reply_text(
                        text=_["admin_6"].format(
                            mention, CallbackQuery.message.chat.title
                        ),
                        reply_markup=close_markup(_),
                    )
                    return await Alone.stop_stream(chat_id)
                except:
                    return
        else:
            txt = f"➻ sᴛʀᴇᴀᴍ ʀᴇ-ᴘʟᴀʏᴇᴅ 🎄\n│ \n└ʙʏ : {mention} 🥀"
        await CallbackQuery.answer()
        # Delete the "Added to Queue" or old player message
        try:
            old_mystic = check[0].get("mystic")
            if old_mystic:
                await old_mystic.delete()
        except:
            pass
        queued = check[0]["file"]
        title = (check[0]["title"]).title()
        user = check[0]["by"]
        duration = check[0]["dur"]
        streamtype = check[0]["streamtype"]
        videoid = check[0]["vidid"]
        status = True if str(streamtype) == "video" else None
        db[chat_id][0]["played"] = 0
        exis = (check[0]).get("old_dur")
        if exis:
            db[chat_id][0]["dur"] = exis
            db[chat_id][0]["seconds"] = check[0]["old_second"]
            db[chat_id][0]["speed_path"] = None
            db[chat_id][0]["speed"] = 1.0
        if "live_" in queued:
            n, link = await YouTube.video(videoid, True)
            if n == 0:
                return await CallbackQuery.message.reply_text(
                    text=_["admin_7"].format(title),
                    reply_markup=close_markup(_),
                )
            try:
                image = await YouTube.thumbnail(videoid, True)
            except:
                image = None
            try:
                await Alone.skip_stream(chat_id, link, title, video=status, image=image)
            except:
                return await CallbackQuery.message.reply_text(_["call_6"])
            button = stream_markup(
                _, chat_id, await is_autoplay_on(chat_id), await is_thumb_on(chat_id), await get_filter(chat_id)
            )
            img = await get_thumb(videoid)
            if await is_thumb_on(chat_id):
                run = await CallbackQuery.message.reply_photo(
                    photo=img,
                    has_spoiler=True,
                    caption=_["stream_1"].format(
                        f"https://t.me/{app.username}?start=info_{videoid}",
                        title[:23],
                        duration,
                        user,
                    ),
                    reply_markup=InlineKeyboardMarkup(button),
                )
            else:
                run = await CallbackQuery.message.reply_text(
                    text=_["stream_1"].format(
                        f"https://t.me/{app.username}?start=info_{videoid}",
                        title[:23],
                        duration,
                        user,
                    ),
                    reply_markup=InlineKeyboardMarkup(button),
                )
            db[chat_id][0]["mystic"] = run
            db[chat_id][0]["markup"] = "tg"
            await CallbackQuery.edit_message_text(txt, reply_markup=close_markup(_))
        elif "vid_" in queued:
            mystic = await CallbackQuery.message.reply_text(
                _["call_7"], disable_web_page_preview=True
            )
            try:
                file_path, direct = await YouTube.download(
                    videoid,
                    mystic,
                    videoid=True,
                    video=status,
                )
            except:
                return await mystic.edit_text(_["call_6"])
            try:
                image = await YouTube.thumbnail(videoid, True)
            except:
                image = None
            try:
                await Alone.skip_stream(chat_id, file_path, title, video=status, image=image)
            except:
                return await mystic.edit_text(_["call_6"])
            button = stream_markup(
                _, chat_id, await is_autoplay_on(chat_id), await is_thumb_on(chat_id), await get_filter(chat_id)
            )
            img = await get_thumb(videoid)
            if await is_thumb_on(chat_id):
                run = await CallbackQuery.message.reply_photo(
                    photo=img,
                    has_spoiler=True,
                    caption=_["stream_1"].format(
                        f"https://t.me/{app.username}?start=info_{videoid}",
                        title[:23],
                        duration,
                        user,
                    ),
                    reply_markup=InlineKeyboardMarkup(button),
                )
            else:
                run = await CallbackQuery.message.reply_text(
                    text=_["stream_1"].format(
                        f"https://t.me/{app.username}?start=info_{videoid}",
                        title[:23],
                        duration,
                        user,
                    ),
                    reply_markup=InlineKeyboardMarkup(button),
                )
            db[chat_id][0]["mystic"] = run
            db[chat_id][0]["markup"] = "stream"
            await CallbackQuery.edit_message_text(txt, reply_markup=close_markup(_))
            await mystic.delete()
        elif "index_" in queued:
            try:
                await Alone.skip_stream(chat_id, videoid, title, video=status)
            except:
                return await CallbackQuery.message.reply_text(_["call_6"])
            button = stream_markup(
                _, chat_id, await is_autoplay_on(chat_id), await is_thumb_on(chat_id), await get_filter(chat_id)
            )
            if await is_thumb_on(chat_id):
                run = await CallbackQuery.message.reply_photo(
                    photo=config.STREAM_IMG_URL,
                    has_spoiler=True,
                    caption=_["stream_2"].format(user),
                    reply_markup=InlineKeyboardMarkup(button),
                )
            else:
                run = await CallbackQuery.message.reply_text(
                    text=_["stream_2"].format(user),
                    reply_markup=InlineKeyboardMarkup(button),
                )
            db[chat_id][0]["mystic"] = run
            db[chat_id][0]["markup"] = "tg"
            await CallbackQuery.edit_message_text(txt, reply_markup=close_markup(_))
        else:
            if videoid == "telegram":
                image = None
            elif videoid == "soundcloud":
                image = None
            else:
                try:
                    image = await YouTube.thumbnail(videoid, True)
                except:
                    image = None
            try:
                await Alone.skip_stream(chat_id, queued, title, video=status, image=image)
            except:
                return await CallbackQuery.message.reply_text(_["call_6"])
            if videoid == "telegram":
                button = stream_markup(
                    _, chat_id, await is_autoplay_on(chat_id), await is_thumb_on(chat_id), await get_filter(chat_id)
                )
                if await is_thumb_on(chat_id):
                    run = await CallbackQuery.message.reply_photo(
                        photo=(
                            config.TELEGRAM_AUDIO_URL
                            if str(streamtype) == "audio"
                            else config.TELEGRAM_VIDEO_URL
                        ),
                        has_spoiler=True,
                        caption=_["stream_1"].format(
                            config.SUPPORT_CHAT, title[:23], duration, user
                        ),
                        reply_markup=InlineKeyboardMarkup(button),
                    )
                else:
                    run = await CallbackQuery.message.reply_text(
                        text=_["stream_1"].format(
                            config.SUPPORT_CHAT, title[:23], duration, user
                        ),
                        reply_markup=InlineKeyboardMarkup(button),
                    )
                db[chat_id][0]["mystic"] = run
                db[chat_id][0]["markup"] = "tg"
            elif videoid == "soundcloud":
                button = stream_markup(
                    _, chat_id, await is_autoplay_on(chat_id), await is_thumb_on(chat_id), await get_filter(chat_id)
                )
                if await is_thumb_on(chat_id):
                    run = await CallbackQuery.message.reply_photo(
                        photo=config.SOUNCLOUD_IMG_URL,
                        has_spoiler=True,
                        caption=_["stream_1"].format(
                            config.SUPPORT_CHAT, title[:23], duration, user
                        ),
                        reply_markup=InlineKeyboardMarkup(button),
                    )
                else:
                    run = await CallbackQuery.message.reply_text(
                        text=_["stream_1"].format(
                            config.SUPPORT_CHAT, title[:23], duration, user
                        ),
                        reply_markup=InlineKeyboardMarkup(button),
                    )
                db[chat_id][0]["mystic"] = run
                db[chat_id][0]["markup"] = "tg"
            else:
                button = stream_markup(
                    _, chat_id, await is_autoplay_on(chat_id), await is_thumb_on(chat_id), await get_filter(chat_id)
                )
                img = await get_thumb(videoid)
                if await is_thumb_on(chat_id):
                    run = await CallbackQuery.message.reply_photo(
                        photo=img,
                        has_spoiler=True,
                        caption=_["stream_1"].format(
                            f"https://t.me/{app.username}?start=info_{videoid}",
                            title[:23],
                            duration,
                            user,
                        ),
                        reply_markup=InlineKeyboardMarkup(button),
                    )
                else:
                    run = await CallbackQuery.message.reply_text(
                        text=_["stream_1"].format(
                            f"https://t.me/{app.username}?start=info_{videoid}",
                            title[:23],
                            duration,
                            user,
                        ),
                        reply_markup=InlineKeyboardMarkup(button),
                    )
                db[chat_id][0]["mystic"] = run
                db[chat_id][0]["markup"] = "stream"
            await CallbackQuery.edit_message_text(txt, reply_markup=close_markup(_))




async def markup_timer():
    while not await asyncio.sleep(7):
        active_chats = await get_active_chats()
        for chat_id in active_chats:
            try:
                if not await is_music_playing(chat_id):
                    continue
                playing = db.get(chat_id)
                if not playing:
                    continue
                duration_seconds = int(playing[0]["seconds"])
                if duration_seconds == 0:
                    continue
                try:
                    mystic = playing[0]["mystic"]
                except:
                    continue
                try:
                    check = checker[chat_id][mystic.id]
                    if check is False:
                        continue
                except:
                    pass
                try:
                    language = await get_lang(chat_id)
                    _ = get_string(language)
                except:
                    _ = get_string("en")
                try:
                    more = playing[0].get("more", False)
                    buttons = stream_markup_timer(
                        _,
                        chat_id,
                        seconds_to_min(playing[0]["played"]),
                        playing[0]["dur"],
                        await is_autoplay_on(chat_id),
                        await is_thumb_on(chat_id),
                        await get_filter(chat_id),
                        more=more,
                    )
                    await mystic.edit_reply_markup(
                        reply_markup=InlineKeyboardMarkup(buttons)
                    )
                except:
                    continue
            except:
                continue


asyncio.create_task(markup_timer())
