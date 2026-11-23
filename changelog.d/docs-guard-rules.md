### Changed

- The shared PreToolUse guard (`scripts/guard.mjs`) now reads this repository's own rules from
  `docs/agents/guard.md`, on top of the ones it applies everywhere: it denies
  `supabase stop --no-backup` and `npx skills update`, asks before `supabase db reset` and a
  `supabase db push` to the hosted project, and protects the local `.env` files, `api/.venv/`,
  `node_modules/` and the Supabase CLI's link in `supabase/.temp/`.
