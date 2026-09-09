#
# Copyright (C) 2021-2026 by Yuki77394@Github, < https://github.com/Yuki77394 >.
#
# This file is part of < https://github.com/TheAloneTeam/SWAGGYMUSIC > project,
# and is released under the "GNU v3.0 License Agreement".
# Please see < https://github.com/TheAloneTeam/SWAGGYMUSIC/blob/master/LICENSE >
#
# All rights reserved.

from pyrogram import filters
from pyrogram.types import InlineKeyboardMarkup, Message

import config
from SWAGGYMUSIC import YouTube, app
from SWAGGYMUSIC.core.call import Alone
from SWAGGYMUSIC.misc import db
from SWAGGYMUSIC.utils.database import (get_filter, get_loop,
                                       is_autoplay_on, is_thumb_on)
from SWAGGYMUSIC.utils.decorators import AdminRightsCheck
from SWAGGYMUSIC.utils.inline import close_markup, stream_markup
from SWAGGYMUSIC.utils.stream.autoclear import auto_clean
from SWAGGYMUSIC.utils.stream.stream import update_stream_ui
from SWAGGYMUSIC.utils.thumbnails import get_thumb
from config import BANNED_USERS


@app.on_message(
    filters.command(["skip", "cskip", "next", "cnext"]) & filters.group & ~BANNED_USERS
)
@AdminRightsCheck
async def skip(cli, message: Message, _, chat_id):
    if not len(message.command) < 2:
        loop = await get_loop(chat_id)
        if loop != 0:
            return await message.reply_text(_["admin_8"])
        state = message.text.split(None, 1)[1].strip()
        if state.isnumeric():
            state = int(state)
            check = db.get(chat_id)
            if check:
                count = len(check)
                if count > 2:
                    count = int(count - 1)
                    if 1 <= state <= count:
                        for x in range(state):
                            popped = None
                            try:
                                old_mystic = check[0].get("mystic") if check else None
                                popped = check.pop(0)
                            except:
                                return await message.reply_text(_["admin_12"])
                            if popped:
                                await auto_clean(popped)
                                # Cancel any in-flight background prefetch task
                                # for the song we just popped — it's now stale.
                                try:
                                    from SWAGGYMUSIC.utils.stream.prefetch import cancel_prefetch_for_song
                                    cancel_prefetch_for_song(chat_id, popped.get("vidid", ""))
                                except Exception:
                                    pass
                            if not check:
                                if await is_autoplay_on(chat_id):
                                    try:
                                        vidid = popped["vidid"]
                                        related = await YouTube.get_related_videos(vidid)
                                        if not related:
                                            raise Exception("no related")
                                        import random
                                        video_id = random.choice(related)
                                        details, track_id = await YouTube.track(video_id, True)
                                        if not details.get("title"):
                                            raise Exception("no track details")
                                        from SWAGGYMUSIC.utils.stream.stream import stream
                                        await stream(
                                            _,
                                            old_mystic,
                                            popped["user_id"],
                                            details,
                                            chat_id,
                                            popped["by"],
                                            popped["chat_id"],
                                            video=True if popped["streamtype"] == "video" else False,
                                            streamtype="youtube",
                                            forceplay=True,
                                        )
                                        return
                                    except:
                                        pass
                                try:
                                    await message.reply_text(
                                        text=_["admin_6"].format(
                                            message.from_user.mention,
                                            message.chat.title,
                                        ),
                                        reply_markup=close_markup(_),
                                    )
                                    await Alone.stop_stream(chat_id)
                                except:
                                    return
                                break
                    else:
                        return await message.reply_text(_["admin_11"].format(count))
                else:
                    return await message.reply_text(_["admin_10"])
            else:
                return await message.reply_text(_["queue_2"])
        else:
            return await message.reply_text(_["admin_9"])
    else:
        check = db.get(chat_id)
        popped = None
        try:
            old_mystic = check[0].get("mystic") if check else None
            popped = check.pop(0)
            if popped:
                await auto_clean(popped)
                # Cancel any in-flight background prefetch task for the
                # song we just popped — it's now stale.
                try:
                    from SWAGGYMUSIC.utils.stream.prefetch import cancel_prefetch_for_song
                    cancel_prefetch_for_song(chat_id, popped.get("vidid", ""))
                except Exception:
                    pass
            if not check:
                if await is_autoplay_on(chat_id):
                    try:
                        vidid = popped["vidid"]
                        related = await YouTube.get_related_videos(vidid)
                        if not related:
                            raise Exception("no related")
                        import random
                        video_id = random.choice(related)
                        details, track_id = await YouTube.track(video_id, True)
                        if not details.get("title"):
                            raise Exception("no track details")
                        from SWAGGYMUSIC.utils.stream.stream import stream
                        await stream(
                            _,
                            old_mystic,
                            popped["user_id"],
                            details,
                            chat_id,
                            popped["by"],
                            popped["chat_id"],
                            video=True if popped["streamtype"] == "video" else False,
                            streamtype="youtube",
                            forceplay=True,
                        )
                        return
                    except:
                        pass
                await message.reply_text(
                    text=_["admin_6"].format(
                        message.from_user.mention, message.chat.title
                    ),
                    reply_markup=close_markup(_),
                )
                try:
                    return await Alone.stop_stream(chat_id)
                except:
                    return
        except:
            try:
                await message.reply_text(
                    text=_["admin_6"].format(
                        message.from_user.mention, message.chat.title
                    ),
                    reply_markup=close_markup(_),
                )
                return await Alone.stop_stream(chat_id)
            except:
                return
    queued = check[0]["file"]

    # Delete the "Added to Queue" message of the next track
    try:
        old_queued_mystic = check[0].get("mystic")
        if old_queued_mystic:
            await old_queued_mystic.delete()
    except:
        pass

    title = (check[0]["title"]).title()
    user = check[0]["by"]
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
    old_mystic = db.get(chat_id, [{}])[0].get("mystic")
    if "live_" in queued:
        n, link = await YouTube.video(videoid, True)
        if n == 0:
            return await message.reply_text(_["admin_7"].format(title))
        try:
            image = await YouTube.thumbnail(videoid, True)
        except:
            image = None
        try:
            await Alone.skip_stream(chat_id, link, title, video=status, image=image)
        except:
            return await message.reply_text(_["call_6"])
        button = stream_markup(
            _, chat_id, await is_autoplay_on(chat_id), await is_thumb_on(chat_id), await get_filter(chat_id)
        )
        img = await get_thumb(videoid)
        caption = _["stream_1"].format(
            f"https://t.me/{app.username}?start=info_{videoid}",
            title[:23],
            check[0]["dur"],
            user,
        )
        run = await update_stream_ui(chat_id, message.chat.id, None, img, caption, button)
        db[chat_id][0]["mystic"] = run
        db[chat_id][0]["markup"] = "tg"
    elif "vid_" in queued:
        try:
            file_path, direct = await YouTube.download(
                videoid,
                old_mystic,
                videoid=True,
                video=status,
            )
        except:
            if old_mystic:
                return await old_mystic.edit_text(_["call_6"])
            else:
                return await message.reply_text(_["call_6"])
        if not file_path:
            if old_mystic:
                return await old_mystic.edit_text(_["call_6"])
            return await message.reply_text(_["call_6"])
        try:
            image = await YouTube.thumbnail(videoid, True)
        except:
            image = None
        try:
            await Alone.skip_stream(chat_id, file_path, title, video=status, image=image)
        except:
            if old_mystic:
                return await old_mystic.edit_text(_["call_6"])
            else:
                return await message.reply_text(_["call_6"])
        button = stream_markup(
            _, chat_id, await is_autoplay_on(chat_id), await is_thumb_on(chat_id), await get_filter(chat_id)
        )
        img = await get_thumb(videoid)
        caption = _["stream_1"].format(
            f"https://t.me/{app.username}?start=info_{videoid}",
            title[:23],
            check[0]["dur"],
            user,
        )
        run = await update_stream_ui(chat_id, message.chat.id, None, img, caption, button)
        db[chat_id][0]["mystic"] = run
        db[chat_id][0]["markup"] = "stream"
    elif "index_" in queued:
        try:
            await Alone.skip_stream(chat_id, videoid, title, video=status)
        except:
            return await message.reply_text(_["call_6"])
        button = stream_markup(
            _, chat_id, await is_autoplay_on(chat_id), await is_thumb_on(chat_id), await get_filter(chat_id)
        )
        caption = _["stream_2"].format(user)
        run = await update_stream_ui(chat_id, message.chat.id, None, config.STREAM_IMG_URL, caption, button)
        db[chat_id][0]["mystic"] = run
        db[chat_id][0]["markup"] = "tg"
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
            return await message.reply_text(_["call_6"])
        if videoid == "telegram":
            button = stream_markup(
                _, chat_id, await is_autoplay_on(chat_id), await is_thumb_on(chat_id), await get_filter(chat_id)
            )
            img = config.TELEGRAM_VIDEO_URL if status else config.TELEGRAM_AUDIO_URL
            caption = _["stream_1"].format(
                config.SUPPORT_CHAT, title[:23], check[0]["dur"], user
            )
            run = await update_stream_ui(chat_id, message.chat.id, None, img, caption, button)
            db[chat_id][0]["mystic"] = run
            db[chat_id][0]["markup"] = "tg"
        elif videoid == "soundcloud":
            button = stream_markup(
                _, chat_id, await is_autoplay_on(chat_id), await is_thumb_on(chat_id), await get_filter(chat_id)
            )
            caption = _["stream_1"].format(
                config.SUPPORT_CHAT, title[:23], check[0]["dur"], user
            )
            run = await update_stream_ui(chat_id, message.chat.id, None, config.SOUNCLOUD_IMG_URL, caption, button)
            db[chat_id][0]["mystic"] = run
            db[chat_id][0]["markup"] = "tg"
        else:
            button = stream_markup(
                _, chat_id, await is_autoplay_on(chat_id), await is_thumb_on(chat_id), await get_filter(chat_id)
            )
            img = await get_thumb(videoid)
            caption = _["stream_1"].format(
                f"https://t.me/{app.username}?start=info_{videoid}",
                title[:23],
                check[0]["dur"],
                user,
            )
            run = await update_stream_ui(chat_id, message.chat.id, None, img, caption, button)
            db[chat_id][0]["mystic"] = run
            db[chat_id][0]["markup"] = "stream"

    # ── After skip: prefetch the new next-up song ─────────────────────────
    # Same as change_stream's hook — fire-and-forget a prefetch for the
    # song now at index 1. Safe no-op if not a vid_ entry or already cached.
    try:
        from SWAGGYMUSIC.utils.stream.prefetch import schedule_prefetch
        new_queue = db.get(chat_id) or []
        if len(new_queue) >= 2:
            next_up = new_queue[1]
            await schedule_prefetch(
                chat_id=chat_id,
                queued_file=next_up.get("file", ""),
                videoid=next_up.get("vidid", ""),
                streamtype=next_up.get("streamtype", ""),
                video=(True if str(next_up.get("streamtype", "")).lower() == "video" else None),
            )
    except Exception:
        pass
