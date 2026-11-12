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
and the `api` and `web` entries in their own jobs. CI-only: the `api` job's `uv run pytest -q`,
which needs the Postgres service. The `changelog` job runs the `Changelog check` on pull requests,
skipping Dependabot's.

The `Main branch rules` ruleset on `main` requires a PR (merge commits only, review threads
resolved), the `api`, `web` and `agents` checks passing on a branch up to date with `main`, and
CodeQL code scanning (`gh api repos/jwh3times/TirelessInvest/rules/branches/main`).
