"use client";

// Sign-in / account affordance for the dashboard header.
//
// Renders nothing when auth is not configured, so the offline demo shows no
// dead link to a login that cannot work.

import Link from "next/link";
import { useAuth } from "../lib/auth";

export default function AccountMenu() {
  const { user, loading, configured } = useAuth();

  if (!configured || loading) return null;

  if (!user) {
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
