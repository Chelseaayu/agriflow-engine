"use client";

// Handles the redirect Supabase sends after a recovery email link is
// clicked.
//
// How the session gets here: app/lib/supabase.ts creates the browser
// Supabase client with @supabase/ssr's createBrowserClient(), which defaults
// detectSessionInUrl to true and flowType to "pkce". On mount, that client
// notices the `?code=` query param this page is loaded with, exchanges it
// for a session using the PKCE verifier it stashed (in a cookie) when
// resetPasswordForEmail() was called, and persists the resulting session to
// cookies — the same cookie jar proxy.ts and the rest of the app read. None
// of that is code we have to write here; useAuth()'s `user` simply becomes
// non-null once it's done, because AuthProvider's getSession() call awaits
// GoTrueClient's internal initialize(), which performs the exchange first.
//
// This is a cookie-based equivalent of Supabase's documented pattern
// (onAuthStateChange firing PASSWORD_RECOVERY, then updateUser()) — we don't
// need to key off that specific event because a plain "is there a session"
// check is more robust across page refreshes than a one-shot event listener
// would be.

import { useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useAuth } from "../lib/auth";

export default function ResetPasswordForm() {
  const { user, loading, configured, updatePassword } = useAuth();
  const router = useRouter();
  const searchParams = useSearchParams();

  // Supabase can report an expired/already-used link either as a query
  // param or (on some redirect paths) a hash fragment; useSearchParams()
  // only sees the query string, so the hash is checked separately. Read via
  // a lazy initializer (not an effect) since this is a one-time read of
  // external state at mount, not a subscription.
  const [hashErrorDescription] = useState<string | null>(() => {
    if (typeof window === "undefined" || !window.location.hash) return null;
    return new URLSearchParams(window.location.hash.slice(1)).get("error_description");
  });
  const linkError = searchParams.get("error_description") ?? hashErrorDescription;

  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);

    if (password !== confirm) {
      setError("Kata sandi tidak sama.");
      return;
    }

    setBusy(true);
    const { error } = await updatePassword(password);
    setBusy(false);

    if (error) {
      setError(error);
      return;
    }
    setDone(true);
  }

  return (
    <main className="flex-1 flex items-center justify-center p-6 bg-slate-50">
      <div className="w-full max-w-sm">
        <Link href="/login" className="block text-sm text-slate-500 hover:text-slate-800 mb-6">
          ← Kembali ke halaman masuk
        </Link>

        <h1 className="text-2xl font-semibold text-slate-900">Atur ulang kata sandi</h1>

        {!configured ? (
          <p className="mt-4 rounded-lg bg-amber-50 border border-amber-200 p-3 text-sm text-amber-900">
            Login belum dikonfigurasi di lingkungan ini. Peta dan data tetap
            dapat diakses tanpa masuk.
          </p>
        ) : loading ? (
          <p className="mt-6 text-sm text-slate-500">Memeriksa tautan…</p>
        ) : done ? (
          <div className="mt-6 space-y-4">
            <p className="rounded-lg bg-emerald-50 border border-emerald-200 p-3 text-sm text-emerald-900">
              Kata sandi berhasil diperbarui.
            </p>
            <button
              onClick={() => router.push("/account")}
              className="w-full rounded-lg bg-emerald-700 px-4 py-2.5 text-sm font-medium text-white
                         hover:bg-emerald-800"
            >
              Lanjut ke akun
            </button>
          </div>
        ) : !user ? (
          <div className="mt-6 space-y-4">
            <p role="alert" className="rounded-lg bg-red-50 border border-red-200 p-3 text-sm text-red-800">
              {linkError
                ? "Tautan atur ulang sudah tidak berlaku atau sudah pernah dipakai."
                : "Tautan atur ulang tidak valid. Buka halaman ini dari tautan di email Anda, atau minta yang baru."}
            </p>
            <Link
              href="/forgot-password"
              className="block text-center rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium
                         text-slate-700 hover:bg-slate-50"
            >
              Kirim ulang tautan
            </Link>
          </div>
        ) : (
          <form onSubmit={onSubmit} className="mt-6 space-y-4">
            <div>
              <label htmlFor="password" className="block text-sm font-medium text-slate-700">
                Kata sandi baru
              </label>
              <input
                id="password"
                type="password"
                required
                minLength={8}
                autoComplete="new-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm
                           focus:border-emerald-600 focus:outline-none focus:ring-1 focus:ring-emerald-600"
              />
              <p className="mt-1 text-xs text-slate-500">Minimal 8 karakter.</p>
            </div>

            <div>
              <label htmlFor="confirm" className="block text-sm font-medium text-slate-700">
                Ulangi kata sandi baru
              </label>
              <input
                id="confirm"
                type="password"
                required
                minLength={8}
                autoComplete="new-password"
                value={confirm}
                onChange={(e) => setConfirm(e.target.value)}
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
              disabled={busy}
              className="w-full rounded-lg bg-emerald-700 px-4 py-2.5 text-sm font-medium text-white
                         hover:bg-emerald-800 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {busy ? "Menyimpan…" : "Simpan kata sandi baru"}
            </button>
          </form>
        )}
      </div>
    </main>
  );
}
