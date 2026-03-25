"use client";

import { useEffect, useMemo, useState } from "react";

import { supabase } from "../../lib/supabase/browserClient";
import type { PricingQuoteResponse } from "../../src/state/transferStore";

type TxRow = {
  id: string;
  status: string;
  created_at: string;
  amount: string | number;
  currency: string;
  speed_preference: "fastest" | "balanced" | "cheapest";
  payout_preference: "bank" | "mobile" | "cash" | "stablecoin";
  all_in_total: string | number | null;
  quote_payload: PricingQuoteResponse | any;
};

type RouteRow = {
  id: string;
  transaction_id: string;
  rail_type: "stablecoin" | "ach" | "mobile_money";
  fee_total: string | number;
  fx_spread: string | number | null;
  eta_seconds: number;
  is_recommended: boolean;
};

function toNum(v: any) {
  const n = typeof v === "number" ? v : Number(v);
  return Number.isFinite(n) ? n : 0;
}

export default function AdminPage() {
  const [accessToken, setAccessToken] = useState<string | null>(null);
  const [txs, setTxs] = useState<TxRow[]>([]);
  const [routes, setRoutes] = useState<RouteRow[]>([]);
  const [loading, setLoading] = useState(true);

  async function refreshSession() {
    const { data } = await supabase.auth.getSession();
    setAccessToken(data.session?.access_token ?? null);
  }

  useEffect(() => {
    refreshSession();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    async function load() {
      if (!accessToken) return;
      setLoading(true);
      const { data: txData } = await supabase
        .from("transactions")
        .select("id,status,created_at,amount,currency,speed_preference,payout_preference,all_in_total,quote_payload")
        .order("created_at", { ascending: false })
        .limit(20);

      const { data: routeData } = await supabase
        .from("routes")
        .select("id,transaction_id,rail_type,fee_total,fx_spread,eta_seconds,is_recommended")
        .order("id", { ascending: false })
        .limit(200);

      setTxs((txData as TxRow[]) ?? []);
      setRoutes((routeData as RouteRow[]) ?? []);
      setLoading(false);
    }

    load().catch(() => setLoading(false));
  }, [accessToken]);

  const byTx = useMemo(() => {
    const map = new Map<string, RouteRow[]>();
    for (const r of routes) {
      const arr = map.get(r.transaction_id) ?? [];
      arr.push(r);
      map.set(r.transaction_id, arr);
    }
    return map;
  }, [routes]);

  const analytics = useMemo(() => {
    return txs.map((tx) => {
      const rs = byTx.get(tx.id) ?? [];
      const amt = toNum(tx.amount);

      const candidates = rs.map((r) => {
        const fee = toNum(r.fee_total);
        const fxSpread = r.fx_spread == null ? 0 : toNum(r.fx_spread);
        // Cost proxy for sender: amount + fee_total + amount * fx_spread
        const costProxy = amt + fee + amt * fxSpread;
        return { ...r, costProxy };
      });

      const cheapest = Math.min(...candidates.map((c) => c.costProxy));
      const recommended = candidates.find((c) => c.is_recommended) ?? candidates[0];
      const recommendedCost = recommended?.costProxy ?? amt;

      return {
        tx,
        candidates: candidates.sort((a, b) => a.costProxy - b.costProxy),
        cheapestCost: cheapest,
        recommendedCost,
        potentialSavings: Math.max(0, recommendedCost - cheapest),
      };
    });
  }, [txs, byTx]);

  const topSavings = useMemo(() => {
    return analytics
      .slice()
      .sort((a, b) => b.potentialSavings - a.potentialSavings)
      .slice(0, 10);
  }, [analytics]);

  const statusCounts = useMemo(() => {
    const counts: Record<string, number> = {};
    for (const tx of txs) {
      counts[tx.status] = (counts[tx.status] ?? 0) + 1;
    }
    return counts;
  }, [txs]);

  return (
    <main className="min-h-screen bg-white text-slate-900">
      <div className="mx-auto max-w-5xl px-6 py-10">
        <h1 className="text-2xl font-semibold">Admin Analytics</h1>
        <p className="mt-2 text-slate-600">Corridor analytics, route performance, and cost savings insights.</p>

        {!accessToken ? (
          <div className="mt-6 rounded border border-amber-200 bg-amber-50 p-4 text-amber-900">
            Sign in to view analytics.{" "}
            <a className="underline" href="/login">
              Go to Login
            </a>
          </div>
        ) : null}

        <div className="mt-6 grid grid-cols-1 gap-3 md:grid-cols-3">
          <div className="rounded border border-slate-200 p-4">
            <div className="text-xs text-slate-500">Total transfers</div>
            <div className="mt-1 text-2xl font-semibold">{txs.length}</div>
          </div>
          {Object.entries(statusCounts).slice(0, 2).map(([k, v]) => (
            <div key={k} className="rounded border border-slate-200 p-4">
              <div className="text-xs text-slate-500">Status: {k}</div>
              <div className="mt-1 text-2xl font-semibold">{v}</div>
            </div>
          ))}
        </div>

        <div className="mt-6">
          <div className="text-sm font-semibold">Top potential cost savings (re: chosen speed)</div>
          {loading ? (
            <div className="mt-3 text-slate-600">Loading...</div>
          ) : (
            <div className="mt-3 space-y-4">
              {topSavings.map((item) => (
                <div key={item.tx.id} className="rounded border border-slate-200 p-4">
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <div className="min-w-[240px]">
                      <div className="text-xs text-slate-500">Transaction</div>
                      <div className="font-mono text-sm break-all">{item.tx.id}</div>
                      <div className="mt-1 text-xs text-slate-500">
                        Speed: {item.tx.speed_preference} • Payout: {item.tx.payout_preference}
                      </div>
                    </div>
                    <div>
                      <div className="text-xs text-slate-500">Potential savings vs cheapest candidate</div>
                      <div className="text-xl font-semibold">{item.potentialSavings.toFixed(2)}</div>
                    </div>
                  </div>

                  <div className="mt-4 grid grid-cols-1 gap-2 md:grid-cols-2">
                    {item.candidates.slice(0, 3).map((c) => (
                      <div key={c.id} className="rounded border border-slate-100 p-3">
                        <div className="flex items-center justify-between">
                          <div className="font-semibold">{c.rail_type.replace("_", " ")}</div>
                          <div className="text-xs text-slate-500">{c.is_recommended ? "Recommended" : ""}</div>
                        </div>
                        <div className="mt-1 text-sm text-slate-700">ETA: {c.eta_seconds}s</div>
                        <div className="text-sm text-slate-700">
                          Proxy cost: {c.costProxy.toFixed(2)} {item.tx.currency}
                        </div>
                      </div>
                    ))}
                  </div>

                  {item.tx.quote_payload?.ai_explanation ? (
                    <div className="mt-4 rounded bg-slate-50 p-3 text-sm text-slate-700">
                      <div className="text-xs font-semibold text-slate-900">Why this route?</div>
                      <div className="mt-1 whitespace-pre-wrap">{String(item.tx.quote_payload.ai_explanation).slice(0, 350)}…</div>
                    </div>
                  ) : null}
                </div>
              ))}
              {topSavings.length === 0 ? (
                <div className="text-slate-600">No analytics data yet.</div>
              ) : null}
            </div>
          )}
        </div>
      </div>
    </main>
  );
}


