# TirelessInvest: Product Requirements Document

| | |
|---|---|
| **Status** | Phase 1 built and in the repo. Phases 2–4 are drafts. |
| **Owner** | Repository owner (sole admin) |
| **Last updated** | 2026-11-10 |
| **Companion doc** | [INFRASTRUCTURE.md](INFRASTRUCTURE.md) |

Every requirement below carries one of these labels, so it's clear what is settled:

- **Built**: implemented and tested in this repo.
- **Decided**: agreed, not yet built.
- **Proposed**: a recommendation awaiting the owner's sign-off.
- **Open**: an unresolved question (see [§11](#11-open-questions)).

---

## 1. Summary

TirelessInvest is meant to become an **autonomous investing product**: a user deposits money,
picks how much risk they want, and the system does the investing without further effort from
them.

It starts as a personal learning project. Before anything trades on its own, the owner wants to
find out which automated strategies are actually worth trusting. So Phase 1 is a **backtesting
lab with simulated money**. It replays market history day by day, runs a strategy as if it had
been live, and reports the result next to the simplest alternative: buying and holding an
S&P 500 index fund.

## 2. Background and problem

- Most people who try to beat the market with active strategies do worse than an index fund
  once costs are included. Most tools that let you test strategies make this worse by producing
  flattering backtests: they ignore costs, let the strategy peek at prices it couldn't have
  known, or test only on stocks that went on to succeed.
- The owner wants to explore investing algorithms, gains and losses hands-on, with a clear path
  from simulated money to (eventually) real money.
- **The core question the product must answer honestly:** *"Would this automated strategy, at
  this risk level, have done better than just holding the index, after costs?"*

## 3. Goals and non-goals

### Goals

| # | Goal | Status |
|---|---|---|
| G1 | Let a user test an automated strategy on historical prices with a simulated deposit, and see gain/loss, risk and costs. | Built |
| G2 | Always compare against buying and holding an index fund under the same costs. | Built |
| G3 | Make risk a single, understandable control (the risk dial), separate from strategy choice. | Built |
| G4 | Produce results that are hard to fool: no look-ahead, realistic costs, warnings about known biases. | Built |
| G5 | Users can sign up; the owner is the sole admin and controls permissions and feature flags. | Built |
| G6 | Run simulated ("paper") portfolios that trade by themselves on live prices, with no user effort after setup. | Decided (Phase 2) |
| G7 | Eventually trade real money in the owner's own brokerage account. | Decided (Phase 4) |

### Non-goals

| Non-goal | Why |
|---|---|
| Managing other people's real money | Trading other people's money on their behalf is regulated investment-adviser activity (registration, custody, KYC, liability). Real money is owner-only. **Decided.** |
| Holding user funds or acting as a broker | Users never deposit real money with TirelessInvest. Simulated deposits only, except the owner's own broker account in Phase 4. **Decided.** |
| Guaranteeing or promising returns | Any such claim would be false. The product reports what happened in history and says plainly that history doesn't predict the future. **Decided.** |
| Claiming to be "AI" | The strategies are rule-based. The SEC has penalized firms for overstating AI use ("AI-washing"). **Decided.** |
| Social features, copy trading, chat | Out of scope. |
| Native mobile apps | The web app must work on phones. Native apps are out of scope. |

## 4. Users

| User | Description | Access |
|---|---|---|
| **Owner / admin** | The project owner. The only admin, ever, unless they deliberately force another. | Every permission; admin dashboard. |
| **Signed-up user** | Anyone who creates an account. Phase 1 assumes this means friends and testers, not the public. | Default permissions (see §6.2), adjustable by the admin. |
| **Public visitor** | Whether strangers can sign up is **Open** (Q2). It affects data licensing, email setup and marketing claims. | No access without an account. |

## 5. Product principles

1. **Honest numbers over impressive numbers.** Include costs by default. Warn about
   survivorship bias, synthetic data and data gaps. Prefer the index-fund default, because it
   usually wins.
2. **Risk and strategy are different questions.** Strategy decides *what* to hold; the risk
   dial decides *how much* money is exposed. Turning risk up never adds leverage.
3. **Rules are enforced on the server.** Hiding a button in the UI is cosmetic. The API checks
   identity, permissions and feature flags on every request.
4. **Simulated before real.** No real-money feature ships until the simulated version has run
   unattended for a meaningful period (see [§9](#9-success-metrics)).
5. **Simple for the user, transparent on request.** One dial and one button by default; full
   trade lists, parameters and data tables for anyone who wants to look.

---

## 6. Phase 1: Backtesting lab (Built)

### 6.1 Accounts and roles

| ID | Requirement | Status |
|---|---|---|
| A1 | Users sign up and sign in with email and password, through Supabase Auth. | Built |
| A2 | The API verifies every request's access token: signature, expiry, audience and issuer. | Built |
| A3 | The admin role is stored only in Supabase `app_metadata`, which users cannot edit. It is never read from `user_metadata`, which users can edit. A test proves a user can't make themselves admin. | Built |
| A4 | There is no UI or API to grant admin. A command-line tool makes the first admin and refuses a second unless `--force` is passed. | Built |
| A5 | New sign-ups automatically receive the default permissions. | Built |
| A6 | Users can delete their own backtests. | Built |
| A7 | Users can delete their own account. | **Not built** (gap) |

### 6.2 Permissions

Admins hold every permission implicitly. Permissions are a catalog in the database, so adding
one needs no code change to the admin UI.

| Permission | Default on sign-up | Grants |
|---|---|---|
| `backtest:run` | Yes | Run backtests on preset universes |
| `backtest:custom_universe` | No | Run backtests on custom symbol lists |

Removing all of a user's permissions effectively suspends them. **Built.**

### 6.3 Feature flags

| ID | Requirement | Status |
|---|---|---|
| F1 | Each flag has a global on/off value, plus optional per-user overrides that win over the global value. | Built |
| F2 | The admin can create, toggle, override per user and delete flags from the dashboard. | Built |
| F3 | Flags are checked on the server, e.g. a flag-gated strategy is rejected by the API (403), not only hidden in the UI. | Built |
| F4 | Every admin change to a flag or permission is written to an audit log. | Built |

Seeded flags:

| Flag | Default | Purpose |
|---|---|---|
| `strategy.mean_reversion` | Off | Gates the experimental mean-reversion strategy |
| `live_trading` | Off | Reserved for Phase 4. No live-trading code exists yet. |

### 6.4 Running a backtest

**Inputs:**

| Input | Rules / default |
|---|---|
| Strategy | One of the built-in strategies (§6.5); flag-gated ones need their flag on |
| Strategy parameters | Per strategy; the form is generated from each strategy's parameter schema |
| Universe | A preset (§6.6), or a custom list of 1–50 symbols (needs `backtest:custom_universe`) |
| Start / end date | End after start; end not in the future; range at most 30 years. UI default start: 2016-06-01 |
| Simulated deposit | $100 – $100,000,000. Default $10,000 |
| Risk level | 1–5, default 5 (unconstrained, so the strategy's raw behavior is visible). Explicit settings can override the preset |
| Rebalance schedule | never / daily / weekly / monthly / quarterly. Defaults to the strategy's own |
| Costs | Fee 0 bps and slippage 5 bps by default, adjustable |
| Rebalance threshold | Skip trades smaller than 0.5% of equity, to avoid pointless churn |
| Benchmark | Default `SPY` |
| Name | Optional label |

**Simulation rules** (the core of goal G4):

| ID | Rule | Status |
|---|---|---|
| S1 | Decisions use closing prices up to and including the decision day only. Orders fill at the **next day's open**. A test checks that no strategy ever sees the price it trades at. | Built |
| S2 | Every trade pays the fee and slippage. Buys are scaled down if cash runs short. | Built |
| S3 | Fractional shares are allowed (matching Alpaca). | Built |
| S4 | If a symbol's data ends (delisting, merger), the position is sold at the last close instead of being frozen. | Built |
| S5 | Prices are split- and dividend-adjusted, so buy-and-hold returns are total returns. | Built |
| S6 | Enough extra history is loaded before the start date to cover the strategy's lookback window, so it can act on day one. | Built |
| S7 | The benchmark runs as buy-and-hold with the same deposit, dates and costs. | Built |

**Outputs:**

- A plain-language verdict, e.g. "$10,000 became $17,885 (+78.9%). That is 11.7% per year behind
  simply holding SPY."
- Metrics: total return, CAGR, volatility, Sharpe, Sortino, max drawdown and its duration,
  Calmar, beta, alpha, correlation, best/worst day, total fees and slippage, trade count, annual
  turnover, average invested exposure. Each is shown next to the benchmark's value where that
  makes sense.
- Charts: portfolio value against the benchmark (log scale optional, table view available) and
  drawdown against the benchmark.
- Monthly returns table: blue for gains, red for losses, neutral at zero.
- Final holdings and cash, plus the trade list (the last 1,000 trades are stored).
- **Warnings**, shown above the results:
  - synthetic data in use;
  - survivorship-biased universe;
  - symbols that start trading after the start date;
  - data beginning later than requested;
  - not enough history for the lookback window.
- Every run is saved to the user's history and has a permalink.

### 6.5 Strategies (Built)

Deliberately simple, well-known strategies, so results can be sanity-checked against published
research.

| Strategy | Behavior | Default rebalance | Key parameters |
|---|---|---|---|
| **Buy and hold / fixed allocation** | Hold a fixed mix, or equal weight if none is given | never | `weights` (e.g. SPY:0.6, TLT:0.4) |
| **Momentum rotation** | Hold the top N symbols by trailing return; optionally go to cash if even the leaders are falling | monthly | lookback 252d, skip 21d, top N 3, absolute filter on |
| **Trend following** | Hold a symbol only while its price is above its moving average | monthly | SMA 200d, concentrate off |
| **Short-term mean reversion** | Buy the worst recent decliners within a long-term uptrend. Flag-gated | weekly | lookback 5d, trend SMA 200d, hold 3 |

### 6.6 Universes (Built)

| Preset | Symbols | Note |
|---|---|---|
| S&P 500 index fund | SPY | The baseline |
| US large / mid / small cap | SPY, MDY, IWM | Covers the large/mid/small-cap range from the original brief |
| Multi-asset | SPY, QQQ, IWM, EFA, EEM, TLT, IEF, GLD, VNQ | |
| US sectors | 11 sector ETFs | XLRE and XLC start later than the others |
| Today's mega caps | 15 large US stocks | **Labelled survivorship-biased**; shows a warning |

### 6.7 The risk dial (Built)

The risk dial applies on top of the strategy. It caps exposure; it never redistributes freed-up
weight to other symbols, and it never borrows.

| Level | Label | Max per symbol | Volatility target | Always in cash |
|---|---|---|---|---|
| 1 | Preservation | 25% | 6% / yr | 5% |
| 2 | Conservative | 35% | 10% / yr | – |
| 3 | Moderate | 50% | 15% / yr | – |
| 4 | Growth | 100% | 22% / yr | – |
| 5 | Unconstrained | 100% | none | – |

Volatility targeting estimates the proposed portfolio's volatility over the last 63 trading days.
If that exceeds the target, all positions are scaled down proportionally.

> **The original brief vs. what's built.** The original idea was a risk setting that runs from
> "all in an index fund" to "full day trading in large/mid/small caps." The built design
> separates those: the dial controls *exposure*, and strategy choice controls *style*. That
> change was made because day trading isn't the high-return end of a risk scale. For most
> retail traders it means more variance and lower returns after costs. Whether the dial should
> eventually also *select* strategies (e.g. level 1 always means the index fund) is **Open**
> (Q5).

### 6.8 Admin dashboard (Built)

- **Users & permissions:** list users with join date, last sign-in and backtest count; toggle
  each permission per user. The admin row shows "all" and can't be edited.
- **Feature flags:** toggle globally; add, flip or remove per-user overrides; create and delete
  flags.
- **Audit log:** who did what to which target, when, and with what details.
- The Admin link appears only for the admin, and every `/admin` API call checks the admin role
  regardless.

### 6.9 Non-functional requirements

| Area | Requirement | Status |
|---|---|---|
| Performance | Typical backtests (monthly rebalance, ≤ 15 symbols, ~10 years) finish in under 1s. The worst case allowed (50 symbols, 30 years, daily rebalance) takes roughly 10–16s and runs inside the request. | Built (measured) |
| Data access | Supabase's auto-generated REST API exposes none of the app's tables: row-level security is on with no policies, and grants are revoked from the public roles. A test proves this. | Built |
| Data accuracy | The nightly price sync re-downloads each symbol's full adjusted history, because dividends and splits rewrite past adjusted prices. | Built |
| Accessibility | Chart colors validated for colorblind separation and contrast in light and dark mode; every chart has a table view or equivalent; identity never relies on color alone. | Built |
| Mobile | The layout works at phone width with no sideways scrolling. | Built (checked at 390px) |
| Privacy | Users see only their own backtests; another user's backtest returns 404, not 403, so IDs can't be probed. | Built |
| Disclaimers | Every page states simulated money only, and that past performance doesn't predict future results. | Built |

### 6.10 Known Phase 1 limitations

- **Price history starts around 2016** (Alpaca's free data). There's no 2008 crash or dot-com
  bust, so strategies are tested on one mostly-rising decade.
- **Daily bars only.** No intraday data, so no day trading.
- **Overfitting isn't detected.** Nothing stops a user from tuning parameters until the past
  looks good. See Q7.
- **No rate limiting** on the backtest endpoint.
- **No account deletion** (A7).

---

## 7. Phase 2: Autonomous paper portfolios (Draft)

The first step that delivers the "works without your effort" promise, still with simulated
money.

| ID | Requirement | Status |
|---|---|---|
| P1 | A user creates a portfolio: name, simulated deposit, strategy plus parameters, risk level. | Decided |
| P2 | A scheduled job runs every trading day. It checks the market calendar (holidays, early closes) and does nothing on non-trading days; it does not rely on cron alone. | Decided |
| P3 | The job uses exactly the same decision and fill logic as the backtester, so live results and backtests are comparable. | Proposed |
| P4 | Every simulated order, fill and resulting position is recorded. Re-running the job for the same day must not create duplicate trades. | Proposed |
| P5 | The user sees current value, performance since creation against the benchmark, holdings and trade history. | Proposed |
| P6 | The user can pause, resume or close a portfolio. Whether they can override individual trades is **Open** (Q3). | Proposed |
| P7 | Simulated "deposits" and "withdrawals" after creation are allowed and handled so they don't distort performance figures. | Proposed |
| P8 | The admin can see every portfolio and disable the job globally with a feature flag (`paper_portfolios`), acting as a kill switch. | Proposed |
| P9 | Notifications (e.g. weekly summary email) | Open; depends on email setup |
| P10 | Data-gap handling: if prices didn't update, the job skips the day and records why. | Proposed |

## 8. Phases 3 and 4 (Outline)

### Phase 3: Intraday data and strategies

- Minute-level bars from a paid data plan; a separate storage strategy for the much larger
  volume.
- A simulator with intraday fills and more realistic slippage for small caps.
- Pattern-day-trader constraints, if margin accounts are ever simulated. FINRA has been revising
  this rule, so check its status when Phase 3 starts.

### Phase 4: Real money, owner only

- Trades the owner's own Alpaca account through Alpaca's trading API. Paper and live share an
  API, so this is mostly configuration plus safety work.
- Gated by the `live_trading` flag, **and** restricted in code to the owner's account.
- Required safety features:
  - a kill switch;
  - per-order and per-day notional limits;
  - a dry-run mode that shows intended orders before enabling execution;
  - reconciliation of local positions against the broker every day;
  - alerts on any failure.
- Broker API keys stored as secrets, never in a database table.
- **Out of scope permanently:** trading anyone else's real money.

---

## 9. Success metrics

This is a personal project, so success is mostly "the tool is trustworthy and teaches the owner
something". All of these are **Proposed**.

| Phase | Metric | Target |
|---|---|---|
| 1 | Correctness checks pass in CI: no look-ahead, cost application, metric math | 100%, every push |
| 1 | The owner can answer "does strategy X beat SPY after costs from 2016 to today?" in under a minute | Yes |
| 1 | Backtest of a monthly strategy on a preset universe | < 2s |
| 2 | Paper portfolios run unattended | 60 consecutive trading days with no manual fixes |
| 2 | Agreement between a paper portfolio and a backtest of the same period | Within 0.5% of ending value |
| 4 (gate) | Phase 2 metrics met **and** a written risk review before any real order is placed | Required |

## 10. Compliance and legal constraints

This isn't legal advice. These constraints come from the planning discussions and shape the
non-goals.

| Topic | Constraint |
|---|---|
| Investment advice | Automatically managing other people's money is investment-adviser activity. Real money stays owner-only (Phase 4). |
| Naming | Avoid "broker", "fund" and "savings" in branding. They imply a registered broker-dealer, a pooled fund or principal protection. "TirelessInvest" avoids all three. |
| Marketing claims | No promised returns. No "AI" claims. "Autonomous" and "effortless" language must sit next to clear risk statements. |
| Market data licensing | Free data plans are generally licensed for personal use. Showing prices to the public can count as redistribution. Prices are never exposed through the API; only derived results are. Check the data provider's terms before public sign-up (Q2). |
| Pattern day trading | Relevant only for Phase 3/4 margin accounts. Check the current FINRA rule at that time. |

## 11. Open questions

These are decisions for the owner. The proposed defaults are suggestions, not decisions.

| # | Question | Why it matters | Suggested default |
|---|---|---|---|
| Q1 | **What does success mean: maximum profit, or best risk-adjusted return compared with the index?** | The original brief said "maximize profit", which literally rewards the riskiest setting. The product currently measures against the index. | Risk-adjusted, against the index |
| Q2 | **Can the public sign up, or is it invite-only?** | Decides data licensing, email (custom SMTP needed), rate limiting and how careful marketing must be. | Invite-only until Phase 2 is proven |
| Q3 | **In Phase 2, can users override individual trades?** | Overrides undercut "autonomous" and make performance hard to attribute. | No overrides; pause/resume only |
| Q4 | **What does a risk level promise the user?** | "Conservative" suggests a maximum loss. The dial currently promises only a volatility target and position caps. | Show the historical worst drawdown per level next to the dial; promise nothing else |
| Q5 | **Should the dial also choose the strategy?** | The original brief tied risk to strategy (index fund up to day trading). The build keeps them separate. | Keep separate; maybe add a "recommended strategy" per level |
| Q6 | **Is the 2016+ data window acceptable, or is a longer history source needed?** | Strategies are untested through a major bear market before 2020. | Add a longer daily-history source before trusting any strategy |
| Q7 | **Should the product guard against overfitting?** | Users can tune until the past looks good. | Add an out-of-sample split option in a later Phase 1 iteration |
| Q8 | **Account deletion and data retention** | Needed before public sign-up. | Self-serve deletion that cascades to all user data |

## 12. Glossary

| Term | Meaning |
|---|---|
| Backtest | Running a strategy on historical prices as if it had been live |
| Benchmark | What a strategy is compared against; here, buy-and-hold SPY |
| CAGR | Compound annual growth rate: the steady yearly return that gives the same end result |
| Drawdown | Fall from the previous peak value |
| Sharpe ratio | Return per unit of volatility; higher is better |
| Slippage | The gap between the quoted price and the price you actually get |
| Survivorship bias | Testing only on things that survived, which flatters results |
| Look-ahead bias | A backtest using information that wasn't available at the time |
| Paper trading | Trading with simulated money on live prices |
| bps | Basis points; 1 bp = 0.01% |
