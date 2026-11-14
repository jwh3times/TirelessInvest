# TirelessInvest: Infrastructure

| | |
|---|---|
| **Status** | In production since 2026-11-11: web at https://tirelessinvest.com, API at https://api.tirelessinvest.com. Supabase on the Free plan, Resend as the Auth SMTP provider, Alpaca Basic market data. |
| **Last updated** | 2026-11-12 |
| **Companion doc** | [PRD.md](PRD.md) |

This document covers how TirelessInvest is hosted: what runs where, why it was chosen, how to
set it up from scratch, how to operate it, and what's still missing.

---

## 1. Architecture at a glance

```
                        tirelessinvest.com (DNS on Cloudflare)
                 ┌───────────────────────┴────────────────────────┐
     tirelessinvest.com                                 api.tirelessinvest.com
     Cloudflare Pages (React, static)                   Railway service: api (FastAPI)
                 │                                                │
                 │  sign-in only                                  │  SQL (session pooler)
                 ▼                                                ▼
     ┌──────────────────── Supabase ─────────────────────────────────────┐
     │  Auth (issues JWTs)                    Postgres (all app data)    │
     └───────────────────────────────────────────────────────────────────┘
                 ▲                                                ▲
                 │ JWT in Authorization header                    │ SQL
     Browser ────┘──────────────────────────▶ api                 │
                                                                  │
                         Railway cron: price-sync ────────────────┘
                         (weekdays 22:30 UTC)  ───────▶ Alpaca market data API

     GitHub (jwh3times/TirelessInvest) ──▶ GitHub Actions CI
                                       ──▶ Railway auto-deploy (api, price-sync), migrations first
                                       ──▶ GitHub Actions release: version tag, then the web app
                                           to Cloudflare Pages once the API runs the merge
```

Every merge to `main` is a release ([GLOSSARY.md](../GLOSSARY.md)): it mints the next version and
goes to production in a fixed order, migrations, then the API, then the web app (§8.2).

**Request flow:**

1. The browser signs in with Supabase Auth and receives a JWT (a signed login token).
2. Every API call sends that JWT. The API verifies it against Supabase's published signing keys.
3. The API checks permissions and feature flags in Postgres, then reads or writes data.
4. The browser never queries the database directly.

## 2. Components

| Component | Platform | Repo path | What it does |
|---|---|---|---|
| Web app | Cloudflare Pages | `web/` | React 19 + Vite + TypeScript single-page app. Static files only. |
| API | Railway service `api` | `api/` | Python 3.15, FastAPI, pandas/numpy. Backtests, permissions, flags, admin. |
| Price sync | Railway cron service `price-sync` | `api/` (same image) | Downloads adjusted daily prices from Alpaca, then exits. |
| Database | Supabase Postgres | `supabase/migrations/` | All app data. Schema managed by migrations, applied by each release (§8.3). |
| Auth | Supabase Auth | `supabase/config.toml` | Email/password accounts; issues JWTs. |
| Market data | Alpaca Market Data API | `api/src/tirelessinvest/market/` | Daily bars, split/dividend-adjusted. |
| DNS / TLS / CDN | Cloudflare | – | DNS for `tirelessinvest.com`; serves Pages; proxies the API. |
| Source + CI | GitHub + GitHub Actions | `.github/workflows/ci.yml` | Lint, tests against a real Postgres, frontend build, changelog, agent-config and docs checks. |
| Releases | GitHub Actions | `.github/workflows/release.yml` | Tags every merge to `main` with its version, then deploys the web app after the API (§8.2). |

## 3. Decision record

The main infrastructure choices, with the reasoning, so they can be revisited deliberately.

### 3.1 A container for the engine, not edge or serverless functions

Backtests are CPU-heavy Python (pandas/numpy) and can take 10+ seconds. Cloudflare Workers and
Supabase Edge Functions have tight CPU-time limits and limited Python package support. So the
engine runs as an ordinary long-lived container, and everything else uses managed services.

### 3.2 Railway for containers (over Fly.io and Azure Container Apps)

