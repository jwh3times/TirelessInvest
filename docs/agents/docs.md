# Docs

## Doc map

- `README.md`: what TirelessInvest is, what the engine and strategies do, the architecture, local
  development, tests, deploying, known limitations and the roadmap; for developers and evaluators.
  Update when a strategy, universe, metric or engine rule changes (`api/src/tirelessinvest/engine/`),
  when routes or jobs change (`api/src/tirelessinvest/routes/`, `jobs/`), when the root
  `package.json` (the pinned Supabase CLI) or `api/.python-version` changes, or when a setup, test
  or deploy command changes.
- `docs/INFRASTRUCTURE.md`: hosting, DNS, configuration, security, the deployment runbook and
  operations. Update when `api/Dockerfile`, `api/.python-version`, `.dockerignore`, `supabase/`,
  `.github/workflows/`, `.github/dependabot.yml` or an environment variable changes, or a GitHub
  repository setting does (the `main` ruleset, CodeQL setup, merge options).
- `CHANGELOG.md`: one dated section per version a merge mints, stamped by the release workflow's
  `scripts/stamp-changelog.mjs` after the merge (`docs/agents/releases.md`). `frozen`: no branch
  writes its sections.
- `changelog.d/README.md`: the fragment format and how fragments are stamped, for whoever writes
  one. Update when the fragment rules in `scripts/check-changelog.mjs` or the stamping in
  `scripts/stamp-changelog.mjs` change.
- `changelog.d/*.md`: each branch's changelog fragment (every file there but the README), stamped
  into `CHANGELOG.md` after its merge and checked by the `changelog` CI job. `ship-owned`, like the
  `VERSION` file.
- `GLOSSARY.md`: the project's own vocabulary, one term per entry with the words to avoid. Update
  when a design session settles a term.
- `docs/adr/*.md`: architecture decision records, one decision each with the reason it was made.
  Add one when a decision is hard to reverse and would surprise a reader; supersede rather than
  rewrite.
- `docs/PRD.md`: goals, users, requirements by phase and the owner's product decisions. `owner-only`.
- `AGENTS.md`: guidance for every coding agent: commands, the development flow, the MCP servers,
  the agent skills. Update when a command changes, or when `.mcp.json`, `.codex/config.toml` or
  `.claude/settings.json` does. The `shared:` blocks are written by `scripts/sync-agents.mjs`;
  never edit them here.
- `CLAUDE.md`: imports `AGENTS.md` for Claude Code. `owner-only`.
- `docs/agents/*.md`: settings the shared skills read. Update when this repository's process
  changes, or the `main` ruleset's required checks do (`open-pr.md` lists them).
- `docs/agents/merging.md`, `docs/agents/local-runs.md`: from open PR to deployed release, and the
  development machine's traps. Update when a merge or local-run lesson is learned that no check
  enforces, or a command they quote changes.
- `docs/agents/dependabot.md`: what reviewing a Dependabot pull request takes here, read by the
  `dependabot` skill. Update when `.github/dependabot.yml`, a workflow's toolchain pins or install
  steps, `api/Dockerfile`, `api/.python-version` or the API's or web app's main dependencies change.
- `docs/agents/guard.md`: the commands `scripts/guard.mjs` denies or asks about here, and the
  paths it protects, on top of its universal rules. Update when a **Never run** command or a
  never-remove path in `docs/agents/workspace.md` changes, or how migrations reach production does.
- `docs/agents/test-proof.md`: how the `test-prover` skill runs one test on its own here, and the
  suites it cannot prove without a service. Update when a test runner, a test folder, a `test`
  command or what a test needs to run (`TEST_DATABASE_URL`, the Postgres container) changes.
- `.agents/skills/**`: installed skills, listed in `skills-lock.json`. `frozen`: a reinstall
  overwrites them, and `scripts/check-skills.mjs` fails on an edited copy.

## Drift probes

- Strategies, risk dial and metrics in `README.md`: `api/src/tirelessinvest/engine/`.
- CI jobs and their commands: `.github/workflows/ci.yml`.
- API commands and dependencies: `api/pyproject.toml`.
- Web commands: the `scripts` in `web/package.json`.
