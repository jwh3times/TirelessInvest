-- The risk dial went from five levels to ten (#22), so a saved `risk_level` of 1-5 now names a
-- different preset. Every saved request that relied on its level alone (no explicit `risk`) is
-- rewritten to the old preset's explicit settings, which override the level, plus a
-- `legacy_risk_level` marker. Re-running it reproduces its original result, and the app shows it
-- as "old 1-5 scale". The report's config gets the same marker; it already holds the settings.
--
-- These values are LEGACY_RISK_PRESETS in api/src/tirelessinvest/engine/risk.py, frozen.

with old_presets (level, risk) as (
  values
    (1, '{"max_position_weight": 0.25, "target_volatility": 0.06, "vol_lookback_days": 63, "cash_buffer": 0.05}'::jsonb),
    (2, '{"max_position_weight": 0.35, "target_volatility": 0.1, "vol_lookback_days": 63, "cash_buffer": 0.0}'::jsonb),
    (3, '{"max_position_weight": 0.5, "target_volatility": 0.15, "vol_lookback_days": 63, "cash_buffer": 0.0}'::jsonb),
    (4, '{"max_position_weight": 1.0, "target_volatility": 0.22, "vol_lookback_days": 63, "cash_buffer": 0.0}'::jsonb),
    (5, '{"max_position_weight": 1.0, "target_volatility": null, "vol_lookback_days": 63, "cash_buffer": 0.0}'::jsonb)
)
update public.backtests b
set request = b.request || jsonb_build_object('risk', p.risk, 'legacy_risk_level', p.level),
    report = jsonb_set(b.report, '{config,legacy_risk_level}', to_jsonb(p.level))
from old_presets p
where coalesce(b.request -> 'risk', 'null'::jsonb) = 'null'::jsonb
  -- The five-level dial defaulted to 5, so a request without a level ran at 5.
  and coalesce((b.request ->> 'risk_level')::int, 5) = p.level;
