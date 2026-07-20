// Development-only login (email/password = admin/admin by default).
//
// ⚠ THIS IS A DEV CONVENIENCE, NOT REAL AUTH. It exists so the signed-in
// experience can be tested before a Supabase project is wired up. It accepts a
// hardcoded credential and issues a client-side cookie — it does NOT verify
// anything against a server.
//
// PRODUCTION SAFETY
// -----------------
// The whole path is gated on NEXT_PUBLIC_DEV_LOGIN === "true", which is set
// ONLY in the gitignored .env.local. It is deliberately absent from
// .env.example and must never be set in the Vercel production environment.
// NEXT_PUBLIC_* values are inlined at build time, so a production build made
// without the flag has this code permanently disabled — DEV_LOGIN_ENABLED is a
// compile-time false and the dead branch cannot be reached.
//
// Even if someone did enable it in production, the blast radius is small: the
// dev cookie only gets a visitor past the page-routing funnel to the map, which
// serves public government data. It does NOT authenticate against the backend
// API — token-gated endpoints (subscriber/billing) verify a real Supabase JWT,
// which this cookie is not. So a leaked dev login cannot read anyone's data.

export const DEV_LOGIN_ENABLED = process.env.NEXT_PUBLIC_DEV_LOGIN === "true";
export const DEV_EMAIL = process.env.NEXT_PUBLIC_DEV_EMAIL ?? "admin";
export const DEV_PASSWORD = process.env.NEXT_PUBLIC_DEV_PASSWORD ?? "admin";

export const DEV_COOKIE = "agriflow_dev"; // keep in sync with proxy.ts

const DEV_MAX_AGE = 12 * 60 * 60; // 12h, matches the guest session

export function credentialsMatch(email: string, password: string): boolean {
  return DEV_LOGIN_ENABLED && email === DEV_EMAIL && password === DEV_PASSWORD;
}

export function enterDev(email: string): void {
  document.cookie =
    `${DEV_COOKIE}=${encodeURIComponent(email)}; path=/; max-age=${DEV_MAX_AGE}; SameSite=Lax`;
}

export function exitDev(): void {
  document.cookie = `${DEV_COOKIE}=; path=/; max-age=0; SameSite=Lax`;
}

export function currentDevUser(): string | null {
  if (typeof document === "undefined" || !DEV_LOGIN_ENABLED) return null;
  const hit = document.cookie
    .split("; ")
    .find((c) => c.startsWith(`${DEV_COOKIE}=`));
  return hit ? decodeURIComponent(hit.slice(DEV_COOKIE.length + 1)) : null;
}
