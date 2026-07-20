import { Suspense } from "react";
import ResetPasswordForm from "./ResetPasswordForm";

// ResetPasswordForm reads the ?error_description= query param Supabase
// attaches when a recovery link is expired or already used, via
// useSearchParams(), which forces client-side rendering for that subtree —
// same reason /login wraps LoginForm.
export default function ResetPasswordPage() {
  return (
    <Suspense
      fallback={
        <main className="flex-1 grid place-items-center text-slate-500">
          Memuat…
        </main>
      }
    >
      <ResetPasswordForm />
    </Suspense>
  );
}
