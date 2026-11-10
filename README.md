# TirelessInvest

An autonomous investing product in the making: you pick a risk level and the system does
the investing for you. It's built in phases, starting with the part that tells you whether
an automated strategy is worth trusting at all.

Today it is a sandbox for testing those strategies with simulated money. You choose a
strategy, a set of investments, a period, a simulated deposit and a risk level. The engine
replays history day by day, trading as the strategy would have, and compares the result
with simply buying and holding an index fund under the same costs.

**Status: Phase 1 (backtesting).** No real money, no live trading.

**Documentation:**
- [Product requirements (PRD)](docs/PRD.md): goals, users, requirements by phase, open
  questions.
- [Infrastructure](docs/INFRASTRUCTURE.md): hosting, DNS, configuration, security, deployment
  runbook, operations.

## What's in the box

- **Backtest engine** (`api/src/tirelessinvest/engine`): pure Python, no I/O.
  - Decisions are made at the close and filled at the **next day's open**, so a strategy never
    trades at a price it has already seen. A test enforces this.
  - Fees, slippage, fractional shares, cash, and forced sale when a symbol's data ends
    (delisting).
  - Metrics: CAGR, volatility, Sharpe, Sortino, max drawdown and its duration, Calmar, beta,
    alpha, turnover, costs, monthly returns.
- **Strategies:**

  | Strategy | What it does |
  |---|---|
  | Buy and hold / fixed allocation | Hold a fixed mix, optionally rebalanced on a schedule |
  | Momentum rotation | Hold the strongest few symbols by trailing return |
  | Trend following | Hold a symbol only while it is above its moving average |
  | Short-term mean reversion | Buy recent losers within an uptrend. Behind a feature flag |

- **Risk dial (1–5)**, kept separate from strategy choice. It caps position size and scales
  exposure down to a volatility target. It never adds leverage.
- **Universes:** S&P 500 ETF; large/mid/small-cap ETFs; multi-asset; sectors; and a
  deliberately labelled *survivorship-biased* list of today's mega caps.
- **Accounts and roles:** Supabase Auth. One admin, set from the command line. Users get
  default permissions on sign-up.
- **Admin dashboard:** per-user permissions, feature flags (global switch plus per-user
  overrides), and an audit log of every admin change.

## Architecture

```
Cloudflare Pages (React)  ──JWT──▶  Railway: api (FastAPI)  ──▶  Supabase Postgres
        │                                   ▲                          ▲
        └──── Supabase Auth (sign-in) ──────┘                          │
                                     Railway: price-sync (cron) ──▶ Alpaca market data
```

- The browser uses Supabase **only to sign in**. All data goes through the API, which checks
  the token, permissions and flags on every request.
- Every table has row-level security on with **no policies**, and grants are revoked from
  Supabase's `anon`/`authenticated` roles. The auto-generated Supabase REST API therefore
  exposes nothing. A test checks this.
- Admin lives in `app_metadata.role`, which only the service role can write. It is never in
  `user_metadata`, which users can edit themselves. There is a test for this too.
- `price-sync` re-downloads each tracked symbol's **full** adjusted history every weekday.
  Adjusted prices change backwards after every dividend or split, so appending only new
  days would corrupt the series.
- The API also backfills unseen symbols on demand when a backtest asks for them.

## Local development

