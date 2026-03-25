"use client";

import { useEffect, useMemo, useState } from "react";

import { supabase } from "../../lib/supabase/browserClient";
import { useQuote, useCreateTransfer } from "../../src/hooks/useTransfers";
import { useTransferStore } from "../../src/state/transferStore";
import type { PricingQuoteResponse, PayoutPreference, SpeedPreference } from "../../src/state/transferStore";

const defaultForm = {
  sender_country: "US",
  receiver_country: "NG",
  currency: "USD",
  amount: "250",
  speed_preference: "cheapest" as SpeedPreference,
  payout_preference: "bank" as PayoutPreference,
  recipient_identifier: "",
};

function safeNumber(v: string | null | undefined) {
  const n = v ? Number(v) : NaN;
  return Number.isFinite(n) ? n : 0;
}

export default function SenderPage() {
  const [accessToken, setAccessToken] = useState<string | null>(null);
  const [form, setForm] = useState(defaultForm);

  const quoteMutation = useQuote(accessToken);
  const createMutation = useCreateTransfer(accessToken);
  const { subscribe } = useTransferStore();

  const [quote, setQuote] = useState<PricingQuoteResponse | null>(null);
  const [transactionId, setTransactionId] = useState<string | null>(null);

  const speedCostSavings = useMemo(() => {
    if (!quote) return null;
    const recommended = safeNumber(quote.recommended_route.all_in_total);
    const cheapest = Math.min(...quote.route_alternatives.map((r) => safeNumber(r.all_in_total)));
    if (recommended <= 0 || cheapest <= 0) return null;
    const delta = recommended - cheapest;
    const pct = delta / recommended;
    return { recommended, cheapest, delta, pct: Math.max(0, pct) };
  }, [quote]);

  async function refreshSession() {
    const { data } = await supabase.auth.getSession();
    const token = data.session?.access_token ?? null;
    setAccessToken(token);
  }

  useEffect(() => {
    refreshSession();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function handleQuote() {
    if (!accessToken) return;
    const recipient_identifier = form.recipient_identifier.trim() || null;
    const body = {
      ...form,
      recipient_identifier,
      amount: Number(form.amount),
    };

    const res = await quoteMutation.mutateAsync(body);
    setQuote(res);
  }

  async function handleSend() {
    if (!accessToken || !quote) return;
    const idem = crypto.randomUUID();
    const recipient_identifier = form.recipient_identifier.trim() || null;

    const res = await createMutation.mutateAsync({
      ...form,
      recipient_identifier,
      amount: Number(form.amount),
      idempotency_key: idem,
    });

    const txId = res.transaction_id as string;
    setTransactionId(txId);
    await subscribe(txId);
  }

  return (
    <main className="min-h-screen bg-white text-slate-900">
      <div className="mx-auto max-w-4xl px-6 py-10">
        <div className="flex items-start justify-between gap-6">
          <div>
            <h1 className="text-2xl font-semibold">Sender Dashboard</h1>
            <p className="mt-2 text-slate-600">Request transparent pricing and recommended delivery.</p>
          </div>
          {transactionId ? (
            <div className="rounded border border-slate-200 bg-slate-50 px-4 py-3">
              <div className="text-xs text-slate-500">Transaction</div>
              <div className="break-all font-mono text-sm">{transactionId}</div>
            </div>
          ) : null}
        </div>

        {!accessToken ? (
          <div className="mt-6 rounded border border-amber-200 bg-amber-50 p-4 text-amber-900">
            Sign in to Supabase to request quotes and send transfers.{" "}
            <a className="underline" href="/login">
              Go to Login
            </a>
          </div>
        ) : null}

        <div className="mt-8 grid grid-cols-1 gap-4 md:grid-cols-2">
          <div>
            <label className="text-sm font-medium">Amount</label>
            <input
              className="mt-1 w-full rounded border border-slate-300 px-3 py-2"
              value={form.amount}
              onChange={(e) => setForm((f) => ({ ...f, amount: e.target.value }))}
            />
          </div>
          <div>
            <label className="text-sm font-medium">Currency (sender)</label>
            <input
              className="mt-1 w-full rounded border border-slate-300 px-3 py-2"
              value={form.currency}
              onChange={(e) => setForm((f) => ({ ...f, currency: e.target.value.toUpperCase() }))}
            />
          </div>
          <div>
            <label className="text-sm font-medium">Sender country</label>
            <input
              className="mt-1 w-full rounded border border-slate-300 px-3 py-2"
              value={form.sender_country}
              onChange={(e) => setForm((f) => ({ ...f, sender_country: e.target.value.toUpperCase() }))}
            />
          </div>
          <div>
            <label className="text-sm font-medium">Receiver country</label>
            <input
              className="mt-1 w-full rounded border border-slate-300 px-3 py-2"
              value={form.receiver_country}
              onChange={(e) => setForm((f) => ({ ...f, receiver_country: e.target.value.toUpperCase() }))}
            />
          </div>

          <div>
            <label className="text-sm font-medium">Speed preference</label>
            <select
              className="mt-1 w-full rounded border border-slate-300 px-3 py-2"
              value={form.speed_preference}
              onChange={(e) => setForm((f) => ({ ...f, speed_preference: e.target.value as SpeedPreference }))}
            >
              <option value="fastest">Fastest</option>
              <option value="balanced">Balanced</option>
              <option value="cheapest">Cheapest</option>
            </select>
          </div>

          <div>
            <label className="text-sm font-medium">Payout preference</label>
            <select
              className="mt-1 w-full rounded border border-slate-300 px-3 py-2"
              value={form.payout_preference}
              onChange={(e) => setForm((f) => ({ ...f, payout_preference: e.target.value as PayoutPreference }))}
            >
              <option value="bank">Bank</option>
              <option value="mobile">Mobile</option>
              <option value="cash">Cash</option>
              <option value="stablecoin">Stablecoin</option>
            </select>
          </div>

          <div className="md:col-span-2">
            <label className="text-sm font-medium">Recipient identifier (optional)</label>
            <input
              className="mt-1 w-full rounded border border-slate-300 px-3 py-2"
              value={form.recipient_identifier}
              onChange={(e) => setForm((f) => ({ ...f, recipient_identifier: e.target.value }))}
              placeholder="Account number / phone / wallet id depending on rail"
            />
          </div>
        </div>

        <div className="mt-6 flex flex-wrap items-center gap-3">
          <button
            className="rounded bg-slate-900 px-4 py-2 text-white disabled:opacity-50"
            onClick={handleQuote}
            disabled={!accessToken || quoteMutation.isPending}
          >
            {quoteMutation.isPending ? "Pricing..." : "Get transparent pricing"}
          </button>

          <button
            className="rounded border border-slate-300 px-4 py-2 disabled:opacity-50"
            onClick={handleSend}
            disabled={!accessToken || !quote || createMutation.isPending}
          >
            {createMutation.isPending ? "Sending..." : "Send transfer"}
          </button>
        </div>

        {quote ? (
          <div className="mt-8 rounded border border-slate-200 p-5">
            <div className="flex flex-wrap items-center justify-between gap-4">
              <div>
                <div className="text-sm text-slate-500">All-in price</div>
                <div className="text-2xl font-semibold">
                  {quote.all_in_total} {quote.request.currency}
                </div>
                <div className="mt-1 text-sm text-slate-600">
                  ETA: {quote.delivery_eta_seconds} seconds via {quote.delivery_method}
                </div>
              </div>

              {speedCostSavings ? (
                <div className="rounded bg-emerald-50 p-3 text-emerald-900">
                  <div className="text-xs text-emerald-700">Cost savings indicator</div>
                  <div className="text-sm">
                    Cheapest candidate: {speedCostSavings.cheapest}. Recommended vs cheapest:{" "}
                    {speedCostSavings.delta > 0 ? `+${speedCostSavings.delta}` : "0"}
                  </div>
                </div>
              ) : null}
            </div>

            {quote.ai_explanation ? (
              <div className="mt-5 rounded border border-slate-200 bg-white p-4">
                <div className="text-sm font-semibold">Why this route?</div>
                <div className="mt-2 whitespace-pre-wrap text-sm text-slate-700">{quote.ai_explanation}</div>
              </div>
            ) : null}

            <div className="mt-6">
              <div className="text-sm font-semibold">Route comparison</div>
              <div className="mt-3 grid grid-cols-1 gap-3 md:grid-cols-2">
                {quote.route_alternatives.map((r, idx) => {
                  const recommended = idx === 0 && r.corridor_key === quote.recommended_route.corridor_key && r.rail_type === quote.recommended_route.rail_type;
                  const cost = safeNumber(r.all_in_total);
                  const maxCost = Math.max(...quote.route_alternatives.map((x) => safeNumber(x.all_in_total)));
                  const pct = maxCost > 0 ? (cost / maxCost) * 100 : 0;
                  return (
                    <div key={`${r.rail_type}-${r.corridor_key}-${idx}`} className="rounded border border-slate-200 p-4">
                      <div className="flex items-center justify-between">
                        <div className="font-semibold">
                          {r.rail_type.replace("_", " ")} {recommended ? "(Recommended)" : ""}
                        </div>
                        <div className="text-xs text-slate-500">{r.eta_seconds}s</div>
                      </div>
                      <div className="mt-2 text-sm text-slate-700">All-in: {r.all_in_total} {quote.request.currency}</div>
                      <div className="mt-3 h-2 w-full rounded bg-slate-100">
                        <div className="h-2 rounded bg-slate-900" style={{ width: `${pct}%` }} />
                      </div>
                      <div className="mt-2 text-xs text-slate-500">
                        Fees: {r.fee_total} • FX spread: {r.fx_spread ?? "0"}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        ) : null}
      </div>
    </main>
  );
}

