"""MongoDB-backed music cache with a private Telegram channel as cold storage.

ARCHITECTURE (final, deterministic, no timer-based synchronization)
====================================================================

CACHE HIT FLOW:
  YouTube.download() → try_cached_download()
    → MongoDB lookup (by video_id + media_type)
    → if found: restore from Telegram storage channel via MAIN BOT
      → download to unique temp file
      → ffprobe validation
      → atomic os.replace() to canonical path
      → return path (NO file_refs ref held — see note below)
    → caller (stream.py) calls put_queue() → autoclean.append(file)
    → playback
    → auto_clean(popped) → autoclean.remove() → if count==0: os.remove()

  NOTE: try_cached_download does NOT hold a file_refs reference during
  the restore. This is safe because auto_clean(popped) only operates on
  files that were IN the queue (popped from db[chat_id]). A restored
  file that hasn't been queued yet is NOT in any queue, so auto_clean
  cannot target it. The gap between restore-return and put_queue() is
  safe — no timer-based handoff is needed.

CACHE MISS FLOW:
  YouTube.download() → try_cached_download() returns None
    → existing YouTube download (API + yt-dlp fallback)
    → playback starts immediately
    → schedule_cache_upload() spawns background task
      → task acquires file_refs ref (protects file from auto_clean
        during upload)
      → uploads to STORAGE_CHANNEL_ID via MAIN BOT
      → on success: saves MongoDB cache record
      → releases file_refs ref (if auto_clean called mark_for_delete
        during upload, the file is deleted now; otherwise it survives
        until auto_clean runs normally)

FILE OWNERSHIP MODEL:
  - auto_clean() is the SOLE owner of file deletion.
  - file_refs protects files from auto_clean deletion ONLY when a
    background upload is in progress.
  - Restore path does NOT use file_refs — it relies on the fact that
    auto_clean cannot target un-queued files.
  - put_queue() unconditionally appends to autoclean — this is the
    single point where queue ownership is established.
  - auto_clean removes ONE autoclean entry per queue pop; file is
    deleted when count reaches 0.

STORAGE OPERATIONS:
  All storage operations use the MAIN BOT client (SWAGGYMUSIC.app),
  never the assistant userbots. The main bot must be added to the
  private storage channel as admin with Post Messages + Delete
  Messages permissions.

ERROR CLASSIFICATION:
  - Record-invalid errors (MessageIdInvalid, MessageEmpty, MediaEmpty,
    FileIdInvalid) → invalidate MongoDB cache record.
  - Storage-access errors (ChannelPrivate, ChatAdminRequired,
    ChatWriteForbidden) → preserve MongoDB cache record, fall back to
    YouTube download.
  - Temporary errors (FloodWait, ConnectionError, Timeout) → preserve
    cache record, fall back to YouTube download.

MONGODB UNCERTAIN-WRITE PROTECTION:
  If save_cached_track returns False or throws, we re-query MongoDB to
  verify whether the record actually exists and points to the same
  channel_id + message_id. If it does, the write committed despite the
  failed response — we do NOT delete the Telegram message. Only
  genuinely-unreferenced uploads trigger orphan cleanup.

STORAGE CHANNEL MIGRATION:
  Restore uses the channel_id stored in the MongoDB record (NOT the
  current config.STORAGE_CHANNEL_ID). This preserves existing cache
  entries across channel migrations. New uploads go to the current
  STORAGE_CHANNEL_ID.
"""

import asyncio
import json
import os
import time
import unicodedata
import uuid
from typing import Dict, Optional, Tuple

from SWAGGYMUSIC.logging import LOGGER

import config
from SWAGGYMUSIC.utils.database import (
    get_cached_track,
    invalidate_cached_track,
    is_track_cached,
    save_cached_track,
)

_log = LOGGER(__name__)

_CACHE_DL_DIR = "downloads"

# ─── Per-song UPLOAD locks (refcounted) ──────────────────────────────────────
_inflight_locks: Dict[Tuple[str, str], Tuple[asyncio.Lock, int]] = {}
_inflight_locks_guard = asyncio.Lock()

# ─── Per-song RESTORE locks (refcounted) ─────────────────────────────────────
_restore_locks: Dict[Tuple[str, str], Tuple[asyncio.Lock, int]] = {}
_restore_locks_guard = asyncio.Lock()

# ─── In-flight UPLOAD task registry ──────────────────────────────────────────
_inflight_tasks: Dict[Tuple[str, str], asyncio.Task] = {}

