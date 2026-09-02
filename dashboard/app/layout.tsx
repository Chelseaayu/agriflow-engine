import type { Metadata, Viewport } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import { AuthProvider } from "./lib/auth";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  // Base for resolving the OG image to an absolute URL when the page is
  // shared; Vercel previews override the host at runtime, production matches.
  metadataBase: new URL("https://agriflow-engine.vercel.app"),
  // "/" is the public landing now, so the default title/description speak to
  // a first-time visitor; sharing the link should read as a product, not an
  // internal dashboard. The OG image is the same live-dashboard shot the
  // landing hero uses.
  title: "AgriFlow · Platform Ketahanan Pangan Jawa Timur",
  description:
    "Pencocokan pasokan pangan surplus-defisit untuk 38 kabupaten/kota Jawa Timur, dihitung optimal dari data BPS dan PIHPS.",
  applicationName: "AgriFlow",
  manifest: "/manifest.webmanifest",
  appleWebApp: { capable: true, title: "AgriFlow", statusBarStyle: "default" },
  openGraph: {
    title: "AgriFlow · Platform Ketahanan Pangan Jawa Timur",
    description:
      "Surplus di satu daerah, defisit di daerah lain. AgriFlow memasangkannya dari data resmi BPS dan PIHPS.",
    images: ["/landing-hero.jpg"],
  },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: "#5b7245",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="id"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col">
        <AuthProvider>{children}</AuthProvider>
      </body>
    </html>
  );
}
