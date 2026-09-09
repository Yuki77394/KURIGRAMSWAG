# Copyright (C) 2021-2026 by Yuki77394@Github, < https://github.com/Yuki77394 >.
#
# This file is part of < https://github.com/TheAloneTeam/SWAGGYMUSIC > project,
# and is released under the "GNU v3.0 License Agreement".
# Please see < https://github.com/TheAloneTeam/SWAGGYMUSIC/blob/master/LICENSE >
#
# All rights reserved.

"""Silent background prefetch system for the next queued song.

Design goals
============
1. Only ONE next song is ever prefetched per chat (never the whole queue).
2. Prefetch runs entirely in the background — no chat messages, no
   progress bars, no notifications. Failures are silent.
3. Current song playback always takes priority over prefetch — both
   for CPU/bandwidth (limited via a global asyncio.Semaphore) and for
   correctness (prefetch tasks are cancelled on /skip, /stop, queue clear).
4. Duplicate-download protection: a per-(chat_id, video_id) asyncio.Lock
   prevents two concurrent prefetches of the same song, and the existing
   YouTube.download() function already returns the cached file if the
   video was previously downloaded — so a prefetch that fires after the
   same song was already downloaded becomes a near-instant no-op.
5. No changes to existing playback flow: change_stream() and skip_command
   still call YouTube.download() exactly as before. If the prefetch
   completed in advance, download() returns the cached file instantly,
   making the switch faster. If the prefetch failed or was cancelled,
   download() proceeds normally — graceful fallback with zero risk of
   passing None to PyTgCalls.

Trigger points
==============
- put_queue() in queue.py — fires when a new song is added to the queue.
  After the song is queued, this module checks if the just-added song is
  now the next-up (index 1) and triggers a silent prefetch for it.
- change_stream() in call.py — after the autoplay branch adds a related
  video to the queue via put_queue(forceplay=True), the same trigger fires.
- Autoplay: handled by the change_stream autoplay branch, which calls
  put_queue → which calls the prefetch trigger. No separate autoplay hook
  is needed; the existing architecture already routes through put_queue.

Cancellation points
===================
- stop_stream() and force_stop_stream() in call.py — cancels all prefetch
  tasks for that chat_id.
- skip command — when the user skips N songs, any prefetch tasks for
  those skipped songs are cancelled.
- _clear_() in call.py — cancels all prefetch tasks for that chat_id.

API surface
===========
- `schedule_prefetch(chat_id, queued_file, videoid, streamtype, video)`:
    Public entry point. Called by put_queue after a song is added.
    Decides whether to actually prefetch (only for "vid_" prefixed queue
    entries — these are the ones that hit YouTube.download()).
    Returns immediately; the actual download happens in a background task.
- `cancel_prefetch_for_chat(chat_id)`:
    Cancel all in-flight prefetch tasks for a chat. Called by stop/skip
    /clear handlers.
- `cancel_prefetch_for_song(chat_id, videoid)`:
    Cancel the prefetch for one specific song. Used by skip-N when the
    skipped songs include the prefetched next song.
- `get_prefetch_stats()`:
    Diagnostic helper — returns a dict of in-flight prefetch counts.
    Used only by /stats or debug tools, never by user-facing UI.
"""

import asyncio
import os
from typing import Dict, Optional, Tuple

from SWAGGYMUSIC.logging import LOGGER
from SWAGGYMUSIC.misc import db

_log = LOGGER(__name__)

# ─── Global concurrency limiter ───────────────────────────────────────────────
# Maximum number of simultaneous prefetch downloads across ALL chats.
# 3 is a deliberate conservative cap:
#   - Current song playback uses yt-dlp / aiohttp separately and is NOT
#     throttled by this semaphore — playback always has priority.
#   - 3 concurrent prefetches is enough for typical multi-group usage
#     (one chat prefetching audio, another video, etc.) without saturating
#     the host's bandwidth, RAM, or disk I/O.
#   - Tunable via env var PREFETCH_CONCURRENCY if an operator needs more.
#   - Falsy or invalid values disable prefetch entirely (set to 0).
try:
    _concurrency = int(os.environ.get("PREFETCH_CONCURRENCY", "1"))