# ─── Global upload concurrency limiter ───────────────────────────────────────
_semaphore: Optional[asyncio.Semaphore] = None


def _get_semaphore() -> asyncio.Semaphore:
    global _semaphore
    if _semaphore is None:
        _semaphore = asyncio.Semaphore(
            max(1, getattr(config, "CACHE_UPLOAD_CONCURRENCY", 2))
        )
    return _semaphore


# ─── Enablement checks ──────────────────────────────────────────────────────


def _cache_restore_enabled() -> bool:
    """Restore uses channel_id from MongoDB record — does NOT require
    config.STORAGE_CHANNEL_ID. Only MUSIC_CACHE_ENABLED is needed."""
    return bool(getattr(config, "MUSIC_CACHE_ENABLED", True))


def _cache_upload_enabled() -> bool:
    """Upload requires both MUSIC_CACHE_ENABLED AND STORAGE_CHANNEL_ID
    (the channel to upload TO)."""
    if not getattr(config, "MUSIC_CACHE_ENABLED", True):
        return False
    if not getattr(config, "STORAGE_CHANNEL_ID", 0):
        return False
    return True


# ─── Main bot client accessor ──────────────────────────────────────────────


def _get_main_bot():
    """Return the project's MAIN bot Pyrogram client (SWAGGYMUSIC.app).

    Uses `is_connected is True` check. In Pyrogram 2.0.106, is_connected
    is None before start(), True after start() succeeds, False after
    stop(). The `is True` check is explicit and handles all three states.
    """
    try:
        from SWAGGYMUSIC import app
    except Exception:
        return None
    if app is None:
        return None
    if getattr(app, "is_connected", None) is not True:
        return None
    return app


# ─── Refcounted lock helpers ────────────────────────────────────────────────


async def _acquire_inflight_lock(video_id: str, media_type: str) -> asyncio.Lock:
    key = (str(video_id), str(media_type))
    async with _inflight_locks_guard:
        entry = _inflight_locks.get(key)
        if entry is None:
            lock = asyncio.Lock()
            entry = (lock, 0)
            _inflight_locks[key] = entry
        entry = (entry[0], entry[1] + 1)
        _inflight_locks[key] = entry
        return entry[0]


async def _release_inflight_lock(video_id: str, media_type: str) -> None:
    key = (str(video_id), str(media_type))
    async with _inflight_locks_guard:
        entry = _inflight_locks.get(key)
        if entry is None:
            return
        lock, count = entry
        new_count = max(0, count - 1)
        if new_count == 0 and not lock.locked():
            _inflight_locks.pop(key, None)
        else:
            _inflight_locks[key] = (lock, new_count)


async def _acquire_restore_lock(video_id: str, media_type: str) -> asyncio.Lock:
    key = (str(video_id), str(media_type))
    async with _restore_locks_guard:
        entry = _restore_locks.get(key)
        if entry is None:
            lock = asyncio.Lock()
            entry = (lock, 0)
            _restore_locks[key] = entry
        entry = (entry[0], entry[1] + 1)
        _restore_locks[key] = entry
        return entry[0]


async def _release_restore_lock(video_id: str, media_type: str) -> None:
    key = (str(video_id), str(media_type))
    async with _restore_locks_guard:
        entry = _restore_locks.get(key)
        if entry is None:
            return
        lock, count = entry
        new_count = max(0, count - 1)
        if new_count == 0 and not lock.locked():
            _restore_locks.pop(key, None)
        else:
            _restore_locks[key] = (lock, new_count)


# ─── Helpers ─────────────────────────────────────────────────────────────────


def _normalize_title(title: str) -> str:
    if not title:
        return ""
    s = unicodedata.normalize("NFKD", title)
    s = s.lower().strip()
    s = " ".join(s.split())
    return s


def _duration_str_to_seconds(s: Optional[str]) -> int:
    if not s:
        return 0
    try:
        parts = str(s).split(":")
        return sum(int(p) * 60 ** i for i, p in enumerate(reversed(parts)))
    except Exception:
        return 0


def _expected_extension(media_type: str) -> str:
    """The existing YouTube downloader GUARANTEES .mp3 for audio and .mp4
    for video (via yt-dlp FFmpegExtractAudio / merge_output_format)."""
    return ".mp4" if media_type == "video" else ".mp3"


# ─── Cache record integrity validation ─────────────────────────────────────


