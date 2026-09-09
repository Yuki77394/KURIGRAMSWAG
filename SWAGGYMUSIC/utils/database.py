#
# Copyright (C) 2021-2022 by TheAloneteam@Github, < https://github.com/TheAloneTeam >.
#
# This file is part of < https://github.com/TheAloneTeam/SWAGGYMUSIC > project,
# and is released under the "GNU v3.0 License Agreement".
# Please see < https://github.com/TheAloneTeam/SWAGGYMUSIC/blob/master/LICENSE >
#
# All rights reserved.

import random
from typing import Dict, List, Union

from SWAGGYMUSIC import userbot
from SWAGGYMUSIC.core.mongo import mongodb

authdb = mongodb.adminauth
authuserdb = mongodb.authuser
autoplaydb = mongodb.autoplay
autoenddb = mongodb.autoend
autoleavedb = mongodb.autoleave
assdb = mongodb.assistants
blacklist_chatdb = mongodb.blacklistChat
blockeddb = mongodb.blockedusers
chatsdb = mongodb.chats
channeldb = mongodb.cplaymode
countdb = mongodb.upcount
gbansdb = mongodb.gban
langdb = mongodb.language
onoffdb = mongodb.onoffper
playmodedb = mongodb.playmode
playtypedb = mongodb.playtypedb
filterdb = mongodb.filters
skipdb = mongodb.skipmode
sudoersdb = mongodb.sudoers
usersdb = mongodb.tgusersdb
thumbdb = mongodb.thumbdb
ttsdb = mongodb.tts
# Welcome system — persistent per-chat enable/disable flag.
# Default is enabled (True) for any chat that has no record yet.
welcomedb = mongodb.welcome_toggle

# ─── Music Cache (Telegram Storage Channel) ─────────────────────────────────
# Stores metadata of songs that have been successfully uploaded to the private
# Telegram storage channel. One document per (video_id, media_type) pair so a
# song cached as both audio and video has two separate entries — they are
# distinct Telegram files with distinct file_ids.
# Indexes are created lazily on startup via ensure_music_cache_indexes().
music_cache_db = mongodb.music_cache

# Shifting to memory [mongo sucks often]
active = []
activevideo = []
assistantdict = {}
autoplay = {}
autoend = {}
autoleave = {}
count = {}
channelconnect = {}
langm = {}
loop = {}
maintenance = []
nonadmin = {}
pause = {}
thumbnail = {}
ttsm = {}
ttsdur = {}
ttstxt = {}
playmode = {}
playtype = {}
skipmode = {}
filters = {}
# Welcome system in-memory cache — mirrors DB to avoid a Mongo round-trip
# on every new-member join event (which fires very frequently).
welcomem = {}


async def save_filter(chat_id: int, name: str, _filter: dict):
    name = name.lower().strip()
    _filters = await _get_filters(chat_id)
    _filters[name] = _filter
    await filtersdb.update_one(
        {"chat_id": chat_id},
        {"$set": {"filters": _filters}},
        upsert=True,
    )

async def get_assistant_number(chat_id: int) -> str:
    assistant = assistantdict.get(chat_id)
    return assistant


async def get_client(assistant: int):
    if int(assistant) == 1:
        return userbot.one
    elif int(assistant) == 2:
        return userbot.two
    elif int(assistant) == 3:
        return userbot.three
    elif int(assistant) == 4:
        return userbot.four
    elif int(assistant) == 5:
        return userbot.five


async def set_assistant_new(chat_id, number):
    number = int(number)
    await assdb.update_one(
        {"chat_id": chat_id},
        {"$set": {"assistant": number}},
        upsert=True,
    )


async def set_assistant(chat_id):
    from SWAGGYMUSIC.core.userbot import assistants

    ran_assistant = random.choice(assistants)
    assistantdict[chat_id] = ran_assistant
    await assdb.update_one(
        {"chat_id": chat_id},
        {"$set": {"assistant": ran_assistant}},
        upsert=True,
    )
    userbot = await get_client(ran_assistant)
    return userbot