except (TypeError, ValueError):
    _concurrency = 1
if _concurrency < 0:
    _concurrency = 1

PREFETCH_CONCURRENCY: int = _concurrency

# The semaphore is created lazily so importing this module never touches the
# event loop at import time (which would break under Pyrogram's startup).
_semaphore: Optional[asyncio.Semaphore] = None


def _get_semaphore() -> asyncio.Semaphore:
    """Return the global prefetch semaphore, creating it on first use.

    Must be called from inside a running event loop, which is always the
    case when `schedule_prefetch` is invoked (it's called from async
    contexts like put_queue).
    """
    global _semaphore
    if _semaphore is None:
        _semaphore = asyncio.Semaphore(PREFETCH_CONCURRENCY)
    return _semaphore


# ─── In-flight task registry ─────────────────────────────────────────────────
# Tracks every currently-running prefetch task so they can be cancelled
# cleanly on stop/skip/clear.
#
# Structure:
#   _tasks: Dict[chat_id, Dict[task_key, asyncio.Task]]
# where task_key = (videoid, media_type_str) so the same video_id requested
# for both audio and video can prefetch both (rare, but possible if a user
# queues the same song as audio then immediately as video).

_tasks: Dict[int, Dict[Tuple[str, str], asyncio.Task]] = {}

# Per-(chat_id, video_id, media_type) asyncio.Lock — prevents two concurrent
# prefetches of the exact same song in the same chat from racing.
_per_song_locks: Dict[Tuple[int, str, str], asyncio.Lock] = {}
_per_song_locks_guard = asyncio.Lock()


async def _get_per_song_lock(
    chat_id: int, videoid: str, media_type: str
) -> asyncio.Lock:
    """Return (or create) a per-song lock.

    The locks dict is small (at most one entry per currently-prefetching
    song) so we don't garbage-collect it — entries are cheap and the
    asyncio.Lock objects are reused if the same song is re-queued.
    """
    key = (chat_id, videoid, media_type)
    lock = _per_song_locks.get(key)
    if lock is None:
        async with _per_song_locks_guard:
            # Re-check after acquiring the guard to avoid races.
            lock = _per_song_locks.get(key)
            if lock is None:
                lock = asyncio.Lock()
                _per_song_locks[key] = lock
    return lock


# ─── Public API ──────────────────────────────────────────────────────────────


def _should_prefetch(queued_file: str) -> bool:
    """Return True only for queue entries that hit YouTube.download().

    The change_stream / skip command branches:
      - "vid_" prefix  → calls YouTube.download() → BENEFITS from prefetch
      - "live_" prefix → calls YouTube.video() (live stream URL) → no
                          local file to prefetch, skip
      - "index_" prefix → streams directly from URL → no local file,
                          skip
      - anything else   → either a Telegram/Soundcloud file_id (already
                          downloaded by the time it's queued) or a URL
                          stream → skip

    So we only bother prefetching "vid_" entries.
    """
    return bool(queued_file) and "vid_" in queued_file


