import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { api, send } from "../lib/api";
import { date, dateTime } from "../lib/format";
import type { AdminUser, AuditEntry, Flag, Permission } from "../lib/types";

type Tab = "users" | "flags" | "audit";

export function AdminPage() {
  const [tab, setTab] = useState<Tab>("users");
  return (
    <div className="narrow">
      <h2>Admin</h2>
      <div className="segmented" role="tablist">
        {(["users", "flags", "audit"] as Tab[]).map((t) => (
          <button key={t} type="button" role="tab" aria-pressed={tab === t}
            aria-selected={tab === t} onClick={() => setTab(t)}>
            {t === "users" ? "Users & permissions" : t === "flags" ? "Feature flags" : "Audit log"}
          </button>
        ))}
      </div>
      {tab === "users" && <UsersPanel />}
      {tab === "flags" && <FlagsPanel />}
      {tab === "audit" && <AuditPanel />}
    </div>
  );
}

function useInvalidate() {
  const qc = useQueryClient();
  return (...keys: string[]) => keys.forEach((k) => qc.invalidateQueries({ queryKey: [k] }));
}

function UsersPanel() {
  const invalidate = useInvalidate();
  const users = useQuery({ queryKey: ["admin-users"], queryFn: () => api<AdminUser[]>("/admin/users") });
  const perms = useQuery({
    queryKey: ["admin-permissions"],
    queryFn: () => api<Permission[]>("/admin/permissions"),
  });
  const save = useMutation({
    mutationFn: ({ userId, permissions }: { userId: string; permissions: string[] }) =>
      send(`/admin/users/${userId}/permissions`, "PUT", { permissions }),
    onSuccess: () => invalidate("admin-users", "admin-audit"),
  });

  if (users.isLoading || perms.isLoading) return <p className="muted">Loading…</p>;
  if (users.error) return <p className="error">{users.error.message}</p>;

  function toggle(user: AdminUser, key: string, on: boolean) {
    const next = on ? [...user.permissions, key] : user.permissions.filter((p) => p !== key);
    save.mutate({ userId: user.id, permissions: next });
  }

  return (
    <section className="card">
      {save.error && <p className="error">{save.error.message}</p>}
      <div className="scroll-x">
        <table className="table">
          <thead>
            <tr>
              <th>User</th><th>Joined</th><th>Last sign-in</th><th className="num">Backtests</th>
              {perms.data!.map((p) => (
                <th key={p.key} title={p.description} className="center-text mono small">{p.key}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {users.data!.map((u) => (
              <tr key={u.id}>
                <td>{u.email} {u.is_admin && <span className="badge">admin</span>}</td>
                <td className="small">{date(u.created_at)}</td>
                <td className="small">{dateTime(u.last_sign_in_at)}</td>
                <td className="num">{u.backtest_count}</td>
                {perms.data!.map((p) => (
                  <td key={p.key} className="center-text">
                    {u.is_admin ? (
                      <span className="muted small" title="The admin holds every permission">all</span>
                    ) : (
                      <input type="checkbox" aria-label={`${p.key} for ${u.email}`}
                        checked={u.permissions.includes(p.key)} disabled={save.isPending}
                        onChange={(e) => toggle(u, p.key, e.target.checked)} />
                    )}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="hint">
        Unchecking every permission effectively suspends a user. New sign-ups get the defaults:{" "}
        {perms.data!.filter((p) => p.granted_by_default).map((p) => p.key).join(", ") || "none"}.
      </p>
    </section>
  );
}

function FlagsPanel() {
  const invalidate = useInvalidate();
  const flags = useQuery({ queryKey: ["admin-flags"], queryFn: () => api<Flag[]>("/admin/flags") });
  const users = useQuery({ queryKey: ["admin-users"], queryFn: () => api<AdminUser[]>("/admin/users") });
  const done = () => invalidate("admin-flags", "admin-audit", "me", "catalog");
  const update = useMutation({
    mutationFn: ({ key, enabled }: { key: string; enabled: boolean }) =>
      send(`/admin/flags/${encodeURIComponent(key)}`, "PATCH", { enabled }),
    onSuccess: done,
  });
  const remove = useMutation({
    mutationFn: (key: string) => send(`/admin/flags/${encodeURIComponent(key)}`, "DELETE"),
    onSuccess: done,
  });
  const setOverride = useMutation({
    mutationFn: ({ key, userId, enabled }: { key: string; userId: string; enabled: boolean | null }) =>
      enabled === null
        ? send(`/admin/flags/${encodeURIComponent(key)}/overrides/${userId}`, "DELETE")
        : send(`/admin/flags/${encodeURIComponent(key)}/overrides/${userId}`, "PUT", { enabled }),
    onSuccess: done,
  });
  const create = useMutation({
    mutationFn: (body: { key: string; description: string }) => send("/admin/flags", "POST", body),
    onSuccess: done,
  });
  const [newKey, setNewKey] = useState("");
  const [newDesc, setNewDesc] = useState("");

  if (flags.isLoading) return <p className="muted">Loading…</p>;
  if (flags.error) return <p className="error">{flags.error.message}</p>;
  const error = update.error ?? remove.error ?? setOverride.error ?? create.error;

  function submitNew(e: FormEvent) {
    e.preventDefault();
    create.mutate({ key: newKey.trim(), description: newDesc.trim() },
      { onSuccess: () => { setNewKey(""); setNewDesc(""); } });
  }

  return (
    <>
      {error && <p className="error">{error.message}</p>}
      {flags.data!.map((f) => (
        <section className="card flag" key={f.key}>
          <div className="spread">
            <div>
              <div className="mono strong">{f.key}</div>
              <div className="muted small">{f.description}</div>
            </div>
            <div className="toolbar">
              <label className="switch">
                <input type="checkbox" checked={f.enabled}
                  onChange={(e) => update.mutate({ key: f.key, enabled: e.target.checked })} />
                {f.enabled ? "On for everyone" : "Off for everyone"}
              </label>
              <button className="ghost small"
                onClick={() => confirm(`Delete flag ${f.key}? Code that checks it will treat it as off.`)
                  && remove.mutate(f.key)}>
                Delete
              </button>
            </div>
          </div>
          <OverrideEditor flag={f} users={users.data ?? []}
            onSet={(userId, enabled) => setOverride.mutate({ key: f.key, userId, enabled })} />
        </section>
      ))}
      <form className="card row" onSubmit={submitNew}>
        <label>
          New flag key
          <input value={newKey} placeholder="strategy.my_idea" required
            onChange={(e) => setNewKey(e.target.value)} />
        </label>
        <label className="grow">
          Description
          <input value={newDesc} required onChange={(e) => setNewDesc(e.target.value)} />
        </label>
        <button type="submit" disabled={create.isPending}>Create</button>
      </form>
      <p className="hint">
        A flag only does something once code checks it. Strategies declare their flag in the API
        (e.g. <span className="mono">strategy.mean_reversion</span>).
      </p>
    </>
  );
}

function OverrideEditor({ flag, users, onSet }: {
  flag: Flag;
  users: AdminUser[];
  onSet: (userId: string, enabled: boolean | null) => void;
}) {
  const [userId, setUserId] = useState("");
  const candidates = users.filter((u) => !flag.overrides.some((o) => o.user_id === u.id));
  return (
    <div className="overrides">
      {flag.overrides.length > 0 && (
        <ul>
          {flag.overrides.map((o) => (
            <li key={o.user_id}>
              <span>{o.email}</span>
              <strong>{o.enabled ? "on" : "off"}</strong>
              <button className="link small" onClick={() => onSet(o.user_id, !o.enabled)}>flip</button>
              <button className="link small" onClick={() => onSet(o.user_id, null)}>remove</button>
            </li>
          ))}
        </ul>
      )}
      <div className="row small">
        <select value={userId} onChange={(e) => setUserId(e.target.value)}
          aria-label="User to override">
          <option value="">Override for a user…</option>
          {candidates.map((u) => <option key={u.id} value={u.id}>{u.email}</option>)}
        </select>
        <button className="ghost small" disabled={!userId}
          onClick={() => { onSet(userId, !flag.enabled); setUserId(""); }}>
          Turn {flag.enabled ? "off" : "on"} for them
        </button>
      </div>
    </div>
  );
}

function AuditPanel() {
  const q = useQuery({ queryKey: ["admin-audit"], queryFn: () => api<AuditEntry[]>("/admin/audit") });
  if (q.isLoading) return <p className="muted">Loading…</p>;
  if (q.error) return <p className="error">{q.error.message}</p>;
  return (
    <section className="card scroll-x">
      <table className="table">
        <thead><tr><th>When</th><th>Who</th><th>Action</th><th>Target</th><th>Detail</th></tr></thead>
        <tbody>
          {q.data!.map((a) => (
            <tr key={a.id}>
              <td className="small">{dateTime(a.created_at)}</td>
              <td className="small">{a.actor_email}</td>
              <td className="mono small">{a.action}</td>
              <td className="mono small">{a.target}</td>
              <td className="mono small">{JSON.stringify(a.detail)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