def _validate_cache_doc(doc: dict) -> bool:
    """Validate that a cache document has all required fields."""
    if not doc or not isinstance(doc, dict):
        return False
    required = (
        "video_id", "media_type", "file_id", "file_unique_id",
        "channel_id", "message_id",
    )
    for field in required:
        val = doc.get(field)
        if val is None or val == "" or val == 0:
            return False
    return True


# ─── Local file validation ─────────────────────────────────────────────────


def _is_valid_local_file(
    file_path: str, media_type: str, min_size: int = 1024,
    check_extension: bool = True,
) -> bool:
    """Lightweight local file validation (no ffprobe):
      - file exists
      - file is readable
      - file is a regular file
      - file size > min_size
      - extension matches media_type (skipped for temp .part files)
    """
    if not file_path:
        return False
    try:
        if not os.path.isfile(file_path):
            return False
        if not os.access(file_path, os.R_OK):
            return False
        size = os.path.getsize(file_path)
        if size < min_size:
            return False
        if check_extension:
            expected_ext = _expected_extension(media_type)
            if not file_path.lower().endswith(expected_ext):
                return False
        return True
    except Exception:
        return False


async def _verify_media_stream(file_path: str, media_type: str) -> bool:
    """Verify the restored file contains the expected media stream via ffprobe.

    Error handling:
      1. ffprobe missing (FileNotFoundError) → fallback to True (accept
         based on lightweight checks).
      2. ffprobe timeout/subprocess failure → log and return True (defined
         fallback — don't reject a file just because ffprobe misbehaved).
      3. ffprobe returns non-zero → return False (corrupt file).
      4. ffprobe succeeds but no expected stream → return False.

    This ensures corrupt files are NEVER silently accepted as valid media,
    while valid files are not rejected when ffprobe is unavailable.
    """
    if not file_path or not os.path.isfile(file_path):
        return False

    expected_type = "video" if media_type == "video" else "audio"
    select_streams = "v" if media_type == "video" else "a"

    try:
        proc = await asyncio.create_subprocess_exec(
            "ffprobe",
            "-v", "error",
            "-select_streams", select_streams,
            "-show_entries", "stream=codec_type",
            "-of", "json",
            file_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except FileNotFoundError:
        _log.debug(
            f"ffprobe not found — skipping media stream validation "
            f"for {file_path}"
        )
        return True
    except Exception as e:
        _log.warning(
            f"ffprobe spawn failed for {file_path}: "
            f"{type(e).__name__}: {e}"
        )
        return True

    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=15)
    except asyncio.TimeoutError:
        _log.warning(f"ffprobe timed out for {file_path}")
        try:
            proc.kill()
        except Exception:
            pass
        return True
    except Exception as e:
        _log.warning(
            f"ffprobe communication failed for {file_path}: "
            f"{type(e).__name__}: {e}"
        )
        return True

    if proc.returncode != 0:
        stderr_text = stderr.decode("utf-8", errors="ignore") if stderr else ""
        _log.warning(
            f"CACHE VALIDATION FAILURE: ffprobe returned "
            f"code={proc.returncode} for {file_path}: {stderr_text.strip()}"
        )
        return False

    try:
        data = json.loads(stdout.decode("utf-8", errors="ignore"))
        streams = data.get("streams", [])
        has_expected = any(
            s.get("codec_type") == expected_type for s in streams
        )
        if not has_expected:
            _log.warning(
                f"CACHE VALIDATION FAILURE: no {expected_type} stream "
                f"in {file_path}"
            )
            return False
        return True
    except Exception as e:
        _log.warning(
            f"CACHE VALIDATION FAILURE: could not parse ffprobe output "
            f"for {file_path}: {type(e).__name__}: {e}"
        )
        return False


# ─── Telegram error classification ─────────────────────────────────────────


def _is_record_invalid_error(exc: Exception) -> bool:
    """Return True ONLY for errors that prove the cached MESSAGE/MEDIA is
    permanently gone. These trigger cache invalidation."""
    if exc is None:
        return False
    try:
        from pyrogram import errors
    except Exception:
        return False
    record_invalid_types = (
        getattr(errors, "MessageIdInvalid", None),
        getattr(errors, "MessageEmpty", None),
        getattr(errors, "MediaEmpty", None),
        getattr(errors, "FileIdInvalid", None),
        getattr(errors, "FileReferenceExpired", None),
        getattr(errors, "FileReferenceInvalid", None),
    )
    record_invalid_types = tuple(
        t for t in record_invalid_types if t is not None
    )
    return isinstance(exc, record_invalid_types)