async def get_assistant(chat_id: int) -> str:
    from SWAGGYMUSIC.core.userbot import assistants

    assistant = assistantdict.get(chat_id)
    if not assistant:
        dbassistant = await assdb.find_one({"chat_id": chat_id})
        if not dbassistant:
            userbot = await set_assistant(chat_id)
            return userbot
        else:
            got_assis = dbassistant["assistant"]
            if got_assis in assistants:
                assistantdict[chat_id] = got_assis
                userbot = await get_client(got_assis)
                return userbot
            else:
                userbot = await set_assistant(chat_id)
                return userbot
    else:
        if assistant in assistants:
            userbot = await get_client(assistant)
            return userbot
        else:
            userbot = await set_assistant(chat_id)
            return userbot


async def set_calls_assistant(chat_id):
    from SWAGGYMUSIC.core.userbot import assistants

    ran_assistant = random.choice(assistants)
    assistantdict[chat_id] = ran_assistant
    await assdb.update_one(
        {"chat_id": chat_id},
        {"$set": {"assistant": ran_assistant}},
        upsert=True,
    )
    return ran_assistant


async def group_assistant(self, chat_id: int) -> int:
    from SWAGGYMUSIC.core.userbot import assistants

    assistant = assistantdict.get(chat_id)
    if not assistant:
        dbassistant = await assdb.find_one({"chat_id": chat_id})
        if not dbassistant:
            assis = await set_calls_assistant(chat_id)
        else:
            assis = dbassistant["assistant"]
            if assis in assistants:
                assistantdict[chat_id] = assis
                assis = assis
            else:
                assis = await set_calls_assistant(chat_id)
    else:
        if assistant in assistants:
            assis = assistant
        else:
            assis = await set_calls_assistant(chat_id)
    if int(assis) == 1:
        return self.one
    elif int(assis) == 2:
        return self.two
    elif int(assis) == 3:
        return self.three
    elif int(assis) == 4:
        return self.four
    elif int(assis) == 5:
        return self.five


async def is_skipmode(chat_id: int) -> bool:
    mode = skipmode.get(chat_id)
    if not mode:
        user = await skipdb.find_one({"chat_id": chat_id})
        if not user:
            skipmode[chat_id] = True
            return True
        skipmode[chat_id] = False
        return False
    return mode


async def skip_on(chat_id: int):
    skipmode[chat_id] = True
    user = await skipdb.find_one({"chat_id": chat_id})
    if user:
        return await skipdb.delete_one({"chat_id": chat_id})


async def skip_off(chat_id: int):
    skipmode[chat_id] = False
    user = await skipdb.find_one({"chat_id": chat_id})
    if not user:
        return await skipdb.insert_one({"chat_id": chat_id})


async def get_upvote_count(chat_id: int) -> int:
    mode = count.get(chat_id)
    if not mode:
        mode = await countdb.find_one({"chat_id": chat_id})
        if not mode:
            return 5
        count[chat_id] = mode["mode"]
        return mode["mode"]
    return mode


async def set_upvotes(chat_id: int, mode: int):
    count[chat_id] = mode
    await countdb.update_one(
        {"chat_id": chat_id}, {"$set": {"mode": mode}}, upsert=True
    )


async def is_autoend() -> bool:
    chat_id = 1234
    user = await autoenddb.find_one({"chat_id": chat_id})
    if not user:
        return False
    return True


async def autoend_on():
    chat_id = 1234
    await autoenddb.insert_one({"chat_id": chat_id})


async def autoend_off():
    chat_id = 1234
    await autoenddb.delete_one({"chat_id": chat_id})


async def is_autoleave() -> bool:
    chat_id = 1234
    user = await autoleavedb.find_one({"chat_id": chat_id})
    if not user:
        return False
    return True


async def autoleave_on():
    chat_id = 1234
    await autoleavedb.insert_one({"chat_id": chat_id})


async def autoleave_off():
    chat_id = 1234
    await autoleavedb.delete_one({"chat_id": chat_id})