| | Railway | Azure Container Apps | Fly.io |
|---|---|---|---|
| Setup effort | Lowest: connect repo, builds Dockerfile | Highest: registry, environment, logs, identities | Medium |
| Scheduled jobs | Built-in cron (5-minute minimum, UTC) | Best (Container Apps Jobs with history and retries) | Weakest (hourly/daily/weekly/monthly only) |
| Burst workloads | Always-on worker | Event-driven jobs that scale to zero | Temporary machine per run |
| Idle cost | Low | Lowest compute, but registry and logs cost extra | Low |
| Secrets | Env vars in dashboard | Key Vault + managed identity (strongest) | `fly secrets` |

**Chosen: Railway.** The project's goal is exploring algorithms, not infrastructure, and Railway
has the least setup. The trade-offs accepted: weaker burst handling for big parameter sweeps,
and weaker secret management than Azure Key Vault (which matters in Phase 4).

**Exit path:** the API is a plain Dockerfile plus environment variables, and the only
Railway-specific features used are cron, the pre-deploy command and `RAILWAY_GIT_COMMIT_SHA`.
Moving to Azure Container Apps or Fly is roughly an afternoon's work.

### 3.3 Supabase for Auth and Postgres

The owner already knows it. Auth and the database in one place means login tokens and data
share an identity (`auth.users`) with no glue code. The rejected alternative, Azure Entra
External ID, would have meant two systems.

### 3.4 Browser talks to Supabase for sign-in only

All data goes through the API, which enforces permissions and flags in one place. Every table
has row-level security (RLS) on with **no policies**, and grants are revoked from Supabase's
`anon` and `authenticated` roles. So even with a valid user token, Supabase's auto-generated
REST API returns nothing. A test checks this.

Trade-off: no Supabase Realtime or direct client queries. Adding any later means writing RLS
policies deliberately.

### 3.5 Cloudflare Pages for the frontend

It's free, served from a global CDN, and DNS is already on Cloudflare. No server-side rendering
is needed for a logged-in dashboard, so a static single-page app is enough.

### 3.6 Alpaca for market data

There's a free tier for daily data, and the same company offers paper and live trading APIs, so
Phase 4 needs no new vendor. Its limit is history: it only goes back to about 2016 (PRD Q6).

### 3.7 Things deliberately not used (yet)

| Not used | Why not | Revisit when |
|---|---|---|
| Kubernetes, microservices | One API and one cron job don't need them | Never, at this scale |
| Redis / message queue | Backtests run inside the request; a Postgres `jobs` table can queue work later | Backtests regularly exceed ~30s |
| Separate staging environment, pull request preview deploys | Cost and effort for a personal project; local Supabase + CI cover most risk | Before Phase 4 (real money) |
| Feature-flag SaaS (LaunchDarkly etc.) | A table plus overrides covers it | Percentage rollouts or experiments are needed |
| Next.js / server-side rendering | Logged-in dashboard; no SEO need | A public marketing site is wanted |

## 4. Domains and DNS

The domain `tirelessinvest.com` is registered. Proposed layout:

| Host | Points to | Cloudflare proxy |
|---|---|---|
| `tirelessinvest.com` | Cloudflare Pages project (custom domain) | Proxied (automatic for Pages) |
| `www.tirelessinvest.com` | Redirect (301) to `tirelessinvest.com` | Proxied |
| `api.tirelessinvest.com` | CNAME to the target Railway gives you, plus Railway's TXT verification record | Proxied (orange cloud) |

**Cloudflare SSL/TLS mode must be "Full", not "Full (Strict)".** Railway's documentation says
Strict breaks with Railway behind Cloudflare's proxy (error 526 during certificate renewal).
The setting is zone-wide; Pages works with "Full".

`api.` is a first-level subdomain, so the proxy works on Cloudflare's free certificates. A
deeper name (e.g. `v1.api.tirelessinvest.com`) would need Cloudflare's paid Advanced
Certificate Manager, or the proxy turned off.

Linked settings that must match the domains:

