// Supabase browser client for dashboard auth.
//
// Auth is OPTIONAL by design. The public map is the hackathon demo surface and
// must render on a fresh clone with no Supabase project attached, so this
// module returns null when the environment is not configured and every caller
// treats that as "auth unavailable" rather than throwing. Check isAuthConfigured()
// before offering a sign-in affordance.
//
// WHY @supabase/ssr AND NOT createClient
// --------------------------------------
// createClient() from supabase-js keeps the session in localStorage, which the
// server cannot read — proxy.ts would have no way to see whether a visitor is
// signed in. createBrowserClient() from @supabase/ssr stores the session in
// cookies instead, so the same session is visible to both the browser and the
// server. That is what makes server-side route protection possible at all.

import { createBrowserClient } from "@supabase/ssr";
import type { SupabaseClient } from "@supabase/supabase-js";

const URL = process.env.NEXT_PUBLIC_SUPABASE_URL;
const ANON_KEY = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

export function isAuthConfigured(): boolean {
  return Boolean(URL && ANON_KEY);
}

let client: SupabaseClient | null = null;

export function getSupabase(): SupabaseClient | null {
  if (!isAuthConfigured()) return null;
  // Created lazily and memoized: instantiating per render would drop the
  // in-memory session and log the user out on every navigation.
  if (!client) {
    // Pin the session-cookie flags instead of leaning on library defaults:
    // Lax keeps the session on same-site navigations without riding along on
    // cross-site requests, Secure keeps it off plaintext HTTP. httpOnly is NOT
    // an option here — this browser client must read the session from JS, so
    // the model is short-lived JWTs revalidated server-side (proxy.ts getUser).
    client = createBrowserClient(URL!, ANON_KEY!, {
      cookieOptions: { sameSite: "lax", secure: true },
    });
  }
  return client;
}