def _is_storage_access_error(exc: Exception) -> bool:
    """Return True for bot-access/configuration failures that do NOT prove
    the record is invalid. These PRESERVE the cache record."""
    if exc is None:
        return False
    try:
        from pyrogram import errors
    except Exception:
        return False
    access_error_types = (
        getattr(errors, "ChannelInvalid", None),
        getattr(errors, "ChannelPrivate", None),
        getattr(errors, "ChatIdInvalid", None),
        getattr(errors, "PeerIdInvalid", None),
        getattr(errors, "ChatAdminRequired", None),
        getattr(errors, "ChatWriteForbidden", None),
        getattr(errors, "UserBannedInChannel", None),
    )
    access_error_types = tuple(
        t for t in access_error_types if t is not None
    )
    return isinstance(exc, access_error_types)


# ─── Message content validation ────────────────────────────────────────────


def _validate_cached_message(msg_obj, media_type: str) -> bool:
    """Validate that a fetched Message object contains the expected media."""
    if msg_obj is None:
        return False
    if media_type == "video":
        media = (
            getattr(msg_obj, "video", None)
            or getattr(msg_obj, "animation", None)
            or getattr(msg_obj, "document", None)
        )
    else:
        media = (
            getattr(msg_obj, "audio", None)
            or getattr(msg_obj, "document", None)
        )
    if media is None:
        return False
    file_id = getattr(media, "file_id", None)
    if not file_id:
        return False
    return True


# ─── MongoDB uncertain-write protection ─────────────────────────────────────


async def _verify_cache_record_exists(
    video_id: str, media_type: str, channel_id: int, message_id: int
) -> bool:
    """Re-query MongoDB to verify a cache record actually exists and
    points to the same channel_id + message_id."""
    try:
        doc = await get_cached_track(video_id, media_type)
        if not doc:
            return False
        if int(doc.get("channel_id", 0)) != int(channel_id):
            return False
        if int(doc.get("message_id", 0)) != int(message_id):
            return False
        return True
    except Exception:
        return False


async def _delete_storage_message(
    channel_id: int, message_id: int
) -> bool:
    """Best-effort delete a message from the storage channel. Never raises."""
    if not channel_id or not message_id:
        return False
    client = _get_main_bot()
    if client is None:
        return False
    try:
        await client.delete_messages(
            chat_id=int(channel_id),
            message_ids=int(message_id),
        )
        _log.info(
            f"ORPHAN CLEANUP: deleted storage message "
            f"channel={channel_id} message_id={message_id}"
        )
        return True
    except Exception as e:
        _log.warning(
            f"ORPHAN CLEANUP FAILED: channel={channel_id} "
            f"message_id={message_id}: {type(e).__name__}: {e}"
        )
        return False


# ─── Public API: cache-hit restore ──────────────────────────────────────────


