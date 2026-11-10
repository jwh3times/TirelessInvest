import { useEffect, useMemo, useState, type FormEvent } from "react";
import type { BacktestRequest, Catalog, JsonSchemaProp, Rebalance } from "../lib/types";

const today = () => new Date().toISOString().slice(0, 10);
const yearsAgo = (n: number) => {
  const d = new Date();
  d.setFullYear(d.getFullYear() - n);
  return d.toISOString().slice(0, 10);
};
const REBALANCE: Rebalance[] = ["never", "daily", "weekly", "monthly", "quarterly"];

interface Props {
  catalog: Catalog;
  canUseCustomUniverse: boolean;
  busy: boolean;
  onSubmit: (req: BacktestRequest) => void;
}

/** Resolve `anyOf: [X, null]` (Optional fields) to X. */
function baseType(prop: JsonSchemaProp): string | undefined {
  if (prop.type) return prop.type;
  return prop.anyOf?.find((p) => p.type !== "null")?.type;
}

function parseWeights(text: string): Record<string, number> | null {
  const trimmed = text.trim();
  if (!trimmed) return null;
  const out: Record<string, number> = {};
  for (const part of trimmed.split(",")) {
    const [sym, w] = part.split(":").map((s) => s.trim());
    if (!sym || w === undefined || Number.isNaN(Number(w))) {
      throw new Error(`Weights must look like "SPY:0.6, TLT:0.4" (got "${part.trim()}")`);
    }
    out[sym.toUpperCase()] = Number(w) > 1 ? Number(w) / 100 : Number(w);
  }
  return out;
}