Prerequisites: Python 3.12+, [uv](https://docs.astral.sh/uv/), Node 22 + pnpm, Docker (for the
local Supabase stack), and the [Supabase CLI](https://supabase.com/docs/guides/cli).

```bash
supabase start          # local Postgres + Auth; applies supabase/migrations
```

API:

```bash
cd api
cp .env.example .env    # fill in Alpaca keys, or set PRICE_SOURCE=synthetic
uv sync
uv run uvicorn tirelessinvest.main:app --reload
```

If `supabase start` reports a legacy JWT secret, set `SUPABASE_JWT_SECRET` to it in
`api/.env`. Otherwise the API verifies tokens using the project's published signing keys.

Web:

```bash
cd web
cp .env.example .env    # VITE_SUPABASE_ANON_KEY from `supabase status`
pnpm install
pnpm dev                # http://localhost:5173
```

Make yourself admin (sign up in the app first):

```bash
cd api && uv run python -m tirelessinvest.cli make-admin you@example.com
```

Then sign out and back in so your token carries the role. The command refuses if another
admin already exists.

### Tests

```bash
cd api
uv run pytest                                   # engine tests only
TEST_DATABASE_URL=postgresql://postgres:postgres@127.0.0.1:54322/postgres uv run pytest
```

The second form also runs API + database integration tests. It creates and drops a scratch
database on whatever server you point it at. CI runs both suites, plus the frontend build.

## Deploying

### 1. Supabase

1. Create a project.
2. Push the schema:

   ```bash
   supabase link --project-ref <ref>
   ```

   ```bash
   supabase db push
   ```

3. Under **Authentication → URL Configuration**, set the Site URL to your frontend domain.
4. Under **Connect**, copy the **Session pooler** connection string. Railway reaches it over
   IPv4; the direct connection string is IPv6-only.
5. Free projects pause after about a week of inactivity, which stops the cron job. Use Pro
   once anything needs to run unattended.
6. Under **Authentication → SMTP Settings**, configure your own email provider. Supabase's
   built-in email only delivers to members of your Supabase organization, so without this
   nobody else can confirm a sign-up.

Full step-by-step setup, DNS and operations details are in
[docs/INFRASTRUCTURE.md](docs/INFRASTRUCTURE.md#10-setup-runbook-first-deployment).

### 2. Railway (two services from this repo)

| Service | Root directory | Config-as-code path | Notes |
|---|---|---|---|
| `api` | `/api` | `/api/railway.toml` | Generate a public domain, e.g. `api.yourdomain.com` |
| `price-sync` | `/api` | `/api/railway.sync.toml` | Cron, weekdays 22:30 UTC, exits when done |

Shared variables for both services: `DATABASE_URL` (session pooler), `SUPABASE_URL`,
`ALPACA_KEY_ID`, `ALPACA_SECRET_KEY`. Only the API needs `CORS_ORIGINS`, set to your
frontend origin.

### 3. Cloudflare Pages

- Root directory: `web`
- Build command: `pnpm build`
- Output directory: `dist`
- Environment variables: `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY` (the publishable key,
  which is safe in a browser), `VITE_API_URL`.

`public/_redirects` handles client-side routes.

## Known limitations (read these before believing a result)

- **Alpaca's free history starts around 2016.** No 2008, no dot-com crash. A strategy that
  looks great from 2016 onward has only been tested in one mostly-bullish decade.
- **Survivorship bias.** Any list of stocks picked today is biased toward winners. Prefer ETF
  universes.
- **Overfitting.** If you tune parameters until the past looks good, you are fitting noise.
  Pick parameters, then test on a period you didn't tune on.
- **Daily bars only.** Intraday and day trading need minute data, which is mostly paid.
  That's Phase 3.
- **Backtests run synchronously.** The worst case (50 symbols, 30 years, daily rebalancing)
  takes roughly 10–15 seconds. Monthly strategies take under a second. Move to a job queue
  if that becomes a problem.
- **Market-data licensing.** Free data plans are generally for personal use. Read your
  provider's terms before letting the public see prices, since that can count as
  redistribution.

## Roadmap

1. ~~Backtesting, risk dial, auth, admin, flags~~ (this release)
2. Paper portfolios: deposit simulated cash and let a scheduled job trade it daily on live
   prices, using a market-calendar check rather than trusting cron.
3. Intraday data and strategies.
4. Real money for the owner's own Alpaca account only, behind the `live_trading` flag.
   Running other people's money is regulated (investment-adviser rules), so it is out of scope.