async def is_autoplay_on(chat_id: int) -> bool:
    mode = autoplay.get(chat_id)
    if mode is None:
        user = await autoplaydb.find_one({"chat_id": chat_id})
        if not user:
            autoplay[chat_id] = False
            return False
        autoplay[chat_id] = True
        return True
    return mode


async def autoplay_on(chat_id: int):
    autoplay[chat_id] = True
    user = await autoplaydb.find_one({"chat_id": chat_id})
    if not user:
        return await autoplaydb.insert_one({"chat_id": chat_id})


async def autoplay_off(chat_id: int):
    autoplay[chat_id] = False
    user = await autoplaydb.find_one({"chat_id": chat_id})
    if user:
        return await autoplaydb.delete_one({"chat_id": chat_id})


async def is_thumb_on(chat_id: int) -> bool:
    mode = thumbnail.get(chat_id)
    if mode is None:
        user = await thumbdb.find_one({"chat_id": chat_id})
        if not user:
            thumbnail[chat_id] = True
            return True
        thumbnail[chat_id] = False
        return False
    return mode


async def thumb_on(chat_id: int):
    thumbnail[chat_id] = True
    user = await thumbdb.find_one({"chat_id": chat_id})
    if user:
        return await thumbdb.delete_one({"chat_id": chat_id})


async def thumb_off(chat_id: int):
    thumbnail[chat_id] = False
    user = await thumbdb.find_one({"chat_id": chat_id})
    if not user:
        return await thumbdb.insert_one({"chat_id": chat_id})


async def get_loop(chat_id: int) -> int:
    lop = loop.get(chat_id)
    if not lop:
        return 0
    return lop


async def set_loop(chat_id: int, mode: int):
    loop[chat_id] = mode


async def get_cmode(chat_id: int) -> int:
    mode = channelconnect.get(chat_id)
    if not mode:
        mode = await channeldb.find_one({"chat_id": chat_id})
        if not mode:
            return None
        channelconnect[chat_id] = mode["mode"]
        return mode["mode"]
    return mode


async def set_cmode(chat_id: int, mode: int):
    channelconnect[chat_id] = mode
    await channeldb.update_one(
        {"chat_id": chat_id}, {"$set": {"mode": mode}}, upsert=True
    )


async def get_playtype(chat_id: int) -> str:
    mode = playtype.get(chat_id)
    if not mode:
        mode = await playtypedb.find_one({"chat_id": chat_id})
        if not mode:
            playtype[chat_id] = "Everyone"
            return "Everyone"
        playtype[chat_id] = mode["mode"]
        return mode["mode"]
    return mode


async def set_playtype(chat_id: int, mode: str):
    playtype[chat_id] = mode
    await playtypedb.update_one(
        {"chat_id": chat_id}, {"$set": {"mode": mode}}, upsert=True
    )


async def get_playmode(chat_id: int) -> str:
    mode = playmode.get(chat_id)
    if not mode:
        mode = await playmodedb.find_one({"chat_id": chat_id})
        if not mode:
            playmode[chat_id] = "Direct"
            return "Direct"
        playmode[chat_id] = mode["mode"]
        return mode["mode"]
    return mode


async def set_playmode(chat_id: int, mode: str):
    playmode[chat_id] = mode
    await playmodedb.update_one(
        {"chat_id": chat_id}, {"$set": {"mode": mode}}, upsert=True
    )


async def get_lang(chat_id: int) -> str:
    mode = langm.get(chat_id)
    if not mode:
        lang = await langdb.find_one({"chat_id": chat_id})
        if not lang:
            langm[chat_id] = "en"
            return "en"
        langm[chat_id] = lang["lang"]
        return lang["lang"]
    return mode


async def set_lang(chat_id: int, lang: str):
    langm[chat_id] = lang
    await langdb.update_one({"chat_id": chat_id}, {"$set": {"lang": lang}}, upsert=True)


async def is_music_playing(chat_id: int) -> bool:
    mode = pause.get(chat_id)
    if not mode:
        return False
    return mode


async def music_on(chat_id: int):
    pause[chat_id] = True


async def music_off(chat_id: int):
    pause[chat_id] = False


async def get_active_chats() -> list:
    return active


