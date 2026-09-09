#
# Copyright (C) 2021-2022 by TheAloneteam@Github, < https://github.com/TheAloneTeam >.
#
# This file is part of < https://github.com/TheAloneTeam/SWAGGYMUSIC > project,
# and is released under the "GNU v3.0 License Agreement".
# Please see < https://github.com/TheAloneTeam/SWAGGYMUSIC/blob/master/LICENSE >
#
# All rights reserved.

import asyncio
from typing import Union

from SWAGGYMUSIC.misc import db
from SWAGGYMUSIC.utils.formatters import check_duration, seconds_to_min
from config import autoclean, time_to_seconds


async def put_queue(
    chat_id,
    original_chat_id,
    file,
    title,
    duration,
    user,
    vidid,
    user_id,
    stream,
    forceplay: Union[bool, str] = None,
    mystic: Union[bool, str] = None,
):
    title = title.title()
    try:
        duration_in_seconds = time_to_seconds(duration) - 3
    except:
        duration_in_seconds = 0
    put = {
        "title": title,
        "dur": duration,
        "streamtype": stream,
        "by": user,
        "user_id": user_id,
        "chat_id": original_chat_id,
        "file": file,
        "vidid": vidid,
        "seconds": duration_in_seconds,
        "played": 0,
        "mystic": mystic,
    }
    if forceplay:
        check = db.get(chat_id)
        if check:
            check.insert(0, put)
        else:
            db[chat_id] = []
            db[chat_id].append(put)
    else:
        db[chat_id].append(put)
    autoclean.append(file)

    # ── Silent background prefetch of the next-up song ────────────────────
    # After the song is queued, fire-and-forget a prefetch task. The task
    # is a no-op if this song is NOT the next-up (index 1) or if it's not
    # a "vid_" entry that would benefit from a pre-download. All error
    # handling is internal to schedule_prefetch — this call never raises.
    try:
        from SWAGGYMUSIC.utils.stream.prefetch import schedule_prefetch
        await schedule_prefetch(
            chat_id=chat_id,
            queued_file=file,
            videoid=vidid,
            streamtype=stream,
            video=(True if str(stream).lower() == "video" else None),
        )
    except Exception:
        # Prefetch is purely an optimization — never let it break the
        # queue-add path.
        pass


async def put_queue_index(
    chat_id,
    original_chat_id,
    file,
    title,
    duration,
    user,
    vidid,
    stream,
    forceplay: Union[bool, str] = None,
    mystic: Union[bool, str] = None,
):
    if "20.212.146.162" in vidid:
        try:
            dur = await asyncio.get_event_loop().run_in_executor(
                None, check_duration, vidid
            )
            duration = seconds_to_min(dur)
        except:
            duration = "ᴜʀʟ sᴛʀᴇᴀᴍ"
            dur = 0
    else:
        dur = 0
    put = {
        "title": title,
        "dur": duration,
        "streamtype": stream,
        "by": user,
        "chat_id": original_chat_id,
        "file": file,
        "vidid": vidid,
        "seconds": dur,
        "played": 0,
        "mystic": mystic,
    }
    if forceplay:
        check = db.get(chat_id)
        if check:
            check.insert(0, put)
        else:
            db[chat_id] = []
            db[chat_id].append(put)
    else:
        db[chat_id].append(put)

    # ── Silent background prefetch of the next-up song ────────────────────
    # Same as put_queue — fire-and-forget a prefetch task. For index_
    # streams (URL streams) the prefetch trigger is a no-op internally
    # since they don't hit YouTube.download(); only "vid_" entries actually
    # trigger a background download.
    try:
        from SWAGGYMUSIC.utils.stream.prefetch import schedule_prefetch
        await schedule_prefetch(
            chat_id=chat_id,
            queued_file=file,
            videoid=vidid,
            streamtype=stream,
            video=(True if str(stream).lower() == "video" else None),
        )
    except Exception:
        pass
