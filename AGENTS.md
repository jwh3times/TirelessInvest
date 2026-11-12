# AGENTS.md

Guidance for every coding agent in this repository (Claude Code reads it through `CLAUDE.md`).
[README.md](README.md) covers what TirelessInvest is, its architecture, local development, tests and
deployment; [docs/PRD.md](docs/PRD.md) and [docs/INFRASTRUCTURE.md](docs/INFRASTRUCTURE.md) hold the
product requirements and the hosting runbook.

## Commands

```bash
cd api && uv sync && uv run pytest       # API and engine tests
cd api && uv run ruff check . && uv run ruff format --check .   # API lint and format
cd web && pnpm install && pnpm build     # web build
node scripts/sync-agents.mjs --check     # agent config is in sync
node scripts/check-skills.mjs            # installed skills match skills-lock.json
node scripts/lint-agent-neutrality.mjs   # skill and agent sources read correctly from both trees
node scripts/check-docs.mjs              # doc links resolve and docs/agents/docs.md maps every doc
node scripts/next-version.mjs            # the version the next merge to main will mint
node scripts/check-changelog.mjs         # CHANGELOG.md has a section for that version
node --test "scripts/*.test.mjs"         # tests for the scripts above
```

## Development flow

<!-- shared:development-flow -->

The flow skills are this repository's binding process for changing code. Read
`.agents/skills/ship/settings/dev-flow.md` (the routing, exemptions and issue linking) and
`docs/agents/dev-flow.md` (what this repository adds) before the first edit of a change, and whenever
no ready issue exists. `/ask-matt` maps the flow itself.

- **The gate.** Every code edit starts from a ready issue: an open `ready-for-agent` issue whose body
  is a `/to-spec` spec or a `/to-tickets` ticket or that carries a `/triage` brief, or a `bug` issue
  worked through `/diagnosing-bugs`, which needs the number and no spec. With none, stop before the
  first edit and route the user. Reading code, running tests and answering questions need no issue.
- **Private work.** A ready issue in the private tracker counts. Its number stays out of the branch,
  the PR, commits and public issues, and it is closed by hand after the merge.
- **The human starts every phase.** `/wayfinder`, `/grill-with-docs`, `/to-spec`, `/to-tickets`,
  `/implement` and `/triage` stay user-invoked. At a phase boundary, name the next command, say in
  one line why, and wait. Inside a phase, use `/tdd`, `/code-review`, `/diagnosing-bugs`,
  `/domain-modeling`, `/codebase-design`, `/prototype` and `/research` whenever they fit.
- **Exempt from the gate:** dependency bumps, changes touching only docs and agent config, release
  prep, and an explicit user waiver recorded in the PR body as `Flow waived by the user: <reason>`.
- **Linking.** Branches are `<type>/<issue#>-<slug>`; the PR body opens with `Closes #N` or
  `Part of #N`.
- **The flow ends at `/ship`.** `/implement` stops at a commit; `/ship` refreshes the docs, writes the
  changelog and the PR body, and opens the PR. `/ask-matt` also routes to `/pr`, `/retro` and
  `/implement-spec`, which are not installed here.
- **`/handoff` is the shared skill.** It parks the session for another machine or harness, closes it
  out with `/end-session`, and `/lets-go` resumes it. It does not write the portable file `/ask-matt`
  describes, so a `/prototype` detour stays in the session or uses a branch.
- **A wizard is not the record.** A step only a human can take follows the `## Procedure` in
  `.agents/skills/ship/settings/human-follow-up.md`, whose instructions stand without the script.
- **Research goes where it is safe to keep.** `/research` findings that would expose private material
  go to the private companion, where there is one, never to an ignored folder with no repository
  behind it. Details of an unpublished vulnerability are a draft advisory, never a research file.

<!-- /shared:development-flow -->

## MCP servers

