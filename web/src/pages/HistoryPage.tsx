import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api, send } from "../lib/api";
import {
  dateTime,
  money,
  pct,
  riskAdjustedLabel,
  riskLevelLabel,
  signedPct,
} from "../lib/format";
import type { BacktestListItem } from "../lib/types";

export function HistoryPage() {
  const queryClient = useQueryClient();
  const q = useQuery({
    queryKey: ["backtests"],
    queryFn: () => api<BacktestListItem[]>("/backtests"),
  });
  const remove = useMutation({
    mutationFn: (id: string) => send<void>(`/backtests/${id}`, "DELETE"),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["backtests"] }),
  });

  if (q.isLoading) return <p className="muted">Loading…</p>;
  if (q.error) return <p className="error">{q.error.message}</p>;
  if (!q.data!.length) return <p className="muted">No backtests yet. Run one from the Lab.</p>;

  return (
    <section className="card">
      <h2>Your backtests</h2>
      <div className="scroll-x">
        <table className="table">
          <thead>
            <tr>
              <th>Name / strategy</th><th>Universe</th><th>Period</th><th>Risk</th>
              <th className="num">Deposit</th><th className="num">Final</th>
              <th className="num">CAGR</th><th className="num">vs bench</th><th>Verdict</th>
              <th className="num">Max DD</th><th>Run</th><th />
            </tr>
          </thead>
          <tbody>
            {q.data!.map((b) => {
              const s = b.summary;
              return (
                <tr key={b.id}>
                  <td><Link to={`/backtests/${b.id}`}>{b.name || b.strategy}</Link></td>
                  <td className="mono small">
                    {b.universe.preset ?? b.universe.symbols?.join(" ")}
                  </td>
                  <td className="small">{b.start_date} → {b.end_date}</td>
                  <td className="small">{riskLevelLabel(b.risk_level, b.legacy_risk_level)}</td>
                  <td className="num">{money(Number(b.starting_cash))}</td>
                  <td className="num">{money(s.end_value)}</td>
                  <td className="num">{pct(s.cagr)}</td>
                  <td className="num">{signedPct(b.verdict.cagr_difference)}</td>
                  <td className="small">{riskAdjustedLabel(b.verdict)}</td>
                  <td className="num">{pct(s.max_drawdown)}</td>
                  <td className="small muted">{dateTime(b.created_at)}</td>
                  <td>
                    <button className="ghost small" disabled={remove.isPending}
                      onClick={() => confirm("Delete this backtest?") && remove.mutate(b.id)}>
                      Delete
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}
