# Docs

## Doc map

- `README.md`: what TirelessInvest is, what the engine and strategies do, the architecture, local
  development, tests, deploying, known limitations and the roadmap; for developers and evaluators.
  Update when a strategy, universe, metric or engine rule changes (`api/src/tirelessinvest/engine/`),
  when routes or jobs change (`api/src/tirelessinvest/routes/`, `jobs/`), or when a setup, test or
  deploy command changes.
- `docs/INFRASTRUCTURE.md`: hosting, DNS, configuration, security, the deployment runbook and
  operations. Update when `api/Dockerfile`, `api/railway*.toml`, `supabase/`, `.github/workflows/`,
  `.github/dependabot.yml` or an environment variable changes, or a GitHub repository setting does (the `main` ruleset,
  CodeQL setup, merge options).
- `docs/PRD.md`: goals, users, requirements by phase and the owner's product decisions. `owner-only`.
- `AGENTS.md`: guidance for every coding agent: commands, the development flow, the agent skills.
  Update when a command changes. The `shared:` blocks are written by `scripts/sync-agents.mjs`;
  never edit them here.
- `CLAUDE.md`: imports `AGENTS.md` for Claude Code. `owner-only`.
- `docs/agents/*.md`: settings the shared skills read. Update when this repository's process
  changes.
- `.agents/skills/**`: installed skills, listed in `skills-lock.json`. `frozen`: a reinstall
  overwrites them, and `scripts/check-skills.mjs` fails on an edited copy.

## Drift probes

- Strategies, risk dial and metrics in `README.md`: `api/src/tirelessinvest/engine/`.
- CI jobs and their commands: `.github/workflows/ci.yml`.
- API commands and dependencies: `api/pyproject.toml`.
- Web commands: the `scripts` in `web/package.json`.
