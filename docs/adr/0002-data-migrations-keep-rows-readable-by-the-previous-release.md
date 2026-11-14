# Data migrations keep rows readable by the previous release

ADR 0001 says migrations stay additive, so that an emergency Railway rollback can run an older
image against a newer schema. That rule is written for schema changes: add columns or tables, and
drop them in a later release. A **data migration**, one that rewrites existing rows, cannot always
be additive. The ten-level risk dial (v0.3.0, #22) needed one:
`supabase/migrations/20261113000000_legacy_risk_levels.sql` rewrote each saved backtest that
relied on a 1–5 `risk_level` alone, so its stored result would still match a re-run.

Schema changes stay additive, as ADR 0001 says. A data migration may rewrite rows when the release
needs it, on two conditions:

- **The previous release can still read every rewritten row.** Its pages and its read endpoints
  keep working. Rejecting a rewritten row sent back as new input is acceptable, as long as no
  screen of the previous release does that.
- **The migration's header says what a rollback would see**, so whoever rolls back knows the cost.

## Considered options

- **Keep every migration additive, data included.** For #22 that would mean storing the old-dial
  marker beside the request, not in it, and teaching every reader to merge the two. It doubles
  the places a saved request lives, for a rollback that may never happen.
- **Accept #22's migration as a one-off and leave the rule as written.** The written rule would
  then be wrong about production, and the next data migration would reopen the question.

## Consequences

- Rolling back to v0.2.1 after the #22 migration: history and saved results display as before.
  `POST /backtests` with a migrated request returns 422, because v0.2.1's request model forbids the
  unknown `legacy_risk_level` field; the web app has no re-run button, so only a hand-made API call
  meets this. A backtest saved by v0.3.0 at levels 1–5 without explicit settings shows its level
  number with the old dial's meaning. Its header predates this ADR and does not say this.
- A data migration is applied once and is not undone by a revert. Where it can, it leaves a marker
  that a later migration could use to reverse it, as `legacy_risk_level` does.
- `docs/INFRASTRUCTURE.md` §6 and §8.3 state the same rule.
