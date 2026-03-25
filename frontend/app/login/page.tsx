"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { supabase } from "../../lib/supabase/browserClient";

export default function LoginPage() {
  const router = useRouter();

  const [email, setEmail] = useState("");
  const [otp, setOtp] = useState("");
  const [stage, setStage] = useState<"enterEmail" | "enterOtp">("enterEmail");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => {
      if (data.session) router.replace("/sender");
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function sendOtp() {
    setError(null);
    const trimmed = email.trim();
    if (!trimmed) {
      setError("Email is required.");
      return;
    }

    setLoading(true);
    try {
      const { error } = await supabase.auth.signInWithOtp({
        email: trimmed,
      });
      if (error) {
        setError(error.message);
        return;
      }
      setStage("enterOtp");
    } finally {
      setLoading(false);
    }
  }

  async function verifyOtp() {
    setError(null);
    const trimmedEmail = email.trim();
    const token = otp.trim();
    if (!trimmedEmail || !token) {
      setError("Email and OTP code are required.");
      return;
    }

    setLoading(true);
    try {
      const { error } = await supabase.auth.verifyOtp({
        email: trimmedEmail,
        token,
        type: "email",
      });
      if (error) {
        setError(error.message);
        return;
      }
      router.replace("/sender");
    } finally {
      setLoading(false);
    }
  }

  async function signOut() {
    await supabase.auth.signOut();
    router.replace("/");
  }

  return (
    <main className="min-h-screen bg-white text-slate-900">
      <div className="mx-auto max-w-lg px-6 py-12">
        <h1 className="text-2xl font-semibold">Login</h1>
        <p className="mt-2 text-slate-600">
          Sign in with email OTP to request pricing and send transfers.
        </p>

        {error ? (
          <div className="mt-4 rounded border border-rose-200 bg-rose-50 p-3 text-rose-900">
            {error}
          </div>
        ) : null}

        <div className="mt-6 rounded border border-slate-200 p-5">
          {stage === "enterEmail" ? (
            <>
              <label className="text-sm font-medium">Email</label>
              <input
                className="mt-1 w-full rounded border border-slate-300 px-3 py-2"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="name@example.com"
                autoComplete="email"
              />

              <button
                className="mt-4 w-full rounded bg-slate-900 px-4 py-2 text-white disabled:opacity-50"
                onClick={sendOtp}
                disabled={loading}
              >
                {loading ? "Sending..." : "Send OTP"}
              </button>
            </>
          ) : (
            <>
              <label className="text-sm font-medium">OTP code</label>
              <input
                className="mt-1 w-full rounded border border-slate-300 px-3 py-2"
                value={otp}
                onChange={(e) => setOtp(e.target.value)}
                placeholder="Enter OTP"
                inputMode="numeric"
              />

              <button
                className="mt-4 w-full rounded bg-slate-900 px-4 py-2 text-white disabled:opacity-50"
                onClick={verifyOtp}
                disabled={loading}
              >
                {loading ? "Verifying..." : "Verify & Continue"}
              </button>

              <button
                className="mt-2 w-full rounded border border-slate-300 px-4 py-2 text-slate-900 disabled:opacity-50"
                onClick={() => {
                  setStage("enterEmail");
                  setOtp("");
                }}
                disabled={loading}
              >
                Back
              </button>
            </>
          )}

          <div className="mt-4 text-center text-xs text-slate-500">
            Need an account? Use any email you can receive OTP for.
          </div>
        </div>

        <div className="mt-6 text-center">
          <button className="text-sm underline" onClick={() => router.replace("/sender")}>
            Go to Sender
          </button>
          <div className="mt-2">
            <button className="text-sm underline" onClick={() => router.replace("/admin")}>
              Go to Admin
            </button>
          </div>
          <div className="mt-2">
            <button className="text-sm underline" onClick={signOut}>
              Sign out
            </button>
          </div>
        </div>
      </div>
    </main>
  );
}

