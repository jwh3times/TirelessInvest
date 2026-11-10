# TirelessInvest: Infrastructure

| | |
|---|---|
| **Status** | Designed and configured in the repo. Not yet deployed. |
| **Last updated** | 2026-11-10 |
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
                                       ──▶ Railway auto-deploy (api, price-sync)
                                       ──▶ Cloudflare Pages auto-build (web)
```

**Request flow:**

1. The browser signs in with Supabase Auth and receives a JWT (a signed login token).
2. Every API call sends that JWT. The API verifies it against Supabase's published signing keys.
3. The API checks permissions and feature flags in Postgres, then reads or writes data.
4. The browser never queries the database directly.

## 2. Components

| Component | Platform | Repo path | What it does |
|---|---|---|---|
| Web app | Cloudflare Pages | `web/` | React 19 + Vite + TypeScript single-page app. Static files only. |
| API | Railway service `api` | `api/` | Python 3.13, FastAPI, pandas/numpy. Backtests, permissions, flags, admin. |
| Price sync | Railway cron service `price-sync` | `api/` (same image) | Downloads adjusted daily prices from Alpaca, then exits. |
| Database | Supabase Postgres | `supabase/migrations/` | All app data. Schema managed by migrations. |
| Auth | Supabase Auth | `supabase/config.toml` | Email/password accounts; issues JWTs. |
| Market data | Alpaca Market Data API | `api/src/tirelessinvest/market/` | Daily bars, split/dividend-adjusted. |
| DNS / TLS / CDN | Cloudflare | – | DNS for `tirelessinvest.com`; serves Pages; proxies the API. |
| Source + CI | GitHub + GitHub Actions | `.github/workflows/ci.yml` | Lint, tests against a real Postgres, frontend build. |

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
Railway-specific features used are cron and config files. Moving to Azure Container Apps or Fly
is roughly an afternoon's work.

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
| Redis / message queue | Backtests run inside the request; a Postgres `jobs` table can queue work later | Backtests regularly exceed ~30s, or parameter sweeps arrive |
| Separate staging environment | Cost and effort for a personal project; local Supabase + CI cover most risk | Before Phase 4 (real money) |
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

### 5.2 Web app (`web`, Cloudflare Pages build variables)

| Variable | Example | Notes |
|---|---|---|
| `VITE_SUPABASE_URL` | `https://<ref>.supabase.co` | Public |
| `VITE_SUPABASE_ANON_KEY` | Supabase publishable / anon key | **Public by design**: it ends up in the browser bundle. Safe because RLS blocks it from all app data (§3.4). |
| `VITE_API_URL` | `https://api.tirelessinvest.com` | |

**Never put** `service_role` keys, Alpaca keys or database URLs in `VITE_*` variables. Anything
with that prefix is shipped to every visitor's browser.

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
locally with `supabase db reset`, then `supabase db push` to production. Push the migration
**before** deploying code that depends on it (§8.3).

## 7. Security model

| Concern | Control |
|---|---|
| Who is calling | Every API route except `/health` needs a valid Supabase JWT: signature, `exp`, `aud=authenticated`, and `iss` checked. |
| Admin rights | `app_metadata.role` only, which needs the service role to change. A test proves `user_metadata` can't grant admin. |
| Becoming admin | No API or UI path. Run `python -m tirelessinvest.cli make-admin <email>` with production `DATABASE_URL`; it refuses if an admin exists. The user then signs out and back in to refresh their token. |
| Permissions and flags | Checked on the server for each request. UI hiding is cosmetic. |
| Direct database access from browsers | Blocked by RLS with no policies plus revoked grants (tested). |
| Other users' data | Other users' backtests return 404. |
| Secrets | Railway variables (Alpaca keys, DB URL). Nothing secret in the repo or the web bundle. |
| CORS | Only `CORS_ORIGINS` may call the API from a browser. |
| Container | Runs as a non-root user (uid 10001). |
| Token freshness | Role changes reach the API only after the user's token refreshes (up to about an hour) or they sign in again. Acceptable with a single admin. |

**Gaps:**

- no rate limiting;
- no web application firewall rules;
- no automated dependency updates (Dependabot);
- no security headers (CSP) on the Pages site.

See §11.

## 8. Build, deploy and CI

### 8.1 Continuous integration (`.github/workflows/ci.yml`)

Runs on every push to `main` and on every pull request:

- **api job:** `uv sync --frozen` → `ruff check` → `ruff format --check` → `pytest`, with a
  Postgres 17 service container. That covers 27 tests: engine, Alpaca client and API/database
  integration.
- **web job:** `pnpm install --frozen-lockfile` → `pnpm build`, which type-checks and builds.

The integration tests run against plain Postgres, using `api/tests/supabase_stub.sql` to stand
in for the parts of Supabase the migration needs (`auth.users`, the `anon` and `authenticated`
roles).

### 8.2 Deployments

| Target | Trigger | How |
|---|---|---|
| `api` | Push to `main` touching `api/**` | Railway builds `api/Dockerfile`; health check `GET /health` must pass before traffic switches |
| `price-sync` | Same image, rebuilt on the same pushes | Runs only on its cron schedule |
| `web` | Push to `main` | Cloudflare Pages runs `pnpm build` in `web/` and serves `dist/` |
| Database schema | **Manual** | `supabase db push` |

