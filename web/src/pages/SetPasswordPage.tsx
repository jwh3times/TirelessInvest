import { useState, type FormEvent } from "react";
import { setPassword, useAuth } from "../lib/auth";
import { supabase } from "../lib/supabase";

// An invited person arrives signed in from the invitation link, with no password yet. They set
// one here before using the app, so later sign-ins work.
export function SetPasswordPage() {
  const { session } = useAuth();
  const [password, setPasswordValue] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (password !== confirm) {
      setError("The passwords don't match.");
      return;
    }
    setBusy(true);
    setError(null);
    const message = await setPassword(password);
    setBusy(false);
    setError(message);
  }

  return (
    <div className="center">
      <form className="card login" onSubmit={submit}>
        <h1>Welcome to TirelessInvest</h1>
        <p className="muted">
          Choose a password for {session?.user.email ?? "your account"}. You'll use it to sign in
          from now on.
        </p>
        <label>
          New password
          <input
            type="password"
            autoComplete="new-password"
            required
            minLength={8}
            value={password}
            onChange={(e) => setPasswordValue(e.target.value)}
          />
        </label>
        <label>
          Confirm password
          <input
            type="password"
            autoComplete="new-password"
            required
            minLength={8}
            value={confirm}
            onChange={(e) => setConfirm(e.target.value)}
          />
        </label>
        {error && <p className="error">{error}</p>}
        <button type="submit" disabled={busy}>
          Set password and continue
        </button>
        <button type="button" className="link" onClick={() => supabase.auth.signOut()}>
          Not you? Sign out
        </button>
      </form>
    </div>
  );
}
