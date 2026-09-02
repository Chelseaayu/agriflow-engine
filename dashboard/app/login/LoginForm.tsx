"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useAuth } from "../lib/auth";
import { enterGuest } from "../lib/guest";
import { DEV_LOGIN_ENABLED, DEV_EMAIL, DEV_PASSWORD } from "../lib/devauth";

export default function LoginForm() {
  const { signIn, signInWithOAuth, configured, user } = useAuth();
  const router = useRouter();
  const searchParams = useSearchParams();

  // proxy.ts appends ?next= when it funnels someone off a gated page.
  // Only relative paths are honoured — accepting an absolute URL here would
  // make this an open redirect an attacker could point at their own site.
  // Default to /dashboard, the app's home; "/" is the public landing now.
  const rawNext = searchParams.get("next");
  const nextPath =
    rawNext && rawNext.startsWith("/") && !rawNext.startsWith("//")
      ? rawNext
      : "/dashboard";

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  // Send an already-signed-in visitor away from the login page. This runs in an
  // effect, not in render: calling router.replace() during render triggers
  // React's "Cannot update a component (Router) while rendering a different
  // component (LoginForm)" warning (a hard error under stricter React modes).
  useEffect(() => {
    if (user) router.replace(nextPath);
  }, [user, nextPath, router]);

  if (user) {
    // Redirect is in flight (handled by the effect above); render nothing.
    return null;
  }

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    const { error } = await signIn(email, password);
    setBusy(false);

    if (error) {
      setError(error);
      return;
    }
    // Full navigation (not router.push) so the proxy re-runs and sees the
    // freshly-set session/dev cookie, letting the destination through.
    window.location.assign(nextPath);
  }

  async function onGoogle() {
    setError(null);
    setBusy(true);
    // On success the browser leaves for Google's consent screen and comes back
    // to nextPath with a session, so only the error path ever runs after this.
    const { error } = await signInWithOAuth("google", nextPath);
    setBusy(false);
    if (error) setError(error);
  }

  function enterAsGuest() {
    enterGuest();
    // Full navigation (not router.push) so the proxy re-runs and now sees the
    // guest cookie, letting the destination page through.
    window.location.assign(nextPath);
  }

  return (
    <main className="flex-1 flex items-center justify-center p-6 bg-slate-50">
      <div className="w-full max-w-sm">
        <h1 className="text-2xl font-semibold text-slate-900">
          Masuk ke AgriFlow
        </h1>
        <p className="mt-1 text-sm text-slate-500">
          Untuk pelanggan dinas, TPID, dan mitra data.
        </p>

        {DEV_LOGIN_ENABLED && (
          <p className="mt-4 rounded-lg bg-sky-50 border border-sky-200 p-3 text-sm text-sky-900">
            Mode pengembangan aktif. Login uji: <b>{DEV_EMAIL}</b> / <b>{DEV_PASSWORD}</b>.
          </p>
        )}

        {!configured && (
          <p className="mt-4 rounded-lg bg-sky-50 border border-sky-200 p-3 text-sm text-sky-900">
            Login akun untuk dinas, TPID, dan mitra data akan segera hadir. Untuk
            meninjau peta dan rekomendasi sekarang, silakan pilih <b>Masuk sebagai
            Tamu</b> di bawah.
          </p>
        )}

        <button
          type="button"
          onClick={onGoogle}
          disabled={busy || !configured}
          className="mt-6 w-full inline-flex items-center justify-center gap-2 rounded-lg
                     border border-slate-300 bg-white px-4 py-2.5 text-sm font-medium
                     text-slate-700 hover:bg-slate-50 disabled:opacity-50
                     disabled:cursor-not-allowed"
        >
          {/* Google "G" mark, inline so no asset or extra request is needed. */}
          <svg aria-hidden="true" width="18" height="18" viewBox="0 0 24 24">
            <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.27-4.74 3.27-8.1Z" />
            <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84A11 11 0 0 0 12 23Z" />
            <path fill="#FBBC05" d="M5.84 14.1a6.6 6.6 0 0 1 0-4.2V7.06H2.18a11 11 0 0 0 0 9.88l3.66-2.84Z" />
            <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.16-3.16A11 11 0 0 0 2.18 7.06L5.84 9.9c.87-2.6 3.3-4.52 6.16-4.52Z" />
          </svg>
          Masuk dengan Google
        </button>

        <div className="mt-6 flex items-center gap-3">
          <span className="h-px flex-1 bg-slate-200" />
          <span className="text-xs text-slate-400">atau dengan email</span>
          <span className="h-px flex-1 bg-slate-200" />
        </div>

        <form onSubmit={onSubmit} className="mt-6 space-y-4">
          <div>
            <label htmlFor="email" className="block text-sm font-medium text-slate-700">
              Email
            </label>
            <input
              id="email"
              // Dev login uses a non-email username ("admin"), which type=email
              // would reject before submit. Relax to text only when dev login
              // is on; production keeps real email validation.
              type={DEV_LOGIN_ENABLED ? "text" : "email"}
              required
              autoComplete="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm
                         focus:border-emerald-600 focus:outline-none focus:ring-1 focus:ring-emerald-600"
            />
          </div>

          <div>
            <div className="flex items-center justify-between">
              <label htmlFor="password" className="block text-sm font-medium text-slate-700">
                Kata sandi
              </label>
              <Link
                href={`/forgot-password${email ? `?email=${encodeURIComponent(email)}` : ""}`}
                className="text-sm text-emerald-700 hover:underline"
              >
                Lupa kata sandi?
              </Link>
            </div>
            <input
              id="password"
              type="password"
              required
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm
                         focus:border-emerald-600 focus:outline-none focus:ring-1 focus:ring-emerald-600"
            />
          </div>

          {error && (
            <p role="alert" className="rounded-lg bg-red-50 border border-red-200 p-3 text-sm text-red-800">
              {error}
            </p>
          )}

          <button
            type="submit"
            disabled={busy || !configured}
            className="w-full rounded-lg bg-emerald-700 px-4 py-2.5 text-sm font-medium text-white
                       hover:bg-emerald-800 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {busy ? "Memproses…" : "Masuk"}
          </button>
        </form>

        <div className="mt-6 flex items-center gap-3">
          <span className="h-px flex-1 bg-slate-200" />
          <span className="text-xs text-slate-400">atau</span>
          <span className="h-px flex-1 bg-slate-200" />
        </div>

        <button
          type="button"
          onClick={enterAsGuest}
          className="mt-6 w-full rounded-lg border border-slate-300 px-4 py-2.5 text-sm
                     font-medium text-slate-700 hover:bg-slate-50"
        >
          Masuk sebagai Tamu (juri)
        </button>
        <p className="mt-2 text-center text-xs text-slate-400">
          Akses peta &amp; data untuk peninjauan, tanpa membuat akun.
        </p>

        <p className="mt-6 text-center text-sm text-slate-600">
          Belum punya akun? Masuk dengan Google di atas, atau hubungi tim
          AgriFlow untuk akun dinas, TPID, dan mitra data.
        </p>
      </div>
    </main>
  );
}
