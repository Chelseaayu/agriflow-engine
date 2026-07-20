"use client";

import { useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useAuth } from "../lib/auth";

export default function ForgotPasswordForm() {
  const { requestPasswordReset, configured } = useAuth();
  const searchParams = useSearchParams();

  const [email, setEmail] = useState(searchParams.get("email") ?? "");
  const [error, setError] = useState<string | null>(null);
  const [sent, setSent] = useState(false);
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    const { error } = await requestPasswordReset(email);
    setBusy(false);

    if (error) {
      setError(error);
      return;
    }
    // Supabase does not signal whether the address is registered, and we
    // don't either — showing the same confirmation either way avoids
    // leaking account existence through this form.
    setSent(true);
  }

  return (
    <main className="flex-1 flex items-center justify-center p-6 bg-slate-50">
      <div className="w-full max-w-sm">
        <Link href="/login" className="block text-sm text-slate-500 hover:text-slate-800 mb-6">
          ← Kembali ke halaman masuk
        </Link>

        <h1 className="text-2xl font-semibold text-slate-900">Lupa kata sandi</h1>
        <p className="mt-1 text-sm text-slate-500">
          Masukkan email akun Anda. Kami akan mengirim tautan untuk mengatur
          ulang kata sandi.
        </p>

        {!configured && (
          <p className="mt-4 rounded-lg bg-amber-50 border border-amber-200 p-3 text-sm text-amber-900">
            Login belum dikonfigurasi di lingkungan ini. Peta dan data tetap
            dapat diakses tanpa masuk.
          </p>
        )}

        {sent ? (
          <p className="mt-6 rounded-lg bg-emerald-50 border border-emerald-200 p-3 text-sm text-emerald-900">
            Jika email tersebut terdaftar, tautan atur ulang kata sandi sudah
            dikirim. Periksa kotak masuk (dan folder spam) Anda.
          </p>
        ) : (
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
              {busy ? "Mengirim…" : "Kirim tautan atur ulang"}
            </button>
          </form>
        )}
      </div>
    </main>
  );
}
