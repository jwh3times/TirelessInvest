import type { Session } from "@supabase/supabase-js";
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