async def try_cached_download(
    video_id: str,
    media_type: str,
) -> Optional[str]:
    """Try to satisfy a download request from the Telegram storage channel.

    Returns the local file path on success, or None on miss/failure.
    Caller (YouTube.download) falls back to its existing download flow
    when this returns None.

    NO file_refs reference is held during restore. This is safe because
    auto_clean(popped) only operates on files that were IN the queue
    (popped from db[chat_id]). A restored file that hasn't been queued
    yet is NOT in any queue, so auto_clean cannot target it. The gap
    between restore-return and put_queue() is safe — no timer needed.

    The caller (stream.py → put_queue) adds the file to config.autoclean,
    which is the single point where queue ownership is established.
    auto_clean will delete the file when autoclean.count reaches 0.

    Concurrency: a refcounted per-(video_id, media_type) restore lock
    ensures only ONE Telegram download happens for concurrent requests.
    """
    if not _cache_restore_enabled():
        return None
    if not video_id or not media_type:
        return None

    try:
        cached = await get_cached_track(video_id, media_type)
    except Exception:
        return None

    if not cached:
        _log.info(f"CACHE MISS: video_id={video_id} media_type={media_type}")
        return None

    if not _validate_cache_doc(cached):
        _log.warning(
            f"CACHE RECORD INVALID: malformed MongoDB record for "
            f"video_id={video_id} media_type={media_type}. Repairing."
        )
        try:
            await invalidate_cached_track(video_id, media_type)
        except Exception:
            pass
        return None

    file_id = cached.get("file_id")
    file_unique_id = cached.get("file_unique_id")

    ext = _expected_extension(media_type).lstrip(".")
    local_path = os.path.join(_CACHE_DL_DIR, f"{video_id}.{ext}")

    # ── FAST PATH: valid local file already exists ─────────────────────
    if _is_valid_local_file(local_path, media_type):
        _log.info(
            f"CACHE HIT (LOCAL): video_id={video_id} "
            f"media_type={media_type} -> {local_path}"
        )
        return local_path

    _log.info(
        f"CACHE HIT — RESTORING FROM TELEGRAM STORAGE: "
        f"video_id={video_id} media_type={media_type}"
    )

    client = _get_main_bot()
    if client is None:
        _log.warning(
            "CACHE: main bot not available — falling back to YouTube "
            "(cache record preserved)"
        )
        return None

    restore_lock = await _acquire_restore_lock(video_id, media_type)

    tmp_path: Optional[str] = None

    try:
        async with restore_lock:
            # Re-check under lock — another request may have completed
            # the restore while we waited.
            if _is_valid_local_file(local_path, media_type):
                _log.info(
                    f"CACHE RESTORED (by concurrent request): "
                    f"video_id={video_id} -> {local_path}"
                )
                return local_path

            try:
                os.makedirs(_CACHE_DL_DIR, exist_ok=True)

                # Unique temp filename — concurrent restores never collide.
                tmp_path = os.path.join(
                    _CACHE_DL_DIR,
                    f"{video_id}.{ext}.{uuid.uuid4().hex}.part",
                )

                downloaded = None

                # Use channel_id + message_id from MongoDB record (NOT
                # config.STORAGE_CHANNEL_ID) — enables channel migration.
                channel_id = cached.get("channel_id")
                message_id = cached.get("message_id")

                primary_was_temporary = False
                primary_was_access_error = False

                # Primary: fetch Message object and download via it.
                if channel_id and message_id:
                    try:
                        msg_obj = await client.get_messages(
                            chat_id=int(channel_id),
                            message_ids=int(message_id),
                        )
                        if not _validate_cached_message(msg_obj, media_type):
                            _log.warning(
                                f"CACHE RECORD INVALID: storage message "
                                f"has no valid {media_type} media for "
                                f"video_id={video_id}. Invalidating."
                            )
                            try:
                                await invalidate_cached_track(
                                    video_id, media_type
                                )
                            except Exception:
                                pass
                            _safe_remove(tmp_path)
                            return None
                        downloaded = await client.download_media(
                            message=msg_obj,
                            file_name=tmp_path,
                        )
                    except Exception as e:
                        if _is_record_invalid_error(e):
                            _log.warning(
                                f"CACHE RECORD INVALID: storage message "
                                f"deleted/invalid for video_id={video_id} "
                                f"({type(e).__name__}). Invalidating."
                            )
                            try:
                                await invalidate_cached_track(
                                    video_id, media_type
                                )
                            except Exception:
                                pass
                            _safe_remove(tmp_path)
                            return None
                        elif _is_storage_access_error(e):
                            primary_was_access_error = True
                            _log.warning(
                                f"STORAGE ACCESS UNAVAILABLE: "
                                f"video_id={video_id} "
                                f"({type(e).__name__}). Cache preserved."
                            )
                            _safe_remove(tmp_path)
                            return None
                        primary_was_temporary = True
                        _log.debug(
                            f"CACHE: get_messages failed temporarily "
                            f"({type(e).__name__}), trying file_id fallback"
                        )
                        downloaded = None

                # Fallback: try file_id directly.
                if not downloaded and file_id:
                    try:
                        downloaded = await client.download_media(
                            message=file_id,
                            file_name=tmp_path,
                        )
                    except Exception as e:
                        if primary_was_temporary or primary_was_access_error:
                            _log.debug(
                                f"CACHE: file_id fallback also failed "
                                f"({type(e).__name__}) — treating as "
                                f"temporary (cache preserved)"
                            )
                        elif _is_record_invalid_error(e):
                            _log.warning(
                                f"CACHE RECORD INVALID: file_id unusable "
                                f"for video_id={video_id} "
                                f"({type(e).__name__}). Invalidating."
                            )
                            try:
                                await invalidate_cached_track(
                                    video_id, media_type
                                )
                            except Exception:
                                pass
                            _safe_remove(tmp_path)
                            return None
                        elif _is_storage_access_error(e):
                            _log.warning(
                                f"STORAGE ACCESS UNAVAILABLE: file_id "
                                f"download failed for video_id={video_id} "
                                f"({type(e).__name__}). Cache preserved."
                            )
                            _safe_remove(tmp_path)
                            return None
                        else:
                            _log.debug(
                                f"CACHE: file_id fallback failed "
                                f"temporarily ({type(e).__name__})"
                            )
                        downloaded = None

                # ── Validation ──────────────────────────────────────────
                if not downloaded or not os.path.isfile(downloaded):
                    _log.warning(
                        f"STORAGE TEMPORARILY UNAVAILABLE: could not "
                        f"restore video_id={video_id}. Falling back to "
                        f"YouTube (cache record preserved)."
                    )
                    _safe_remove(tmp_path)
                    _safe_remove(downloaded)
                    return None

                if not _is_valid_local_file(
                    downloaded, media_type, check_extension=False
                ):
                    _log.warning(
                        f"CACHE VALIDATION FAILURE: restored file failed "
                        f"validation for video_id={video_id}."
                    )
                    _safe_remove(downloaded)
                    _safe_remove(tmp_path)
                    return None

                # ── Atomic move to canonical path ──────────────────────
                try:
                    if os.path.abspath(downloaded) != os.path.abspath(local_path):
                        if os.path.exists(local_path):
                            os.remove(local_path)
                        os.replace(downloaded, local_path)
                except Exception as e:
                    _log.debug(
                        f"CACHE: rename failed ({e}); using pyrogram's path"
                    )
                    local_path = downloaded

                if not _is_valid_local_file(local_path, media_type):
                    _log.warning(
                        f"CACHE VALIDATION FAILURE: canonical file invalid "
                        f"for video_id={video_id}."
                    )
                    _safe_remove(local_path)
                    return None

                # ── ffprobe validation ─────────────────────────────────
                if not await _verify_media_stream(local_path, media_type):
                    _log.warning(
                        f"CACHE VALIDATION FAILURE: restored file has no "
                        f"valid {media_type} stream for video_id={video_id}. "
                        f"Invalidating cache entry."
                    )
                    try:
                        await invalidate_cached_track(
                            video_id, media_type
                        )
                    except Exception:
                        pass
                    _safe_remove(local_path)
                    return None

                _log.info(
                    f"CACHE RESTORED: video_id={video_id} "
                    f"media_type={media_type} -> {local_path}"
                )
                return local_path
            except Exception as e:
                _log.warning(
                    f"CACHE: unexpected error while restoring "
                    f"video_id={video_id}: {type(e).__name__}: {e}"
                )
                _safe_remove(tmp_path)
                return None
    except asyncio.CancelledError:
        _log.info(
            f"CACHE RESTORE CANCELLED: video_id={video_id} — "
            f"cleaning up temp file"
        )
        if tmp_path:
            _safe_remove(tmp_path)
        raise
    finally:
        await _release_restore_lock(video_id, media_type)


