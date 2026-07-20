import { Suspense } from "react";
import LoginForm from "./LoginForm";

// useSearchParams() forces client-side rendering for whatever subtree reads it,
// so the form lives behind a Suspense boundary. Without this the /login route
// cannot be prerendered and the build fails.
export default function LoginPage() {
  return (
    <Suspense
      fallback={
        <main className="flex-1 grid place-items-center text-slate-500">
          Memuat…
        </main>
      }
    >
      <LoginForm />
    </Suspense>
  );
}
