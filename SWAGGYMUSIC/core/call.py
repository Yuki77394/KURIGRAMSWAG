#
# Copyright (C) 2021-2022 by Yuki77394@Github, < https://github.com/Yuki77394 >.
#
# This file is part of < https://github.com/TheAloneTeam/SWAGGYMUSIC > project,
# and is released under the "GNU v3.0 License Agreement".
# Please see < https://github.com/TheAloneTeam/SWAGGYMUSIC/blob/master/LICENSE >
#
# All rights reserved.

import asyncio
import os
import random
from datetime import datetime, timedelta
from typing import Union

from ntgcalls import ConnectionNotFound, TelegramServerError
from pyrogram import Client
from pyrogram.enums import ButtonStyle
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from pytgcalls import PyTgCalls, exceptions, types
import config
from SWAGGYMUSIC import LOGGER, YouTube, app
from SWAGGYMUSIC.misc import db
from SWAGGYMUSIC.utils.database import (add_active_chat, add_active_video_chat,
                                       autoplay_off, get_filter, get_lang, get_loop,
                                       group_assistant, is_autoend,
                                       is_autoplay_on, is_thumb_on,
                                       music_on, remove_active_chat,
                                       remove_active_video_chat, set_loop)
from SWAGGYMUSIC.utils.errors import capture_internal_err
from SWAGGYMUSIC.utils.exceptions import AssistantErr
from SWAGGYMUSIC.utils.formatters import (check_duration, seconds_to_min,
                                         speed_converter)
from SWAGGYMUSIC.utils.inline.play import stream_markup
from SWAGGYMUSIC.utils.stream.autoclear import auto_clean
from SWAGGYMUSIC.utils.thumbnails import get_thumb
from strings import get_string


async def delete_old_message(chat_id: int):
    try:
        old = db.get(chat_id, [{}])[0].get("mystic")
        if old:
            await old.delete()
    except:
        pass


autoend = {}
counter = {}


async def _clear_(chat_id: int):
    try:
        for popped in db.get(chat_id, []):
            try:
                mystic = popped.get("mystic")
                if mystic:
                    await mystic.delete()
            except:
                pass
    except:
        pass
    db[chat_id] = []
    await remove_active_video_chat(chat_id)
    await remove_active_chat(chat_id)
    try:
        await autoplay_off(chat_id)
    except Exception:
        pass

    # Cancel any in-flight background prefetch tasks for this chat so they
    # don't keep downloading a song that's no longer needed.
    try:
        from SWAGGYMUSIC.utils.stream.prefetch import cancel_prefetch_for_chat
        cancel_prefetch_for_chat(chat_id)
    except Exception:
        pass