async def is_active_chat(chat_id: int) -> bool:
    if chat_id not in active:
        return False
    else:
        return True


async def add_active_chat(chat_id: int):
    if chat_id not in active:
        active.append(chat_id)


async def remove_active_chat(chat_id: int):
    if chat_id in active:
        active.remove(chat_id)


async def get_active_video_chats() -> list:
    return activevideo


async def is_active_video_chat(chat_id: int) -> bool:
    if chat_id not in activevideo:
        return False
    else:
        return True


async def add_active_video_chat(chat_id: int):
    if chat_id not in activevideo:
        activevideo.append(chat_id)


async def remove_active_video_chat(chat_id: int):
    if chat_id in activevideo:
        activevideo.remove(chat_id)


async def check_nonadmin_chat(chat_id: int) -> bool:
    user = await authdb.find_one({"chat_id": chat_id})
    if not user:
        return False
    return True


async def is_nonadmin_chat(chat_id: int) -> bool:
    mode = nonadmin.get(chat_id)
    if not mode:
        user = await authdb.find_one({"chat_id": chat_id})
        if not user:
            nonadmin[chat_id] = False
            return False
        nonadmin[chat_id] = True
        return True
    return mode


async def add_nonadmin_chat(chat_id: int):
    nonadmin[chat_id] = True
    is_admin = await check_nonadmin_chat(chat_id)
    if is_admin:
        return
    return await authdb.insert_one({"chat_id": chat_id})


async def remove_nonadmin_chat(chat_id: int):
    nonadmin[chat_id] = False
    is_admin = await check_nonadmin_chat(chat_id)
    if not is_admin:
        return
    return await authdb.delete_one({"chat_id": chat_id})


async def is_on_off(on_off: int) -> bool:
    onoff = await onoffdb.find_one({"on_off": on_off})
    if not onoff:
        return False
    return True


async def add_on(on_off: int):
    is_on = await is_on_off(on_off)
    if is_on:
        return
    return await onoffdb.insert_one({"on_off": on_off})


async def add_off(on_off: int):
    is_off = await is_on_off(on_off)
    if not is_off:
        return
    return await onoffdb.delete_one({"on_off": on_off})


async def is_maintenance():
    if not maintenance:
        get = await onoffdb.find_one({"on_off": 1})
        if not get:
            maintenance.clear()
            maintenance.append(2)
            return True
        else:
            maintenance.clear()
            maintenance.append(1)
            return False
    else:
        if 1 in maintenance:
            return False
        else:
            return True


async def maintenance_off():
    maintenance.clear()
    maintenance.append(2)
    is_off = await is_on_off(1)
    if not is_off:
        return
    return await onoffdb.delete_one({"on_off": 1})


async def maintenance_on():
    maintenance.clear()
    maintenance.append(1)
    is_on = await is_on_off(1)
    if is_on:
        return
    return await onoffdb.insert_one({"on_off": 1})


async def is_served_user(user_id: int) -> bool:
    user = await usersdb.find_one({"user_id": user_id})
    if not user:
        return False
    return True


async def get_served_users() -> list:
    users_list = []
    async for user in usersdb.find({"user_id": {"$gt": 0}}):
        users_list.append(user)
    return users_list


async def add_served_user(user_id: int):
    is_served = await is_served_user(user_id)
    if is_served:
        return
    return await usersdb.insert_one({"user_id": user_id})


async def get_served_chats() -> list:
    chats_list = []
    async for chat in chatsdb.find({"chat_id": {"$lt": 0}}):
        chats_list.append(chat)
    return chats_list


async def is_served_chat(chat_id: int) -> bool:
    chat = await chatsdb.find_one({"chat_id": chat_id})
    if not chat:
        return False
    return True


async def add_served_chat(chat_id: int):
    is_served = await is_served_chat(chat_id)
    if is_served:
        return
    return await chatsdb.insert_one({"chat_id": chat_id})


async def blacklisted_chats() -> list:
    chats_list = []
    async for chat in blacklist_chatdb.find({"chat_id": {"$lt": 0}}):
        chats_list.append(chat["chat_id"])
    return chats_list


