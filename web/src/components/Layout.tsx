import { NavLink, Outlet } from "react-router-dom";
import { useAuth } from "../lib/auth";
import { releaseLabel } from "../lib/release";
import { supabase } from "../lib/supabase";

export function Layout() {
  const { me } = useAuth();
  return (
    <div className="app">
      <header className="topbar">
        <span className="brand">TirelessInvest</span>
        <nav>
          <NavLink to="/" end>
            Lab
          </NavLink>
          <NavLink to="/backtests">History</NavLink>
          {/* Hiding the link is cosmetic; the API enforces admin on every /admin call. */}
          {me?.is_admin && <NavLink to="/admin">Admin</NavLink>}
        </nav>
        <div className="topbar-user">
          <span className="muted">{me?.email}</span>
          <button className="ghost" onClick={() => supabase.auth.signOut()}>
            Sign out
          </button>
        </div>
      </header>
      <main>
        <Outlet />
      </main>
      <footer className="muted small">
        Simulated money only. Past performance in a backtest does not predict future results.
        <div className="release">{releaseLabel}</div>
      </footer>
    </div>
  );
}