The shared servers are listed in `.mcp.json` (Claude Code) and `.codex/config.toml` (Codex, which
loads it only in a trusted project); change both together. Each signs in per person with OAuth or
needs no credentials, so neither file holds a secret. Once per person: approve the project's servers
when Claude Code asks and sign in from `/mcp`; in Codex, trust the project, then run
`codex mcp login <name>` for `cloudflare-api` and `railway`.

- **`context7`**: current docs for any library or service the code calls. The stack is newer than
  training data, so check here before relying on what you remember.
- **`cloudflare-api`**: Cloudflare Pages deployments and DNS for `tirelessinvest.com`.
- **`railway`**: status, logs, metrics and config for the `api` and `price-sync` services. These are
  production, and the server can also change them: deploys, variables, services, volumes, domains
  and Railway's own feature flags (not the app's, which live in Postgres). Use its read tools; make
  a change only when the user asks for that change. Both harnesses enforce this: every mutating
  tool, plus `list-variables` and `get-bucket-credentials` (they return production secrets) and the
  open-ended `railway-agent`, prompts first. Claude Code lists them by name in
  `.claude/settings.json`, so a tool Railway adds goes on that list; Codex prompts for any tool not
  marked read-only and names those three in `.codex/config.toml`.
- **`supabase-local`**: the local `supabase start` stack, so it answers only while that runs. Schema
  changes go in `supabase/migrations/`.

Left out on purpose:

- **Supabase's hosted server.** The one Supabase project is production, and Supabase advises
  against pointing its MCP at production data.
- **1Password.** Production secrets live in the TirelessInvest vault; reach them with `op run` or
  `op read`, which keep secret values out of the model's context.
- **GitHub and GitKraken.** `git` and `gh` already cover them, and the flow skills use those.
- **Alpaca.** Its server can place orders, and live trading waits for the `live_trading` flag.

## Agent skills

Skills are authored in `.agents/skills/` (Codex reads it directly); `.claude/skills/` is a
generated mirror for Claude Code. Never edit the mirror: run `node scripts/sync-agents.mjs`.

### Shared skills

<!-- shared:shared-skills -->

`end-session`, `handoff`, `lets-go`, `ship`, `docs-updater` and `what-next` install from
`jwh3times/skills`, and are never edited here: reinstalling overwrites a local edit. A fix goes
upstream, and what they need to know about this repository goes in the settings files under
`docs/agents/`, which each skill proposes on first run.

The other shared skills come from one `mattpocock/skills` snapshot (v1.3.2, pinned by commit), the
same in every repository, and are never edited here either: what they need to know goes in this
file or `docs/agents/`. Moving to a newer snapshot is a change in `jwh3times/skills`. Keep
`.agents/skills/` out of every formatter: `scripts/check-skills.mjs` fails when an installed copy
differs from `skills-lock.json`, or the lock from these commands.

Re-running the install is the update; never run `npx skills update`, which leaves `.claude/skills/`
linked to its source instead of copied:

```bash
npx skills add jwh3times/skills -s end-session -s handoff -s lets-go -s ship -s docs-updater -s what-next -a codex --copy -y
npx skills add mattpocock/skills#d1478fcb140db0b93c0c8df17bcfd311844749d0 \
  -s ask-matt -s code-review -s codebase-design -s diagnosing-bugs -s domain-modeling -s grill-me \
  -s grill-with-docs -s grilling -s implement -s improve-codebase-architecture -s prototype \
  -s research -s setup-matt-pocock-skills -s tdd -s teach -s to-questionnaire -s to-spec \
  -s to-tickets -s triage -s wait-what -s wayfinder -s wizard -s writing-for-agents \
  -a codex --copy -y
node scripts/sync-agents.mjs
```

`scripts/sync-agents.mjs`, `lint-agent-neutrality.mjs`, `check-docs.mjs`, `check-skills.mjs`, and
`sync-main.mjs`, `next-version.mjs` and `check-changelog.mjs` where this repository carries them, are
canonical in `jwh3times/skills` with their tests: fix them there, then copy them here.
`sync-agents.mjs` also writes the marked blocks in this file: change them in `jwh3times/skills`, not
here.

<!-- /shared:shared-skills -->
