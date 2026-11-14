import type { Session, User } from "@supabase/supabase-js";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { api } from "./api";
import { supabase } from "./supabase";
import type { Me } from "./types";

interface AuthState {
  session: Session | null;
  loading: boolean;
  me: Me | undefined;
  meError: Error | null;
}

const AuthContext = createContext<AuthState>({
  session: null,
  loading: true,
  me: undefined,
  meError: null,
});

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(null);
  const [loading, setLoading] = useState(true);
  const queryClient = useQueryClient();

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => {
      setSession(data.session);
      setLoading(false);
    });
    const { data } = supabase.auth.onAuthStateChange((_event, next) => {
      setSession(next);
      queryClient.invalidateQueries();
    });
    return () => data.subscription.unsubscribe();
  }, [queryClient]);

  const meQuery = useQuery({
    queryKey: ["me", session?.user.id],
    queryFn: () => api<Me>("/me"),
    enabled: !!session,
  });

  return (
    <AuthContext.Provider
      value={{ session, loading, me: meQuery.data, meError: meQuery.error }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);

// The user_metadata key the set-password step writes along with the password.
export const PASSWORD_SET_FLAG = "password_set";

// An invited user arrives from the invitation link signed in but with no password. Supabase
// doesn't say whether a user has a password, and supabase-js clears the link's `type=invite`
// from the URL as it reads it, so the lasting signal is `invited_at` without the flag. It gates
// only the user's own screen, never a permission, so a user editing their metadata gains nothing.
export function needsPassword(user: User): boolean {
  return !!user.invited_at && user.user_metadata?.[PASSWORD_SET_FLAG] !== true;
}