async def schedule_prefetch(
    chat_id: int,
    queued_file: str,
    videoid: str,
    streamtype: str,
    video: Optional[bool] = None,
) -> None:
    """Silently prefetch the next song in the background.

    Called by put_queue() after a song is added to the queue. Decides
    whether the just-added song is now the next-up song (queue index 1)
    and whether it's a "vid_" entry worth prefetching.

    NEVER raises — all errors are caught and logged at debug level only
    (no user-facing message, no traceback spam).
    """
    if PREFETCH_CONCURRENCY <= 0:
        # Prefetch explicitly disabled via env var.
        return

    # Always resolve the actual NEXT-UP entry from the live queue. Do not
    # decide from the caller arguments first: the song just added may be at
    # index 2+ while queue[1] is the actual next-up song that needs prefetch.
    # prefetch correct even when the just-added song was appended behind
    # multiple existing entries.
    try:
        queue_snapshot = db.get(chat_id) or []
        if len(queue_snapshot) < 2:
            return
        next_up = queue_snapshot[1]
        queued_file = next_up.get("file") or ""
        videoid = next_up.get("vidid") or ""
        streamtype = next_up.get("streamtype") or streamtype
        video = True if str(streamtype).lower() == "video" else None
        if not _should_prefetch(queued_file) or not videoid:
            return
    except Exception:
        return

    # Determine media type (audio vs video) for the download call.
    media_type = "video" if (video or str(streamtype).lower() == "video") else "audio"

    # Build task key for dedup.
    task_key = (videoid, media_type)

    # Check if a prefetch task is already running for this (chat, video, media_type).
    chat_tasks = _tasks.get(chat_id)
    if chat_tasks and task_key in chat_tasks:
        # Already prefetching this exact song — duplicate protection engaged.
        return

    # Acquire the per-song lock to prevent two simultaneous prefetch tasks
    # for the same song (e.g. if put_queue is called twice in rapid succession).
    song_lock = await _get_per_song_lock(chat_id, videoid, media_type)

    # Spawn the background task. We deliberately do NOT await it.
    task = asyncio.create_task(
        _prefetch_worker(chat_id, videoid, media_type, song_lock, task_key)
    )

    # Register the task so it can be cancelled later if needed.
    if chat_id not in _tasks:
        _tasks[chat_id] = {}
    _tasks[chat_id][task_key] = task

    # Attach a done callback to clean up the registry and silently log
    # any unexpected exceptions (no traceback spam — just a single
    # warning line).
    task.add_done_callback(
        lambda t, cid=chat_id, tk=task_key, vid=videoid: _on_task_done(t, cid, tk, vid)
    )


async def _prefetch_worker(
    chat_id: int,
    videoid: str,
    media_type: str,
    song_lock: asyncio.Lock,
    task_key: Tuple[str, str],
) -> None:
    """The actual background prefetch coroutine.

    Wrapped end-to-end in try/except so it can never raise to the caller
    (it's a fire-and-forget task). All errors are logged at debug level
    only — no user-facing notifications, no traceback spam.
    """
    # The per-song lock ensures that if put_queue was called twice in
    # rapid succession for the same song (rare but possible), only one
    # actual download happens. The second caller's worker will find the
    # file already cached and return immediately.
    async with song_lock:
        try:
            # Acquire the global semaphore to bound concurrent downloads
            # across ALL chats. Playback itself does NOT go through this
            # semaphore — only prefetch — so current-song playback always
            # has priority.
            sem = _get_semaphore()
            async with sem:
                # Re-check: the song might have been cancelled while we
                # were waiting on the semaphore. If the task was removed
                # from the registry, that's the cancellation signal.
                chat_tasks = _tasks.get(chat_id)
                if not chat_tasks or task_key not in chat_tasks:
                    # Cancelled while waiting — abort.
                    return

                # Lazy import to avoid any chance of a circular import
                # at module load time (Youtube is heavy).
                from SWAGGYMUSIC import YouTube

                # YouTube.download(videoid, None, videoid=True, video=...)
                # already has internal caching: if the file is already on
                # disk (>1KB), it returns the cached path instantly. So
                # this call is effectively a no-op if the song was ever
                # downloaded before. That gives us automatic idempotency.
                try:
                    file_path, direct = await YouTube.download(
                        videoid,
                        None,
                        videoid=True,
                        video=(True if media_type == "video" else None),
                    )
                    # We don't need to do anything with file_path — it's
                    # already on disk in the downloads/ directory. The
                    # next change_stream / skip call will find it via the
                    # same YouTube.download() call.
                    if not file_path:
                        # Download returned (None, False) — silently
                        # fail. The normal playback flow will retry when
                        # this song comes up, and if it fails again, the
                        # existing call_6 error message will be shown to
                        # the user at that point (which is the existing
                        # behavior — not a prefetch-induced message).
                        _log.debug(
                            "prefetch: download returned None for "
                            f"chat={chat_id} video={videoid} "
                            f"({media_type}) — will retry on play"
                        )
                except Exception as e:
                    # Silent failure. Don't traceback-spam the logs.
                    _log.debug(
                        "prefetch: download failed silently for "
                        f"chat={chat_id} video={videoid} "
                        f"({media_type}): {type(e).__name__}: {e}"
                    )
        except asyncio.CancelledError:
            # Cancellation is normal (stop/skip/clear). Re-raise so the
            # task's cancelled state is properly propagated.
            raise
        except Exception as e:
            # Catch-all to ensure the worker never raises to the task
            # scheduler (which would log a noisy "Task exception was
            # never retrieved" warning).
            _log.debug(
                "prefetch: worker uncaught error for "
                f"chat={chat_id} video={videoid} ({media_type}): "
                f"{type(e).__name__}: {e}"
            )


