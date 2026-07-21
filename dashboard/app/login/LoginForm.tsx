"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useAuth } from "../lib/auth";
import { enterGuest } from "../lib/guest";
import { DEV_LOGIN_ENABLED, DEV_EMAIL, DEV_PASSWORD } from "../lib/devauth";

type Mode = "signin" | "signup";

export default function LoginForm() {
  const { signIn, signUp, configured, user } = useAuth();
  const router = useRouter();
  const searchParams = useSearchParams();

  // proxy.ts appends ?next= when it funnels someone off a gated page.
  // Only relative paths are honoured — accepting an absolute URL here would
  // make this an open redirect an attacker could point at their own site.
  // Default to the map (/), which is the app's home, not /account.
  const rawNext = searchParams.get("next");
  const nextPath =
    rawNext && rawNext.startsWith("/") && !rawNext.startsWith("//")
      ? rawNext
      : "/";

  const [mode, setMode] = useState<Mode>("signin");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
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
    setNotice(null);
    setBusy(true);
    const fn = mode === "signin" ? signIn : signUp;
    const { error } = await fn(email, password);
    setBusy(false);

    if (error) {
      setError(error);
      return;
    }
    if (mode === "signup") {
      // Supabase may require email confirmation depending on project settings,
      // so we cannot assume a session exists yet.
      setNotice(
        "Akun dibuat. Jika diminta, cek email Anda untuk tautan konfirmasi, lalu masuk.",
      );
      setMode("signin");
      return;
    }
    // Full navigation (not router.push) so the proxy re-runs and sees the
    // freshly-set session/dev cookie, letting the destination through.
    window.location.assign(nextPath);
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
          {mode === "signin" ? "Masuk ke AgriFlow" : "Buat akun AgriFlow"}
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
              {mode === "signin" && (
                <Link
                  href={`/forgot-password${email ? `?email=${encodeURIComponent(email)}` : ""}`}
                  className="text-sm text-emerald-700 hover:underline"
                >
                  Lupa kata sandi?
                </Link>
              )}
            </div>
            <input
              id="password"
              type="password"
              required
              // Enforce length only when CREATING a password (signup). On
              // signin you are entering an existing one, so a length rule here
              // is wrong, and it was also blocking the short dev-login password.
              minLength={mode === "signup" ? 8 : undefined}
              autoComplete={mode === "signin" ? "current-password" : "new-password"}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm
                         focus:border-emerald-600 focus:outline-none focus:ring-1 focus:ring-emerald-600"
            />
            {mode === "signup" && (
              <p className="mt-1 text-xs text-slate-500">Minimal 8 karakter.</p>
            )}
          </div>

          {error && (
            <p role="alert" className="rounded-lg bg-red-50 border border-red-200 p-3 text-sm text-red-800">
              {error}
            </p>
          )}
          {notice && (
            <p className="rounded-lg bg-emerald-50 border border-emerald-200 p-3 text-sm text-emerald-900">
              {notice}
            </p>
          )}

          <button
            type="submit"
            disabled={busy || !configured}
            className="w-full rounded-lg bg-emerald-700 px-4 py-2.5 text-sm font-medium text-white
                       hover:bg-emerald-800 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {busy ? "Memproses…" : mode === "signin" ? "Masuk" : "Daftar"}
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
          {mode === "signin" ? "Belum punya akun? " : "Sudah punya akun? "}
          <button
            type="button"
            onClick={() => {
              setMode(mode === "signin" ? "signup" : "signin");
              setError(null);
              setNotice(null);
            }}
            className="font-medium text-emerald-700 hover:underline"
          >
            {mode === "signin" ? "Daftar" : "Masuk"}
          </button>
        </p>
      </div>
    </main>
  );
}
