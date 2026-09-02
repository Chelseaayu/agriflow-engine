"use client";

// Account affordance for the dashboard header.
//
// The site is login-first (see proxy.ts), so by the time a page renders the
// visitor is always either a real signed-in user or a guest. This menu shows
// which, and gives each a way out:
//   - real user  -> account link (email), sign-out lives on /account
//   - guest      -> a "Tamu" chip plus "Keluar" to drop the guest cookie and
//                   return to /login, where they can sign in for real

import Link from "next/link";
import { useSyncExternalStore } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "../lib/auth";
import { exitGuest, isGuest } from "../lib/guest";

// The guest cookie is not reactive; read it through useSyncExternalStore so
// the server snapshot (false) and the client snapshot stay consistent without
// a setState-in-effect.
const noSubscribe = () => () => {};

export default function AccountMenu() {
  const { user, loading } = useAuth();
  const router = useRouter();
  const guest = useSyncExternalStore(noSubscribe, isGuest, () => false);

  if (loading) return null;

  if (user) {
    return (
      <Link
        href="/account"
        className="flex items-center gap-2 rounded-lg border border-slate-300 px-3 py-1.5
                   text-sm font-medium text-slate-700 hover:bg-slate-50"
        title={user.email ?? undefined}
      >
        <span
          aria-hidden
          className="grid h-6 w-6 place-items-center rounded-full bg-emerald-700 text-xs text-white"
        >
          {(user.email ?? "?").charAt(0).toUpperCase()}
        </span>
        <span className="max-w-[12ch] truncate">{user.email}</span>
      </Link>
    );
  }

  if (guest) {
    return (
      <div className="flex items-center gap-2">
        <span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs font-medium text-slate-500">
          Mode Tamu
        </span>
        <button
          onClick={() => {
            exitGuest();
            router.push("/login");
          }}
          className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm font-medium
                     text-slate-700 hover:bg-slate-50"
        >
          Keluar
        </button>
      </div>
    );
  }

  // Fallback (e.g. brief pre-hydration flash): offer the way in.
  return (
    <Link
      href="/login"
      className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm font-medium
                 text-slate-700 hover:bg-slate-50"
    >
      Masuk
    </Link>
  );
}