- API `CORS_ORIGINS` = `https://tirelessinvest.com`
- Supabase **Authentication → URL Configuration**: Site URL `https://tirelessinvest.com`
- Web `VITE_API_URL` = `https://api.tirelessinvest.com`

## 5. Configuration reference

### 5.1 API service (`api`) and price sync (`price-sync`)

Read by `api/src/tirelessinvest/config.py`. Names are case-insensitive.

| Variable | Used by | Example / default | Notes |
|---|---|---|---|
| `DATABASE_URL` | both | Supabase **session pooler** URI | The direct connection is IPv6-only; the pooler works over IPv4. Prepared statements are disabled in code, so transaction-mode pooling also works. |
| `SUPABASE_URL` | api | `https://<ref>.supabase.co` | Used to fetch the published signing keys (JWKS) and to check the token issuer |
| `SUPABASE_JWT_SECRET` | api | empty | Only for projects still on the legacy shared JWT secret. Leave empty to use JWKS. |
| `CORS_ORIGINS` | api | `https://tirelessinvest.com` | Comma-separated |
| `PRICE_SOURCE` | api | `db` | `synthetic` gives random prices for demos (results carry a warning) |
| `ALPACA_KEY_ID` | both | – | **Secret** |
| `ALPACA_SECRET_KEY` | both | – | **Secret** |
| `ALPACA_FEED` | both | `sip` | All exchanges. The client falls back to `iex` if the plan refuses `sip`. |
| `ALPACA_DATA_URL` | both | `https://data.alpaca.markets` | |
| `BACKFILL_ON_DEMAND` | api | `true` | Fetch unseen symbols when a backtest needs them |
| `BACKFILL_FLOOR` | both | `2016-01-01` | Earliest date to request history from |
| `PORT` | api | set by Railway | Read by the container command |
| `RAILWAY_GIT_COMMIT_SHA` | api | set by Railway | The commit the deploy was built from, reported by `/health` (`null` outside Railway) |
| `MIGRATIONS_DIR` | both | `/app/supabase/migrations`, set in the image | Where the pre-deploy migration step reads migrations from (§8.3) |

### 5.2 Web app (`web`, build variables)

The release workflow builds the web app; Cloudflare Pages runs no build. The first three are
variables of the GitHub `production` environment (§5.3); the release workflow sets the last two.

| Variable | Example | Notes |
|---|---|---|
| `VITE_SUPABASE_URL` | `https://<ref>.supabase.co` | Public |
| `VITE_SUPABASE_ANON_KEY` | Supabase publishable / anon key | **Public by design**: it ends up in the browser bundle. Safe because RLS blocks it from all app data (§3.4). |
| `VITE_API_URL` | `https://api.tirelessinvest.com` | |
| `VITE_APP_VERSION` | `0.1.0` | The version the release minted. The footer shows `v<version> · <short commit>`, or `dev build` when unset. |
| `VITE_APP_COMMIT` | the merge commit | |

**Never put** `service_role` keys, Alpaca keys or database URLs in `VITE_*` variables. Anything
with that prefix is shipped to every visitor's browser.

### 5.3 Release workflow (GitHub `production` environment)

The `web` job of `.github/workflows/release.yml` runs in the GitHub environment `production`, whose
deployment branches are limited to `main`, so pull request and Dependabot workflows can't read its
secret.

| Name | Kind | Notes |
|---|---|---|
| `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY`, `VITE_API_URL` | Environment variables | The web build values (§5.2) |
| `OP_SERVICE_ACCOUNT_TOKEN` | Environment secret | A 1Password service account token that can read the vault `TirelessInvest CI` |

The job loads the Cloudflare credentials from 1Password at run time, from the item
`Cloudflare Pages deploy` in that vault: `credential` becomes `CLOUDFLARE_API_TOKEN` (an API token
with Cloudflare Pages edit permission) and `account id` becomes `CLOUDFLARE_ACCOUNT_ID`. No
Cloudflare credential is stored in GitHub.

## 6. Data model

Defined in `supabase/migrations/20261110000000_init.sql`.