async def blacklist_chat(chat_id: int) -> bool:
    if not await blacklist_chatdb.find_one({"chat_id": chat_id}):
        await blacklist_chatdb.insert_one({"chat_id": chat_id})
        return True
    return False


async def whitelist_chat(chat_id: int) -> bool:
    if await blacklist_chatdb.find_one({"chat_id": chat_id}):
        await blacklist_chatdb.delete_one({"chat_id": chat_id})
        return True
    return False


async def _get_authusers(chat_id: int) -> Dict[str, int]:
    _notes = await authuserdb.find_one({"chat_id": chat_id})
    if not _notes:
        return {}
    return _notes["notes"]


async def get_authuser_names(chat_id: int) -> List[str]:
    _notes = []
    for note in await _get_authusers(chat_id):
        _notes.append(note)
    return _notes


async def get_authuser(chat_id: int, name: str) -> Union[bool, dict]:
    name = name
    _notes = await _get_authusers(chat_id)
    if name in _notes:
        return _notes[name]
    else:
        return False


async def save_authuser(chat_id: int, name: str, note: dict):
    name = name
    _notes = await _get_authusers(chat_id)
    _notes[name] = note

    await authuserdb.update_one(
        {"chat_id": chat_id}, {"$set": {"notes": _notes}}, upsert=True
    )


async def delete_authuser(chat_id: int, name: str) -> bool:
    notesd = await _get_authusers(chat_id)
    name = name
    if name in notesd:
        del notesd[name]
        await authuserdb.update_one(
            {"chat_id": chat_id},
            {"$set": {"notes": notesd}},
            upsert=True,
        )
        return True
    return False


async def get_gbanned() -> list:
    results = []
    async for user in gbansdb.find({"user_id": {"$gt": 0}}):
        user_id = user["user_id"]
        results.append(user_id)
    return results


async def is_gbanned_user(user_id: int) -> bool:
    user = await gbansdb.find_one({"user_id": user_id})
    if not user:
        return False
    return True


async def add_gban_user(user_id: int):
    is_gbanned = await is_gbanned_user(user_id)
    if is_gbanned:
        return
    return await gbansdb.insert_one({"user_id": user_id})


async def remove_gban_user(user_id: int):
    is_gbanned = await is_gbanned_user(user_id)
    if not is_gbanned:
        return
    return await gbansdb.delete_one({"user_id": user_id})


async def get_sudoers() -> list:
    sudoers = await sudoersdb.find_one({"sudo": "sudo"})
    if not sudoers:
        return []
    return sudoers["sudoers"]


async def add_sudo(user_id: int) -> bool:
    sudoers = await get_sudoers()
    sudoers.append(user_id)
    await sudoersdb.update_one(
        {"sudo": "sudo"}, {"$set": {"sudoers": sudoers}}, upsert=True
    )
    return True


async def remove_sudo(user_id: int) -> bool:
    sudoers = await get_sudoers()
    sudoers.remove(user_id)
    await sudoersdb.update_one(
        {"sudo": "sudo"}, {"$set": {"sudoers": sudoers}}, upsert=True
    )
    return True


async def get_banned_users() -> list:
    results = []
    async for user in blockeddb.find({"user_id": {"$gt": 0}}):
        user_id = user["user_id"]
        results.append(user_id)
    return results


async def get_banned_count() -> int:
    users = blockeddb.find({"user_id": {"$gt": 0}})
    users = await users.to_list(length=100000)
    return len(users)


async def is_banned_user(user_id: int) -> bool:
    user = await blockeddb.find_one({"user_id": user_id})
    if not user:
        return False
    return True


async def add_banned_user(user_id: int):
    is_gbanned = await is_banned_user(user_id)
    if is_gbanned:
        return
    return await blockeddb.insert_one({"user_id": user_id})


async def remove_banned_user(user_id: int):
    is_gbanned = await is_banned_user(user_id)
    if not is_gbanned:
        return
    return await blockeddb.delete_one({"user_id": user_id})


