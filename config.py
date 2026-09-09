#
# Copyright (C) 2021-2022 by SWAGGYMUSIC@Github, < https://github.com/Yuki77394/NEWSRMUSIC >.
#
# This file is part of < https://github.com/Yuki77394/NEWSRMUSIC > project,
# and is released under the "GNU v3.0 License Agreement".
# Please see < https://github.com/Yuki77394/NEWSRMUSIC/blob/master/LICENSE >
# All rights reserved.

import re
from os import getenv

from dotenv import load_dotenv
from pyrogram import filters
from os import getenv
import random

RANDOM_THUMBS = [
    "https://files.catbox.moe/jf0yqq.jpg",
    "https://files.catbox.moe/7w0ec2.jpg",
    "https://files.catbox.moe/dfj1l8.jpg",
    "https://files.catbox.moe/e7pbwj.jpg",
    "https://files.catbox.moe/bta4qz.jpg",
    "https://files.catbox.moe/1a1pu2.jpg",
    "https://files.catbox.moe/xvirq4.jpg",
    "https://files.catbox.moe/8dyj3u.jpg",
    "https://files.catbox.moe/x63yfj.jpg",
    "https://files.catbox.moe/3rtw9v.jpg",
    "https://files.catbox.moe/0u6db2.jpg",
]

def get_thumb():
    return random.choice(RANDOM_THUMBS)


START_IMG_URL = getenv("START_IMG_URL", get_thumb())
PING_IMG_URL = getenv("PING_IMG_URL", get_thumb())

PLAYLIST_IMG_URL = get_thumb()
STATS_IMG_URL = get_thumb()
TELEGRAM_AUDIO_URL = get_thumb()
TELEGRAM_VIDEO_URL = get_thumb()
STREAM_IMG_URL = get_thumb()
SOUNCLOUD_IMG_URL = get_thumb()
YOUTUBE_IMG_URL = get_thumb()
SPOTIFY_ARTIST_IMG_URL = get_thumb()
SPOTIFY_ALBUM_IMG_URL = get_thumb()
SPOTIFY_PLAYLIST_IMG_URL = get_thumb()

load_dotenv()
YTPROXY_URL = getenv("YTPROXY_URL", 'https://tgapi.xbitcode.com') ## xBit Music Endpoint.
YT_API_KEY = getenv("YT_API_KEY" , "xbit_KiY0HWimxyDMVxjg6R7-7UtJKyPW9kSD")

# Get this value from my.telegram.org/apps
API_ID = int(getenv("API_ID", 0))
API_HASH = getenv("API_HASH")

# Get your token from @BotFather on Telegram.
BOT_TOKEN = getenv("BOT_TOKEN")

# Get your mongo url from cloud.mongodb.com
MONGO_DB_URI = getenv("MONGO_DB_URI", None)

DURATION_LIMIT_MIN = int(getenv("DURATION_LIMIT", 18000))

# Set this to true if you want post ads automatically
ADS_MODE = getenv("ADS_MODE", None)

# Chat id of a group for logging bot's activities
LOGGER_ID = int(getenv("LOGGER_ID", 0))

DEBUG_IGNORE_LOG = True
# Get this value from  on Telegram by /id
OWNER_ID = int(getenv("OWNER_ID", 0))

## Fill these variables if you're deploying on heroku.
# Your heroku app name
HEROKU_APP_NAME = getenv("HEROKU_APP_NAME")
# Get it from http://dashboard.heroku.com/account
HEROKU_API_KEY = getenv("HEROKU_API_KEY")

UPSTREAM_REPO = getenv(
    "UPSTREAM_REPO",
    "https://github.com/Yuki77394/SRMUSICNEW",
)
UPSTREAM_BRANCH = getenv("UPSTREAM_BRANCH", "main")
GIT_TOKEN = getenv(
    "GIT_TOKEN", None
)  # Fill this variable if your upstream repository is private


SUPPORT_CHANNEL = getenv("SUPPORT_CHANNEL", "https://t.me/+sTyS-zKwUIk4YWI1")
SUPPORT_CHAT = getenv("SUPPORT_CHAT", "https://t.me/SpIcYxNeTwOrK")
# Set this to True if you want the assistant to automatically leave chats after an interval
AUTO_LEAVING_ASSISTANT = bool(getenv("AUTO_LEAVING_ASSISTANT", False))

# Privacy policy link for the bot
PRIVACY_LINK = getenv("PRIVACY_LINK", "https://telegra.ph/Privacy-Policy-for-SWAGGYMUSIC-08-14")


