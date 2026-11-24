# Test proof

How `test-prover` runs one test on its own here, and how it tells a run that tested nothing from a
pass. The suites and their CI jobs are in `docs/agents/ship.md`; the traps of running them on a
development machine are in `docs/agents/local-runs.md`.

## Test commands

- `api/`: `tests/test_*.py`, pytest. One file: `uv run --no-sync pytest <file>`; one test, by its
  node id: `uv run --no-sync pytest "<file>::<name>"` (a parametrized one as
  `"<file>::<name>[<id>]"`). Count: pytest's closing summary, which `mutate.mjs` reads already.
  Worktree: link `api/.venv`; `--no-sync` makes `uv` use it as it is instead of reinstalling the
  project into the checkout's environment. Where `uv` is not on `PATH`, see
  `docs/agents/local-runs.md`.
  - `tests/test_engine.py` and `tests/test_alpaca.py` need nothing more.
  - `tests/test_api.py` and `tests/test_migrate.py` are integration tests: without
    `TEST_DATABASE_URL` pointing at a Postgres server they skip, which reads as `zero-match`, so
    they are not proven on a machine without one. With the throwaway container from
    `docs/agents/local-runs.md` running:
    `TEST_DATABASE_URL=postgresql://postgres:postgres@127.0.0.1:55432/postgres uv run --no-sync pytest "<file>::<name>"`.
- repo root: `scripts/*.test.mjs`, node's runner. One file: `node --test <file>`; one test:
  `node --test --test-name-pattern="<name>" <file>`. Worktree: link `node_modules`.
- `web/` has no tests: its check is the `pnpm build` typecheck and bundle.

## Guide

docs/agents/local-runs.md
