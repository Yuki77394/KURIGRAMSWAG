import asyncio
import json
import logging
import os
import random
import re
import urllib.parse
from typing import Union

import aiohttp
import yt_dlp
from py_yt import VideosSearch
from pyrogram.enums import MessageEntityType
from pyrogram.types import Message


API_URL = os.environ.get(
    "SHRUTI_API_URL",
    "https://api01.shrutibots.site",
).rstrip("/")

API_KEY = os.environ.get(
    "SHRUTI_API_KEY",
    "ShrutiBotslhO8FIaHdScR3G2JtmuD",
).strip()

DOWNLOAD_DIR = "downloads"

LOGGER = logging.getLogger(__name__)

os.makedirs(
    DOWNLOAD_DIR,
    exist_ok=True,
)

# Shared per-video download locks. Both normal playback and background
# prefetch use YouTube.download(), so this prevents them from writing the same
# .part/final file concurrently during rapid skips or queue transitions.
_download_locks = {}
_download_locks_guard = None


async def _get_download_lock(video_key: str, media_type: str):
    """Return a shared per-media lock and register one active user.

    The user count includes callers waiting for the lock, so cleanup can never
    remove a lock while another playback/prefetch task is still waiting on it.
    """
    global _download_locks_guard

    if _download_locks_guard is None:
        _download_locks_guard = asyncio.Lock()

    key = (video_key, media_type)

    async with _download_locks_guard:
        entry = _download_locks.get(key)

        if entry is None:
            entry = {
                "lock": asyncio.Lock(),
                "users": 0,
            }
            _download_locks[key] = entry

        entry["users"] += 1

        return (
            key,
            entry["lock"],
            entry,
        )


async def _release_download_lock(
    key,
    lock,
    entry,
):
    """Release one registered lock user and safely clean up unused entries."""
    global _download_locks_guard

    if _download_locks_guard is None:
        return

    async with _download_locks_guard:
        current_entry = _download_locks.get(key)

        # Only touch the exact entry originally registered by this caller.
        # This prevents an old caller from deleting a newer entry.
        if current_entry is not entry:
            return

        entry["users"] = max(
            0,
            int(entry.get("users", 0)) - 1,
        )

        # A lock can be removed only when nobody owns it AND nobody is waiting.
        if (
            entry["users"] == 0
            and not lock.locked()
        ):
            _download_locks.pop(
                key,
                None,
            )


def _download_lock_key(link: str):
    video_id = extract_video_id(link)
    return video_id or str(link or "")


async def _has_audio_stream(file_path: str) -> bool:
    """Verify that a media file actually contains an audio stream using ffprobe.

    Returns True if the file has at least one audio stream, False otherwise
    (including when ffprobe is unavailable or the file is corrupt).
    """
    if not file_path or not os.path.isfile(file_path):
        return False

    try:
        proc = await asyncio.create_subprocess_exec(
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "a",
            "-show_entries",
            "stream=codec_type",
            "-of",
            "json",
            file_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=15)
        if proc.returncode != 0:
            return False
        data = json.loads(stdout.decode("utf-8", errors="ignore"))
        streams = data.get("streams", [])
        return any(s.get("codec_type") == "audio" for s in streams)
    except Exception:
        return False


async def _has_video_stream(file_path: str) -> bool:
    """Verify that a media file actually contains a video stream using ffprobe."""
    if not file_path or not os.path.isfile(file_path):
        return False

    try:
        proc = await asyncio.create_subprocess_exec(
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v",
            "-show_entries",
            "stream=codec_type",
            "-of",
            "json",
            file_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=15)
        if proc.returncode != 0:
            return False
        data = json.loads(stdout.decode("utf-8", errors="ignore"))
        streams = data.get("streams", [])
        return any(s.get("codec_type") == "video" for s in streams)
    except Exception:
        return False


