import { useState, type FormEvent } from "react";
import { supabase } from "../lib/supabase";

// An expired or already-used invitation link lands here with its error in the URL fragment,
// which supabase-js leaves in place. Read it once and clear it, so a reload starts clean.
function takeLinkError(): string | null {
  const params = new URLSearchParams(window.location.hash.slice(1));
  if (!params.has("error") && !params.has("error_code")) return null;
  window.history.replaceState(window.history.state, "", window.location.pathname);
  return params.get("error_code") === "otp_expired"
    ? "That invitation link has expired or was already used. Ask for a new invitation, " +
        "or sign in if you've set a password."
    : (params.get("error_description") ?? "That sign-in link didn't work.");
}

// Sign-in only: accounts come from the owner's Supabase invitations (PRD A8).
export function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(takeLinkError);
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
