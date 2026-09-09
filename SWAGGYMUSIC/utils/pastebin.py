#
# Copyright (C) 2021-2022 by Yuki77394@Github, < https://github.com/yuki77394 >.
#
# This file is part of < https://github.com/Yuki77394/SWAGGYMUSIC > project,
# and is released under the "GNU v3.0 License Agreement".
# Please see < https://github.com/Yuki77394/SWAGGYMUSIC/blob/master/LICENSE >
#
# All rights reserved.

import aiohttp

BASE = "https://batbin.me/"


async def post(url: str, *args, **kwargs):
    async with aiohttp.ClientSession() as session:
        async with session.post(url, *args, **kwargs) as resp:
            try:
                data = await resp.json()
            except Exception:
                data = await resp.text()
        return data


async def AloneBin(text):
    resp = await post(f"{BASE}api/v2/paste", data=text)
    if not resp["success"]:
        return
    link = BASE + resp["message"]
    return link


AloneBin = AloneBin
