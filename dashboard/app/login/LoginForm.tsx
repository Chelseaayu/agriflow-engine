"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useAuth } from "../lib/auth";

type Mode = "signin" | "signup";

export default function LoginForm() {
  const { signIn, signUp, configured, user } = useAuth();
  const router = useRouter();
  const searchParams = useSearchParams();

  // proxy.ts appends ?next= when it bounces someone off a protected page.
  // Only relative paths are honoured — accepting an absolute URL here would
  // make this an open redirect an attacker could point at their own site.
  const rawNext = searchParams.get("next");
  const nextPath =
    rawNext && rawNext.startsWith("/") && !rawNext.startsWith("//")
      ? rawNext
      : "/account";

  const [mode, setMode] = useState<Mode>("signin");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  if (user) {
    // Already signed in — nothing to do on this page.
    router.replace(nextPath);
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
    router.push(nextPath);
  }

  return (
    <main className="flex-1 flex items-center justify-center p-6 bg-slate-50">
      <div className="w-full max-w-sm">
        <Link href="/" className="block text-sm text-slate-500 hover:text-slate-800 mb-6">
          ← Kembali ke peta
        </Link>

        <h1 className="text-2xl font-semibold text-slate-900">
          {mode === "signin" ? "Masuk ke AgriFlow" : "Buat akun AgriFlow"}
        </h1>
        <p className="mt-1 text-sm text-slate-500">
          Untuk pelanggan dinas, TPID, dan mitra data.
        </p>

        {!configured && (
          <p className="mt-4 rounded-lg bg-amber-50 border border-amber-200 p-3 text-sm text-amber-900">
            Login belum dikonfigurasi di lingkungan ini. Peta dan data tetap
            dapat diakses tanpa masuk.
          </p>
        )}

        <form onSubmit={onSubmit} className="mt-6 space-y-4">
          <div>
            <label htmlFor="email" className="block text-sm font-medium text-slate-700">
              Email
            </label>
            <input
              id="email"
              type="email"
              required
              autoComplete="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm
                         focus:border-emerald-600 focus:outline-none focus:ring-1 focus:ring-emerald-600"
            />
          </div>

          <div>
            <label htmlFor="password" className="block text-sm font-medium text-slate-700">
              Kata sandi
            </label>
            <input
              id="password"
              type="password"
              required
              minLength={8}
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
