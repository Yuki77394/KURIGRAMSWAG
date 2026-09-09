"""Safe file lifecycle reference counting.

Simple deterministic model:
  - Multiple consumers can hold references simultaneously (refcount).
  - auto_clean() calls mark_for_delete() — if refs > 0, deletion is
    deferred until the last consumer releases.
  - If refs == 0 at mark_for_delete time, the file is deleted immediately.

This module exists because the background cache-upload task reads a file
that auto_clean() might want to delete (after playback ends). Without this
protection, auto_clean would delete the file mid-upload, causing
FileNotFoundError and corrupt cache entries.

Restore path does NOT need file_refs protection:
  auto_clean(popped) only operates on files that were IN the queue
  (popped from db[chat_id]). A restored file that hasn't been queued yet
  is NOT in any queue, so auto_clean cannot target it. Therefore, the
  gap between try_cached_download() returning and put_queue() adding the
  file to the queue is SAFE — no timer-based handoff is needed.

Design rules:
  - acquire(path)  → +1 ref
  - release(path)   → -1 ref; if refs hit 0 AND mark_for_delete was
                      called, delete the file now.
  - mark_for_delete(path) → if refs == 0, delete immediately. Otherwise
                      record the pending delete; the file will be deleted
                      when the last consumer calls release().
  - has_refs(path)  → fast sync check used by auto_clean.
  - Never raises — all filesystem errors are swallowed.
  - Counter never goes negative (clamped at 0).
  - Pending deletes are idempotent (duplicate calls are safe).
  - NO timer-based synchronization. NO generation tokens. NO transfer_ref.
    Just a simple refcount + pending-delete flag.
"""

import asyncio
import os
from typing import Dict, Set

from SWAGGYMUSIC.logging import LOGGER

_log = LOGGER(__name__)

# Per-file reference counter. A path key is present iff at least one
# consumer has called acquire() and not yet released().
_refs: Dict[str, int] = {}

# Files that auto_clean() wanted to delete but couldn't (because refs > 0
# at that moment). When the last ref is released, the file is deleted and
# the path is removed from this set.
_pending_deletes: Set[str] = set()

# Single async lock guarding _refs and _pending_deletes. Critical sections
# are tiny (dict get/set only), so contention is negligible.
_guard = asyncio.Lock()


async def acquire(file_path: str) -> None:
    """Register a new consumer for `file_path`.

    MUST be matched by a `release(file_path)` call in a finally-block.
    Nested acquires are allowed and increment the counter.
    """
    if not file_path:
        return
    async with _guard:
        _refs[file_path] = _refs.get(file_path, 0) + 1


async def release(file_path: str) -> None:
    """Release one consumer reference for `file_path`.

    If the counter drops to zero AND mark_for_delete was previously
    called, the file is removed from disk now. Otherwise the counter is
    simply decremented.

    Never raises — all filesystem errors are swallowed.
    """
    if not file_path:
        return
    should_delete = False
    async with _guard:
        current = _refs.get(file_path, 0)
        if current <= 1:
            _refs.pop(file_path, None)
            should_delete = file_path in _pending_deletes
            if should_delete:
                _pending_deletes.discard(file_path)
        else:
            _refs[file_path] = current - 1

    if should_delete:
        try:
            if os.path.isfile(file_path):
                os.remove(file_path)
                _log.debug(
                    f"file_refs: deferred delete completed for {file_path}"
                )
        except Exception as e:
            _log.debug(
                f"file_refs: deferred delete failed for {file_path}: "
                f"{type(e).__name__}: {e}"
            )


async def mark_for_delete(file_path: str) -> None:
    """Tell the ref system that auto_clean wants this file gone.

    If no consumers currently hold refs, the file is deleted immediately.
    Otherwise the path is added to _pending_deletes and will be deleted
    when the last consumer calls release().

    Never raises.
    """
    if not file_path:
        return
    do_delete_now = False
    async with _guard:
        if _refs.get(file_path, 0) == 0:
            do_delete_now = True
        else:
            _pending_deletes.add(file_path)

    if do_delete_now:
        try:
            if os.path.isfile(file_path):
                os.remove(file_path)
        except Exception as e:
            _log.debug(
                f"file_refs: immediate delete failed for {file_path}: "
                f"{type(e).__name__}: {e}"
            )


def has_refs(file_path: str) -> bool:
    """Fast sync check: are there any outstanding consumers for this file?"""
    if not file_path:
        return False
    return _refs.get(file_path, 0) > 0


def stats() -> dict:
    """Diagnostic helper — returns current refs and pending deletes."""
    return {
        "refs": dict(_refs),
        "pending_deletes": list(_pending_deletes),
    }
