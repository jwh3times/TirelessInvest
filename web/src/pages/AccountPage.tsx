import { useMutation } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { send } from "../lib/api";
import { useAuth } from "../lib/auth";
import { supabase } from "../lib/supabase";

export function AccountPage() {
  const { me } = useAuth();
  const [typed, setTyped] = useState("");
  const email = me?.email ?? "";
  // The server checks the confirmation too; matching here only enables the button.
  const confirmed = email !== "" && typed.trim().toLowerCase() === email.toLowerCase();

  const remove = useMutation({
    mutationFn: () => send<void>("/me", "DELETE", { confirm_email: typed }),
    // The account is gone, and Supabase revoked its refresh token with it. Clear the session
    // in this browser only: a global sign-out would ask Supabase about a user that no longer
    // exists.
    onSuccess: () => supabase.auth.signOut({ scope: "local" }),
  });

  function submit(e: FormEvent) {
    e.preventDefault();
    if (confirmed) remove.mutate();
  }

  return (
    <section className="card account">
      <h2>Account</h2>
      <p>
        Signed in as <strong>{email}</strong>.
      </p>

      <h3>Delete your account</h3>
      {me?.is_admin ? (
        <p className="muted">The admin account can't be deleted from the app.</p>
      ) : (
        <form className="form" onSubmit={submit}>
          <p className="muted">
            Deleting your account is immediate and permanent. Your saved backtests, permissions
            and settings are removed, and you're signed out. It can't be undone.
          </p>
          <label>
            Type your email address to confirm
            <input
              type="email"
              autoComplete="off"
              value={typed}
              onChange={(e) => setTyped(e.target.value)}
            />
          </label>
          {remove.error && <p className="error">{remove.error.message}</p>}
          <button type="submit" className="danger" disabled={!confirmed || remove.isPending}>
            {remove.isPending ? "Deleting…" : "Delete my account"}
          </button>
        </form>
      )}
    </section>
  );
}
