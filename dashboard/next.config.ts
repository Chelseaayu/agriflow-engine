import type { NextConfig } from "next";

// Baseline security headers on every response (DRA hardening brief item 1).
// A full nonce-based CSP is deliberately deferred: it must be plumbed through
// proxy.ts and shipped report-only first, or it silently breaks the Leaflet
// tiles and the HF Space/Supabase fetches. These five are safe everywhere.
const securityHeaders = [
  {
    // Redundant on *.vercel.app (already HSTS-preloaded) but correct to set
    // now for when a custom domain is attached.
    key: "Strict-Transport-Security",
    value: "max-age=63072000; includeSubDomains; preload",
  },
  { key: "X-Content-Type-Options", value: "nosniff" },
  // Neither the login page nor the dashboard should ever render in a frame
  // (anti-clickjacking). Superseded by CSP frame-ancestors, kept for older
  // browsers until the CSP lands.
  { key: "X-Frame-Options", value: "DENY" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  {
    key: "Permissions-Policy",
    value: "camera=(), microphone=(), geolocation=(), browsing-topics=()",
  },
];

const nextConfig: NextConfig = {
  async headers() {
    return [{ source: "/:path*", headers: securityHeaders }];
  },
};

export default nextConfig;
