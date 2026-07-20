// Server-side route protection.
//
// In Next.js 16 this file is `proxy.ts` (it was `middleware.ts` before 16) and
// the exported function must be named `proxy`.
//
// SCOPE — read this before adding logic here
// ------------------------------------------
// Per the Next.js docs, proxy is for *optimistic* checks, not authorization.
// It refreshes the Supabase session cookie and bounces obviously-signed-out
// visitors away from account pages so they never see a protected shell flash.
// It is NOT what keeps data safe: every protected response is authorized by
// FastAPI verifying the JWT signature (whatsapp_bot/auth.py). A forged or
// tampered cookie gets a visitor past this file and then straight into a 401
// from the API, which is the intended layering.
//
// When Supabase is not configured, this is a no-op so the public demo runs
// unchanged.

import { createServerClient } from "@supabase/ssr";
import { NextResponse, type NextRequest } from "next/server";

// Pages that require a signed-in user.
//
// /forgot-password and /reset-password must NOT be added here. Supabase
// lands a signed-out visitor on /reset-password?code=... to complete a
// password recovery — if that route required a session, this proxy would
// bounce them to /login before the client-side code exchange (see
// app/reset-password/ResetPasswordForm.tsx) ever got a chance to run, and
// the recovery link would be a dead end.
const PROTECTED = ["/account"];

export async function proxy(request: NextRequest) {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const anonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

  // Auth not configured — leave every route open (offline demo posture).
  if (!url || !anonKey) return NextResponse.next();

  let response = NextResponse.next({ request });

  const supabase = createServerClient(url, anonKey, {
    cookies: {
      getAll() {
        return request.cookies.getAll();
      },
      setAll(cookiesToSet) {
        // Write refreshed tokens onto BOTH the request (so any later read in
        // this same pass sees them) and the response (so the browser stores
        // them). Skipping the request copy is the classic cause of a user
        // being logged out one navigation after a token refresh.
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
  // cookie's contents, and refreshes it when it is close to expiry. This call
  // is what keeps a long-open tab from silently falling out of session.
  const { data: { user } } = await supabase.auth.getUser();

  const needsAuth = PROTECTED.some((p) => request.nextUrl.pathname.startsWith(p));
  if (needsAuth && !user) {
    const redirect = request.nextUrl.clone();
    redirect.pathname = "/login";
    // Preserve where they were heading so login can return them there.
    redirect.searchParams.set("next", request.nextUrl.pathname);
    return NextResponse.redirect(redirect);
  }

  return response;
}

export const config = {
  // Skip static assets and image optimization — running auth on every .svg
  // request would add a Supabase round trip to each one.
  matcher: [
    "/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp)$).*)",
  ],
};
