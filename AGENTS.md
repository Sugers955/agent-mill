# AGENTS.md

## Language

- Use English for code comments and commit messages
- Chinese documentation is in `docs/zh/`, English in `docs/en/`

## Quick Commands

```bash
# Local development
make dev                              # Start backend:8000 + frontend:5173
make stop                             # Stop
make logs                             # View backend logs (last 50 lines)
make logs-f                           # Tail backend logs
make status                           # Check status
make clean                            # Cleanup temp files and processes

# Frontend build
make build                            # vue-tsc && vite build
make typecheck                        # TypeScript type check only

# Database
make db-migrate                       # Run database migration
make db-reset                         # Reset database (danger! deletes all data)
```

## Architecture Key Points

- **Dual streaming path**: `backend/app/runtime/agent_runner.py` (2200+ lines) routes by provider — Anthropic uses Claude Agent SDK true streaming, OpenAI-compatible uses `/v1/chat/completions` stream + `tool_calls` multi-turn loop (max 8 turns)
- **Database migration**: Uses `app/db/init_db.py` idempotent migration (`CREATE TABLE IF NOT EXISTS` + `ALTER TABLE ADD COLUMN IF NOT EXISTS`), auto-executes on startup
- **Mobile is independent Vue app**: `frontend/m.html` → `src/mobile/`, fully separate router/stores/views/styles — do not modify mobile code when working on desktop
- **Skill triform**: path type (ZIP upload SKILL.md), callable type (Python function), composite type (YAML DAG step orchestration)
- **Storage isolation**: `storage/uploads/<user_id>/`, `storage/outputs/<user_id>/`, `storage/skills/<code>/`

## Important Notes

- `.env` and `backend/.env` are gitignored — configure via `.env.example`
- Frontend has no test framework, no lint config, no CI/CD pipeline
- Backend has no unit tests, `pyproject.toml` has no test dependencies
- `main.py` `_auto_migrate()` auto-executes ALTER TABLE on startup — new columns must use IF NOT EXISTS
- Security: Anthropic path disables Bash/Write/Edit by default, input regex filtering, Skill upload AST scanning, file cwd sandbox
- SSE event order: `meta` → `thinking` → `text` → `tool_use` → `tool_result` → `file` → `ui` → `error` → `done`
- Update `docs/zh/PROJECT_OVERVIEW.md` after completing new features

## Dual-Repository Workflow

This project uses two GitHub repositories:

| Repo | URL | Visibility | Branch | Purpose |
|------|-----|-----------|--------|---------|
| public | `origin` → `Sugers955/agent-mill` | **Public** | `main` | Open-source version |
| private | `private` → `Sugers955/agent-mill-pro` | **Private** | `v2` + `main` | Commercial development |

### Daily Development (v2)

```bash
# Work on v2 as usual
git checkout v2
# ... code, commit ...
git push private v2       # Push to private repo ONLY
```

### Sync to Open-Source (main → public)

When a feature is complete and ready for open-source release:

```bash
git checkout main
git merge v2                    # Merge v2 changes into main
git push origin main            # Push to public repo
git push private main           # Also sync main to private repo
git checkout v2                 # Back to v2
```

### Important Rules

- **NEVER** `git push origin v2` — public repo has no v2 branch
- **ALWAYS** use `git push private v2` for development pushes
- Before merging v2 → main, ensure no sensitive files (internal docs, keys) leak
- `.env`, `backend/.env`, `.claude/`, `.workbuddy/`, `storage/` are gitignored — safe
- `docs-internal/` directory exists only on v2, excluded from main

### First-Time Setup

```bash
# Add private remote (already done)
git remote add private git@github.com:Sugers955/agent-mill-pro.git

# Push branches
git push origin main             # main → public
git push private v2              # v2 → private
git push private main            # main → private (sync baseline)

## Frontend Development Guide

Follow the design guide at `docs/en/frontend-design-guide.md`.

Key points:
- Page container uses `.page`, header uses `.page-head`, table card uses `.surface`
- **Pagination must be inside `.surface`**, forming a whole with the table
- Element Plus configured with `zh-cn` locale
- Use CSS variables for colors, never hardcode hex values
- Verify against the checklist after completing new pages

## Database Development Guide

- **Table structures must have Chinese comments**: All `CREATE TABLE` statements must have `COMMENT='table description'` for each table and `COMMENT='field description'` for each field
- Comments should include: field purpose, value ranges (e.g., `active/disabled`), foreign key relationships (e.g., `FK → users.id`), cascade strategies (e.g., `SET NULL on delete`)
- Example: `status VARCHAR(16) DEFAULT 'active' COMMENT 'Account status: active=normal / disabled=disabled'`
- Update `docs/zh/PROJECT_OVERVIEW.md` when adding new tables or fields