async def _ytdlp_fallback(link: str, media_type: str) -> Union[str, None]:
    """Fallback downloader using yt-dlp directly when the API download fails
    or produces a file with no audio/video stream.

    media_type: 'audio' or 'video'
    """
    video_id = extract_video_id(link)
    if not video_id:
        return None

    ext = "mp4" if media_type == "video" else "mp3"
    file_path = os.path.join(DOWNLOAD_DIR, f"{video_id}.{ext}")

    if os.path.isfile(file_path) and os.path.getsize(file_path) > 1024:
        if media_type == "audio" and await _has_audio_stream(file_path):
            return file_path
        if media_type == "video" and await _has_video_stream(file_path):
            return file_path
        try:
            os.remove(file_path)
        except Exception:
            pass

    out_template = os.path.join(DOWNLOAD_DIR, f"{video_id}.%(ext)s")

    if media_type == "audio":
        ydl_opts = {
            "format": "bestaudio/best",
            "outtmpl": out_template,
            "quiet": True,
            "no_warnings": True,
            "noprogress": True,
            "default_search": "auto",
            "source_address": "0.0.0.0",
            "nocheckcertificate": True,
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "192",
                }
            ],
        }
    else:
        ydl_opts = {
            "format": "best[ext=mp4][height<=720]/best[ext=mp4]/best",
            "outtmpl": out_template,
            "quiet": True,
            "no_warnings": True,
            "noprogress": True,
            "default_search": "auto",
            "source_address": "0.0.0.0",
            "nocheckcertificate": True,
            "merge_output_format": "mp4",
        }

    def _do_download():
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([link])

    try:
        await asyncio.get_event_loop().run_in_executor(None, _do_download)
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        LOGGER.exception(
            "yt-dlp fallback failed: video=%s type=%s error=%r",
            video_id,
            media_type,
            exc,
        )
        return None

    if os.path.isfile(file_path) and os.path.getsize(file_path) > 1024:
        if media_type == "audio" and await _has_audio_stream(file_path):
            return file_path
        if media_type == "video" and await _has_video_stream(file_path):
            return file_path
        try:
            os.remove(file_path)
        except Exception:
            pass
        LOGGER.error(
            "yt-dlp produced an invalid media file: video=%s type=%s path=%s",
            video_id,
            media_type,
            file_path,
        )

    return None


def time_to_seconds(time):
    if not time:
        return 0

    try:
        stringt = str(time)

        if stringt.upper() in (
            "LIVE",
            "NONE",
        ):
            return 0

        return sum(
            int(x) * 60 ** i
            for i, x in enumerate(
                reversed(
                    stringt.split(":")
                )
            )
        )

    except Exception:
        return 0


def extract_video_id(link: str):
    if not link:
        return None

    link = str(link).strip()

    if len(link) == 11 and "://" not in link:
        return link

    patterns = [
        r"(?:v=)([A-Za-z0-9_-]{11})",
        r"youtu\.be/([A-Za-z0-9_-]{11})",
        r"/shorts/([A-Za-z0-9_-]{11})",
        r"/embed/([A-Za-z0-9_-]{11})",
        r"/live/([A-Za-z0-9_-]{11})",
    ]

    for pattern in patterns:
        match = re.search(
            pattern,
            link,
        )

        if match:
            return match.group(1)

    return None


def normalize_youtube_url(link: str):
    if not link:
        return ""

    link = str(link).strip()

    video_id = extract_video_id(
        link
    )

    if video_id:
        return (
            "https://www.youtube.com/"
            f"watch?v={video_id}"
        )

    return link


