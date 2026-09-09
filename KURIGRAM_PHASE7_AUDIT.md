# Kurigram Migration — Phase 7+ Audit

## Scope
Startup/import graph and Telegram-facing handler registration were audited after the Kurigram 2.2.25 migration. Phase 7+ applies the static-audit fixes that did not change user-facing behavior.

## Results
- Python source files discovered: 100
- `compileall`: PASS
- Legacy PyroBlack/PyroFork/TgCrypto-pyroblack references in active source/config: none
- Private `pytgcalls_session` dependency: none
- Dynamic plugin loader remains `SWAGGYMUSIC.plugins` + `ALL_MODULES` and is unchanged.
- Telegram handler surface uses the normal Pyrogram-compatible decorators (`on_message`, `on_callback_query`, `on_chat_member_updated`), which Kurigram documents as compatible with the Pyrogram import namespace.
- `resolve_peer()` calls remain on the existing client objects; no unnecessary API rewrite was made.

## Important finding — NOT changed
The repository creates two sets of Pyrogram/Kurigram `Client` objects for each assistant session:

1. `SWAGGYMUSIC.core.userbot.Userbot` creates the five assistant clients (with `no_updates=True`).
2. `SWAGGYMUSIC.core.call.Call` creates another five clients using the same session strings (with `no_updates=None`) and passes those into PyTgCalls.

This is the **safe** design and must NOT be refactored:
- Kurigram's `Client.__init__` forces `SQLiteStorage(in_memory=True)` whenever `session_string` is provided, so the two clients per session string do **not** contend on a `.session` file on disk.
- The `no_updates=True` flag on the Userbot clients prevents update-stream duplication; only the Call clients receive updates, which is what PyTgCalls requires (it attaches `@client.on_raw_update(group=-9999)` only on the Call-side client — see `pytgcalls/mtproto/pyrogram_client.py:105`).
- Sharing the Userbot client with PyTgCalls would trigger PyTgCalls' `no_updates mode is not recommended` warning and silently break its update dispatch.

## Static-compatibility verification (Phase 7+)
Installed `kurigram==2.2.25`, `py-tgcalls==2.3.3`, `ntgcalls==2.2.5` in a venv and:
- `MtProtoClient(100, kurigram_client)` → `package_name='pyrogram'`, `_bind_client=PyrogramClient` — PyTgCalls correctly identifies Kurigram as a pyrogram-namespace client.
- `PyTgCalls(kurigram_client, cache_duration=100)` constructs successfully.
- `Environment.check_environment()` passes (Kurigram 2.2.25 ≥ PyTgCalls' required 1.2.20).
- All Client attributes/methods PyTgCalls relies on exist in Kurigram: `on_raw_update(group=)`, `resolve_peer`, `is_connected`, `no_updates`, `get_me`, `media_sessions`, `storage.test_mode/dc_id/auth_key`, `start`, `add_handler`.
- `import SWAGGYMUSIC` succeeds; 44/48 plugins import cleanly. The 4 plugin import failures (`admins.callback`, `misc.autoleave`, `misc.broadcast`, `misc.seeker`) raise `RuntimeError: no running event loop` because they spawn `asyncio.create_task` at import time. In production, plugins are imported inside `init()` which runs inside `asyncio.run(init())`, so they will not fail at runtime. **Pre-existing behavior, not Kurigram-related.**

## Phase 7+ fixes applied (no behavior change)
1. `render.yaml`: `pip install ".[all]"` → `pip install -r requirements.txt`. The `.[all]` extra does not exist in `pyproject.toml` (`optional-dependencies` is empty), so Render deploys would fail. Render now uses the same `requirements.txt` that Docker/Koyeb/Heroku use.
2. `strings/__init__.py`: replaced relative-path `./strings/langs/` with `os.path.join(os.path.dirname(os.path.abspath(__file__)), "langs")`. The old form only worked when `CWD == project_root`; the new form works for `pip install -e .`, the `swaggymusic` console script, and `python -m SWAGGYMUSIC` from any directory.
3. `SWAGGYMUSIC/__main__.py`: `asyncio.get_event_loop().run_until_complete(init())` → `asyncio.run(init())`. Removes the Python 3.10+ `DeprecationWarning` and avoids the future removal in 3.14. No runtime behavior change.
4. Removed orphan/backup files that were never loaded by the plugin loader (which only matches `*.py`):
   - `SWAGGYMUSIC/platforms/Youtube.p` — stale older snapshot of `Youtube.py`; the active `Youtube.py` is the modern refactored version.
   - `SWAGGYMUSIC/plugins/Vclogger.py#` — Emacs-style auto-save backup; no active `Vclogger.py` counterpart exists. The Vclogger plugin was already inactive.
   - `log.txt` — leftover test artifact from a local audit run; covered by `.gitignore`.

## Packaging cleanup
Stale `__pycache__` and `.pyc` artifacts were removed from the distribution tree. These are also in `.gitignore` and will not be committed.

## Current production dependency baseline
- Kurigram 2.2.25
- PyTgCalls 2.3.3
- ntgcalls 2.2.5
- Python 3.11 target

## Music cache architecture confirmation
`SWAGGYMUSIC/utils/music_cache.py` uses the **MAIN BOT client only** (`from SWAGGYMUSIC import app` — see `_get_main_bot()` at line 146-161). Assistant userbots are never used for Telegram storage operations. The module docstring (lines 49-53) documents this invariant explicitly.

## Runtime boundary
This phase does not claim successful Telegram login, voice-chat join, stream playback, reconnect, or skip/pause/resume. Those require a real Telegram runtime with valid credentials and a test group call. Specifically, the following remain to be validated in the deployment environment:
- Real Telegram login with valid `API_ID`/`API_HASH`/`BOT_TOKEN`
- Real assistant session strings (`STRING1`-`STRING5`) — two clients per session string connecting concurrently
- Group call join/play/pause/resume/skip/seek/speed/volume/filter/stop
- DC-migration path (`media_sessions` in `pytgcalls/mtproto/pyrogram_client.py:830-900`)
- Reconnect after `TelegramServerError`
- MongoDB connection under real `MONGO_DB_URI`
- Storage-channel upload with real `STORAGE_CHANNEL_ID`