class Call(PyTgCalls):
    def __init__(self):
        self.userbot1 = Client(
            name="SWAGGYMUSIC1",
            api_id=config.API_ID,
            api_hash=config.API_HASH,
            session_string=str(config.STRING1),
        )
        self.one = PyTgCalls(self.userbot1, cache_duration=100)

        self.userbot2 = Client(
            name="SWAGGYMUSIC2",
            api_id=config.API_ID,
            api_hash=config.API_HASH,
            session_string=str(config.STRING2),
        )
        self.two = PyTgCalls(self.userbot2, cache_duration=100)

        self.userbot3 = Client(
            name="SWAGGYMUSIC3",
            api_id=config.API_ID,
            api_hash=config.API_HASH,
            session_string=str(config.STRING3),
        )
        self.three = PyTgCalls(self.userbot3, cache_duration=100)

        self.userbot4 = Client(
            name="SWAGGYMUSIC4",
            api_id=config.API_ID,
            api_hash=config.API_HASH,
            session_string=str(config.STRING4),
        )
        self.four = PyTgCalls(self.userbot4, cache_duration=100)

        self.userbot5 = Client(
            name="SWAGGYMUSIC5",
            api_id=config.API_ID,
            api_hash=config.API_HASH,
            session_string=str(config.STRING5),
        )
        self.five = PyTgCalls(self.userbot5, cache_duration=100)

    def _build_stream(
        self,
        source: str,
        video: bool,
        ffmpeg: str | None = None,
    ) -> types.MediaStream:
        # Guard against None/empty source — pytgcalls would otherwise raise a
        # raw TypeError ("media_path has incorrect type... got 'NoneType'")
        # which surfaces as a confusing "Telegram server error" to the user.
        # This happens when YouTube.download() returns (None, False) due to
        # age-restriction, region-block, or stream-expiry upstream.
        if not source:
            raise AssistantErr(
                "Stream source is empty — the underlying download or "
                "URL resolver returned no media path."
            )
        return types.MediaStream(
            media_path=source,
            audio_parameters=types.AudioQuality.HIGH,
            video_parameters=types.VideoQuality.HD_720p,
            audio_flags=types.MediaStream.Flags.REQUIRED,
            video_flags=(
                types.MediaStream.Flags.AUTO_DETECT
                if video
                else types.MediaStream.Flags.IGNORE
            ),
            ffmpeg_parameters=ffmpeg,
        )

    @capture_internal_err
    async def _play_on_assistant(
        self,
        client: PyTgCalls,
        chat_id: int,
        stream: types.MediaStream,
    ):
        try:
            await client.play(
                chat_id=chat_id,
                stream=stream,
                config=types.GroupCallConfig(auto_start=False),
            )
        except asyncio.TimeoutError:
            await asyncio.sleep(3)
            try:
                await client.play(
                    chat_id=chat_id,
                    stream=stream,
                    config=types.GroupCallConfig(auto_start=False),
                )
            except Exception:
                raise
        except exceptions.NoActiveGroupCall:
            raise
        except exceptions.NoAudioSourceFound:
            raise
        except (ConnectionNotFound, TelegramServerError):
            raise
        except Exception:
            raise

    @capture_internal_err
    async def pause_stream(self, chat_id: int):
        assistant = await group_assistant(self, chat_id)
        try:
            await assistant.pause(chat_id)
        except (exceptions.NotInCallError, ConnectionNotFound):
            # Bot is not in a call (e.g. user hit /pause after the call ended).
            # Silently no-op — there is nothing to pause.
            return

    @capture_internal_err
    async def resume_stream(self, chat_id: int):
        assistant = await group_assistant(self, chat_id)
        try:
            await assistant.resume(chat_id)
        except (exceptions.NotInCallError, ConnectionNotFound):
            # Bot is not in a call (e.g. user hit /resume after the call ended,
            # or the underlying ntgcalls connection was never established).
            # Silently no-op — there is nothing to resume.
            return

    @capture_internal_err
    async def stop_stream(self, chat_id: int):
        assistant = await group_assistant(self, chat_id)
        try:
            await _clear_(chat_id)
            await assistant.leave_call(chat_id, close=False)
        except Exception:
            pass

    @capture_internal_err
    async def stop_stream_force(self, chat_id: int):
        for string, client in [
            (config.STRING1, self.one),
            (config.STRING2, self.two),
            (config.STRING3, self.three),
            (config.STRING4, self.four),
            (config.STRING5, self.five),
        ]:
            if not string:
                continue
            try:
                await client.leave_call(chat_id, close=False)
            except Exception:
                pass
        try:
            await _clear_(chat_id)
        except Exception:
            pass
        # Belt-and-suspenders: cancel all prefetch tasks for this chat
        # even if _clear_ failed for some reason.
        try:
            from SWAGGYMUSIC.utils.stream.prefetch import cancel_prefetch_for_chat
            cancel_prefetch_for_chat(chat_id)
        except Exception:
            pass

    @capture_internal_err
    async def speedup_stream(self, chat_id: int, file_path, speed, playing):
        assistant = await group_assistant(self, chat_id)
        if str(speed) != "1.0":
            base = os.path.basename(file_path)
            chatdir = os.path.join(os.getcwd(), "playback", str(speed))
            if not os.path.isdir(chatdir):
                os.makedirs(chatdir)
            out = os.path.join(chatdir, base)
            if not os.path.isfile(out):
                if str(speed) == "0.5":
                    vs = 2.0
                elif str(speed) == "0.75":
                    vs = 1.35
                elif str(speed) == "1.5":
                    vs = 0.68
                elif str(speed) == "2.0":
                    vs = 0.5
                else:
                    vs = 1.0
                try:
                    proc = await asyncio.create_subprocess_shell(
                        cmd=(
                            "ffmpeg "
                            "-i "
                            f"{file_path} "
                            "-filter:v "
                            f"setpts={vs}*PTS "
                            "-filter:a "
                            f"atempo={speed} "
                            f"{out}"
                        ),
                        stdin=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                    )
                    await proc.communicate()
                except:
                    pass
        else:
            out = file_path

        if not os.path.isfile(out):
            out = file_path

        dur = await asyncio.get_event_loop().run_in_executor(None, check_duration, out)
        if str(dur) == "Unknown":
            dur = 0
        dur = int(dur)
        played, con_seconds = speed_converter(playing[0]["played"], speed)
        duration = seconds_to_min(dur)
        xx = f"-ss {played} -to {duration}"
        video_mode = playing[0]["streamtype"] == "video"
        stream = self._build_stream(out, video=video_mode, ffmpeg=xx)
        if chat_id in db and db[chat_id] and str(db[chat_id][0]["file"]) == str(file_path):
            await self._play_on_assistant(assistant, chat_id, stream)
        else:
            raise AssistantErr("Umm")
        if chat_id in db and db[chat_id] and str(db[chat_id][0]["file"]) == str(file_path):
            exis = (playing[0]).get("old_dur")
            if not exis:
                db[chat_id][0]["old_dur"] = db[chat_id][0]["dur"]
                db[chat_id][0]["old_second"] = db[chat_id][0]["seconds"]
            db[chat_id][0]["played"] = con_seconds
            db[chat_id][0]["dur"] = duration
            db[chat_id][0]["seconds"] = dur
            db[chat_id][0]["speed_path"] = out
            db[chat_id][0]["speed"] = speed

    @capture_internal_err
    async def apply_filter(self, chat_id: int, file_path, filter_type, playing):
        assistant = await group_assistant(self, chat_id)
        base = os.path.basename(file_path)
        chatdir = os.path.join(os.getcwd(), "filters", str(filter_type))
        if not os.path.isdir(chatdir):
            os.makedirs(chatdir)
        out = os.path.join(chatdir, base)

        if not os.path.isfile(out) or filter_type == "normal":
            if filter_type == "bass":
                ff_filter = "bass=g=20,firequalizer=gain_entry='entry(0,0);entry(250,0);entry(4000,0);entry(16000,0)'"
            elif filter_type == "echo":
                ff_filter = "aecho=0.8:0.88:60:0.4"
            elif filter_type == "slowed":
                ff_filter = "atempo=0.8,aecho=0.8:0.88:60:0.4"
            elif filter_type == "nightcore":
                ff_filter = "asetrate=48000*1.25,atempo=1.25"
            else:
                ff_filter = "cat" # normal

            if filter_type == "normal":
                out = file_path
            else:
                try:
                    proc = await asyncio.create_subprocess_shell(
                        cmd=(
                            "ffmpeg "
                            "-i "
                            f"{file_path} "
                            "-filter:a "
                            f"\"{ff_filter}\" "
                            f"{out} -y"
                        ),
                        stdin=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                    )
                    await proc.communicate()
                except:
                    pass

                if not os.path.isfile(out):
                    out = file_path

        dur = await asyncio.get_event_loop().run_in_executor(None, check_duration, out)
        if str(dur) == "Unknown":
            dur = 0
        dur = int(dur)
        played = playing[0]["played"]
        duration = seconds_to_min(dur)
        xx = f"-ss {played} -to {duration}"
        video_mode = playing[0]["streamtype"] == "video"
        stream = self._build_stream(out, video=video_mode, ffmpeg=xx)

        if chat_id in db and db[chat_id] and str(db[chat_id][0]["file"]) == str(file_path):
            await self._play_on_assistant(assistant, chat_id, stream)
        else:
            raise AssistantErr("Stream changed")

        if chat_id in db and db[chat_id] and str(db[chat_id][0]["file"]) == str(file_path):
            db[chat_id][0]["played"] = played
            db[chat_id][0]["dur"] = duration
            db[chat_id][0]["seconds"] = dur

    async def force_stop_stream(self, chat_id: int):
        assistant = await group_assistant(self, chat_id)
        try:
            check = db.get(chat_id)
            if check:
                popped = check.pop(0)
                if popped:
                    await auto_clean(popped)
        except Exception:
            pass
        await remove_active_video_chat(chat_id)
        await remove_active_chat(chat_id)
        try:
            await assistant.leave_call(chat_id, close=False)
        except Exception:
            pass

    @capture_internal_err
    async def skip_stream(
        self,
        chat_id: int,
        link: str,
        title: str = None,
        video: Union[bool, str] = None,
        image: Union[bool, str] = None,
    ):
        assistant = await group_assistant(self, chat_id)
        stream = self._build_stream(link, video=bool(video))
        await self._play_on_assistant(assistant, chat_id, stream)

    @capture_internal_err
    async def seek_stream(self, chat_id, file_path, to_seek, duration, mode):
        assistant = await group_assistant(self, chat_id)
        ffmpeg = f"-ss {to_seek} -to {duration}"
        video_mode = mode == "video"
        stream = self._build_stream(
            file_path,
            video=video_mode,
            ffmpeg=ffmpeg,
        )
        await self._play_on_assistant(assistant, chat_id, stream)

    @capture_internal_err
    async def stream_call(self, link):
        assistant = await group_assistant(self, config.LOGGER_ID)
        stream = self._build_stream(link, video=True)
        await self._play_on_assistant(assistant, config.LOGGER_ID, stream)
        await asyncio.sleep(0.2)
        try:
            await assistant.leave_call(config.LOGGER_ID, close=False)
        except Exception:
            pass

    @capture_internal_err
    async def join_call(
        self,
        chat_id: int,
        original_chat_id: int,
        link,
        title: str = None,
        video: Union[bool, str] = None,
        image: Union[bool, str] = None,
    ):
        assistant = await group_assistant(self, chat_id)
        language = await get_lang(chat_id)
        _ = get_string(language)
        try:
            stream = self._build_stream(link, video=bool(video))
            await self._play_on_assistant(assistant, chat_id, stream)
        except AssistantErr:
            # User-facing errors raised by _build_stream (e.g. empty source)
            # must pass through unchanged — don't re-wrap them as call_10.
            raise
        except exceptions.NoActiveGroupCall:
            raise AssistantErr(_["call_8"])
        except exceptions.NoAudioSourceFound:
            raise AssistantErr(_["call_11"])
        except (ConnectionNotFound, TelegramServerError):
            raise AssistantErr(_["call_10"])
        except TypeError:
            # Defensive: if a None slips past _build_stream's guard somehow,
            # translate the raw pytgcalls TypeError into a user-friendly
            # "failed to fetch audio" message instead of "Telegram server error".
            raise AssistantErr(_["call_11"])
        except Exception:
            raise AssistantErr(_["call_10"])
        await add_active_chat(chat_id)
        await music_on(chat_id)
        if video:
            await add_active_video_chat(chat_id)
        if await is_autoend():
            counter[chat_id] = {}
            users = len(await assistant.get_participants(chat_id))
            if users == 1:
                autoend[chat_id] = datetime.now() + timedelta(minutes=1)

    @capture_internal_err
    async def change_stream(self, client: PyTgCalls, chat_id: int):
        from SWAGGYMUSIC.utils.stream.stream import update_stream_ui
        check = db.get(chat_id)
        old_mystic = None
        if check and len(check) > 0:
            old_mystic = check[0].get("mystic")

        popped = None
        loop = await get_loop(chat_id)
        try:
            if loop == 0:
                if check:
                    popped = check.pop(0)
            else:
                loop = loop - 1
                await set_loop(chat_id, loop)

            if popped:
                await auto_clean(popped)

            if not check:
                if await is_autoplay_on(chat_id):
                    try:
                        vidid = popped["vidid"]
                        related = await YouTube.get_related_videos(vidid)
                        if not related:
                            return await _clear_(chat_id)
                        video_id = random.choice(related)
                        try:
                            details, track_id = await YouTube.track(video_id, True)
                            if not details.get("title"):
                                raise Exception("no details")
                        except:
                            raise Exception("fetch fail")

                        from SWAGGYMUSIC.utils.stream.queue import put_queue
                        await put_queue(
                            chat_id,
                            popped["chat_id"],
                            f"vid_{video_id}",
                            details["title"],
                            details["duration_min"],
                            popped["by"],
                            video_id,
                            popped["user_id"],
                            popped["streamtype"],
                            forceplay=True,
                        )
                        # Re-fetch check because put_queue added a song
                        check = db.get(chat_id)
                    except:
                        pass

                if not check:
                    await _clear_(chat_id)
                    if not await is_autoplay_on(chat_id):
                        try:
                            buttons = InlineKeyboardMarkup(
                                [
                                    [
                                        InlineKeyboardButton(
                                            "✙ ʌᴅᴅ ϻє вᴧʙʏ ✙",
                                            url=f"https://t.me/{app.username}?startgroup=true",
                                            style=ButtonStyle.PRIMARY,
                                        ),
                                    ],
                                    [
                                        InlineKeyboardButton(
                                            "⋞ ᴄʟᴏsє ⋟",
                                            callback_data="close_message",
                                            style=ButtonStyle.DANGER,
                                        ),
                                    ]
                                ]
                            )
                            await app.send_message(
                                chat_id,
                                "🎵 𝐓ʜᴇ 𝐐ᴜᴇᴜᴇ 𝐇ᴀs 𝐅ɪɴɪsʜᴇᴅ. 𝐔sᴇ /play 𝐓ᴏ 𝐀ᴅᴅ 𝐌ᴏʀᴇ 𝐒ᴏɴɢs!!",
                                reply_markup=buttons,
                            )
                        except:
                            pass
                    return await client.leave_call(chat_id, close=False)
        except Exception:
            try:
                await _clear_(chat_id)
                try:
                    buttons = InlineKeyboardMarkup(
                        [
                            [
                                InlineKeyboardButton(
                                    "✙ ʌᴅᴅ ϻє вᴧʙʏ ✙",
                                    url=f"https://t.me/{app.username}?startgroup=true",
                                    style=ButtonStyle.PRIMARY,
                                ),
                            ],
                            [
                                InlineKeyboardButton(
                                    "⋞ ᴄʟᴏsє ⋟",
                                    callback_data="close_message",
                                    style=ButtonStyle.DANGER,
                                ),
                            ]
                        ]
                    )
                    await app.send_message(
                        chat_id,
                        "🎵 𝐓ʜᴇ 𝐐ᴜᴇᴜᴇ 𝐇ᴀs 𝐅ɪɴɪsʜᴇᴅ. 𝐔sᴇ /play 𝐓ᴏ 𝐀ᴅᴅ 𝐌ᴏʀᴇ 𝐒ᴏɴɢs!!",
                        reply_markup=buttons,
                    )
                except:
                    pass
                return await client.leave_call(chat_id, close=False)
            except Exception:
                return

        if not check:
            return await client.leave_call(chat_id, close=False)

        queued = check[0]["file"]

        # Delete the "Added to Queue" message of the next track
        try:
            old_queued_mystic = check[0].get("mystic")
            if old_queued_mystic:
                await old_queued_mystic.delete()
        except:
            pass

        language = await get_lang(chat_id)
        _ = get_string(language)

        if not check: # Final check
            return await client.leave_call(chat_id, close=False)

        title = (check[0]["title"]).title()
        user = check[0]["by"]
        original_chat_id = check[0]["chat_id"]
        streamtype = check[0]["streamtype"]
        videoid = check[0]["vidid"]

        if chat_id in db and db[chat_id]:
            db[chat_id][0]["played"] = 0

        exis = (check[0]).get("old_dur")
        if exis:
            if chat_id in db and db[chat_id]:
                db[chat_id][0]["dur"] = exis
                db[chat_id][0]["seconds"] = check[0]["old_second"]
                db[chat_id][0]["speed_path"] = None
                db[chat_id][0]["speed"] = 1.0

        video = True if str(streamtype) == "video" else False
        if "live_" in queued:
            n, link = await YouTube.video(videoid, True)
            if n == 0 or not link:
                # Either the resolver returned 0 results, or it returned a
                # result but with no playable URL (link is None/empty).
                # Treat both as a failed switch and notify the user.
                return await app.send_message(
                    original_chat_id,
                    text=_["call_6"],
                )
            stream = self._build_stream(link, video=video)
            try:
                await self._play_on_assistant(client, chat_id, stream)
            except Exception:
                return await app.send_message(
                    original_chat_id,
                    text=_["call_6"],
                )
            img = await get_thumb(videoid)
            button = stream_markup(
                _, chat_id, await is_autoplay_on(chat_id), await is_thumb_on(chat_id), await get_filter(chat_id)
            )
            caption=_["stream_1"].format(
                f"https://t.me/{app.username}?start=info_{videoid}",
                title[:23],
                check[0]["dur"],
                user,
            )
            run = await update_stream_ui(chat_id, original_chat_id, None, img, caption, button)
            if chat_id in db and db[chat_id]:
                db[chat_id][0]["mystic"] = run
                db[chat_id][0]["markup"] = "tg"
                db[chat_id][0]["file"] = link
        elif "vid_" in queued:
            try:
                file_path, direct = await YouTube.download(
                    videoid,
                    None,
                    videoid=True,
                    video=video,
                )
            except Exception as download_error:
                # The previous "Now Playing" message may already have been
                # deleted by auto_clean(). Never try to edit old_mystic here.
                # It is a stale Message object at this point.
                try:
                    LOGGER(__name__).error(
                        "YouTube download raised an exception for chat=%s video=%s: %s",
                        chat_id,
                        videoid,
                        download_error,
                    )
                except Exception:
                    pass

                # Remove the failed queue item and continue with the next
                # track instead of leaving the voice chat stuck.
                try:
                    failed = check.pop(0)
                    await auto_clean(failed)
                except Exception:
                    pass

                # Re-run the normal queue transition. If another playable
                # track exists it will be selected; if the queue is empty,
                # the normal autoplay/queue-finished logic handles it.
                return await self.change_stream(client, chat_id)

            if not file_path:
                # YouTube.download() returned (None, False). The old mystic
                # message was already cleaned above, so editing it causes
                # MESSAGE_ID_INVALID. Log the failed track, remove it, and
                # continue with the next queued item.
                try:
                    LOGGER(__name__).error(
                        "YouTube download failed without exception for chat=%s video=%s",
                        chat_id,
                        videoid,
                    )
                except Exception:
                    pass

                try:
                    failed = check.pop(0)
                    await auto_clean(failed)
                except Exception:
                    pass

                return await self.change_stream(client, chat_id)
            stream = self._build_stream(file_path, video=video)
            try:
                await self._play_on_assistant(client, chat_id, stream)
            except Exception:
                return await app.send_message(
                    original_chat_id,
                    text=_["call_6"],
                )
            img = await get_thumb(videoid)
            button = stream_markup(
                _, chat_id, await is_autoplay_on(chat_id), await is_thumb_on(chat_id), await get_filter(chat_id)
            )
            caption=_["stream_1"].format(
                f"https://t.me/{app.username}?start=info_{videoid}",
                title[:23],
                check[0]["dur"],
                user,
            )
            run = await update_stream_ui(chat_id, original_chat_id, None, img, caption, button)
            if chat_id in db and db[chat_id]:
                db[chat_id][0]["mystic"] = run
                db[chat_id][0]["markup"] = "stream"
                db[chat_id][0]["file"] = file_path

        elif "index_" in queued:
            stream = self._build_stream(videoid, video=video)
            try:
                await self._play_on_assistant(client, chat_id, stream)
            except Exception:
                return await app.send_message(
                    original_chat_id,
                    text=_["call_6"],
                )
            button = stream_markup(
                _, chat_id, await is_autoplay_on(chat_id), await is_thumb_on(chat_id), await get_filter(chat_id)
            )
            caption=_["stream_2"].format(user)
            run = await update_stream_ui(chat_id, original_chat_id, None, config.STREAM_IMG_URL, caption, button)
            if chat_id in db and db[chat_id]:
                db[chat_id][0]["mystic"] = run
                db[chat_id][0]["markup"] = "tg"
                db[chat_id][0]["file"] = videoid
        else:
            stream = self._build_stream(queued, video=video)
            try:
                await self._play_on_assistant(client, chat_id, stream)
            except Exception:
                return await app.send_message(
                    original_chat_id,
                    text=_["call_6"],
                )
            if videoid == "telegram":
                button = stream_markup(
                    _, chat_id, await is_autoplay_on(chat_id), await is_thumb_on(chat_id), await get_filter(chat_id)
                )
                img = config.TELEGRAM_VIDEO_URL if video else config.TELEGRAM_AUDIO_URL
                caption=_["stream_1"].format(
                    config.SUPPORT_CHAT, title[:23], check[0]["dur"], user
                )
                run = await update_stream_ui(chat_id, original_chat_id, None, img, caption, button)
                if chat_id in db and db[chat_id]:
                    db[chat_id][0]["mystic"] = run
                    db[chat_id][0]["markup"] = "tg"
                    db[chat_id][0]["file"] = img
            elif videoid == "soundcloud":
                button = stream_markup(
                    _, chat_id, await is_autoplay_on(chat_id), await is_thumb_on(chat_id), await get_filter(chat_id)
                )
                caption=_["stream_1"].format(
                    config.SUPPORT_CHAT, title[:23], check[0]["dur"], user
                )
                run = await update_stream_ui(chat_id, original_chat_id, None, config.SOUNCLOUD_IMG_URL, caption, button)
                if chat_id in db and db[chat_id]:
                    db[chat_id][0]["mystic"] = run
                    db[chat_id][0]["markup"] = "tg"
                    db[chat_id][0]["file"] = queued
            else:
                img = await get_thumb(videoid)
                button = stream_markup(
                    _, chat_id, await is_autoplay_on(chat_id), await is_thumb_on(chat_id), await get_filter(chat_id)
                )
                caption=_["stream_1"].format(
                    f"https://t.me/{app.username}?start=info_{videoid}",
                    title[:23],
                    check[0]["dur"],
                    user,
                )
                run = await update_stream_ui(chat_id, original_chat_id, None, img, caption, button)
                if chat_id in db and db[chat_id]:
                    db[chat_id][0]["mystic"] = run
                    db[chat_id][0]["markup"] = "stream"
                    db[chat_id][0]["file"] = queued

        # ── After queue advance: prefetch the new next-up song ─────────────
        # The song that just became the new current (index 0) was likely
        # already prefetched when it was at index 1. Now that it's playing,
        # the song at index 1 (the new next-up) may not have been prefetched
        # if there were 3+ songs in queue when it was added. Fire-and-forget
        # a prefetch for the new next-up song. Safe no-op if not a vid_ entry
        # or if already cached.
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

    @capture_internal_err
    async def ping(self):
        pings = []
        if config.STRING1:
            pings.append(self.one.ping)
        if config.STRING2:
            pings.append(self.two.ping)
        if config.STRING3:
            pings.append(self.three.ping)
        if config.STRING4:
            pings.append(self.four.ping)
        if config.STRING5:
            pings.append(self.five.ping)
        return str(round(sum(pings) / len(pings), 3)) if pings else "0"

    @capture_internal_err
    async def start(self):
        LOGGER(__name__).info("Starting PyTgCalls Client...\n")
        if config.STRING1:
            await self.one.start()
        if config.STRING2:
            await self.two.start()
        if config.STRING3:
            await self.three.start()
        if config.STRING4:
            await self.four.start()
        if config.STRING5:
            await self.five.start()

    @capture_internal_err
    async def decorators(self):
        for string, client in [
            (config.STRING1, self.one),
            (config.STRING2, self.two),
            (config.STRING3, self.three),
            (config.STRING4, self.four),
            (config.STRING5, self.five),
        ]:
            if not string:
                continue

            @client.on_update()
            async def _update_handler(_, update: types.Update, _client=client):
                if isinstance(update, types.StreamEnded):
                    if update.stream_type == types.StreamEnded.Type.AUDIO:
                        await self.change_stream(_client, update.chat_id)
                elif isinstance(update, types.ChatUpdate):
                    if update.status in [
                        types.ChatUpdate.Status.KICKED,
                        types.ChatUpdate.Status.LEFT_GROUP,
                        types.ChatUpdate.Status.CLOSED_VOICE_CHAT,
                    ]:
                        await self.stop_stream(update.chat_id)


Alone = Call()
