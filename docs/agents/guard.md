# Guard

The commands and paths `scripts/guard.mjs` stops here, on top of the rules it applies everywhere.
Each `##` heading is one setting, defined in `.agents/skills/ship/settings/guard.md`.

## Deny commands

- `^((pnpm|npm) exec |npx )?supabase stop\b.*\s--no-backup\b` — it discards the local stack's data.
  Stop it with `pnpm exec supabase stop`, which keeps the data.
- `^npx (-y |--yes )?skills update\b` — it leaves `.claude/skills/` linked to its source instead of
  copied. Re-run the install commands in the `shared-skills` block of `AGENTS.md` instead.

## Ask commands

- `^((pnpm|npm) exec |npx )?supabase db reset\b` — it wipes the local database. Testing a new
  migration locally is its one documented use (`docs/INFRASTRUCTURE.md`), on the owner's word.
- `^((pnpm|npm) exec |npx )?supabase db push\b.*\s--(remote|linked|project-ref|db-url)\b` — it
  pushes the schema to the hosted production project. Each release applies new migrations at
  deploy, so a manual push belongs only to first-time setup of a new project.

## Protected paths

- `^((api|web)/)?\.env(\.(?!example(/|$))[^/]*)?$` — local configuration, not regenerable from the
  repository; only the tracked `.env.example` templates are.
- `^api/\.venv/` — the API's virtual environment: regenerable, but slow to rebuild.
- `^(web/)?node_modules/` — the pinned Supabase CLI and the web app's dependencies: regenerable,
  but slow to rebuild.
- `^supabase/\.temp/` — the Supabase CLI's link to the production project, made during deployment.
