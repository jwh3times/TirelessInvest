# Workspace

## Private companion

none

## Safe-to-remove paths

- `.pytest_cache/`, `.ruff_cache/` and `__pycache__/` (test and lint caches)
- `web/dist/` (the web build output)

## Never-remove paths

- `.env` and `.env.*` files: local configuration, not regenerable from the repository.
- `api/.venv/` and `web/node_modules/`: regenerable, but slow to rebuild.
- `supabase/.temp/`: the Supabase CLI's link to the production project, made during deployment.

## Dev stack

Show the local stack with `supabase status`, and stop it with `supabase stop`.

**Never run:**

- `supabase db reset` (wipes the local database)
- `supabase stop --no-backup` (discards local data)
