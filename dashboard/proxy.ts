// Server-side route protection — login-first.
//
// In Next.js 16 this file is `proxy.ts` (renamed from `middleware.ts` in 16)
// and the exported function must be named `proxy`.
//
// GATE MODEL
// ----------
// Every page requires a signed-in user OR a guest cookie. Unauthenticated
// visitors are funneled to /login. The auth pages themselves (/login,
// /forgot-password, /reset-password) stay reachable while signed out, otherwise
// you could never get in.
//
// The guest cookie is the judge bypass (see app/lib/guest.ts). It is a UX
// funnel, not security: this proxy decides which PAGE renders, while the data
// itself is authorized separately by JWT verification in the FastAPI backend
// (whatsapp_bot/auth.py). A forged cookie gets someone to the map, which shows
// public government data anyway, and no further.
//
// Per the Next.js docs, proxy is for optimistic checks, not authorization —
// which is exactly this split: routing funnel here, real enforcement at the
// data layer.

import { createServerClient } from "@supabase/ssr";
import { NextResponse, type NextRequest } from "next/server";

const GUEST_COOKIE = "agriflow_guest"; // keep in sync with app/lib/guest.ts
const DEV_COOKIE = "agriflow_dev"; // keep in sync with app/lib/devauth.ts

// Pages that must stay reachable while signed out.
const PUBLIC_PREFIXES = ["/login", "/forgot-password", "/reset-password"];

export async function proxy(request: NextRequest) {
  const path = request.nextUrl.pathname;

  // The public landing. Exact match only: "/" cannot go into PUBLIC_PREFIXES
  // because every path startsWith "/", which would un-gate the whole site.
  // Short-circuited before the Supabase call so the landing costs no auth
  // round-trip.
  if (path === "/") return NextResponse.next({ request });

  const isPublic = PUBLIC_PREFIXES.some((p) => path.startsWith(p));
  const hasGuest = request.cookies.get(GUEST_COOKIE)?.value === "1";
  // Dev-login cookie (see app/lib/devauth.ts). Only honoured when dev login is
  // explicitly enabled, so production ignores it even if someone sets it by
  // hand — the guest cookie is the only intended bypass there. Like guest, it
  // is a page-routing bypass only and never satisfies the backend's JWT check.
  const hasDev =
    process.env.NEXT_PUBLIC_DEV_LOGIN === "true" &&
    Boolean(request.cookies.get(DEV_COOKIE)?.value);

  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const anonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

  let response = NextResponse.next({ request });
  let user = null;

  // Resolve the real session when Supabase is configured. Wrapped in try/catch
  // because a misconfigured or unreachable Supabase URL (e.g. placeholder creds
  // in local preview) would otherwise throw and 500 every page. On any failure
  // we treat the visitor as signed out and let the guest cookie be the way in.
  if (url && anonKey) {
    try {
      const supabase = createServerClient(url, anonKey, {
        cookies: {
          getAll() {
            return request.cookies.getAll();
          },
          setAll(cookiesToSet) {
            // Write refreshed tokens onto both the request (so any later read
            // this pass sees them) and the response (so the browser stores
            // them). Skipping the request copy logs the user out one navigation
            // after a token refresh.
            cookiesToSet.forEach(({ name, value }) =>
              request.cookies.set(name, value),
            );
            response = NextResponse.next({ request });
            cookiesToSet.forEach(({ name, value, options }) =>
              response.cookies.set(name, value, options),
            );
          },
        },
      });
      // getUser() revalidates the token with Supabase rather than trusting the
      // cookie contents, and refreshes it near expiry.
      user = (await supabase.auth.getUser()).data.user;
    } catch {
      user = null;
    }
  }

  const authed = Boolean(user) || hasGuest || hasDev;

  // A genuinely signed-in user has no reason to see the login page.
  // Guests are NOT redirected away from /login, so they can upgrade to a real
  // account whenever they want.
  if (path.startsWith("/login") && user) {
    return NextResponse.redirect(new URL("/dashboard", request.url));
  }

  // Auth pages are always reachable.
  if (isPublic) return response;

  // Everything else is gated.
  if (!authed) {
    const redirect = request.nextUrl.clone();
    redirect.pathname = "/login";
    // Preserve the destination so login can return them there. LoginForm only
    // honours relative paths, so this cannot become an open redirect.
    redirect.searchParams.set("next", path);
    return NextResponse.redirect(redirect);
  }

  return response;
}

export const config = {
  // Skip static assets and image optimization — gating a .svg on a Supabase
  // round trip would add one to every asset request.
  matcher: [
    "/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp)$).*)",
  ],
};
