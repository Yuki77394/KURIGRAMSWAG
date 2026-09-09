# Kurigram Migration

This build migrates the Telegram MTProto layer from PyroBlack to **Kurigram 2.2.25** without changing the application's existing `pyrogram` import namespace. Kurigram is a Pyrogram-compatible fork, so the plugin and handler flow remains intact.

## Runtime baseline

- Python: 3.11.9
- Kurigram: 2.2.25
- PyTgCalls: 2.3.3
- ntgcalls: 2.2.5
- FFmpeg: existing deployment/system FFmpeg

## Changed

- Replaced `pyroblack` and `TgCrypto-pyroblack` dependencies with `kurigram[fast]==2.2.25`.
- Upgraded PyTgCalls from 2.2.11/2.3.0 metadata to stable 2.3.3.
- Pinned stable ntgcalls 2.2.5 (compatible with PyTgCalls 2.3.3).
- Standardized Docker, Koyeb, Heroku runtime metadata around Python 3.11.
- Removed the stale `uv.lock` because it represented the pre-migration PyroBlack dependency graph and could silently restore the old stack.
- Preserved existing `from pyrogram ...` imports intentionally; these are the Kurigram-compatible namespace.

## Validation completed

- Python `compileall` passes for the complete source tree.
- No active source/deployment dependency references to `pyroblack` or `TgCrypto-pyroblack` remain.
- Existing plugin/module layout was not rewritten.
- Existing bot, assistant, queue, cache, platform resolver, and PyTgCalls call logic was preserved.

## Runtime validation limitation

A real Telegram/MongoDB/voice-chat runtime test was not possible in the isolated build environment because external package installation/network access is unavailable there. Before production deployment, install the pinned dependencies and run the bot against the real Telegram credentials and voice-chat test group. This is the only part that cannot be truthfully certified offline.
