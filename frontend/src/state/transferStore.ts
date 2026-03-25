"use client";

import { create } from "zustand";
import { supabase } from "../../lib/supabase/browserClient";
import type { RealtimeChannel } from "@supabase/supabase-js";

export type DeliveryMethod = "bank" | "mobile" | "cash" | "stablecoin";
export type SpeedPreference = "fastest" | "balanced" | "cheapest";
export type PayoutPreference = "bank" | "mobile" | "cash" | "stablecoin";

export type RailType = "stablecoin" | "ach" | "mobile_money";

export type RouteCandidate = {
  corridor_key: string;
  rail_type: RailType;
  fee_total: string;
  eta_seconds: number;
  liquidity_confidence: number;
  payout_currency: string;
  provider_path: string[];
  cost_score: string | null;
  confidence: number;
  fx_rate: string | null;
  fx_spread: string | null;
  all_in_total: string | null;
};

export type PricingQuoteResponse = {
  request: {
    sender_country: string;
    receiver_country: string;
    amount: string;
    currency: string;
    speed_preference: SpeedPreference;
    payout_preference: PayoutPreference;
    recipient_identifier: string | null;
  };
  recommended_route: RouteCandidate;
  route_alternatives: RouteCandidate[];
  total_fee: string;
  fx_rate_snapshot: string | null;
  fx_spread: string | null;
  delivery_eta_seconds: number;
  delivery_method: DeliveryMethod;
  all_in_total: string;
  ai_explanation: string | null;
  confidence: number;
};

type TransferState = {
  activeTransactionId: string | null;
  status: string | null;
  quote: PricingQuoteResponse | null;
  channel: RealtimeChannel | null;

  setFromRecord: (record: any) => void;
  subscribe: (transactionId: string) => Promise<void>;
  unsubscribe: () => Promise<void>;
};

export const useTransferStore = create<TransferState>((set, get) => ({
  activeTransactionId: null,
  status: null,
  quote: null,
  channel: null,

  setFromRecord: (record: any) => {
    const payload = record?.quote_payload ?? null;
    set({
      activeTransactionId: record?.id ? String(record.id) : get().activeTransactionId,
      status: record?.status ? String(record.status) : null,
      quote: payload ?? null,
    });
  },

  subscribe: async (transactionId: string) => {
    const { channel: existing } = get();
    if (existing) {
      await existing.unsubscribe();
    }

    const ch = supabase
      .channel(`transfers:${transactionId}`)
      .on(
        "postgres_changes",
        {
          event: "UPDATE",
          schema: "public",
          table: "transactions",
          filter: `id=eq.${transactionId}`,
        },
        (payload) => {
          get().setFromRecord(payload.new);
        },
      )
      .subscribe();

    set({ activeTransactionId: transactionId, channel: ch });
  },

  unsubscribe: async () => {
    const { channel } = get();
    if (channel) {
      await channel.unsubscribe();
    }
    set({ channel: null });
  },
}));

