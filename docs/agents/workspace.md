# Workspace

## Private companion

none

## Safe-to-remove paths

- `.pytest_cache/`, `.ruff_cache/` and `__pycache__/` (test and lint caches)
- `web/dist/` (the web build output)

## Never-remove paths

- `.env` and `.env.*` files: local configuration, not regenerable from the repository.
- `api/.venv/`, `node_modules/` (the pinned Supabase CLI) and `web/node_modules/`: regenerable,
  but slow to rebuild.
- `supabase/.temp/`: the Supabase CLI's link to the production project, made during deployment.

## Dev stack

Run the Supabase CLI pinned in the root `package.json` as `pnpm exec supabase …`. Show the
local stack with `pnpm exec supabase status`, and stop it with `pnpm exec supabase stop`.

**Never run:**

- `pnpm exec supabase db reset` (wipes the local database)
- `pnpm exec supabase stop --no-backup` (discards local data)