async def _api_download(
    link: str,
    media_type: str,
):
    video_id = extract_video_id(
        link
    )

    if not video_id:
        return None

    ext = (
        "mp4"
        if media_type == "video"
        else "mp3"
    )

    file_path = os.path.join(
        DOWNLOAD_DIR,
        f"{video_id}.{ext}",
    )

    if (
        os.path.isfile(file_path)
        and os.path.getsize(file_path)
        > 1024
    ):
        return file_path

    temp_path = (
        file_path
        + ".part"
    )

    try:

        timeout = aiohttp.ClientTimeout(
            total=600,
            connect=30,
            sock_connect=30,
            sock_read=120,
        )

        params = {
            "url": video_id,
            "type": media_type,
            "api_key": API_KEY,
        }

        headers = {
            "User-Agent": (
                "Mozilla/5.0 "
                "(X11; Linux x86_64) "
                "AppleWebKit/537.36 "
                "Chrome/131 Safari/537.36"
            )
        }

        async with aiohttp.ClientSession(
            timeout=timeout,
            headers=headers,
        ) as session:

            async with session.get(
                f"{API_URL}/download",
                params=params,
            ) as response:

                if response.status != 200:
                    LOGGER.error(
                        "YouTube API download failed: video=%s type=%s status=%s url=%s",
                        video_id,
                        media_type,
                        response.status,
                        API_URL,
                    )
                    return None

                content_type = (
                    response.headers.get(
                        "Content-Type",
                        "",
                    )
                    .lower()
                )

                if (
                    "text/html"
                    in content_type
                    or "application/json"
                    in content_type
                ):
                    LOGGER.error(
                        "YouTube API returned non-media response: video=%s type=%s content_type=%s",
                        video_id,
                        media_type,
                        content_type,
                    )
                    return None

                size = 0

                with open(
                    temp_path,
                    "wb",
                ) as file:

                    async for chunk in (
                        response.content.iter_chunked(
                            131072
                        )
                    ):

                        if chunk:
                            file.write(
                                chunk
                            )

                            size += len(
                                chunk
                            )

                if size < 1024:
                    if os.path.exists(
                        temp_path
                    ):
                        os.remove(
                            temp_path
                        )

                    return None

                if (
                    media_type == "audio"
                    and size < 2048
                ):
                    return None

                if os.path.exists(
                    file_path
                ):
                    os.remove(
                        file_path
                    )

                os.replace(
                    temp_path,
                    file_path,
                )

                if media_type == "audio" and not await _has_audio_stream(file_path):
                    LOGGER.error(
                        "YouTube API produced file without audio stream: video=%s path=%s",
                        video_id,
                        file_path,
                    )
                    try:
                        os.remove(file_path)
                    except Exception:
                        pass
                    return None

                if media_type == "video" and not await _has_video_stream(file_path):
                    LOGGER.error(
                        "YouTube API produced file without video stream: video=%s path=%s",
                        video_id,
                        file_path,
                    )
                    try:
                        os.remove(file_path)
                    except Exception:
                        pass
                    return None

                return file_path

    except asyncio.CancelledError:
        raise
    except Exception as exc:
        LOGGER.exception(
            "YouTube API downloader exception: video=%s type=%s error=%r",
            video_id,
            media_type,
            exc,
        )

        if os.path.exists(
            temp_path
        ):

            try:
                os.remove(
                    temp_path
                )

            except Exception:
                pass

        return None


async def download_song(
    link: str,
) -> str:

    result = await _api_download(
        link,
        "audio",
    )

    if result:
        return result

    return await _ytdlp_fallback(
        link,
        "audio",
    )


async def download_video(
    link: str,
) -> str:

    result = await _api_download(
        link,
        "video",
    )

    if result:
        return result

    return await _ytdlp_fallback(
        link,
        "video",
    )


