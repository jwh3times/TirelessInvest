export type Rebalance = "never" | "daily" | "weekly" | "monthly" | "quarterly";

export interface Me {
  id: string;
  email: string | null;
  is_admin: boolean;
  permissions: string[];
  flags: Record<string, boolean>;
}

export interface JsonSchemaProp {
  type?: string;
  anyOf?: JsonSchemaProp[];
  title?: string;
  description?: string;
  default?: unknown;
  minimum?: number;
  maximum?: number;
}

export interface StrategyInfo {
  key: string;
  label: string;
  description: string;
  default_rebalance: Rebalance;
  params_schema: { properties?: Record<string, JsonSchemaProp> };
  available: boolean;
}

export interface UniverseInfo {
  key: string;
  label: string;
  description: string;
  symbols: string[];
  survivorship_biased: boolean;
}

export interface RiskSettings {
  max_position_weight: number;
  target_volatility: number | null;
  vol_lookback_days: number;
  cash_buffer: number;
}

export interface Catalog {
  strategies: StrategyInfo[];
  universes: UniverseInfo[];
  risk_levels: { level: number; label: string; settings: RiskSettings }[];
  default_costs: { fee_bps: number; slippage_bps: number };
}

export interface BacktestRequest {
  name?: string | null;
  strategy: string;
  params: Record<string, unknown>;
  universe: { preset: string } | { symbols: string[] };
  start_date: string;
  end_date: string;
  starting_cash: number;
  rebalance?: Rebalance | null;
  risk_level: number;
  /** Set on backtests saved on the old 1–5 dial; their explicit `risk` holds that level's settings. */
  legacy_risk_level?: number | null;
  costs: { fee_bps: number; slippage_bps: number };
  benchmark: string;
}

export type Metrics = Record<string, number | null>;

/** The API's risk-adjusted judgement of a strategy against its benchmark, over the same dates. */
export interface Verdict {
  /** False when a Sharpe ratio is undefined, e.g. no volatility over a very short period. */
  comparable: boolean;
  /** Higher Sharpe than the benchmark's; null when no comparison is possible. */
  better_risk_adjusted: boolean | null;
  sharpe: number | null;
  benchmark_sharpe: number | null;
  /** Strategy CAGR minus benchmark CAGR, as context for the verdict. */
  cagr_difference: number | null;
}

export interface Report {
  config: BacktestRequest & { rebalance: Rebalance; risk: RiskSettings; symbols: string[] };
  summary: Metrics;
  benchmark: { symbol: string; summary: Metrics };
  verdict: Verdict;
  series: {
    dates: string[];
    equity: number[];
    benchmark: (number | null)[];
    drawdown: number[];
    benchmark_drawdown: (number | null)[];
    exposure: number[];
  };
  monthly_returns: { month: string; return: number }[];
  trades: {
    date: string;
    symbol: string;
    side: "buy" | "sell";
    shares: number;
    price: number;
    notional: number;
    fee: number;
    reason: string;
  }[];
  trades_truncated: boolean;
  final_positions: { symbol: string; shares: number; value: number; weight: number }[];
  final_cash: number;
  warnings: string[];
}

export interface BacktestRecord {
  id: string;
  name: string | null;
  created_at: string;
  duration_ms: number;
  report: Report;
}

export interface BacktestListItem {
  id: string;
  name: string | null;
  strategy: string;
  created_at: string;
  duration_ms: number;
  universe: { preset?: string; symbols?: string[] };
  start_date: string;
  end_date: string;
  starting_cash: string;
  risk_level: number;
  legacy_risk_level: number | null;
  summary: Metrics;
  verdict: Verdict;
}

export interface AdminUser {
  id: string;
  email: string;
  created_at: string;
  last_sign_in_at: string | null;
  is_admin: boolean;
  permissions: string[];
  backtest_count: number;
}

export interface Permission {
  key: string;
  description: string;
  granted_by_default: boolean;
}

export interface Flag {
  key: string;
  description: string;
  enabled: boolean;
  updated_at: string;
  overrides: { user_id: string; email: string; enabled: boolean }[];
}

export interface AuditEntry {
  id: number;
  action: string;
  target: string;
  detail: Record<string, unknown>;
  created_at: string;
  actor_email: string | null;
}
