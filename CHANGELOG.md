# Changelog

All notable changes to TirelessInvest are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). The product has
one version, the `vX.Y.Z` tag the release workflow puts on every merge to `main`; `VERSION` holds
the current release line as `X.Y.0`. Each section below names the version its merge minted.
A major version means a breaking change for users (see `GLOSSARY.md`); until `1.0.0`, breaking
changes raise the minor version.

Branches never edit this file. Each writes its entries to `changelog.d/`, and after the merge the
release workflow stamps them into the section for the version that merge mints; a merge with
none, Dependabot's included, gets a section from its PR title
([ADR 0003](docs/adr/0003-stamp-changelog-on-tag.md)). Up to 0.7.13, a Dependabot merge minted a
version with no section of its own (0.7.4, 0.7.5 and 0.7.10): its changes are in the next section.

## [Unreleased]

No unreleased changes.

## [0.7.36] - 2026-11-24

### Changed

- build(deps): Bump the `python-minor-and-patch` group across 1 directory with 3 updates (#107)

## [0.7.35] - 2026-11-24

### Changed

- `docs/agents/merging.md` names `release.yml` as the `land` skill's `Release workflow`, so `land`
  watches this repository's release run instead of looking for a `version.yml` it doesn't have.

## [0.7.34] - 2026-11-24

### Changed

- Take the latest shared skills and scripts from `jwh3times/skills` (#120)

## [0.7.33] - 2026-11-23

### Changed

- Take the latest shared skills and scripts from `jwh3times/skills` (#119)

## [0.7.32] - 2026-11-23

### Changed

- `docs/agents/test-proof.md` records how the shared `test-prover` skill runs one test on its own
  here: the pytest and node commands, what a scratch worktree links, and that the API's
  integration tests are proven only with a Postgres server behind `TEST_DATABASE_URL`. The
  board's new `Due` date field is described in `docs/agents/issue-tracker.md`, and the Doc map
  names the new settings file.

## [0.7.31] - 2026-11-23

### Changed

- Take the latest shared skills and scripts from `jwh3times/skills` (#116)

## [0.7.30] - 2026-11-23

### Changed

- Take the latest shared skills and scripts from `jwh3times/skills` (#115)

## [0.7.29] - 2026-11-23

### Changed

- Take the latest shared skills and scripts from `jwh3times/skills` (#114)

## [0.7.28] - 2026-11-23

### Changed

- The shared PreToolUse guard (`scripts/guard.mjs`) now reads this repository's own rules from
  `docs/agents/guard.md`, on top of the ones it applies everywhere: it denies
  `supabase stop --no-backup` and `npx skills update`, asks before `supabase db reset` and a
  `supabase db push` to the hosted project, and protects the local `.env` files, `api/.venv/`,
  `node_modules/` and the Supabase CLI's link in `supabase/.temp/`.

## [0.7.27] - 2026-11-23

### Changed

- Take the latest shared skills and scripts from `jwh3times/skills` (#110)

## [0.7.26] - 2026-11-23

### Changed

- Take the latest shared skills and scripts from `jwh3times/skills` (#109)

## [0.7.25] - 2026-11-22

### Changed

- Take the latest shared skills and scripts from `jwh3times/skills` (#106)

## [0.7.24] - 2026-11-22

### Changed

- The `dependabot` skill now reads this repository's own review settings from
  `docs/agents/dependabot.md`: the bumps that need a full review, how to reproduce CI's installs,
  the stack facts a verdict must not get wrong, and the known fix for a Python base-image bump.

## [0.7.23] - 2026-11-22

### Changed

- Take the latest shared skills and scripts from jwh3times/skills (#104)

## [0.7.22] - 2026-11-21

### Changed

- Take the latest shared skills and scripts from jwh3times/skills (#103)

## [0.7.21] - 2026-11-21

### Changed

- Take the latest shared skills and scripts from jwh3times/skills (#102)

## [0.7.20] - 2026-11-21

### Changed

- Take the latest shared skills and scripts from jwh3times/skills (#101)

## [0.7.19] - 2026-11-21

### Changed

- Take the latest shared skills and scripts from jwh3times/skills (#100)

## [0.7.18] - 2026-11-21

### Changed

- Take the latest shared skills and scripts from jwh3times/skills (#99)

## [0.7.17] - 2026-11-21

### Changed

- build(deps): Bump supabase from 3.1.0 to 3.2.0 (#90)

## [0.7.16] - 2026-11-21

### Changed

- build(deps): Bump the python-minor-and-patch group across 1 directory with 2 updates (#88)

## [0.7.15] - 2026-11-20

### Fixed

- **A release no longer stalls on Railway's deploy of its changelog stamp commit.** Railway ignores
  `[skip ci]`, so on `v0.7.14` it deployed the stamp commit 13 seconds after the merge: the merge's
  deploy was superseded, the stamp commit's failed, the API stayed on the previous release for over
  30 minutes, and the web deploy timed out until a redeploy and a re-run. Both Railway services now
  set watch paths (`**`, `!/CHANGELOG.md`, `!/changelog.d/**`): a stamp commit no longer deploys,
  and every push that changes anything else still does. ADR 0003 carries a dated correction, and
  `docs/INFRASTRUCTURE.md`, `docs/agents/merging.md` and the release workflow's comments describe
  the watch paths.
- **The runbook covers a merge that changes only the changelog files.** The watch paths skip it too,
  so the API never reports it and the release's `web` job fails. `docs/INFRASTRUCTURE.md` §11 gives
  the recovery: redeploy `api` in Railway, then re-run the failed `web` job.

## [0.7.14] - 2026-11-20

### Changed

- **Each merge's changelog section is now stamped after it lands** (#89). A branch writes its
  entries to its own `changelog.d/<branch-slug>.md` fragment and never edits `CHANGELOG.md`; after
  the merge, the release workflow turns the fragment, or the PR title when there is none, into the
  dated section, tags the merge commit, and creates a GitHub Release from the section. Pull
  requests no longer renumber their sections after each other's merges, and a Dependabot merge
  gets a section of its own instead of rolling up into the next one. The stamp commit is pushed by
  the release GitHub App, the `main` ruleset's one bypass actor, from a `tag` job that runs in the
  `main`-only `production` environment, so no other branch's workflow can use the App's key.
  ADR 0003 records the move, and `docs/agents/releases.md`, `merging.md`, `ship.md`, the docs map,
  the README and `docs/INFRASTRUCTURE.md` describe it.

## [0.7.13] - 2026-11-18

### Changed

- Claude Code no longer asks permission for the read-only commands agents run most in this
  repository: the check scripts and their tests, the API's lint and format checks, the full API
  test run, GitHub board, label and CI-run reads, the local Supabase status, the `context7` docs
  tools, and the Railway reads that return no secrets (service config, service and project lists,
  logs, docs). The allow list in `.claude/settings.json` was built from how often these were called
  in recent sessions. Every Railway tool that changes production or returns a secret still prompts,
  and `AGENTS.md` now says which of the two lists a new Railway tool belongs on.

## [0.7.12] - 2026-11-18

### Fixed

- `CHANGELOG.md` is valid UTF-8. Since 0.1.0 its footer example had held a Latin-1 middle dot,
  which showed as a replacement character and made UTF-8 editors and tools refuse the file; it is
  now the `·` the footer actually prints. `docs/agents/merging.md` no longer tells agents to keep
  that byte.

## [0.7.11] - 2026-11-18

### Changed

- Dependency updates rolled up from v0.7.10: FastAPI 0.162.7 and pydantic-settings 2.16.3 in the
  API.
- What coding agents have learned about merging pull requests and running the stack on a
  development machine now lives in the repository, in `docs/agents/merging.md` and
  `docs/agents/local-runs.md`, linked from `AGENTS.md`. It used to sit in one machine's private
  agent memory, where other agents and machines could not read it.

## [0.7.9] - 2026-11-17

### Changed

- The API's tests run Starlette's test client on `httpx2`, a new development-only dependency, so
  they no longer print Starlette's warning to install it. The pytest config makes any
  `StarletteDeprecationWarning` an error: if `httpx2` is ever dropped, or Starlette deprecates
  something else the tests use, the integration tests fail instead of warning. The production
  image is unchanged, and the Alpaca client still uses `httpx`.

## [0.7.8] - 2026-11-16

### Changed

- The API's Python version is pinned once, in `api/.python-version`, which CI and local `uv` both
  read. CI fails when the pin and the `api/Dockerfile` base image production runs name different
  Python versions, so a Dependabot bump of the base image stays red until the pin moves with it,
  instead of CI passing on a Python production no longer runs. Locally, `uv sync` in `api/` now
  builds the environment on Python 3.15, and installs it if it is missing.

## [0.7.7] - 2026-11-15

### Fixed

- A backtest whose strategy parameters fail their checks now gets one readable message per
  parameter, such as "params.top_n: Input should be greater than or equal to 1". It used to get
  Pydantic's whole multi-line error, with its type tags, the input and a docs link. The API's 422
  for these has the same shape as every other request error.

## [0.7.6] - 2026-11-15

### Changed

- Dependency updates rolled up from v0.7.4 and v0.7.5: Vite 8.3.8 in the web app, and FastAPI
  0.162.5 and Ruff 0.17.5 in the API.

### Fixed

- The Lab's backtest errors no longer start with "Value error, ". The checks that look at several
  fields together (a holdout that leaves less than a year in-sample, an end date before the start,
  a range over 30 years, a custom universe outside 1 to 50 symbols) now read as written, and so do
  the API's 422 responses for every request body.

## [0.7.3] - 2026-11-15

### Changed

- Local development pins the Supabase CLI at 3.1.0 in a root `package.json`: run `pnpm install`
  at the repository root, then `pnpm exec supabase start`, instead of installing the CLI yourself.
  Dependabot proposes each new CLI version as its own pull request, so moving to CLI v4 is a
  deliberate merge.
- The local Supabase config uses the `enabled` spelling for the email and phone providers, which
  CLI v4 requires, so `supabase start` and `stop` no longer print deprecation warnings. Sign-up
  stays closed and password sign-in still works.

### Fixed

- The first-time production setup's `db push`, and the `migration list` check, now pass `--remote`:
  the Supabase CLI 3.x runs both against the local database unless told otherwise.

## [0.7.2] - 2026-11-15

### Changed

- The product requirements record invite-only sign-in (A1, A5, A8, G5, Q2), self-serve account
  deletion (A7) and the data-window notice (§6.4) as built, and §6.10 no longer lists public
  sign-up or missing account deletion as limitations.
- The PRD glossary defines the data window, and its Verdict row uses the app's "better
  risk-adjusted" wording instead of "ahead of SPY".

## [0.7.1] - 2026-11-14

### Changed

- The product requirements (PRD §6.4 and §6.10) record the holdout period as built: the last N
  whole years reported beside the in-sample period, each with its own verdict, and refused when
  under a year would remain in-sample.

## [0.7.0] - 2026-11-14

### Added

- A backtest can hold out its last years: the form's "Hold out the last … years" field reports
  those years separately from the rest, to check a strategy on a period it wasn't tuned on. The
  simulation still runs once, straight through, so the holdout starts from where the portfolio
  stood, not from a fresh deposit.
- With a holdout, the results page shows the in-sample and held-out periods side by side, each
  with its own risk-adjusted verdict against SPY over its own dates, its annual return, Sharpe
  ratio, worst drawdown and volatility. The full-period results stay as they were.
- A holdout that would leave less than a year in-sample is refused with a message saying how to
  fix it, whether the requested dates or the available price history fall short.
- Backtest requests to the API take an optional `holdout_years`, and reports carry `in_sample` and
  `holdout` sections, each with its dates, summary metrics, the benchmark's summary and a verdict.
  Both are null without a holdout.

## [0.6.0] - 2026-11-14

### Added

- Every backtest result states its data window, right under the verdict: the first and last
  dates it had prices for. The first can be later than the requested start, since price history
  currently begins around 2016.
- When that period spans neither the 2000–02 nor the 2008–09 bear market, the result says so:
  "Tested only from <first> to <last>: this period has no long bear market." The notice depends
  only on the dates, so it goes away by itself once longer price history lets a backtest reach
  back through one of them.
- Backtests saved earlier show their data window too, worked out from the dates they stored.
- Backtest reports from the API carry `data_window`, with `first_date`, `last_date` and `notice`.

## [0.5.0] - 2026-11-14

### Added

- Users can delete their own account from the new Account page, reached by clicking their email
  address in the top bar. They confirm by typing that address. Deletion is immediate and
  permanent: their backtests, permissions and flag overrides are removed, and they are signed
  out. The admin's own account can't be deleted this way.
- `DELETE /me` deletes the caller's account when the request carries their email address as
  `confirm_email`. A missing or wrong confirmation is a 422, and the admin account is a 403.
- The "Could not reach the API" screen has a Sign out button.

### Changed

- The API refuses a token whose user no longer exists with a 401, on every route, even before the
  token expires.
- Admin audit-log entries about a deleted user stay, with the user's id replaced by
  "deleted user".
- Admin changes to a user who no longer exists, removing a flag override included, return 404
  instead of writing an audit entry.

## [0.4.0] - 2026-11-14

### Added

- An invited person who follows Supabase's invitation email arrives signed in and is asked to
  choose a password before using the app. From then on they sign in with it like anyone else, and
  get the same default permissions as before.
- An expired or already-used invitation link says so on the sign-in page, instead of showing a
  bare form.

### Changed

- Local development matches production: sign-up is off in the local Supabase configuration.
  Create your local account by inviting yourself from Supabase Studio; the README walks through
  it, and the email lands in the local inbox.

### Removed

- The sign-in page no longer offers to create an account. TirelessInvest is invite-only: accounts
  come from the owner's Supabase invitations.

## [0.3.1] - 2026-11-14

### Changed

- The product requirements (PRD §6.4, §6.7 and Q4) record the ten-level risk dial as built,
  default 5 (Moderate), and keep the original 1–5 dial only as the settings backtests saved on it
  still use.
- Data migrations have a rule of their own (ADR 0002, `docs/INFRASTRUCTURE.md` §6 and §8.3).
  Schema changes stay additive. A migration that rewrites existing rows must leave them readable
  by the previous release, and its header says what a rollback would see.

## [0.3.0] - 2026-11-13

### Added

- Backtests saved on the earlier five-level dial say so: history and the results page show their
  risk level as "old 1–5 scale". The history list has a Risk column, and each item in
  `GET /backtests` carries `risk_level` and `legacy_risk_level`.

### Changed

- The risk dial has ten levels instead of five, with the same mechanics in finer steps: a cap on
  any one symbol from 20% to 100%, a volatility target from 4% to 28% a year (none at level 10),
  and a cash floor of 10% at level 1 and 5% at level 2. The default is level 5, Moderate (40% per
  symbol, a 12% volatility target), where it was level 5, Unconstrained. A request's `risk_level`
  now names a level on the new dial, so an API caller sending 1–5 gets a different preset than
  before, and one sending no level runs Moderate. Explicit `risk` settings still override the
  level.
- The backtest form's dial shows each level's label and mechanics, and says plainly that a risk
  level is not a loss limit.
- Backtests saved before this release keep their results. A one-time database migration rewrites
  each saved request that relied on its 1–5 level to that old preset's explicit settings plus a
  `legacy_risk_level` marker, so re-running it reproduces the original result; requests that
  already had explicit settings are untouched. The API accepts the marker only with the exact
  old-preset settings it stands for.

## [0.2.1] - 2026-11-13

### Changed

- The product requirements (PRD §6.4) record the risk-adjusted verdict as built: the API decides
  it by Sharpe ratio against SPY's over the same dates and costs, and the headline sentence's
  example matches what the app now shows.

## [0.2.0] - 2026-11-13

### Added

- Every backtest report from the API carries a `verdict`: the strategy's and the benchmark's
  Sharpe ratios over the same dates and costs, whether the strategy is better risk-adjusted,
  the difference in annual return (CAGR), and whether a comparison was possible. Each item in
  `GET /backtests` carries it too, and backtests saved before this release show one derived from
  their stored results.
- The history list has a Verdict column beside the CAGR difference against the benchmark.

### Changed

- The results headline judges a strategy risk-adjusted: it is better than SPY when its Sharpe
  ratio beats SPY's, so a strategy that earned more only by taking more risk is no longer shown as
  ahead. The sentence still states how much more or less per year it earned, next to both
  volatilities and Sharpe ratios. When a Sharpe ratio is undefined, for example with no volatility
  over a very short period, it says no risk-adjusted comparison is possible.


## [0.1.1] - 2026-11-12

### Changed

- `/what-next` puts an active handoff first: when `handoff_map.json` names one for this
  repository, the report leads with it and recommends `/lets-go`, and one whose document has not
  reached this machine is shown as pending. It still changes nothing, and a machine without the
  handoffs config skips the check.

## [0.1.0] - 2026-11-12

The first versioned release. Everything below it existed before versioning began: the backtesting
engine and API, the web app, sign-in with an admin and default permissions, the admin dashboard with
feature flags and an audit log, and the nightly price sync.

### Added

- Every merge to `main` is a release. It is tagged `v<major>.<minor>.<build>` and reaches production
  without a manual step: Railway applies pending database migrations before the new API takes
  traffic, and the web app is deployed only once the API reports the new release.
- The web app's footer shows the release it belongs to, as `v0.1.0 · <short commit>`.
- `GET /health` reports the commit the API is running, as `commit`.
- This changelog, with one section per release, checked on every pull request.

### Changed

- Production schema migrations are applied by the release itself. Running `supabase db push`
  against production is no longer part of a release; merge the migration with the code that needs
  it, and keep it additive.
- The web app is built and deployed by the release workflow instead of by Cloudflare Pages on each
  push, so it never goes live ahead of the API it calls. Pull requests no longer get preview
  deployments.
- Railway service settings live in the Railway dashboard, recorded in `docs/INFRASTRUCTURE.md`,
  instead of the config files Railway stops reading on 2026-12-01.
