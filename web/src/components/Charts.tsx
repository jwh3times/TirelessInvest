import { useMemo, useState } from "react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { money, pct } from "../lib/format";
import type { Report } from "../lib/types";

interface SeriesDef {
  key: "strategy" | "benchmark";
  name: string;
  color: string;
}

type Point = { date: string; strategy: number | null; benchmark: number | null };

const compactMoney = (v: number) =>
  new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    notation: "compact",
    maximumFractionDigits: 1,
  }).format(v);

const year = (d: string) => d.slice(0, 4);
const axisTick = { fill: "var(--text-secondary)", fontSize: 12 };

function Legend({ series }: { series: SeriesDef[] }) {
  return (
    <div className="legend">
      {series.map((s) => (
        <span key={s.key}>
          <svg width="16" height="8" aria-hidden>
            <line x1="0" y1="4" x2="16" y2="4" stroke={s.color} strokeWidth="2" strokeLinecap="round" />
          </svg>
          {s.name}
        </span>
      ))}
    </div>
  );
}

function ChartTooltip({
  active,
  payload,
  label,
  series,
  format,
}: {
  active?: boolean;
  payload?: { dataKey: string; value: number | null }[];
  label?: string;
  series: SeriesDef[];
  format: (v: number) => string;
}) {
  if (!active || !payload?.length) return null;
  return (
    <div className="chart-tooltip">
      <div className="muted small">{label}</div>
      {series.map((s) => {
        const value = payload.find((p) => p.dataKey === s.key)?.value;
        return (
          <div key={s.key} className="tooltip-row">
            <svg width="12" height="8" aria-hidden>
              <line x1="0" y1="4" x2="12" y2="4" stroke={s.color} strokeWidth="2" />
            </svg>
            <strong>{value == null ? "–" : format(value)}</strong>
            <span className="muted">{s.name}</span>
          </div>
        );
      })}
    </div>
  );
}

/** Direct label at the last point of a line. */
function endLabel(name: string, lastIndex: number) {
  return (props: { x?: number | string; y?: number | string; index?: number }) => {
    if (props.index !== lastIndex || props.x == null || props.y == null) return null;
    return (
      <text x={Number(props.x) + 6} y={Number(props.y)} dy={4} fontSize={12}
        fill="var(--text-secondary)">
        {name}
      </text>
    );
  };
}

function TimeSeriesChart({
  data,
  series,
  format,
  tickFormat,
  log = false,
  height = 300,
  zeroLine = false,
  directLabels = true,
}: {
  data: Point[];
  series: SeriesDef[];
  format: (v: number) => string;
  tickFormat: (v: number) => string;
  log?: boolean;
  height?: number;
  zeroLine?: boolean;
  directLabels?: boolean;
}) {
  const last = data.length - 1;
  // One tick per year (first trading day), thinned to at most ~10 so labels never repeat.
  const ticks = useMemo(() => {
    const firsts = data.filter((p, i) => i === 0 || year(data[i - 1].date) !== year(p.date));
    const step = Math.ceil(firsts.length / 10);
    return firsts.filter((_, i) => i % step === 0).map((p) => p.date);
  }, [data]);
  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={data} margin={{ top: 8, right: 80, bottom: 0, left: 0 }}>
        <CartesianGrid vertical={false} stroke="var(--grid)" />
        <XAxis dataKey="date" ticks={ticks} interval={0} tickFormatter={year} tick={axisTick}
          stroke="var(--axis)" tickLine={false} />
        <YAxis scale={log ? "log" : "linear"} domain={["auto", "auto"]} tickFormatter={tickFormat}
          tick={axisTick} stroke="var(--axis)" tickLine={false} axisLine={false} width={64}
          allowDataOverflow={false} />
        {zeroLine && <ReferenceLine y={0} stroke="var(--axis)" />}
        <Tooltip
          content={<ChartTooltip series={series} format={format} />}
          cursor={{ stroke: "var(--text-muted)", strokeWidth: 1 }}
          isAnimationActive={false}
        />
        {series.map((s) => (
          <Line key={s.key} dataKey={s.key} name={s.name} stroke={s.color} strokeWidth={2}
            dot={false} activeDot={{ r: 4, strokeWidth: 2, stroke: "var(--surface)" }}
            isAnimationActive={false} connectNulls label={directLabels ? endLabel(s.name, last) : undefined} />
        ))}
      </LineChart>
    </ResponsiveContainer>
  );
}

function seriesDefs(report: Report): SeriesDef[] {
  return [
    { key: "strategy", name: "Strategy", color: "var(--series-1)" },
    { key: "benchmark", name: report.benchmark.symbol, color: "var(--series-2)" },
  ];
}

