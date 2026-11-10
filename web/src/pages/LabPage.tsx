import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { BacktestForm } from "../components/BacktestForm";
import { Results } from "../components/Results";
import { api, send } from "../lib/api";
import { useAuth } from "../lib/auth";
import type { BacktestRecord, BacktestRequest, Catalog } from "../lib/types";

export function LabPage() {
  const { me } = useAuth();
  const queryClient = useQueryClient();
  const catalog = useQuery({ queryKey: ["catalog"], queryFn: () => api<Catalog>("/catalog") });
  const run = useMutation({
    mutationFn: (req: BacktestRequest) => send<BacktestRecord>("/backtests", "POST", req),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["backtests"] }),
  });

  if (catalog.isLoading) return <p className="muted">Loading…</p>;
  if (catalog.error) return <p className="error">{catalog.error.message}</p>;
  const canRun = me?.permissions.includes("backtest:run");

  return (
    <div className="lab">
      <aside>
        {canRun ? (
          <BacktestForm
            catalog={catalog.data!}
            canUseCustomUniverse={!!me?.permissions.includes("backtest:custom_universe")}
            busy={run.isPending}
            onSubmit={(req) => run.mutate(req)}
          />
        ) : (
          <div className="card">Your account can't run backtests yet. Ask the admin.</div>
        )}
      </aside>
      <section className={run.isPending ? "pending" : undefined}>
        {run.error && <p className="error">{run.error.message}</p>}
        {run.data ? (
          <>
            <p className="muted small">
              Saved · ran in {(run.data.duration_ms / 1000).toFixed(1)}s ·{" "}
              <Link to={`/backtests/${run.data.id}`}>permalink</Link>
            </p>
            <Results report={run.data.report} />
          </>
        ) : (
          !run.isPending && (
            <div className="empty">
              <h2>Can a strategy beat just holding the index?</h2>
              <p className="muted">
                Pick a strategy, a set of investments, a period and a simulated deposit, then run
                it. Every result is compared against buying and holding {""}
                <span className="mono">SPY</span> with the same costs.
              </p>
            </div>
          )
        )}
      </section>
    </div>
  );
}
