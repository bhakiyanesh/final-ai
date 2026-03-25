import { createClient } from "@supabase/supabase-js";

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

if (!supabaseUrl || !supabaseAnonKey) {
  // In dev, this keeps the app bootable even if env vars aren't set yet.
  // Realtime + auth will work once the env vars are configured.
  // eslint-disable-next-line no-console
  console.warn("Missing NEXT_PUBLIC_SUPABASE_URL or NEXT_PUBLIC_SUPABASE_ANON_KEY");
}

export const supabase = createClient(
  supabaseUrl ?? "http://localhost:54321",
  supabaseAnonKey ?? "anon",
  {
    auth: {
      persistSession: true,
      autoRefreshToken: true,
      detectSessionInUrl: true,
    },
  },
);