| Table | Purpose | Key points |
|---|---|---|
| `auth.users` | Supabase-managed accounts | Admin = `raw_app_meta_data.role = 'admin'` |
| `permissions` | Catalog of permission keys | `granted_by_default` drives sign-up grants |
| `user_permissions` | Who holds which permission | Filled by a trigger on new `auth.users` rows |
| `feature_flags` | Global flag values | Seeded: `strategy.mean_reversion`, `live_trading` |
| `feature_flag_overrides` | Per-user flag values | Override wins over the global value |
| `admin_audit_log` | Admin actions | Actor, action, target, details (JSON) |
| `symbols` | Tracked tickers | `history_from` prevents repeated backfills |
| `prices_daily` | Adjusted daily bars | Primary key (symbol, date); about 2,500 rows per symbol for 10 years |
| `backtests` | Saved runs | Request, summary and full report as JSON. Reports of a few hundred KB are fine at this scale. |

All tables have RLS on with no policies; grants for `anon` and `authenticated` are revoked.

**Migrations workflow:** add a new timestamped file under `supabase/migrations/`, test it
locally with `supabase db reset`, and merge it with the code that needs it: the release applies it
to production before that code takes traffic (§8.3). Keep schema changes additive; a data
migration that rewrites rows must leave them readable by the previous release
([ADR 0002](adr/0002-data-migrations-keep-rows-readable-by-the-previous-release.md)).

## 7. Security model

