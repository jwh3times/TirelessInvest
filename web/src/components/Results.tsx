import { money, num, pct, riskAdjustedLabel, signedPct } from "../lib/format";
import type { DataWindow, HoldoutSection, Report } from "../lib/types";
import { DrawdownChart, EquityChart, MonthlyReturns } from "./Charts";

function Tile({ label, value, compare, hint }: {
  label: string;
  value: string;
  compare?: string;
  hint?: string;
}) {
  return (
    <div className="tile" title={hint}>
      <div className="tile-label">{label}</div>
      <div className="tile-value">{value}</div>
      {compare && <div className="tile-compare">{compare}</div>}
    </div>
  );
}

/** The headline's second sentence, worded from the API's verdict. */
function VerdictSentence({ report }: { report: Report }) {
  const { verdict: v, summary: s } = report;
  const b = report.benchmark.summary;
  const bench = report.benchmark.symbol;
  const diff = v.cagr_difference;
  return (
    <>
      {" "}
      {diff == null ? (
        <>Against simply holding {bench}</>
      ) : (
        <>
          That is <strong>{pct(Math.abs(diff))} per year {diff >= 0 ? "more" : "less"}</strong> than
          simply holding {bench}
        </>
      )}
      , with {pct(s.volatility)} volatility against {pct(b.volatility)}:{" "}
      <strong>{riskAdjustedLabel(v)}</strong>
      {v.comparable
        ? ` (Sharpe ${num(v.sharpe)} against ${num(v.benchmark_sharpe)}).`
        : ", because a Sharpe ratio is undefined when a return series has no volatility."}
    </>
  );
}

/** The period tested, right under the verdict, so a result from a rising market can't pass as
 * proven. The API words the notice, which names the dates itself; without one, this line states
 * them. */
function DataWindowLine({ dataWindow: w }: { dataWindow: DataWindow }) {
  return w.notice ? (
    <p className="data-window warning" role="note">{w.notice}</p>
  ) : (
    <p className="data-window small muted">Tested {w.first_date} to {w.last_date}.</p>
  );
}

const SECTION_ROWS: { label: string; key: string; format: (v: number | null) => string }[] = [
  { label: "Annual return (CAGR)", key: "cagr", format: (v) => pct(v) },
  { label: "Sharpe ratio", key: "sharpe", format: (v) => num(v) },
  { label: "Worst drawdown", key: "max_drawdown", format: (v) => pct(v) },
  { label: "Volatility", key: "volatility", format: (v) => pct(v) },
];

/** The in-sample and holdout sections side by side, so a strategy that only shines on the period
 * it was tuned on stands out. */
