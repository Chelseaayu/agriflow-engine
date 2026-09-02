"use client";

// Tiny client island so the server-rendered landing page can set the guest
// cookie. Full navigation (not router.push) so proxy.ts re-runs and sees the
// freshly-set cookie, letting /dashboard through.
import { enterGuest } from "../lib/guest";

export default function GuestCta({
  className,
  children,
}: {
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={() => {
        enterGuest();
        window.location.assign("/dashboard");
      }}
      className={className}
    >
      {children}
    </button>
  );
}
