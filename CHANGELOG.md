# Changelog

All notable changes to TirelessInvest are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). The product has
one version, the `vX.Y.Z` tag the release workflow puts on every merge to `main`; `VERSION` holds
the current release line as `X.Y.0`. Each section below names the version its merge minted. A Dependabot
merge mints a version with no section of its own: its changes are rolled up into the next section.
A major version means a breaking change for users (see `GLOSSARY.md`); until `1.0.0`, breaking
changes raise the minor version.

## [Unreleased]

No unreleased changes.

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
- The web app's footer shows the release it belongs to, as `v0.1.0 � <short commit>`.
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