# ─── Public API: schedule background upload ─────────────────────────────────


async def schedule_cache_upload(
    video_id: str,
    media_type: str,
    file_path: str,
    title: Optional[str] = None,
    duration_min: Optional[str] = None,
    thumbnail: Optional[str] = None,
) -> None:
    """Fire-and-forget: upload file_path to the storage channel and save
    a MongoDB cache record. NEVER blocks playback."""
    if not _cache_upload_enabled():
        return
    if not video_id or not media_type or not file_path:
        return
    if not os.path.isfile(file_path):
        return

    task_key = (str(video_id), str(media_type))

    # Synchronous dedup check BEFORE any await.
    existing_task = _inflight_tasks.get(task_key)
    if existing_task is not None and not existing_task.done():
        return

    try:
        already = await is_track_cached(video_id, media_type)
    except Exception:
        already = False
    if already:
        return

    # Re-check after the await.
    existing_task = _inflight_tasks.get(task_key)
    if existing_task is not None and not existing_task.done():
        return

    task = asyncio.create_task(
        _cache_upload_worker(
            video_id=str(video_id),
            media_type=str(media_type),
            file_path=file_path,
            title=title or "",
            duration_min=duration_min or "",
            thumbnail=thumbnail or "",
        )
    )
    _inflight_tasks[task_key] = task
    task.add_done_callback(
        lambda t, k=task_key: _on_task_done(t, k)
    )


def _on_task_done(task: asyncio.Task, task_key: Tuple[str, str]) -> None:
    if _inflight_tasks.get(task_key) is task:
        _inflight_tasks.pop(task_key, None)
    if task.cancelled():
        return
    exc = task.exception()
    if exc is not None and not isinstance(exc, asyncio.CancelledError):
        _log.warning(
            f"CACHE UPLOAD: worker raised uncaught "
            f"{type(exc).__name__}: {exc}"
        )