class YouTubeAPI:

    def __init__(self):

        self.base = (
            "https://www.youtube.com/"
            "watch?v="
        )

        self.regex = (
            r"(?:youtube\.com|youtu\.be)"
        )

        self.status = (
            "https://www.youtube.com/"
            "oembed?url="
        )

        self.listbase = (
            "https://www.youtube.com/"
            "playlist?list="
        )

        self.reg = re.compile(
            r"\x1B(?:[@-Z\\-_]"
            r"|\[[0-?]*[ -/]*[@-~])"
        )

    async def exists(
        self,
        link: str,
        videoid: Union[bool, str] = None,
    ):

        if videoid:
            link = (
                self.base
                + str(link)
            )

        return bool(
            re.search(
                self.regex,
                str(link),
                re.IGNORECASE,
            )
        )

    async def url(
        self,
        message_1: Message,
    ) -> Union[str, None]:

        messages = [
            message_1,
        ]

        if (
            message_1.reply_to_message
        ):
            messages.append(
                message_1.reply_to_message
            )

        for message in messages:

            text = (
                message.text
                or message.caption
                or ""
            )

            entities = (
                message.entities
                or message.caption_entities
                or []
            )

            for entity in entities:

                if (
                    entity.type
                    == MessageEntityType.TEXT_LINK
                ):

                    if entity.url:
                        return entity.url

                elif (
                    entity.type
                    == MessageEntityType.URL
                ):

                    return text[
                        entity.offset:
                        entity.offset
                        + entity.length
                    ]

        return None

    async def _search(
        self,
        link: str,
        limit: int = 1,
    ):

        try:

            search = VideosSearch(
                link,
                limit=limit,
            )

            data = (
                await search.next()
            )

            return (
                data.get(
                    "result",
                    [],
                )
                or []
            )

        except Exception:

            return []

    async def _get_result(
        self,
        link: str,
    ):

        link = normalize_youtube_url(
            link
        )

        results = await self._search(
            link,
            limit=1,
        )

        if not results:
            return None

        return results[0]

    def _parse_result(
        self,
        result,
    ):

        if not result:
            return (
                None,
                None,
                0,
                None,
                None,
            )

        title = result.get(
            "title"
        )

        duration_min = (
            result.get(
                "duration"
            )
            or "0:00"
        )

        duration_sec = (
            time_to_seconds(
                duration_min
            )
        )

        thumbnails = (
            result.get(
                "thumbnails",
                [],
            )
            or []
        )

        thumbnail = None

        if thumbnails:

            first = thumbnails[0]

            if isinstance(
                first,
                dict,
            ):

                thumbnail = (
                    first.get(
                        "url"
                    )
                )

            else:

                thumbnail = str(
                    first
                )

            if thumbnail:
                thumbnail = (
                    thumbnail.split(
                        "?"
                    )[0]
                )

        vidid = (
            result.get(
                "id"
            )
        )

        return (
            title,
            duration_min,
            duration_sec,
            thumbnail,
            vidid,
        )

    async def details(
        self,
        link: str,
        videoid: Union[bool, str] = None,
    ):

        if videoid:

            link = (
                self.base
                + str(link)
            )

        result = await self._get_result(
            link
        )

        return self._parse_result(
            result
        )

    async def title(
        self,
        link: str,
        videoid: Union[bool, str] = None,
    ):

        if videoid:

            link = (
                self.base
                + str(link)
            )

        result = await self._get_result(
            link
        )

        if result:

            return result.get(
                "title"
            )

        return None

    async def duration(
        self,
        link: str,
        videoid: Union[bool, str] = None,
    ):

        if videoid:

            link = (
                self.base
                + str(link)
            )

        result = await self._get_result(
            link
        )

        if result:

            return result.get(
                "duration"
            )

        return None

    async def thumbnail(
        self,
        link: str,
        videoid: Union[bool, str] = None,
    ):

        if videoid:

            link = (
                self.base
                + str(link)
            )

        result = await self._get_result(
            link
        )

        if not result:

            return None

        thumbnails = (
            result.get(
                "thumbnails",
                [],
            )
            or []
        )

        if not thumbnails:

            return None

        first = thumbnails[0]

        if isinstance(
            first,
            dict,
        ):

            return (
                first.get(
                    "url"
                )
                or ""
            ).split("?")[0]

        return str(first).split(
            "?"
        )[0]

    async def video(
        self,
        link: str,
        videoid: Union[bool, str] = None,
    ):

        if videoid:

            link = (
                self.base
                + str(link)
            )

        try:

            downloaded_file = (
                await download_video(
                    link
                )
            )

            if downloaded_file:

                return (
                    1,
                    downloaded_file,
                )

            return (
                0,
                "Video download failed",
            )

        except Exception as e:

            return (
                0,
                f"Video download error: {e}",
            )

    async def playlist(
        self,
        link,
        limit,
        user_id,
        videoid: Union[bool, str] = None,
    ):

        if videoid:

            link = (
                self.listbase
                + str(link)
            )

        try:

            loop = (
                asyncio.get_running_loop()
            )

            ydl_opts = {
                "quiet": True,
                "extract_flat": True,
                "skip_download": True,
                "ignoreerrors": True,
                "playlistend": int(
                    limit
                ),
            }

            def extract():

                with yt_dlp.YoutubeDL(
                    ydl_opts
                ) as ydl:

                    return (
                        ydl.extract_info(
                            link,
                            download=False,
                        )
                    )

            info = (
                await loop.run_in_executor(
                    None,
                    extract,
                )
            )

            if not info:
                return []

            ids = []

            for entry in (
                info.get(
                    "entries",
                    [],
                )
                or []
            ):

                if not entry:
                    continue

                vid = entry.get(
                    "id"
                )

                if (
                    vid
                    and vid not in ids
                ):
                    ids.append(
                        vid
                    )

            return ids[
                :int(limit)
            ]

        except Exception:

            return []

    async def get_related_videos(
        self,
        vidid: str,
    ):

        if not vidid:
            return []

        seen = {
            vidid,
        }

        related = []

        try:

            radio_url = (
                f"{self.base}{vidid}"
                f"&list=RD{vidid}"
            )

            ydl_opts = {
                "quiet": True,
                "extract_flat": True,
                "skip_download": True,
                "ignoreerrors": True,
                "playlist_items": "2-20",
            }

            loop = (
                asyncio.get_running_loop()
            )

            def extract():

                with yt_dlp.YoutubeDL(
                    ydl_opts
                ) as ydl:

                    return (
                        ydl.extract_info(
                            radio_url,
                            download=False,
                        )
                    )

            info = (
                await loop.run_in_executor(
                    None,
                    extract,
                )
            )

            if info:

                for entry in (
                    info.get(
                        "entries",
                        [],
                    )
                    or []
                ):

                    if not entry:
                        continue

                    entry_id = (
                        entry.get(
                            "id"
                        )
                    )

                    duration = (
                        entry.get(
                            "duration"
                        )
                        or 0
                    )

                    if (
                        entry_id
                        and entry_id
                        not in seen
                    ):

                        if (
                            duration
                            and duration
                            > 600
                        ):
                            continue

                        seen.add(
                            entry_id
                        )

                        related.append(
                            entry_id
                        )

            if related:
                return related

        except Exception:
            pass

        try:

            current_title = (
                await self.title(
                    vidid,
                    True,
                )
            )

            if current_title:

                results = (
                    await self._search(
                        f"{current_title} songs",
                        limit=20,
                    )
                )

                for result in results:

                    result_id = (
                        result.get(
                            "id"
                        )
                    )

                    duration = (
                        time_to_seconds(
                            result.get(
                                "duration"
                            )
                        )
                    )

                    if (
                        not result_id
                        or result_id
                        in seen
                    ):
                        continue

                    if (
                        duration
                        and duration
                        > 600
                    ):
                        continue

                    seen.add(
                        result_id
                    )

                    related.append(
                        result_id
                    )

            if related:
                return related

        except Exception:
            pass

        queries = [
            "Latest Hindi Songs",
            "Trending Bollywood Songs",
            "Indian Pop Songs",
            "Latest English Songs",
            "Trending Music",
        ]

        try:

            random.shuffle(
                queries
            )

            for query in queries:

                results = (
                    await self._search(
                        query,
                        limit=20,
                    )
                )

                for result in results:

                    result_id = (
                        result.get(
                            "id"
                        )
                    )

                    duration = (
                        time_to_seconds(
                            result.get(
                                "duration"
                            )
                        )
                    )

                    if (
                        not result_id
                        or result_id
                        in seen
                    ):
                        continue

                    if (
                        duration
                        and duration
                        > 600
                    ):
                        continue

                    seen.add(
                        result_id
                    )

                    related.append(
                        result_id
                    )

                if related:
                    return related

        except Exception:
            pass

        return []

    async def track(
        self,
        link: str,
        videoid: Union[bool, str] = None,
    ):

        if videoid:

            link = (
                self.base
                + str(link)
            )

        result = await self._get_result(
            link
        )

        if not result:

            return (
                None,
                None,
            )

        title = result.get(
            "title"
        )

        duration_min = (
            result.get(
                "duration"
            )
            or "0:00"
        )

        vidid = (
            result.get(
                "id"
            )
        )

        yturl = (
            result.get(
                "link"
            )
            or (
                self.base
                + str(vidid)
            )
        )

        thumbnails = (
            result.get(
                "thumbnails",
                [],
            )
            or []
        )

        thumbnail = None

        if thumbnails:

            first = thumbnails[0]

            if isinstance(
                first,
                dict,
            ):

                thumbnail = (
                    first.get(
                        "url"
                    )
                )

            else:

                thumbnail = str(
                    first
                )

            if thumbnail:
                thumbnail = (
                    thumbnail.split(
                        "?"
                    )[0]
                )

        track_details = {
            "title": title,
            "link": yturl,
            "vidid": vidid,
            "duration_min": duration_min,
            "thumb": thumbnail,
        }

        return (
            track_details,
            vidid,
        )

    async def formats(
        self,
        link: str,
        videoid: Union[bool, str] = None,
    ):

        if videoid:

            link = (
                self.base
                + str(link)
            )

        link = normalize_youtube_url(
            link
        )

        try:

            loop = (
                asyncio.get_running_loop()
            )

            def extract():

                ydl_opts = {
                    "quiet": True,
                    "no_warnings": True,
                    "noplaylist": True,
                }

                with yt_dlp.YoutubeDL(
                    ydl_opts
                ) as ydl:

                    return (
                        ydl.extract_info(
                            link,
                            download=False,
                        )
                    )

            info = (
                await loop.run_in_executor(
                    None,
                    extract,
                )
            )

            formats_available = []

            for fmt in (
                info.get(
                    "formats",
                    [],
                )
                or []
            ):

                try:

                    if (
                        "dash"
                        in str(
                            fmt.get(
                                "format",
                                "",
                            )
                        ).lower()
                    ):
                        continue

                    formats_available.append(
                        {
                            "format": fmt.get(
                                "format"
                            ),
                            "filesize": fmt.get(
                                "filesize"
                            ),
                            "format_id": fmt.get(
                                "format_id"
                            ),
                            "ext": fmt.get(
                                "ext"
                            ),
                            "format_note": fmt.get(
                                "format_note"
                            ),
                            "yturl": link,
                        }
                    )

                except Exception:
                    continue

            return (
                formats_available,
                link,
            )

        except Exception:

            return (
                [],
                link,
            )

    async def slider(
        self,
        link: str,
        query_type: int,
        videoid: Union[bool, str] = None,
    ):

        if videoid:

            link = (
                self.base
                + str(link)
            )

        try:

            result = (
                await self._search(
                    link,
                    limit=10,
                )
            )

            if (
                not result
                or len(result)
                <= query_type
            ):

                return (
                    None,
                    None,
                    None,
                    None,
                )

            data = result[
                query_type
            ]

            title = data.get(
                "title"
            )

            duration_min = (
                data.get(
                    "duration"
                )
            )

            vidid = data.get(
                "id"
            )

            thumbnails = (
                data.get(
                    "thumbnails",
                    [],
                )
                or []
            )

            thumbnail = None

            if thumbnails:

                first = thumbnails[0]

                if isinstance(
                    first,
                    dict,
                ):

                    thumbnail = (
                        first.get(
                            "url"
                        )
                    )

                else:

                    thumbnail = str(
                        first
                    )

                if thumbnail:

                    thumbnail = (
                        thumbnail.split(
                            "?"
                        )[0]
                    )

            return (
                title,
                duration_min,
                thumbnail,
                vidid,
            )

        except Exception:

            return (
                None,
                None,
                None,
                None,
            )

    async def download(
        self,
        link: str,
        mystic,
        video: Union[bool, str] = None,
        videoid: Union[bool, str] = None,
        songaudio: Union[bool, str] = None,
        songvideo: Union[bool, str] = None,
        format_id: Union[bool, str] = None,
        title: Union[bool, str] = None,
        duration: Union[bool, str] = None,
        thumbnail: Union[bool, str] = None,
    ):

        if videoid:
            link = (
                self.base
                + str(link)
            )

        media_type = "video" if (video or songvideo) else "audio"

        # ─── Mongo Cache Lookup (BEFORE acquiring the download lock) ────────
        # Try to satisfy this request from the Telegram storage channel
        # cache. On hit we return immediately — no YouTube download, no
        # download lock contention. On miss we fall through to the existing
        # download flow unchanged.
        #
        # The cache lookup is intentionally OUTSIDE the per-video download
        # lock so a cache hit doesn't block (or get blocked by) other
        # downloads of the same video. Duplicate-upload protection is
        # handled separately inside music_cache._cache_upload_worker.
        resolved_video_id = extract_video_id(link)
        if resolved_video_id:
            try:
                from SWAGGYMUSIC.utils import music_cache
                cached_path = await music_cache.try_cached_download(
                    resolved_video_id, media_type
                )
                if cached_path:
                    # Cache HIT — return immediately. The file is already
                    # on disk in the downloads/ directory with the same
                    # naming convention YouTube.download() would have used.
                    return (cached_path, True)
            except Exception:
                # Any cache failure is non-fatal — fall through to the
                # normal download path so playback is never broken by a
                # cache subsystem hiccup.
                pass

        (
            lock_key,
            lock,
            lock_entry,
        ) = await _get_download_lock(
            _download_lock_key(link),
            media_type,
        )

        try:
            async with lock:
                # Reaching this lock after another caller finished means the
                # existing downloader cache checks will return immediately.
                if media_type == "video":
                    downloaded_file = await download_video(link)
                else:
                    downloaded_file = await download_song(link)

                if downloaded_file:
                    # ─── Background cache upload (fire-and-forget) ────────
                    # Schedule an upload of the just-downloaded file to the
                    # private Telegram storage channel. This NEVER blocks
                    # playback — schedule_cache_upload spawns an asyncio
                    # task and returns immediately. The task acquires a
                    # file_refs reference so auto_clean can't delete the
                    # file mid-upload.
                    #
                    # Fix 9: pass title/duration/thumbnail through when the
                    # caller already has them (avoids a duplicate
                    # YouTube.details() call in the background worker).
                    if resolved_video_id:
                        try:
                            from SWAGGYMUSIC.utils import music_cache
                            await music_cache.schedule_cache_upload(
                                video_id=resolved_video_id,
                                media_type=media_type,
                                file_path=downloaded_file,
                                title=title if isinstance(title, str) else None,
                                duration_min=duration if isinstance(duration, str) else None,
                                thumbnail=thumbnail if isinstance(thumbnail, str) else None,
                            )
                        except Exception:
                            # Cache upload scheduling failed — playback
                            # continues normally. The song just won't be
                            # cached, which is a perf regression, not a
                            # correctness issue.
                            pass

                    return (
                        downloaded_file,
                        True,
                    )

                return (
                    None,
                    False,
                )
        except asyncio.CancelledError:
            raise
        except Exception:
            return (
                None,
                False,
        )
        finally:
            try:
                await _release_download_lock(
                    lock_key,
                    lock,
                    lock_entry,
                )
            except Exception:
                pass


YouTube = YouTubeAPI()