| Concern | Control |
|---|---|
| Who is calling | Every API route except `/health` needs a valid Supabase JWT: signature, `exp`, `aud=authenticated`, and `iss` checked. |
| Admin rights | `app_metadata.role` only, which needs the service role to change. A test proves `user_metadata` can't grant admin. |
| Becoming admin | No API or UI path. Run `python -m tirelessinvest.cli make-admin <email>` with production `DATABASE_URL`; it refuses if an admin exists. The user then signs out and back in to refresh their token. |
| Permissions and flags | Checked on the server for each request. UI hiding is cosmetic. |
| Direct database access from browsers | Blocked by RLS with no policies plus revoked grants (tested). |
| Other users' data | Other users' backtests return 404. |
| Secrets | Railway variables (Alpaca keys, DB URL). The owner keeps the production values in a password manager, never in `.env` files. Nothing secret in the repo or the web bundle. The database credential stays in Railway: migrations run there, not in CI ([ADR 0001](adr/0001-railway-applies-migrations-at-deploy.md)). The release workflow's Cloudflare token comes from 1Password, through a secret only the `main`-only `production` environment can read (§5.3). |
| Release tags | A tag ruleset on `v*` blocks updating or deleting a version tag once the release workflow has pushed it. |
| CORS | Only `CORS_ORIGINS` may call the API from a browser. |
| Container | Runs as a non-root user (uid 10001). |
| Code scanning | CodeQL (GitHub's default setup) scans pull requests and runs weekly; `main` accepts no merge with a CodeQL error or warning, or a medium-or-higher security alert (§8.1). |
| Dependencies | Dependabot alerts and security updates are on. `.github/dependabot.yml` opens version updates daily at 05:00 US Eastern for the API (uv), the web app (npm), the API's Docker base image and GitHub Actions, with minor and patch updates grouped per package ecosystem (Docker updates come one at a time). |
| Token freshness | Role changes reach the API only after the user's token refreshes (up to about an hour) or they sign in again. Acceptable with a single admin. |

**Gaps:**

- no rate limiting;
- no web application firewall rules;
- no security headers (CSP) on the Pages site.

See §11.

## 8. Build, deploy and CI

### 8.1 Continuous integration (`.github/workflows/ci.yml`)

Runs on every push to `main` and on every pull request:

- **api job:** `uv sync --frozen` → `ruff check` → `ruff format --check` → `pytest`, with a
  Postgres 17 service container. That covers 34 tests: engine, Alpaca client, API/database
  integration and the migration runner.
- **web job:** `pnpm install --frozen-lockfile` → `pnpm build`, which type-checks and builds.
- **changelog job:** on pull requests, `node scripts/check-changelog.mjs` checks that
  `CHANGELOG.md` has a section for the version the merge will mint (`docs/agents/releases.md`).
  Dependabot's pull requests pass without one; their changes roll up into the next section. On a
  push to `main` it passes without checking.
- **agents job:** `sync-agents.mjs --check` → `check-skills.mjs` → `lint-agent-neutrality.mjs` →
  `check-docs.mjs` → the script tests, all on Node 22 with nothing installed. It fails when the
  agent config mirror is stale, an installed skill differs from `skills-lock.json`, a skill or
  agent source is not tool-neutral, a doc link or the `Doc map` in `docs/agents/docs.md` is out
  of date, or a script test fails.

The `Main branch rules` ruleset makes all four jobs required checks on `main`, with the branch up
to date before merge. It also requires a pull request (merge commits only, review threads
resolved) and CodeQL code scanning (GitHub's default setup, weekly and on pull requests), and it
blocks force-pushes and deletion of `main`.

The integration tests run against plain Postgres, using `api/tests/supabase_stub.sql` to stand
in for the parts of Supabase the migrations need (`auth.users`, the `anon` and `authenticated`
roles). They apply the migrations with the same runner production uses (§8.3).

### 8.2 Releases and deployments

Every merge to `main` is a release, and goes to production in this order
([ADR 0001](adr/0001-railway-applies-migrations-at-deploy.md)):

| Step | Trigger | How |
|---|---|---|
| Database schema | Every merge to `main` | The pre-deploy command of `api` and `price-sync` applies pending migrations before the new deploy takes over (§8.3) |
| `api` | Every merge to `main` | Railway builds `api/Dockerfile` from the repository root; health check `GET /health` must pass before traffic switches |
| `price-sync` | Same image, rebuilt on every merge | Runs only on its cron schedule |
| Version tag | Every merge to `main` | `release.yml` `tag` job: tags the merge commit `v<major>.<minor>.<build>`, computed by `scripts/next-version.mjs` from `VERSION` and the existing tags |
| `web` | After the tag, once the API runs the merge | `release.yml` `web` job, below |

The `web` job polls `https://api.tirelessinvest.com/health` for up to 15 minutes until it reports
the merge commit, or a later commit that contains it. It then builds the web app with
`VITE_APP_VERSION` and `VITE_APP_COMMIT` and deploys `web/dist` with `wrangler pages deploy` to the
Cloudflare Pages project `tirelessinvest`. If the API never reports the commit, the job fails and
the web app is not deployed, so it never ships ahead of the API it calls. Web deploys run one at a
time, in merge order.

The tag is minted whether or not the deploy succeeds; a failed deploy is fixed forward with the
next release. A re-run of the workflow on a tagged commit reuses its tag. The versioning rules
(release line, roll-up of Dependabot merges) are in `docs/agents/releases.md`.

The release workflow is the only path to production for the web app: Cloudflare Pages' automatic
production and preview builds are off, and there are no staging or pull request preview deploys
(§3.7).

**Railway's "Wait for CI" stays off on both services.** It would hold the API deploy until every
workflow run on the commit finished, while the release workflow waits for the API, and neither
would move. The `main` ruleset already requires CI to pass before a merge.

### 8.3 Migrations at deploy

Railway runs `python -m tirelessinvest.jobs.migrate` as the pre-deploy command of both services,
with their `DATABASE_URL`. The runner reads `supabase/migrations/` from the image
(`MIGRATIONS_DIR`) and:

- holds a Postgres advisory lock, so the two services' runs take turns;
- applies each migration not yet recorded, in filename order, each in its own transaction, and
  stops at the first failure, exiting non-zero so the deploy does not go ahead;
- records each one in `supabase_migrations.schema_migrations`, the Supabase CLI's own history
  table, so `supabase migration list` agrees;
- logs, and tolerates, migrations the database has recorded but the image lacks (an older image
  against a newer schema).

`python -m tirelessinvest.jobs.migrate --dry-run` lists the pending migrations without applying
them.

So a migration ships by merging it with the code that needs it. Nobody runs `supabase db push`
against production after the first-time setup of a new project (§10 step 2). Make schema changes
additive (add columns or tables; drop them in a later release), so the previous deploy keeps
working while the new one starts, and so does an older image after an emergency rollback. A data
migration, one that rewrites existing rows, must leave them readable by the previous release, and
its header says what a rollback would see
([ADR 0002](adr/0002-data-migrations-keep-rows-readable-by-the-previous-release.md)).

**Rollback** is a revert: revert the pull request and merge the revert, which is a new release
(fix forward). A revert does not undo a migration already applied; the schema keeps it, which is
safe because schema changes are additive and rewritten rows stay readable. Railway's and
Cloudflare Pages' own rollback buttons are an emergency stop only, followed by a revert.

### 8.4 Container image (`api/Dockerfile`)

- Built from the repository root, so the image can carry `supabase/migrations/`. The root
  `.dockerignore` admits only `api/pyproject.toml`, `api/uv.lock`, `api/src` and
  `supabase/migrations`.
- `python:3.15-slim` plus a pinned `uv` 0.11.32.
- Dependencies install in their own layer from `uv.lock` (`--frozen --no-dev`).
- The migrations sit at `/app/supabase/migrations`, named by `MIGRATIONS_DIR`.
- Default command: `uvicorn tirelessinvest.main:app --host 0.0.0.0 --port ${PORT:-8000}`.
  It trusts proxy headers so client IPs are correct behind Railway and Cloudflare.
- The `price-sync` service overrides the start command:
  `python -m tirelessinvest.jobs.sync_prices`.

Railway builds the image on every deploy. To build it locally, from the repository root:
`docker build -f api/Dockerfile -t tirelessinvest-api .`.

### 8.5 Railway service settings

The services are configured in Railway's dashboard; the repository holds no Railway config file.
Both services deploy from `jwh3times/TirelessInvest`, with:

| Setting | `api` | `price-sync` |
|---|---|---|
| Builder | Dockerfile | Dockerfile |
| Root directory | `/` | `/` |
| Dockerfile path | `api/Dockerfile` | `api/Dockerfile` |
| Watch paths | none: every release rebuilds both | none |
| Auto-deploy | on, from `main` | on, from `main` |
| Wait for CI | **off** (§8.2) | **off** |
| Pre-deploy command | `python -m tirelessinvest.jobs.migrate` | `python -m tirelessinvest.jobs.migrate` |
| Start command | the image's default | `python -m tirelessinvest.jobs.sync_prices` |
| Cron schedule | – | `30 22 * * 1-5` (UTC, §9) |
| Health check | `/health`, 60 s timeout | – |
| Restart policy | on failure, 5 retries | never |

## 9. Scheduled jobs

| Job | Schedule | What it does | Idempotent | On failure |
|---|---|---|---|---|
| `price-sync` | `30 22 * * 1-5` (UTC) = 5:30 pm EST / 6:30 pm EDT, after the US close in both | 1. Makes sure every preset-universe symbol is tracked and backfilled. 2. Re-downloads the **full** adjusted history of every tracked symbol and upserts it. | Yes (upsert on symbol + date) | Exits non-zero; Railway shows the failed run; the next weekday retries. No alerting yet (§11). |

**Why a full re-download:** with `adjustment=all`, every dividend or split rescales a symbol's
whole past. Appending only new days would mix two price bases and invent jumps on those dates.
Cost: about 30 symbols × 10 years ≈ 75k rows, a few Alpaca requests per night.

**Railway cron rules:**

- schedules are in UTC;
- the minimum interval is 5 minutes;
- the job must exit when done;
- if the previous run is still going when the next one is due, the new run is skipped, not
  queued.

**On-demand backfill:** when a backtest needs a symbol the database doesn't have, or doesn't have
far enough back, the API fetches it from Alpaca during the request. Symbols Alpaca doesn't
recognize aren't registered, so a typo isn't synced forever.

## 10. Setup runbook (first deployment)

### Step 1: Accounts

- **Alpaca** (free): create a paper account, then generate API keys. These are for market data.
- **Supabase:** create a project. Choose Pro if the cron job must run unattended, because free
  projects pause after about a week without activity.
- **Railway:** connect your GitHub account.
- **Cloudflare:** add `tirelessinvest.com` as a site and switch nameservers at the registrar.

### Step 2: Supabase

1. Link the project and push the schema:

   ```bash
   supabase link --project-ref <ref>
   ```

   ```bash
   supabase db push
   ```

   This first push is the only manual one: from then on each release applies new migrations
   (§8.3).

2. Under **Authentication → URL Configuration**, set the Site URL to
   `https://tirelessinvest.com`.
3. Under **Authentication → SMTP Settings**, configure a custom SMTP provider (e.g. Resend,
   Postmark, SES). **This is required before anyone else can sign up.** Supabase's built-in
   email service only delivers to members of your Supabase organization, on every plan, and is
   heavily rate-limited.
4. Under **Connect**, copy the **Session pooler** connection string for `DATABASE_URL`.
5. Under **Authentication → Sign In / Providers**, turn off **Allow new users to sign up**.
   Accounts are invite-only ([PRD Q2](PRD.md#11-product-decisions)).

### Step 3: Railway

1. Create a project from the GitHub repo `jwh3times/TirelessInvest`.
2. Create the `api` and `price-sync` services from the repo, and set each one's settings as in
   §8.5. Leave **Wait for CI** off.
3. Set shared variables on both services (§5.1). Mark the Alpaca keys and `DATABASE_URL` as
   sealed/secret.
4. On `api`, add the custom domain `api.tirelessinvest.com`. Copy the CNAME target and the TXT
   verification record Railway shows.

### Step 4: Cloudflare

1. DNS: add the Railway CNAME for `api` (proxied) and the TXT record.
2. SSL/TLS → Overview: set the mode to **Full**.
3. Pages: create the project `tirelessinvest` with production branch `main`. The release workflow
   builds the web app and uploads it (§8.2), so the project needs no build settings or variables.
   If it is connected to the GitHub repo, turn off its automatic production and preview builds.
4. Pages → Custom domains: add `tirelessinvest.com`.
5. Add a 301 redirect from `www.tirelessinvest.com` to `tirelessinvest.com`.
6. Create an API token with Cloudflare Pages edit permission for the release workflow.

### Step 5: GitHub and 1Password

1. In 1Password, store the token and the Cloudflare account ID in the vault `TirelessInvest CI`,
   item `Cloudflare Pages deploy`, fields `credential` and `account id` (§5.3). Create a service
   account that can read only that vault.
2. In the GitHub repo, create the environment `production` with deployment branches limited to
   `main`. Add the service account token as its secret `OP_SERVICE_ACCOUNT_TOKEN`, and the web
   build values (§5.2) as its variables.
3. Rulesets: the `Main branch rules` ruleset requires the `api`, `web`, `changelog` and `agents`
   checks (§8.1); a tag ruleset on `v*` blocks updating and deleting version tags.

### Step 6: First run

1. Trigger `price-sync` once by hand from Railway, so prices exist before the first backtest.
2. Create your account in the Supabase dashboard: **Authentication → Users → Add user**, with
   **Auto Confirm User** on. Sign-up is off (step 2.5), so the app can't create it.
3. Make yourself admin by running the CLI from the API image, from the repository root, with the
   production `DATABASE_URL` exported in your shell (never typed on the command line):

   ```bash
   docker build -f api/Dockerfile -t tirelessinvest-api .
   ```

   ```bash
   docker run --rm -e DATABASE_URL tirelessinvest-api python -m tirelessinvest.cli make-admin you@example.com
   ```

4. Sign out and back in. The Admin tab should appear.

### Step 7: Smoke test

- `GET https://api.tirelessinvest.com/health` returns `{"status":"ok","commit":"<the deployed commit>"}`.
- After a merge, the Release workflow run is green, the merge commit carries its `v*` tag, and the
  web app's footer shows `v<version> · <short commit>` for it.
- A buy-and-hold SPY backtest from 2016 to today shows SPY results with no "synthetic data"
  warning.
- A second test account can't see the first account's backtests.

## 11. Operations

| Area | Current state | Gap / next step |
|---|---|---|
| Logs | Railway service logs (API logs requests and rejected tokens); Supabase logs | Nothing aggregated or searchable long-term |
| Health | Railway health check on `/health`, which also reports the running commit | No uptime monitor. Add a free external check on `/health` and the Pages URL. |
| Releases | The Release workflow run for each merge; the `v*` tags; the footer's version and commit | No alerting on a failed run |
| Alerting | None | Alert on a failed `price-sync` run and on repeated API 5xx errors |
| Backups | Supabase Pro includes daily backups | Confirm retention on the chosen plan; test a restore once |
| Errors | Logged only | Consider Sentry (free tier) for API and web |
| Cost visibility | Each provider's dashboard | Set usage alerts on Railway and Supabase |

**Failure modes:**

| Failure | Effect | Mitigation |
|---|---|---|
| Alpaca down | Backtests needing a new symbol fail (502); stored symbols still work; nightly sync fails | The next nightly run recovers automatically |
| Supabase paused (free plan) | Everything fails | Use Pro, or accept pausing during development |
| Supabase Auth email limits | Other users can't confirm sign-up | Custom SMTP (§10 step 2.3) |
| A migration fails at deploy | The new `api` and `price-sync` deploys stop and the previous ones keep running; the release's `web` job fails after 15 minutes, so the web app stays on the previous release | Fix forward: merge a fix for the migration (§8.3) |
| The API deploy fails or is slow | The `web` job fails after 15 minutes without deploying | Check the `api` deploy in Railway; fix forward, or re-run the workflow once the API is up |
| JWT signing key rotated | Tokens briefly rejected | The API caches published keys for 10 minutes; wait about 20 minutes after creating a standby key before rotating |
| Very long backtest | Request takes up to about 16s | Within limits today; move to a queued job if it grows (§3.7) |

## 12. Cost estimate

Prices change, so treat these as directional and check each provider's pricing page.

| Item | During development | Running for real |
|---|---|---|
| Cloudflare (DNS, Pages) | $0 | $0 |
| Supabase | $0 (free tier, pauses when idle) | ~$25/month (Pro) |
| Railway | ~$5/month (Hobby, includes some usage) | ~$5–20/month depending on usage |
| Alpaca market data | $0 (basic) | $0, intraday data for Phase 3 included |
| Longer price history (Sharadar) | $0 | About $299/year, only while a strategy is up for promotion (PRD P11); not in the total |
| SMTP provider | $0 | $0 on free tiers at low volume |
| Domain | ~$10–15/year | same |
| **Total** | **~$5/month** | **~$30–50/month** |

## 13. How infrastructure grows with each phase

| Phase | Additions |
|---|---|
| 2: paper portfolios | Tables for portfolios, orders and positions. A daily `portfolio-runner` cron service (same image) that checks Alpaca's market calendar before acting. A `paper_portfolios` flag as kill switch. Alerting on runner failure. Possibly a Postgres `jobs` table plus a worker for long backtests. |
| 3: intraday | Alpaca's free minute bars and real-time IEX stream (PRD §8). Separate storage for minute bars: a partitioned table, or Parquet files in object storage. More CPU for simulations. Probably a background worker instead of synchronous requests. |
| 4: real money (owner only) | A staging environment. Broker keys in a dedicated secret store; consider moving the trading service to Azure with Key Vault (§3.2). Order idempotency keys, daily reconciliation against the broker, per-order and per-day limits, a kill switch, and alerting that pages the owner. A dry-run period before live orders. |

## 14. Local development

Covered step by step in the [README](../README.md#local-development). Summary:

```bash
supabase start
```

```bash
cd api && cp .env.example .env && uv sync && uv run uvicorn tirelessinvest.main:app --reload
```

```bash
cd web && cp .env.example .env && pnpm install && pnpm dev
```

Integration tests need a Postgres server you can create databases on:

```bash
cd api && TEST_DATABASE_URL=postgresql://postgres:postgres@127.0.0.1:54322/postgres uv run pytest
```
