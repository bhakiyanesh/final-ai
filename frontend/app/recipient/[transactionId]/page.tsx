"use client";

import { useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";

import { supabase } from "../../../lib/supabase/browserClient";
import { useTransfer } from "../../../src/hooks/useTransfers";
import { useTransferStore } from "../../../src/state/transferStore";

export default function RecipientTrackingPage() {
  const params = useParams();
  const transactionId = useMemo(() => String(params.transactionId ?? ""), [params.transactionId]);

  const [accessToken, setAccessToken] = useState<string | null>(null);
  const store = useTransferStore();

  const transferQuery = useTransfer(accessToken, transactionId || null);

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => {
      setAccessToken(data.session?.access_token ?? null);
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!transactionId) return;
    if (!accessToken) return;
    store.subscribe(transactionId).catch(() => null);
    return () => {
      store.unsubscribe().catch(() => null);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [transactionId, accessToken]);

  const quote = store.quote ?? transferQuery.data?.quote ?? null;
  const status = store.status ?? transferQuery.data?.status ?? null;

  return (
    <main className="min-h-screen bg-white text-slate-900">
      <div className="mx-auto max-w-4xl px-6 py-10">
        <h1 className="text-2xl font-semibold">Recipient Tracking</h1>
        <p className="mt-2 text-slate-600">Real-time updates from your transfer status.</p>

        {!accessToken ? (
          <div className="mt-6 rounded border border-amber-200 bg-amber-50 p-4 text-amber-900">
            Sign in to Supabase to view transfer updates.{" "}
            <a className="underline" href="/login">
              Go to Login
            </a>
          </div>
        ) : null}

        <div className="mt-6 rounded border border-slate-200 p-5">
          <div className="text-sm text-slate-500">Transaction</div>
          <div className="break-all font-mono text-sm">{transactionId}</div>

          <div className="mt-3 text-sm text-slate-500">Status</div>
          <div className="text-lg font-semibold">{status ?? (transferQuery.isLoading ? "Loading..." : "—")}</div>

          {quote ? (
            <>
              <div className="mt-5 text-sm text-slate-500">All-in price</div>
              <div className="text-2xl font-semibold">
                {quote.all_in_total} {quote.request.currency}
              </div>

              <div className="mt-2 text-sm text-slate-600">
                Delivery: {quote.delivery_method} • ETA: {quote.delivery_eta_seconds} seconds
              </div>

              {quote.ai_explanation ? (
                <div className="mt-5 rounded border border-slate-200 bg-white p-4">
                  <div className="text-sm font-semibold">Why this route?</div>
                  <div className="mt-2 whitespace-pre-wrap text-sm text-slate-700">{quote.ai_explanation}</div>
                </div>
              ) : null}
            </>
          ) : null}
        </div>
      </div>
    </main>
  );
}