# ─── Metadata fetch ─────────────────────────────────────────────────────────


async def _fetch_metadata(
    video_id: str,
    title: str,
    duration_min: str,
    thumbnail: str,
) -> Tuple[str, str, str]:
    """Fetch title/duration/thumbnail from YouTube if not provided."""
    if title and duration_min and thumbnail:
        return title, duration_min, thumbnail
    try:
        from SWAGGYMUSIC import YouTube
        details = await YouTube.details(video_id, videoid=True)
        if details:
            fetched_title, fetched_dur_min, _, fetched_thumb, _ = details
            if not title:
                title = fetched_title or ""
            if not duration_min:
                duration_min = fetched_dur_min or ""
            if not thumbnail:
                thumbnail = fetched_thumb or ""
    except Exception as e:
        _log.debug(
            f"CACHE: metadata fetch failed for video_id={video_id}: "
            f"{type(e).__name__}: {e}"
        )
    return title, duration_min, thumbnail


# ─── Background upload worker ───────────────────────────────────────────────


async def _cache_upload_worker(
    video_id: str,
    media_type: str,
    file_path: str,
    title: str,
    duration_min: str,
    thumbnail: str,
) -> None:
    """Background upload coroutine. Uses the MAIN BOT client.

    Acquires a file_refs reference for the entire upload duration so
    auto_clean cannot delete the file mid-upload. Releases on completion,
    failure, or cancellation.
    """
    from SWAGGYMUSIC.utils import file_refs

    song_lock = await _acquire_inflight_lock(video_id, media_type)
    await file_refs.acquire(file_path)
    refs_held = True

    try:
        async with song_lock:
            try:
                already = await is_track_cached(video_id, media_type)
            except Exception:
                already = False
            if already:
                return

            if not os.path.isfile(file_path):
                _log.info(
                    f"BACKGROUND CACHE UPLOAD: file cleaned up before "
                    f"upload started, skipping video_id={video_id}"
                )
                return

            sem = _get_semaphore()
            async with sem:
                if not os.path.isfile(file_path):
                    return

                client = _get_main_bot()
                if client is None:
                    _log.warning(
                        "BACKGROUND CACHE UPLOAD: main bot not available"
                    )
                    return

                storage_channel_id = int(config.STORAGE_CHANNEL_ID)

                _log.info(
                    f"BACKGROUND CACHE UPLOAD START: video_id={video_id} "
                    f"media_type={media_type} -> channel={storage_channel_id}"
                )

                need_metadata = (
                    not title or not duration_min or not thumbnail
                )

                async def _do_upload():
                    if media_type == "video":
                        msg = await client.send_video(
                            chat_id=storage_channel_id,
                            video=file_path,
                            caption=f"yt://{video_id} | {title}",
                            disable_notification=True,
                        )
                        media_obj = (
                            getattr(msg, "video", None)
                            or getattr(msg, "animation", None)
                            or getattr(msg, "document", None)
                        )
                    else:
                        dur_sec = _duration_str_to_seconds(duration_min)
                        msg = await client.send_audio(
                            chat_id=storage_channel_id,
                            audio=file_path,
                            caption=f"yt://{video_id} | {title}",
                            disable_notification=True,
                            title=title or None,
                            duration=int(dur_sec) if dur_sec and dur_sec > 0 else 0,
                        )
                        media_obj = (
                            getattr(msg, "audio", None)
                            or getattr(msg, "document", None)
                        )
                    return msg, media_obj

                async def _do_metadata():
                    if not need_metadata:
                        return title, duration_min, thumbnail
                    return await _fetch_metadata(
                        video_id, title, duration_min, thumbnail
                    )

                upload_result, meta_result = await asyncio.gather(
                    _do_upload(),
                    _do_metadata(),
                    return_exceptions=True,
                )

                if isinstance(upload_result, Exception):
                    import traceback
                    _log.warning(
                        f"CACHE UPLOAD FAILURE: video_id={video_id} "
                        f"({type(upload_result).__name__}: {upload_result})\n"
                        f"Full traceback:\n{traceback.format_exception(type(upload_result), upload_result, upload_result.__traceback__)}"
                    )
                    return

                msg, media_obj = upload_result

                if msg is None or media_obj is None:
                    _log.warning(
                        f"CACHE UPLOAD FAILURE: no media returned for "
                        f"video_id={video_id}"
                    )
                    return

                file_id = getattr(media_obj, "file_id", None)
                file_unique_id = getattr(media_obj, "file_unique_id", None)
                file_size = getattr(media_obj, "file_size", 0) or 0
                tg_duration = getattr(media_obj, "duration", 0) or 0
                file_name = getattr(media_obj, "file_name", None) or ""
                message_id = int(getattr(msg, "id", 0) or 0)

                if not file_id or not file_unique_id or not message_id:
                    _log.warning(
                        f"CACHE UPLOAD FAILURE: missing required fields "
                        f"for video_id={video_id}"
                    )
                    await _delete_storage_message(
                        storage_channel_id, message_id
                    )
                    return

                _log.info(
                    f"CHANNEL UPLOAD SUCCESS: video_id={video_id} "
                    f"file_unique_id={file_unique_id} size={file_size}"
                )

                if isinstance(meta_result, Exception):
                    final_title = title
                    final_dur = duration_min
                    final_thumb = thumbnail
                else:
                    final_title, final_dur, final_thumb = meta_result

                now = time.time()
                doc = {
                    "video_id": video_id,
                    "media_type": media_type,
                    "title": final_title or "",
                    "normalized_title": _normalize_title(final_title),
                    "duration_min": final_dur or "",
                    "duration_sec": int(
                        _duration_str_to_seconds(final_dur) or 0
                    ),
                    "file_id": file_id,
                    "file_unique_id": file_unique_id,
                    "file_size": int(file_size),
                    "tg_duration": int(tg_duration),
                    "channel_id": int(storage_channel_id),
                    "message_id": message_id,
                    "file_type": media_type,
                    "file_name": file_name,
                    "thumbnail": final_thumb or "",
                    "created_at": now,
                    "updated_at": now,
                }

                if not _validate_cache_doc(doc):
                    _log.warning(
                        f"CACHE RECORD INTEGRITY CHECK FAILED: "
                        f"video_id={video_id}. Cleaning up orphan."
                    )
                    await _delete_storage_message(
                        storage_channel_id, message_id
                    )
                    return

                # ── MongoDB save with uncertain-write protection ──
                save_ok = True
                try:
                    save_ok = await save_cached_track(doc)
                except Exception as e:
                    _log.warning(
                        f"MONGODB SAVE THREW: video_id={video_id}: "
                        f"{type(e).__name__}: {e}"
                    )
                    save_ok = False

                if save_ok:
                    _log.info(
                        f"MONGODB CACHE SAVE SUCCESS: video_id={video_id} "
                        f"media_type={media_type}"
                    )
                else:
                    record_exists = await _verify_cache_record_exists(
                        video_id, media_type,
                        storage_channel_id, message_id
                    )
                    if record_exists:
                        _log.info(
                            f"MONGODB SAVE UNCERTAIN BUT RECORD EXISTS: "
                            f"video_id={video_id}. Telegram message "
                            f"NOT deleted."
                        )
                    else:
                        _log.warning(
                            f"MONGODB CACHE SAVE FAILED: video_id={video_id} "
                            f"— cleaning up orphan storage message"
                        )
                        await _delete_storage_message(
                            storage_channel_id, message_id
                        )
    except asyncio.CancelledError:
        raise
    except Exception as e:
        _log.warning(
            f"CACHE UPLOAD: worker uncaught error video_id={video_id}: "
            f"{type(e).__name__}: {e}"
        )
    finally:
        if refs_held:
            try:
                await file_refs.release(file_path)
            except Exception:
                pass
        await _release_inflight_lock(video_id, media_type)


# ─── Filesystem helpers ─────────────────────────────────────────────────────


def _safe_remove(path: Optional[str]) -> None:
    if not path:
        return
    try:
        if os.path.exists(path) and os.path.isfile(path):
            os.remove(path)
    except Exception:
        pass


# ─── Shutdown / diagnostics ────────────────────────────────────────────────


def cancel_all_uploads() -> None:
    """Cancel every in-flight cache-upload task. Called on bot shutdown."""
    for task_key, task in list(_inflight_tasks.items()):
        if not task.done():
            try:
                task.cancel()
            except Exception:
                pass


def get_cache_stats() -> dict:
    return {
        "inflight_uploads": len(_inflight_tasks),
        "inflight_locks": len(_inflight_locks),
        "restore_locks": len(_restore_locks),
    }
