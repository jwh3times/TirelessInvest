import { useState, type FormEvent } from "react";
import { supabase } from "../lib/supabase";

// Sign-in only: accounts come from the owner's Supabase invitations (PRD A8).
export function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    const { error } = await supabase.auth.signInWithPassword({ email, password });
    setBusy(false);
    if (error) setError(error.message);
  }

  return (
    <div className="center">
      <form className="card login" onSubmit={submit}>
        <h1>TirelessInvest</h1>
        <p className="muted">
          Test investing strategies on historical prices with simulated money.
        </p>
        <label>
          Email
          <input
            type="email"
            autoComplete="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
        </label>
        <label>
          Password
          <input
            type="password"
            autoComplete="current-password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </label>
        {error && <p className="error">{error}</p>}
        <button type="submit" disabled={busy}>
          Sign in
        </button>
        <p className="muted">TirelessInvest is invite-only for now.</p>
      </form>
    </div>
  );
}
