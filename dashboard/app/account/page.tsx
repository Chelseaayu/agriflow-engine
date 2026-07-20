"use client";

// Protected account page: shows the signed-in dashboard user and lets them
// look up the plan attached to a WhatsApp number.
//
// The two identities are deliberately separate for now — a dinas account on the
// dashboard and a farmer's WhatsApp subscription are different things. The
// subscriber.dashboard_user_id column exists to link them when that is wanted.

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { api, type BillingStatus } from "../lib/api";
import { useAuth } from "../lib/auth";

export default function AccountPage() {
  const { user, loading, configured, signOut } = useAuth();
  const router = useRouter();

  const [phone, setPhone] = useState("");
  const [status, setStatus] = useState<BillingStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    // Only bounce once we know the session state, or a signed-in user gets
    // kicked to /login on every refresh while the session is still resolving.
    if (!loading && !user && configured) router.replace("/login");
  }, [loading, user, configured, router]);

  if (loading) {
    return <main className="flex-1 grid place-items-center text-slate-500">Memuat…</main>;
  }

  if (!configured) {
    return (
      <main className="flex-1 p-6 max-w-2xl mx-auto">
        <Link href="/" className="text-sm text-slate-500 hover:text-slate-800">← Kembali ke peta</Link>
        <p className="mt-6 rounded-lg bg-amber-50 border border-amber-200 p-4 text-sm text-amber-900">
          Login belum dikonfigurasi di lingkungan ini.
        </p>
      </main>
    );
  }

  if (!user) return null; // redirect in flight

  async function lookup(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setStatus(null);
    setBusy(true);
    try {
      setStatus(await api.billingStatus(phone));
    } catch {
      setError("Nomor tidak valid atau layanan sedang tidak tersedia.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="flex-1 p-6 max-w-2xl mx-auto w-full">
      <Link href="/" className="text-sm text-slate-500 hover:text-slate-800">← Kembali ke peta</Link>

      <h1 className="mt-6 text-2xl font-semibold text-slate-900">Akun</h1>

      <section className="mt-4 rounded-xl border border-slate-200 bg-white p-5">
        <p className="text-sm text-slate-500">Masuk sebagai</p>
        <p className="font-medium text-slate-900">{user.email}</p>
        <button
          onClick={async () => { await signOut(); router.push("/"); }}
          className="mt-4 rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium
                     text-slate-700 hover:bg-slate-50"
        >
          Keluar
        </button>
      </section>

      <section className="mt-6 rounded-xl border border-slate-200 bg-white p-5">
        <h2 className="font-semibold text-slate-900">Langganan WhatsApp</h2>
        <p className="mt-1 text-sm text-slate-500">
          Cek paket dan sisa kuota untuk sebuah nomor WhatsApp. Nomor di-hash di
          server dan tidak disimpan dalam bentuk aslinya.
        </p>

        <form onSubmit={lookup} className="mt-4 flex gap-2">
          <input
            type="tel"
            required
            placeholder="+628123456789"
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
            className="flex-1 rounded-lg border border-slate-300 px-3 py-2 text-sm
                       focus:border-emerald-600 focus:outline-none focus:ring-1 focus:ring-emerald-600"
          />
          <button
            type="submit"
            disabled={busy}
            className="rounded-lg bg-emerald-700 px-4 py-2 text-sm font-medium text-white
                       hover:bg-emerald-800 disabled:opacity-50"
          >
            {busy ? "…" : "Cek"}
          </button>
        </form>

        {error && (
          <p role="alert" className="mt-3 rounded-lg bg-red-50 border border-red-200 p-3 text-sm text-red-800">
            {error}
          </p>
        )}

        {status && (
          <dl className="mt-4 grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
            <dt className="text-slate-500">Paket</dt>
            <dd className="font-medium text-slate-900">
              {status.is_pro ? "PRO" : "GRATIS"}
            </dd>

            <dt className="text-slate-500">Kuota hari ini</dt>
            <dd className="font-medium text-slate-900">
              {status.is_pro
                ? "Tanpa batas"
                : `${status.used_today} dari ${status.limit} terpakai`}
            </dd>

            {status.expires_at && (
              <>
                <dt className="text-slate-500">Aktif sampai</dt>
                <dd className="font-medium text-slate-900">
                  {new Date(status.expires_at).toLocaleDateString("id-ID", {
                    day: "numeric", month: "long", year: "numeric",
                  })}
                </dd>
              </>
            )}
          </dl>
        )}
      </section>
    </main>
  );
}