export function EquityChart({ report }: { report: Report }) {
  const [log, setLog] = useState(false);
  const [view, setView] = useState<"chart" | "table">("chart");
  const series = seriesDefs(report);
  const data = useMemo<Point[]>(
    () =>
      report.series.dates.map((date, i) => ({
        date,
        strategy: report.series.equity[i],
        benchmark: report.series.benchmark[i],
      })),
    [report],
  );
  // Year-end values for the table view.
  const yearEnds = useMemo(() => {
    const rows: Point[] = [];
    data.forEach((p, i) => {
      if (i === data.length - 1 || year(data[i + 1].date) !== year(p.date)) rows.push(p);
    });
    return rows;
  }, [data]);

  return (
    <section className="card">
      <div className="card-head">
        <h3>Portfolio value</h3>
        <div className="toolbar">
          {view === "chart" && (
            <label className="check small">
              <input type="checkbox" checked={log} onChange={(e) => setLog(e.target.checked)} />
              Log scale
            </label>
          )}
          <div className="segmented small">
            <button type="button" aria-pressed={view === "chart"} onClick={() => setView("chart")}>
              Chart
            </button>
            <button type="button" aria-pressed={view === "table"} onClick={() => setView("table")}>
              Table
            </button>
          </div>
        </div>
      </div>
      {view === "chart" ? (
        <>
          <Legend series={series} />
          <TimeSeriesChart data={data} series={series} log={log}
            format={(v) => money(v)} tickFormat={compactMoney} />
        </>
      ) : (
        <table className="table">
          <thead>
            <tr><th>Year end</th><th className="num">Strategy</th>
              <th className="num">{report.benchmark.symbol}</th></tr>
          </thead>
          <tbody>
            {yearEnds.map((p) => (
              <tr key={p.date}>
                <td>{p.date}</td>
                <td className="num">{money(p.strategy)}</td>
                <td className="num">{money(p.benchmark)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}

export function DrawdownChart({ report }: { report: Report }) {
  const series = seriesDefs(report);
  const data = useMemo<Point[]>(
    () =>
      report.series.dates.map((date, i) => ({
        date,
        strategy: report.series.drawdown[i],
        benchmark: report.series.benchmark_drawdown[i],
      })),
    [report],
  );
  return (
    <section className="card">
      <div className="card-head">
        <h3>Drawdown</h3>
        <span className="muted small">Fall from the previous peak</span>
      </div>
      <Legend series={series} />
      <TimeSeriesChart data={data} series={series} height={200} zeroLine directLabels={false}
        format={(v) => pct(v)} tickFormat={(v) => pct(v, 0)} />
    </section>
  );
}

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

/** Diverging tint: blue for gains, red for losses, neutral at zero. Text stays in ink colors. */
function tint(r: number): string {
  const strength = Math.min(Math.abs(r) / 0.08, 1) * 45;
  const hue = r >= 0 ? "var(--diverge-pos)" : "var(--diverge-neg)";
  return `color-mix(in srgb, ${hue} ${strength.toFixed(0)}%, var(--diverge-mid))`;
}

export function MonthlyReturns({ report }: { report: Report }) {
  const byYear = useMemo(() => {
    const map = new Map<string, (number | null)[]>();
    for (const { month, return: r } of report.monthly_returns) {
      const [y, m] = month.split("-");
      if (!map.has(y)) map.set(y, Array(12).fill(null));
      map.get(y)![Number(m) - 1] = r;
    }
    return [...map.entries()].map(([y, months]) => ({
      year: y,
      months,
      total: months.reduce<number>((acc, r) => (r == null ? acc : acc * (1 + r)), 1) - 1,
    }));
  }, [report]);

  return (
    <section className="card">
      <div className="card-head">
        <h3>Monthly returns</h3>
        <span className="muted small">Blue = gain, red = loss</span>
      </div>
      <div className="scroll-x">
        <table className="table monthly">
          <thead>
            <tr>
              <th>Year</th>
              {MONTHS.map((m) => <th key={m} className="num">{m}</th>)}
              <th className="num">Year</th>
            </tr>
          </thead>
          <tbody>
            {byYear.map((row) => (
              <tr key={row.year}>
                <td>{row.year}</td>
                {row.months.map((r, i) => (
                  <td key={i} className="num" style={r == null ? undefined : { background: tint(r) }}
                    title={r == null ? undefined : `${MONTHS[i]} ${row.year}: ${pct(r, 2)}`}>
                    {r == null ? "" : pct(r)}
                  </td>
                ))}
                <td className="num strong" style={{ background: tint(row.total / 4) }}>
                  {pct(row.total)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
