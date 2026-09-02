// Guest ("judge") access.
//
// The site is login-first: proxy.ts funnels every page to /login until you are
// signed in. A guest cookie is the deliberate bypass so hackathon judges can
// enter the dashboard without creating an account.
//
// THIS IS A UX FUNNEL, NOT A SECURITY BOUNDARY. The cookie is set client-side,
// is not httpOnly, and anyone could set it by hand. That is acceptable because
// the map runs on public government reference data, and the things that
// actually need protecting (subscriber/billing data) are guarded server-side
// by JWT verification in the FastAPI layer, not by this cookie. Do not gate
// anything sensitive on guest state.

export const GUEST_COOKIE = "agriflow_guest";

// 12 hours: long enough for a judging session, short enough that a shared
// machine does not stay "logged in as guest" indefinitely.
const GUEST_MAX_AGE = 12 * 60 * 60;

export function enterGuest(): void {
  document.cookie =
    `${GUEST_COOKIE}=1; path=/; max-age=${GUEST_MAX_AGE}; SameSite=Lax; Secure`;
}

export function exitGuest(): void {
  document.cookie = `${GUEST_COOKIE}=; path=/; max-age=0; SameSite=Lax; Secure`;
}

export function isGuest(): boolean {
  if (typeof document === "undefined") return false;
  return document.cookie
    .split("; ")
    .some((c) => c === `${GUEST_COOKIE}=1`);
}
