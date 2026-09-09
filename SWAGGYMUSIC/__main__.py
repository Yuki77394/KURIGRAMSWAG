#
# Copyright (C) 2021-2022 by Yuki77394@Github, < https://github.com/yuki77394 >.
# This file is part of < https://github.com/Yuki77394/SWAGGYMUSIC > project,
# and is released under the "GNU v3.0 License Agreement".
# Please see < https://github.com/Yuki77394/SWAGGYMUSIC/blob/master/LICENSE >
#
# All rights reserved.

import asyncio
import importlib

import static_ffmpeg
from pyrogram import idle
from pytgcalls.exceptions import NoActiveGroupCall

import config
from SWAGGYMUSIC import LOGGER, app, userbot
from SWAGGYMUSIC.core.call import Alone
from SWAGGYMUSIC.misc import sudo
from SWAGGYMUSIC.plugins import ALL_MODULES
from SWAGGYMUSIC.utils.database import get_banned_users, get_gbanned
from config import BANNED_USERS


async def init():
    static_ffmpeg.add_paths()
    if (
        not config.STRING1
        and not config.STRING2
        and not config.STRING3
        and not config.STRING4
        and not config.STRING5
    ):
        LOGGER(__name__).error("Assistant client variables not defined, exiting...")
        exit()

    await sudo()

    try:
        users = await get_gbanned()
        for user_id in users:
            BANNED_USERS.add(user_id)

        users = await get_banned_users()
        for user_id in users:
            BANNED_USERS.add(user_id)
    except:
        pass

    # ─── Initialize music cache indexes ───────────────────────────────────
    # Creates the unique (video_id, media_type) index on the music_cache
    # collection so duplicate uploads can never produce two records, plus
    # secondary indexes on file_unique_id and normalized_title for fast
    # reverse lookups. Idempotent — safe to call on every boot.
    try:
        from SWAGGYMUSIC.utils.database import ensure_music_cache_indexes

        await ensure_music_cache_indexes()

        if getattr(config, "MUSIC_CACHE_ENABLED", True) and getattr(
            config, "STORAGE_CHANNEL_ID", 0
        ):
            LOGGER("SWAGGYMUSIC.music_cache").info(
                f"Music cache ENABLED — storage channel={config.STORAGE_CHANNEL_ID}"
            )
        else:
            LOGGER("SWAGGYMUSIC.music_cache").info(
                "Music cache DISABLED (STORAGE_CHANNEL_ID not set or "
                "MUSIC_CACHE_ENABLED=false) — bot will run without caching"
            )
    except Exception as e:
        LOGGER("SWAGGYMUSIC.music_cache").warning(
            f"Could not initialize music cache indexes: {type(e).__name__}: {e}"
        )

    await app.start()

    for all_module in ALL_MODULES:
        importlib.import_module("SWAGGYMUSIC.plugins" + all_module)

    LOGGER("SWAGGYMUSIC.plugins").info("Successfully Imported Modules...")

    await userbot.start()
    await Alone.start()

    try:
        await Alone.stream_call(
            "https://te.legra.ph/file/29f784eb49d230ab62e9e.mp4"
        )
    except NoActiveGroupCall:
        LOGGER("SWAGGYMUSIC").error(
            "Please turn on the videochat of your log group/channel.\n\n"
            "Stopping Bot..."
        )
        exit()
    except:
        pass

    await Alone.decorators()

    LOGGER("SWAGGYMUSIC").info(
        "ʙᴏᴛ sᴛᴀʀᴛᴇᴅ sᴜᴄᴄᴇssғᴜʟʟʏ, ɴᴏᴡ ɢɪʙ ʏᴏᴜʀ ɢɪʀʟғʀɪᴇɴᴅ ᴄʜᴜᴛ ᴛᴏ @SexyProfessor"
    )

    await idle()

    # ─── Graceful shutdown: cancel any in-flight cache uploads ───────────
    try:
        from SWAGGYMUSIC.utils.music_cache import cancel_all_uploads

        cancel_all_uploads()
    except Exception:
        pass

    await app.stop()
    await userbot.stop()

    LOGGER("SWAGGYMUSIC").info(
        "Stopping 𝚻հҽ 𝚨Łꪮⲛ𝛆 🚩𝗧ε᧘‌ᴍ Bot..."
    )


def main():
    """Console entry point for packaged deployments."""
    asyncio.get_event_loop().run_until_complete(init())


if __name__ == "__main__":
    main()
