# AGENTS.md

Start with [CLAUDE.md](CLAUDE.md) for project overview, [KNOWLEDGE_BASE.md](KNOWLEDGE_BASE.md) for comprehensive reference, and [specs/](specs/) for authoritative constraints. This file covers what an agent is most likely to guess wrong.

## Toolchain reality

- **No build system:** no `pyproject.toml`, no `setup.py`, no venv management. `python main.py` is the only entrypoint.
- **No test framework, lint, or formatter.** `test/` contains ad-hoc scripts (run with `python test/<name>.py`).
- `pyrightconfig.json` is gitignored — do not rely on it in CI/automation.
- Dependencies are documented only: robot depends on `websocket-client`, `requests`, `Pillow`; the web app (single `webapp` process hosting the 6 feature modules) depends on `webapp/requirements.txt`.
- **Git hooks:** run `git config core.hooksPath .githooks` after clone to enable Conventional Commits validation on every commit.
- **Commit messages MUST be written in Chinese** with Conventional Commits format (e.g. `feat(任务): 新增周常全清称号`).
- **Commits MUST be logically chunked**: one commit = one logical change (feature/fix/test/docs/refactor), never bundle unrelated changes; the companion files of one logical change (code + behavior tests + spec + menu text + CHANGELOG + KNOWLEDGE_BASE) go in the SAME commit, unrelated fixes go to SEPARATE commits (see `specs/conventions.md` §Commit 提交分块).

## Plugin auto-import magic

Creating a plugin package in `plugins/<name>/` (or a bare `.py` file) is sufficient — `plugins/__init__.py` uses `pkgutil.walk_packages` to import every module, which triggers `@register_plugin`. No manual wiring needed. The decorator is at `core/utils.py:83`.

## Two path constants — one data

| Constant | Value | Use for |
|----------|-------|---------|
| `context.llonebot_data_path` | `/app/llonebot/server_data` | OneBot API calls (the bot process sees this path) |
| `context.python_data_path` | `./server_data` | Python file I/O |

**Using the wrong one is silent — the API call just returns empty/failure.**

## Week boundary is 08:00, not 00:00

Always use `get_monday_to_monday()` from `core.utils`. A "week" runs Monday 08:00 → next Monday 08:00. This also applies to `day_of_year()`, streak calculations, and heatmap logic.

## Threading model

Every event spawns a new thread with a **fresh Plugin instance**. Plugin instances are thread-local — do not store mutable state on `self` expecting it to persist across events. `TimedHeartbeatPlugin._last_run_minute` is a class-level dict, shared correctly.

## send_msg quirks

- Auto-routes: `group_id` present → group; only `user_id` → private; neither → `DEFAULT_GROUP_ID`.
- Auto-injects title prefixes before `@` mentions (via `_inject_titles_before_at`). Do not prepend titles manually.

## Hard constraints that agents miss

- **No `async`/`await`** — the system is synchronous, threading-based.
- **No relative imports** between plugins (exception: `menu/__init__.py`'s `from .bot_menu_text` is a known violation, do not replicate).
- **No f-string SQL** — use `?` parameterized queries (`database_manager.py` manages all tables).
- **`handle()` MUST have try/except** with `logger.exception()` — unhandled exceptions in threads die silently.
- **`match()` MUST NOT have side effects** (no DB writes, no message sends).
- **Specs MUST be updated in the same commit** as related code changes (see `specs/README.md` maintenance rules).
- **每次用户可见变更 MUST 同 commit 更新 `CHANGELOG.md` 并 bump `core/config.py::BOTERO_VERSION`**：在 CHANGELOG 顶部新增 `[新版本]` 节记录变更，版本号同步递增（新功能 minor / 修复 patch，如 1.9.0 → 1.9.1 / 1.10.0）；CHANGELOG 顶部版本节与 `BOTERO_VERSION` 必须一致。纯文档/测试/内部重构可只更新 CHANGELOG 不 bump。
- **New/renamed commands MUST update `plugins/menu/bot_menu_text.py`** in the same commit.
- **Touching protocol code** (`core/api.py`, `core/event.py`, `core/cq.py`, or any plugin's OneBot event/message-segment access) **MUST consult the authoritative upstream first** — see `specs/onebot-protocol.md` §权威上游文档; the LLOneBot doc index is mirrored at `specs/llms.txt` (fetch the relevant single page via webfetch before editing).

## Hardcoded values (no config file)

| What | Where | Value |
|------|-------|-------|
| WS URL | `main.py:14` | `ws://127.0.0.1:3001` |
| WS token | `main.py:15` | `123456` |
| Default group | `core/context.py:14` | `296470819` |
| Super user | `core/base.py:12` | `[1057613133]` |
| Bot QQ | `core/base.py:13` | `"3915014383"` |
| Download proxy | `core/utils.py:53-55` | `127.0.0.1:7890` |

## API behavior

- `call_api()` blocks up to 30s, returns `{}` on timeout.
- Most API methods return `0` / `""` / `False` on failure — always check return values.
- `group_id` from `self.bot_event` can be `None` in private messages — guard before use.

## Knowledge base maintenance

[KNOWLEDGE_BASE.md](KNOWLEDGE_BASE.md) is the comprehensive project knowledge base (full plugin catalog, database schema, economy details, title definitions, all hardcoded values, etc.). It was generated from a complete repository exploration.

**When to update:**
- After completing any feature development or significant code changes
- When adding/removing plugins, commands, or database tables
- When changing hardcoded constants, paths, or API behavior
- When modifying the economy (lottery odds, shop prices, point rewards)
- When changing the title system (TITLE_DEFS, condition titles, unlock rules)

**MUST:** Update `KNOWLEDGE_BASE.md` in the same commit as related code changes — alongside `specs/` and `plugins/menu/bot_menu_text.py` updates.