async def get_filter(chat_id: int) -> str:
    mode = filters.get(chat_id)
    if not mode:
        mode = await filterdb.find_one({"chat_id": chat_id})
        if not mode:
            filters[chat_id] = "Normal"
            return "Normal"
        filters[chat_id] = mode["mode"]
        return mode["mode"]
    return mode


async def set_filter(chat_id: int, mode: str):
    filters[chat_id] = mode
    await filterdb.update_one(
        {"chat_id": chat_id}, {"$set": {"mode": mode}}, upsert=True
    )


async def is_tts_on() -> bool:
    chat_id = 1234
    mode = ttsm.get(chat_id)
    if mode is None:
        user = await ttsdb.find_one({"chat_id": chat_id})
        if not user:
            ttsm[chat_id] = True
            return True
        mode = user.get("mode", True)
        ttsm[chat_id] = mode
        return mode
    return mode


async def tts_on():
    chat_id = 1234
    ttsm[chat_id] = True
    await ttsdb.update_one(
        {"chat_id": chat_id}, {"$set": {"mode": True}}, upsert=True
    )


async def tts_off():
    chat_id = 1234
    ttsm[chat_id] = False
    await ttsdb.update_one(
        {"chat_id": chat_id}, {"$set": {"mode": False}}, upsert=True
    )


async def get_tts_duration() -> int:
    chat_id = 1234
    duration = ttsdur.get(chat_id)
    if duration is None:
        user = await ttsdb.find_one({"chat_id": chat_id})
        if not user:
            ttsdur[chat_id] = 6
            return 6
        dur = user.get("duration", 6)
        ttsdur[chat_id] = dur
        return dur
    return duration


async def set_tts_duration(duration: int):
    chat_id = 1234
    ttsdur[chat_id] = duration
    await ttsdb.update_one(
        {"chat_id": chat_id}, {"$set": {"duration": duration}}, upsert=True
    )


async def get_tts_text() -> str:
    chat_id = 1234
    text = ttstxt.get(chat_id)
    if text is None:
        user = await ttsdb.find_one({"chat_id": chat_id})
        if not user:
            default_text = "Hello, I am Shraddha. Now playing . Thank you for listening!"
            ttstxt[chat_id] = default_text
            return default_text
        text = user.get("text", "Hello, I am Shraddha. Now playing . Thank you for listening!")
        ttstxt[chat_id] = text
        return text
    return text


async def set_tts_text(text: str):
    chat_id = 1234
    ttstxt[chat_id] = text
    await ttsdb.update_one(
        {"chat_id": chat_id}, {"$set": {"text": text}}, upsert=True
    )


# ─── Welcome system helpers ─────────────────────────────────────────────────
# Persistent per-chat enable/disable flag for the welcome message feature.
# State survives bot/dyno/server restarts because it is backed by MongoDB.
# An in-memory cache (welcomem) mirrors the DB row to avoid a Mongo
# round-trip on every ChatMemberUpdated / new_chat_members event.

async def is_welcome_enabled(chat_id: int) -> bool:
    """Return True if welcome messages are enabled for this chat.

    Default is True for any chat that has no DB record yet, so the
    welcome feature is opt-out rather than opt-in.
    """
    cached = welcomem.get(chat_id)
    if cached is not None:
        return cached
    try:
        data = await welcomedb.find_one({"chat_id": chat_id})
        if not data:
            welcomem[chat_id] = True
            return True
        val = bool(data.get("welcome", True))
        welcomem[chat_id] = val
        return val
    except Exception:
        # If Mongo is unreachable, fail-open (welcome stays enabled)
        # so a transient DB hiccup doesn't silently disable the feature.
        return True


async def enable_welcome(chat_id: int) -> None:
    welcomem[chat_id] = True
    try:
        await welcomedb.update_one(
            {"chat_id": chat_id},
            {"$set": {"welcome": True}},
            upsert=True,
        )
    except Exception:
        # Cache is already updated — Mongo write will retry on next toggle.
        pass


async def disable_welcome(chat_id: int) -> None:
    welcomem[chat_id] = False
    try:
        await welcomedb.update_one(
            {"chat_id": chat_id},
            {"$set": {"welcome": False}},
            upsert=True,
        )
    except Exception:
        pass


