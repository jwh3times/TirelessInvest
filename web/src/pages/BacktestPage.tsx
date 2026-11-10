import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { Results } from "../components/Results";
import { api } from "../lib/api";
import { dateTime } from "../lib/format";
import type { BacktestRecord } from "../lib/types";

export function BacktestPage() {
  const { id } = useParams();
  const q = useQuery({
    queryKey: ["backtests", id],
    queryFn: () => api<BacktestRecord>(`/backtests/${id}`),
  });
  if (q.isLoading) return <p className="muted">Loading…</p>;
  if (q.error) return <p className="error">{q.error.message}</p>;
  const { report, name, created_at } = q.data!;
  const c = report.config;
  return (
    <div className="narrow">
      <p><Link to="/backtests">← History</Link></p>
      <h2>{name || c.strategy}</h2>
      <p className="muted">
        {c.strategy} · {c.symbols.join(", ")} · {c.start_date} → {c.end_date} · rebalance{" "}
        {c.rebalance} · risk level {c.risk_level} · run {dateTime(created_at)}
      </p>
      <Results report={report} />
    </div>
  );
}