function HoldoutComparison({ inSample, holdout, bench }: {
  inSample: HoldoutSection;
  holdout: HoldoutSection;
  bench: string;
}) {
  const sections = [
    { label: "In-sample", section: inSample },
    { label: "Holdout", section: holdout },
  ];
  return (
    <section className="card">
      <h3>In-sample against holdout</h3>
      <p className="hint">
        One continuous run, split at {holdout.first_date}. The holdout starts from where the
        portfolio stood, not from a fresh deposit. A strategy that only does well in-sample was
        probably fitted to that period.
      </p>
      <table className="table">
        <thead>
          <tr>
            <th />
            {sections.map(({ label, section }) => (
              <th key={label}>
                {label}{" "}
                <span className="muted small">
                  {section.first_date} to {section.last_date}
                </span>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          <tr>
            <td>Against {bench}</td>
            {sections.map(({ label, section }) => (
              <td key={label}><strong>{riskAdjustedLabel(section.verdict)}</strong></td>
            ))}
          </tr>
          {SECTION_ROWS.map((row) => (
            <tr key={row.key}>
              <td>{row.label}</td>
              {sections.map(({ label, section }) => (
                <td key={label} className="num">
                  {row.format(section.summary[row.key])}{" "}
                  <span className="muted small">
                    {bench} {row.format(section.benchmark.summary[row.key])}
                  </span>
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}

export function Results({ report }: { report: Report }) {
  const s = report.summary;
  const b = report.benchmark.summary;
  const bench = report.benchmark.symbol;

  return (
    <div className="results">
      {report.warnings.length > 0 && (
        <div className="warning" role="note">
          <strong>Read before trusting these numbers</strong>
          <ul>{report.warnings.map((w) => <li key={w}>{w}</li>)}</ul>
        </div>
      )}

      <p className="verdict">
        {money(s.start_value)} became <strong>{money(s.end_value)}</strong> ({signedPct(s.total_return)}).
        <VerdictSentence report={report} />
      </p>
      <DataWindowLine dataWindow={report.data_window} />

      <div className="tiles">
        <Tile label="Annual return (CAGR)" value={pct(s.cagr)} compare={`${bench}: ${pct(b.cagr)}`} />
        <Tile label="Worst drawdown" value={pct(s.max_drawdown)}
          compare={`${bench}: ${pct(b.max_drawdown)}`}
          hint="Largest fall from a previous peak" />
        <Tile label="Sharpe ratio" value={num(s.sharpe)} compare={`${bench}: ${num(b.sharpe)}`}
          hint="Return per unit of volatility (risk-free rate 0). Higher is better." />
        <Tile label="Volatility" value={pct(s.volatility)} compare={`${bench}: ${pct(b.volatility)}`}
          hint="Annualized standard deviation of daily returns" />
        <Tile label="Costs paid" value={money((s.total_fees ?? 0) + (s.total_slippage ?? 0))}
          compare={`${s.trade_count} trades`} hint="Fees plus slippage" />
        <Tile label="Turnover" value={`${num(s.annual_turnover, 1)}× / yr`}
          compare={`avg ${pct(s.average_exposure, 0)} invested`}
          hint="Value traded per year relative to average portfolio value" />
        <Tile label="Beta" value={num(s.beta)} compare={`correlation ${num(s.correlation)}`}
          hint={`Sensitivity to ${bench}. 1 = moves with it.`} />
      </div>

      {report.in_sample && report.holdout && (
        <HoldoutComparison inSample={report.in_sample} holdout={report.holdout} bench={bench} />
      )}

      <EquityChart report={report} />
      <DrawdownChart report={report} />
      <MonthlyReturns report={report} />

      <section className="card">
        <h3>Holdings at the end</h3>
        <table className="table">
          <thead>
            <tr><th>Symbol</th><th className="num">Shares</th><th className="num">Value</th>
              <th className="num">Weight</th></tr>
          </thead>
          <tbody>
            {report.final_positions.map((p) => (
              <tr key={p.symbol}>
                <td className="mono">{p.symbol}</td>
                <td className="num">{num(p.shares, 3)}</td>
                <td className="num">{money(p.value)}</td>
                <td className="num">{pct(p.weight)}</td>
              </tr>
            ))}
            <tr>
              <td>Cash</td><td /><td className="num">{money(report.final_cash)}</td>
              <td className="num">{pct(report.final_cash / (s.end_value || 1))}</td>
            </tr>
          </tbody>
        </table>
      </section>

      <details className="card">
        <summary>
          Trades ({report.trades_truncated ? `last ${report.trades.length}` : report.trades.length})
        </summary>
        <div className="scroll-y">
          <table className="table">
            <thead>
              <tr><th>Date</th><th>Side</th><th>Symbol</th><th className="num">Shares</th>
                <th className="num">Price</th><th className="num">Amount</th><th>Note</th></tr>
            </thead>
            <tbody>
              {[...report.trades].reverse().map((t, i) => (
                <tr key={i}>
                  <td>{t.date}</td><td>{t.side}</td><td className="mono">{t.symbol}</td>
                  <td className="num">{num(t.shares, 3)}</td>
                  <td className="num">{money(t.price, true)}</td>
                  <td className="num">{money(t.notional, true)}</td>
                  <td className="muted">{t.reason === "delisted" ? "data ended" : ""}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </div>
  );
}