### 8.3 Deploy-order rule

The schema is migrated by hand, but code deploys automatically. So:

1. Push the migration first (`supabase db push`).
2. Then merge the code that needs it.

Make migrations additive (add columns or tables; drop them in a later release), so old and new
code both work during the switch.

### 8.4 Container image (`api/Dockerfile`)

- `python:3.13-slim` plus a pinned `uv` 0.11.32.
- Dependencies install in their own layer from `uv.lock` (`--frozen --no-dev`).
- Default command: `uvicorn tirelessinvest.main:app --host 0.0.0.0 --port ${PORT:-8000}`.
  It trusts proxy headers so client IPs are correct behind Railway and Cloudflare.
- The `price-sync` service overrides the start command:
  `python -m tirelessinvest.jobs.sync_prices`.

**Not yet verified:** the image hasn't been built during development, because Docker wasn't
available. The first Railway deploy is its first real build.

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

2. Under **Authentication → URL Configuration**, set the Site URL to
   `https://tirelessinvest.com`.
3. Under **Authentication → SMTP Settings**, configure a custom SMTP provider (e.g. Resend,
   Postmark, SES). **This is required before anyone else can sign up.** Supabase's built-in
   email service only delivers to members of your Supabase organization, on every plan, and is
   heavily rate-limited.
4. Under **Connect**, copy the **Session pooler** connection string for `DATABASE_URL`.

### Step 3: Railway

1. Create a project from the GitHub repo `jwh3times/TirelessInvest`.
2. Create the `api` service:
   - Root Directory `/api`
   - Config-as-code path `/api/railway.toml`
3. Create the `price-sync` service:
   - Root Directory `/api`
   - Config-as-code path `/api/railway.sync.toml`
4. Set shared variables on both services (§5.1). Mark the Alpaca keys and `DATABASE_URL` as
   sealed/secret.
5. On `api`, add the custom domain `api.tirelessinvest.com`. Copy the CNAME target and the TXT
   verification record Railway shows.

### Step 4: Cloudflare

1. DNS: add the Railway CNAME for `api` (proxied) and the TXT record.
2. SSL/TLS → Overview: set the mode to **Full**.
3. Pages: create a project from the repo.
   - Root directory: `web`
   - Build command: `pnpm build`
   - Output directory: `dist`
   - Variables: as in §5.2
4. Pages → Custom domains: add `tirelessinvest.com`.
5. Add a 301 redirect from `www.tirelessinvest.com` to `tirelessinvest.com`.

### Step 5: First run

1. Trigger `price-sync` once by hand from Railway, so prices exist before the first backtest.
2. Sign up on `https://tirelessinvest.com`.
3. Make yourself admin, from a machine with the production `DATABASE_URL` (or with
   `railway run`):

   ```bash
   cd api && uv run python -m tirelessinvest.cli make-admin you@example.com
   ```

4. Sign out and back in. The Admin tab should appear.

### Step 6: Smoke test

- `GET https://api.tirelessinvest.com/health` returns `{"status":"ok"}`.
- A buy-and-hold SPY backtest from 2016 to today shows SPY results with no "synthetic data"
  warning.
- A second test account can't see the first account's backtests.

## 11. Operations

| Area | Current state | Gap / next step |
|---|---|---|
| Logs | Railway service logs (API logs requests and rejected tokens); Supabase logs | Nothing aggregated or searchable long-term |
| Health | Railway health check on `/health` | No uptime monitor. Add a free external check on `/health` and the Pages URL. |
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
| JWT signing key rotated | Tokens briefly rejected | The API caches published keys for 10 minutes; wait about 20 minutes after creating a standby key before rotating |
| Very long backtest | Request takes up to about 16s | Within limits today; move to a queued job if it grows (§3.7) |

## 12. Cost estimate

Prices change, so treat these as directional and check each provider's pricing page.

| Item | During development | Running for real |
|---|---|---|
| Cloudflare (DNS, Pages) | $0 | $0 |
| Supabase | $0 (free tier, pauses when idle) | ~$25/month (Pro) |
| Railway | ~$5/month (Hobby, includes some usage) | ~$5–20/month depending on usage |
| Alpaca market data | $0 (basic) | $0; paid plans only if intraday data is needed (Phase 3) |
| SMTP provider | $0 | $0 on free tiers at low volume |
| Domain | ~$10–15/year | same |
| **Total** | **~$5/month** | **~$30–50/month** |

## 13. How infrastructure grows with each phase

| Phase | Additions |
|---|---|
| 2: paper portfolios | Tables for portfolios, orders and positions. A daily `portfolio-runner` cron service (same image) that checks Alpaca's market calendar before acting. A `paper_portfolios` flag as kill switch. Alerting on runner failure. Possibly a Postgres `jobs` table plus a worker for long backtests. |
| 3: intraday | A paid intraday data plan. Separate storage for minute bars: a partitioned table, or Parquet files in object storage. More CPU for simulations. Probably a background worker instead of synchronous requests. |
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
