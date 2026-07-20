import { Suspense } from "react";
import ForgotPasswordForm from "./ForgotPasswordForm";

// ForgotPasswordForm reads ?email= via useSearchParams() to prefill the
// field when arriving from the login page, which forces client-side
// rendering for that subtree — same reason /login wraps LoginForm.
export default function ForgotPasswordPage() {
  return (
    <Suspense
      fallback={
        <main className="flex-1 grid place-items-center text-slate-500">
          Memuat…
        </main>
      }
    >
      <ForgotPasswordForm />
    </Suspense>
  );
}
