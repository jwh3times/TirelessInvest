# Ship

## Fast checks

- Repo root: `node scripts/sync-agents.mjs --check`, fixed by `node scripts/sync-agents.mjs`,
  committing both sides.
- Repo root: `node scripts/check-skills.mjs`, fixed by re-running the install commands in the
  `shared-skills` block of `AGENTS.md`.
- Repo root: `node scripts/lint-agent-neutrality.mjs`.
- Repo root: `node scripts/check-docs.mjs`.
- Repo root: `node --test "scripts/*.test.mjs"`, only when `scripts/` changed.
- `api/`: `uv run ruff check .`, only when `api/` changed.
- `api/`: `uv run ruff format --check .`, only when `api/` changed, fixed by `uv run ruff format .`.
- `web/`: `pnpm build`, only when `web/` changed (`tsc -b` and the Vite build).

CI runs every repo-root entry above in its `agents` job on every run, the script tests included,
and the `api` and `web` entries in their own jobs. CI-only: the `api` job's `uv run pytest -q`, which needs the Postgres service. `main` has
no required status checks.