# ─── Music Cache DB helpers ─────────────────────────────────────────────────
# These wrap music_cache_db with safe, typed accessors. The actual upload +
# cache-lookup orchestration lives in SWAGGYMUSIC/utils/music_cache.py — these
# are only the persistence primitives so the cache module stays small and
# testable.

async def ensure_music_cache_indexes() -> None:
    """Create the indexes needed for fast, dedup-safe cache lookups.

    Idempotent — safe to call on every boot. Motor raises OperationFailure
    if an index already exists, which we swallow.

    Indexes:
      - video_id (1) + media_type (1)   ← unique compound, the primary lookup
      - file_unique_id (1)              ← reverse-lookup / dedup check
      - normalized_title (1)             ← optional fuzzy search (not unique)
    """
    try:
        await music_cache_db.create_index(
            [("video_id", 1), ("media_type", 1)],
            unique=True,
            name="uniq_video_media",
        )
    except Exception:
        # Index already exists — fine.
        pass
    try:
        await music_cache_db.create_index(
            [("file_unique_id", 1)],
            name="file_unique_id",
        )
    except Exception:
        pass
    try:
        await music_cache_db.create_index(
            [("normalized_title", 1)],
            name="normalized_title",
        )
    except Exception:
        pass


async def get_cached_track(video_id: str, media_type: str) -> Union[dict, None]:
    """Return the cached track document for (video_id, media_type) or None.

    media_type is 'audio' or 'video'. The caller is responsible for
    validating that the returned Telegram file_id is still usable.
    """
    if not video_id or not media_type:
        return None
    try:
        return await music_cache_db.find_one(
            {"video_id": str(video_id), "media_type": str(media_type)}
        )
    except Exception:
        return None


async def save_cached_track(doc: dict) -> bool:
    """Insert or update a cached track. Returns True on success.

    Uses upsert on the (video_id, media_type) unique key so duplicate uploads
    can never produce two documents — the second upload simply overwrites the
    first record with a fresh file_id/message_id.
    """
    if not doc:
        return False
    video_id = doc.get("video_id")
    media_type = doc.get("media_type")
    if not video_id or not media_type:
        return False
    try:
        await music_cache_db.update_one(
            {"video_id": str(video_id), "media_type": str(media_type)},
            {"$set": doc},
            upsert=True,
        )
        return True
    except Exception:
        return False


async def invalidate_cached_track(video_id: str, media_type: str) -> None:
    """Delete a cache entry. Called when a cached Telegram file turns out
    to be unusable (deleted from the storage channel, file_id stale, etc.)."""
    if not video_id or not media_type:
        return
    try:
        await music_cache_db.delete_one(
            {"video_id": str(video_id), "media_type": str(media_type)}
        )
    except Exception:
        pass


async def is_track_cached(video_id: str, media_type: str) -> bool:
    """Lightweight existence check — used by the cache-upload scheduler to
    skip uploading songs that are already cached.

    Fix 5: A MongoDB document merely existing does NOT mean the song is
    successfully cached. This function validates that the record has all
    required fields (video_id, media_type, file_id, file_unique_id,
    channel_id, message_id). If a malformed/incomplete record exists,
    it is treated as invalid → returns False (so the song can be
    re-cached). The malformed record is also repaired (deleted) so it
    doesn't block future caching attempts.
    """
    if not video_id or not media_type:
        return False
    try:
        doc = await music_cache_db.find_one(
            {"video_id": str(video_id), "media_type": str(media_type)},
        )
        if doc is None:
            return False
        # Fix 5: validate required fields.
        required = (
            "video_id", "media_type", "file_id", "file_unique_id",
            "channel_id", "message_id",
        )
        for field in required:
            val = doc.get(field)
            if val is None or val == "" or val == 0:
                # Malformed record — repair (delete) it so the song can
                # be re-cached.
                try:
                    await music_cache_db.delete_one(
                        {"video_id": str(video_id),
                         "media_type": str(media_type)}
                    )
                except Exception:
                    pass
                return False
        return True
    except Exception:
        return False