# ─── Telegram Storage Channel + MongoDB Music Cache ─────────────────────────
# ID of the *private* Telegram channel used as permanent music storage.
# Must be a numeric id with -100 prefix, e.g. -1001234567890.
# Leave unset/0 to disable the cache system gracefully.
STORAGE_CHANNEL_ID = int(getenv("STORAGE_CHANNEL_ID", 0) or 0)

# Master toggle for the music cache subsystem. When False, the bot behaves
# exactly as before (no MongoDB lookup, no background channel upload).
MUSIC_CACHE_ENABLED = str(getenv("MUSIC_CACHE_ENABLED", "true")).lower() in (
    "1", "true", "yes", "on",
)

# Maximum number of simultaneous background uploads to the storage channel.
# Playback is NEVER throttled by this — only the cache-upload workers.
try:
    CACHE_UPLOAD_CONCURRENCY = int(getenv("CACHE_UPLOAD_CONCURRENCY", "2"))
except (TypeError, ValueError):
    CACHE_UPLOAD_CONCURRENCY = 2
if CACHE_UPLOAD_CONCURRENCY < 1:
    CACHE_UPLOAD_CONCURRENCY = 2


# Get this credentials from https://developer.spotify.com/dashboard
SPOTIFY_CLIENT_ID = getenv("SPOTIFY_CLIENT_ID", None)
SPOTIFY_CLIENT_SECRET = getenv("SPOTIFY_CLIENT_SECRET", None)


# Maximum limit for fetching playlist's track from youtube, spotify, apple links.
PLAYLIST_FETCH_LIMIT = int(getenv("PLAYLIST_FETCH_LIMIT", 25))


# Telegram audio and video file size limit (in bytes)
TG_AUDIO_FILESIZE_LIMIT = int(getenv("TG_AUDIO_FILESIZE_LIMIT", 104857600))
TG_VIDEO_FILESIZE_LIMIT = int(getenv("TG_VIDEO_FILESIZE_LIMIT", 1073741824))
# Checkout https://www.gbmb.org/mb-to-bytes for converting mb to bytes


# Get your pyrogram v2 session from @StringFatherBot on Telegram
STRING1 = getenv("STRING_SESSION", None)
STRING2 = getenv("STRING_SESSION2", None)
STRING3 = getenv("STRING_SESSION3", None)
STRING4 = getenv("STRING_SESSION4", None)
STRING5 = getenv("STRING_SESSION5", None)


BANNED_USERS = filters.user()
adminlist = {}
lyrical = {}
votemode = {}
autoclean = []
confirmer = {}

"""
START_IMG_URL = getenv(
    "START_IMG_URL",
    "https://files.catbox.moe/abplbz.jpg",
)
PING_IMG_URL = getenv(
    "PING_IMG_URL",
    "https://files.catbox.moe/3picc9.jpg",
)
PLAYLIST_IMG_URL = "https://files.catbox.moe/34xlvu.jpg"
STATS_IMG_URL = "https://files.catbox.moe/34xlvu.jpg"
TELEGRAM_AUDIO_URL = "https://files.catbox.moe/34xlvu.jpg"
TELEGRAM_VIDEO_URL = "https://files.catbox.moe/34xlvu.jpg"
STREAM_IMG_URL = "https://files.catbox.moe/34xlvu.jpg"
SOUNCLOUD_IMG_URL = "https://files.catbox.moe/34xlvu.jpg"
YOUTUBE_IMG_URL = "https://files.catbox.moe/34xlvu.jpg"
SPOTIFY_ARTIST_IMG_URL = "https://files.catbox.moe/34xlvu.jpg"
SPOTIFY_ALBUM_IMG_URL = "https://files.catbox.moe/34xlvu.jpg"
SPOTIFY_PLAYLIST_IMG_URL = "https://files.catbox.moe/34xlvu.jpg"
"""

def time_to_seconds(time):
    stringt = str(time)
    return sum(int(x) * 60**i for i, x in enumerate(reversed(stringt.split(":"))))


DURATION_LIMIT = int(time_to_seconds(f"{DURATION_LIMIT_MIN}:00"))


if SUPPORT_CHANNEL:
    if not re.match("(?:http|https)://", SUPPORT_CHANNEL):
        raise SystemExit(
            "[ERROR] - Your SUPPORT_CHANNEL url is wrong. Please ensure that it starts with https://"
        )

if SUPPORT_CHAT:
    if not re.match("(?:http|https)://", SUPPORT_CHAT):
        raise SystemExit(
            "[ERROR] - Your SUPPORT_CHAT url is wrong. Please ensure that it starts with https://"
        )
