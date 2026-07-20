"use client";

// Auth context for the dashboard.
//
// Wraps Supabase Auth in a shape the UI can consume without knowing whether
// Supabase is configured at all. When it is not (the offline demo), `configured`
// is false, `user` stays null, and the sign-in calls return a clear error rather
// than throwing — the public map keeps working either way.

import {
  createContext, useCallback, useContext, useEffect, useMemo, useState,
} from "react";
import type { Session, User } from "@supabase/supabase-js";
import { getSupabase, isAuthConfigured } from "./supabase";

type AuthResult = { error: string | null };

type AuthContextValue = {
  user: User | null;
  session: Session | null;
  loading: boolean;
  configured: boolean;
  signIn: (email: string, password: string) => Promise<AuthResult>;
  signUp: (email: string, password: string) => Promise<AuthResult>;
  signOut: () => Promise<void>;
  requestPasswordReset: (email: string) => Promise<AuthResult>;
  updatePassword: (newPassword: string) => Promise<AuthResult>;
};

const NOT_CONFIGURED =
  "Login belum aktif di lingkungan ini. Atur NEXT_PUBLIC_SUPABASE_URL dan NEXT_PUBLIC_SUPABASE_ANON_KEY.";

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const configured = isAuthConfigured();
  const [session, setSession] = useState<Session | null>(null);
  const [loading, setLoading] = useState(configured);

  useEffect(() => {
    const supabase = getSupabase();
    if (!supabase) {
      setLoading(false);
      return;
    }
    let active = true;

    supabase.auth.getSession().then(({ data }) => {
      if (!active) return;
      setSession(data.session);
      setLoading(false);
    });

    // Keeps this tab in sync with sign-in/out that happened elsewhere,
    // including token refreshes.
    const { data: sub } = supabase.auth.onAuthStateChange((_event, next) => {
      setSession(next);
    });

    return () => {
      active = false;
      sub.subscription.unsubscribe();
    };
  }, []);

  const signIn = useCallback(async (email: string, password: string) => {
    const supabase = getSupabase();
    if (!supabase) return { error: NOT_CONFIGURED };
    const { error } = await supabase.auth.signInWithPassword({ email, password });
    return { error: error?.message ?? null };
  }, []);

  const signUp = useCallback(async (email: string, password: string) => {
    const supabase = getSupabase();
    if (!supabase) return { error: NOT_CONFIGURED };
    const { error } = await supabase.auth.signUp({ email, password });
    return { error: error?.message ?? null };
  }, []);

  const signOut = useCallback(async () => {
    await getSupabase()?.auth.signOut();
    setSession(null);
  }, []);

  // Step 1 of password recovery: ask Supabase to email a link. The link
  // lands the visitor back on /reset-password?code=... . redirectTo must be
  // present in the Supabase project's Authentication > URL Configuration
  // allow-list, or Supabase silently falls back to the Site URL instead —
  // see docs/DEPLOY_AUTH.md.
  const requestPasswordReset = useCallback(async (email: string) => {
    const supabase = getSupabase();
    if (!supabase) return { error: NOT_CONFIGURED };
    const { error } = await supabase.auth.resetPasswordForEmail(email, {
      redirectTo: `${window.location.origin}/reset-password`,
    });
    return { error: error?.message ?? null };
  }, []);

  // Step 2: called from /reset-password once the recovery link has been
  // exchanged for a session (see app/lib/supabase.ts — the browser client's
  // detectSessionInUrl does that exchange automatically on load). updateUser
  // works against whatever session is currently active, recovery or normal.
  const updatePassword = useCallback(async (newPassword: string) => {
    const supabase = getSupabase();
    if (!supabase) return { error: NOT_CONFIGURED };
    const { error } = await supabase.auth.updateUser({ password: newPassword });
    return { error: error?.message ?? null };
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      user: session?.user ?? null,
      session,
      loading,
      configured,
      signIn,
      signUp,
      signOut,
      requestPasswordReset,
      updatePassword,
    }),
    [session, loading, configured, signIn, signUp, signOut, requestPasswordReset, updatePassword],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}
