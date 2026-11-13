import { money, num, pct, riskAdjustedLabel, signedPct } from "../lib/format";
import type { Report } from "../lib/types";
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