def _on_task_done(
    task: asyncio.Task,
    chat_id: int,
    task_key: Tuple[str, str],
    videoid: str,
) -> None:
    """Cleanup callback invoked when a prefetch task finishes (success,
    failure, or cancellation). Removes the task from the registry."""
    try:
        chat_tasks = _tasks.get(chat_id)
        if chat_tasks:
            # Only remove if it's still our task (avoid removing a
            # replacement task that was scheduled in the meantime).
            if chat_tasks.get(task_key) is task:
                chat_tasks.pop(task_key, None)
            if not chat_tasks:
                _tasks.pop(chat_id, None)
        media_type = task_key[1]
        _per_song_locks.pop((chat_id, videoid, media_type), None)
    except Exception:
        # Never let a cleanup callback raise.
        pass

    # Swallow the exception reference if any (prevents Python's
    # "Task exception was never retrieved" warning).
    if task.cancelled():
        return
    exc = task.exception()
    if exc is not None and not isinstance(exc, asyncio.CancelledError):
        # Already logged at debug level inside the worker. Don't
        # re-log here — that would duplicate the message.
        pass


def cancel_prefetch_for_chat(chat_id: int) -> None:
    """Cancel all in-flight prefetch tasks for a chat.

    Called by stop_stream / force_stop_stream / _clear_ / queue clear
    handlers. Synchronous (not async) so it can be called from any
    context — task.cancel() schedules the CancelledError, it doesn't
    block.
    """
    chat_tasks = _tasks.pop(chat_id, None)
    if not chat_tasks:
        return
    for task in chat_tasks.values():
        if not task.done():
            try:
                task.cancel()
            except Exception:
                pass


def cancel_prefetch_for_song(chat_id: int, videoid: str) -> None:
    """Cancel the prefetch for one specific song in a chat.

    Used by the /skip command when skipping N songs — any prefetch
    task for a skipped song becomes stale and should be aborted.
    """
    chat_tasks = _tasks.get(chat_id)
    if not chat_tasks:
        return
    # Cancel all media_type variants of this videoid (audio + video).
    keys_to_cancel = [k for k in chat_tasks if k[0] == videoid]
    for key in keys_to_cancel:
        task = chat_tasks.pop(key, None)
        if task and not task.done():
            try:
                task.cancel()
            except Exception:
                pass


def get_prefetch_stats() -> Dict[int, int]:
    """Return a dict mapping chat_id → number of in-flight prefetch tasks.

    For diagnostics only — never shown to end users.
    """
    return {cid: len(tasks) for cid, tasks in _tasks.items() if tasks}


# ─── Module-level shutdown helper ────────────────────────────────────────────
# Called on bot shutdown (best-effort) to cancel all prefetch tasks cleanly.
# Prevents "Task was destroyed but it is pending!" warnings on shutdown.


def cancel_all_prefetch() -> None:
    """Cancel every in-flight prefetch task across all chats.

    Intended to be called during bot shutdown to ensure a clean exit.
    """
    for chat_id in list(_tasks.keys()):
        cancel_prefetch_for_chat(chat_id)
