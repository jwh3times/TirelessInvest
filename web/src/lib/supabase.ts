import { createClient } from "@supabase/supabase-js";

const url = import.meta.env.VITE_SUPABASE_URL as string | undefined;
const key = import.meta.env.VITE_SUPABASE_ANON_KEY as string | undefined;

if (!url || !key) {
  throw new Error("Set VITE_SUPABASE_URL and VITE_SUPABASE_ANON_KEY (see web/.env.example)");
}

// Supabase is used for sign-in only. All app data goes through the Python API.
export const supabase = createClient(url, key);
