const money0 = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  maximumFractionDigits: 0,
});
const money2 = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" });

export const money = (v: number | null | undefined, cents = false) =>
  v == null ? "–" : (cents ? money2 : money0).format(v);

export const pct = (v: number | null | undefined, digits = 1) =>
  v == null ? "–" : `${(v * 100).toFixed(digits)}%`;

export const signedPct = (v: number | null | undefined, digits = 1) =>
  v == null ? "–" : `${v > 0 ? "+" : ""}${(v * 100).toFixed(digits)}%`;

export const num = (v: number | null | undefined, digits = 2) =>
  v == null ? "–" : v.toFixed(digits);

export const date = (iso: string | null | undefined) =>
  iso ? new Date(iso).toLocaleDateString("en-US", { dateStyle: "medium" }) : "–";

export const dateTime = (iso: string | null | undefined) =>
  iso ? new Date(iso).toLocaleString("en-US", { dateStyle: "medium", timeStyle: "short" }) : "–";