export function BacktestForm({ catalog, canUseCustomUniverse, busy, onSubmit }: Props) {
  const firstAvailable = catalog.strategies.find((s) => s.available) ?? catalog.strategies[0];
  const [strategyKey, setStrategyKey] = useState(firstAvailable.key);
  const strategy = catalog.strategies.find((s) => s.key === strategyKey)!;

  const [params, setParams] = useState<Record<string, string | boolean>>({});
  const [universeMode, setUniverseMode] = useState<"preset" | "custom">("preset");
  const [preset, setPreset] = useState("multi_asset");
  const [customSymbols, setCustomSymbols] = useState("AAPL, MSFT, NVDA");
  const [startDate, setStartDate] = useState("2016-06-01");
  const [endDate, setEndDate] = useState(today());
  const [cash, setCash] = useState("10000");
  const [riskLevel, setRiskLevel] = useState(5);
  const [rebalance, setRebalance] = useState<Rebalance>(strategy.default_rebalance);
  const [feeBps, setFeeBps] = useState(String(catalog.default_costs.fee_bps));
  const [slipBps, setSlipBps] = useState(String(catalog.default_costs.slippage_bps));
  const [benchmark, setBenchmark] = useState("SPY");
  const [name, setName] = useState("");
  const [formError, setFormError] = useState<string | null>(null);

  const paramProps = useMemo(
    () => Object.entries(strategy.params_schema.properties ?? {}),
    [strategy],
  );

  // Reset strategy-specific inputs when the strategy changes.
  useEffect(() => {
    setParams({});
    setRebalance(strategy.default_rebalance);
  }, [strategy]);

  const universe = catalog.universes.find((u) => u.key === preset);
  const risk = catalog.risk_levels.find((r) => r.level === riskLevel)!;

  function submit(e: FormEvent) {
    e.preventDefault();
    setFormError(null);
    try {
      const builtParams: Record<string, unknown> = {};
      for (const [key, prop] of paramProps) {
        const raw = params[key];
        if (raw === undefined || raw === "") continue;
        const type = baseType(prop);
        if (type === "object") builtParams[key] = parseWeights(String(raw));
        else if (type === "boolean") builtParams[key] = raw;
        else builtParams[key] = Number(raw);
      }
      onSubmit({
        name: name.trim() || null,
        strategy: strategyKey,
        params: builtParams,
        universe:
          universeMode === "preset"
            ? { preset }
            : { symbols: customSymbols.split(/[\s,]+/).filter(Boolean) },
        start_date: startDate,
        end_date: endDate,
        starting_cash: Number(cash),
        rebalance,
        risk_level: riskLevel,
        costs: { fee_bps: Number(feeBps), slippage_bps: Number(slipBps) },
        benchmark: benchmark.trim().toUpperCase() || "SPY",
      });
    } catch (err) {
      setFormError((err as Error).message);
    }
  }

  return (
    <form className="card form" onSubmit={submit}>
      <h2>New backtest</h2>

      <label>
        Strategy
        <select value={strategyKey} onChange={(e) => setStrategyKey(e.target.value)}>
          {catalog.strategies.map((s) => (
            <option key={s.key} value={s.key} disabled={!s.available}>
              {s.label}
              {s.available ? "" : " (not enabled)"}
            </option>
          ))}
        </select>
      </label>
      <p className="hint">{strategy.description}</p>

      {paramProps.length > 0 && (
        <fieldset>
          <legend>Strategy parameters</legend>
          {paramProps.map(([key, prop]) => {
            const type = baseType(prop);
            const label = prop.title ?? key;
            if (type === "boolean") {
              const checked = (params[key] as boolean | undefined) ?? Boolean(prop.default);
              return (
                <label key={key} className="check" title={prop.description}>
                  <input
                    type="checkbox"
                    checked={checked}
                    onChange={(e) => setParams({ ...params, [key]: e.target.checked })}
                  />
                  {label}
                </label>
              );
            }
            return (
              <label key={key} title={prop.description}>
                {label}
                <input
                  type={type === "object" ? "text" : "number"}
                  min={prop.minimum}
                  max={prop.maximum}
                  step={type === "integer" ? 1 : "any"}
                  placeholder={
                    type === "object"
                      ? "SPY:0.6, TLT:0.4 (blank = equal weight)"
                      : String(prop.default ?? "")
                  }
                  value={(params[key] as string | undefined) ?? ""}
                  onChange={(e) => setParams({ ...params, [key]: e.target.value })}
                />
                {prop.description && <span className="hint">{prop.description}</span>}
              </label>
            );
          })}
        </fieldset>
      )}

      <fieldset>
        <legend>What to invest in</legend>
        {canUseCustomUniverse && (
          <div className="segmented" role="radiogroup">
            <button
              type="button"
              aria-pressed={universeMode === "preset"}
              onClick={() => setUniverseMode("preset")}
            >
              Preset
            </button>
            <button
              type="button"
              aria-pressed={universeMode === "custom"}
              onClick={() => setUniverseMode("custom")}
            >
              Custom symbols
            </button>
          </div>
        )}
        {universeMode === "preset" ? (
          <>
            <select value={preset} onChange={(e) => setPreset(e.target.value)}>
              {catalog.universes.map((u) => (
                <option key={u.key} value={u.key}>
                  {u.label}
                </option>
              ))}
            </select>
            {universe && (
              <p className="hint">
                {universe.description} <span className="mono">{universe.symbols.join(" ")}</span>
              </p>
            )}
          </>
        ) : (
          <label>
            Symbols (comma or space separated, up to 50)
            <input value={customSymbols} onChange={(e) => setCustomSymbols(e.target.value)} />
            <span className="hint">
              Picking stocks you know did well is survivorship bias. Expect flattering results.
            </span>
          </label>
        )}
      </fieldset>

      <fieldset>
        <legend>Period and money</legend>
        <div className="row">
          <label>
            Start
            <input type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} />
          </label>
          <label>
            End
            <input type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)} />
          </label>
        </div>
        <div className="chips">
          {[3, 5, 10].map((n) => (
            <button key={n} type="button" className="chip" onClick={() => setStartDate(yearsAgo(n))}>
              Last {n}y
            </button>
          ))}
          <button type="button" className="chip" onClick={() => setStartDate("2016-06-01")}>
            Since 2016
          </button>
        </div>
        <label>
          Simulated deposit (USD)
          <input
            type="number"
            min={100}
            step={100}
            value={cash}
            onChange={(e) => setCash(e.target.value)}
          />
        </label>
      </fieldset>

      <fieldset>
        <legend>Risk</legend>
        <label>
          <span className="spread">
            <span>Risk level</span>
            <strong>
              {riskLevel} · {risk.label}
            </strong>
          </span>
          <input
            type="range"
            min={1}
            max={5}
            value={riskLevel}
            onChange={(e) => setRiskLevel(Number(e.target.value))}
          />
        </label>
        <p className="hint">
          {risk.settings.target_volatility
            ? `Scales exposure down when recent volatility exceeds ${(risk.settings.target_volatility * 100).toFixed(0)}%/yr. `
            : "No volatility cap. "}
          Max {(risk.settings.max_position_weight * 100).toFixed(0)}% in any one symbol
          {risk.settings.cash_buffer ? `, ${risk.settings.cash_buffer * 100}% always in cash` : ""}
          . Risk only limits exposure; it never adds leverage.
        </p>
      </fieldset>

      <details>
        <summary>Advanced</summary>
        <label>
          Rebalance
          <select value={rebalance} onChange={(e) => setRebalance(e.target.value as Rebalance)}>
            {REBALANCE.map((r) => (
              <option key={r} value={r}>
                {r}
                {r === strategy.default_rebalance ? " (strategy default)" : ""}
              </option>
            ))}
          </select>
        </label>
        <div className="row">
          <label>
            Fee (bps)
            <input type="number" min={0} step="any" value={feeBps}
              onChange={(e) => setFeeBps(e.target.value)} />
          </label>
          <label>
            Slippage (bps)
            <input type="number" min={0} step="any" value={slipBps}
              onChange={(e) => setSlipBps(e.target.value)} />
          </label>
        </div>
        <label>
          Benchmark
          <input value={benchmark} onChange={(e) => setBenchmark(e.target.value)} />
        </label>
        <label>
          Name (optional)
          <input value={name} maxLength={120} onChange={(e) => setName(e.target.value)} />
        </label>
      </details>

      {formError && <p className="error">{formError}</p>}
      <button type="submit" disabled={busy || !strategy.available}>
        {busy ? "Running…" : "Run backtest"}
      </button>
    </form>
  );
}
