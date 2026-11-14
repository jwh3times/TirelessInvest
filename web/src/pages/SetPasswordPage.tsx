import { useState, type FormEvent } from "react";
import { PASSWORD_SET_FLAG } from "../lib/auth";
import { supabase } from "../lib/supabase";

// An invited person arrives signed in from the invitation link, with no password yet. They set
// one here before using the app, so later sign-ins work.
export function SetPasswordPage({ email }: { email: string | undefined }) {
  const [password, setPassword] = useState("");
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
    // The flag rides on the same update, so the app stops asking once the password is saved.
    const { error } = await supabase.auth.updateUser({
      password,
      data: { [PASSWORD_SET_FLAG]: true },
    });
    setBusy(false);
    if (error) setError(error.message);
  }

  return (
    <div className="center">
      <form className="card login" onSubmit={submit}>
        <h1>Welcome to TirelessInvest</h1>
        <p className="muted">
          Choose a password for {email ?? "your account"}. You'll use it to sign in from now on.
        </p>
        <label>
          New password
          <input
            type="password"
            autoComplete="new-password"
            required
            minLength={8}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
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
