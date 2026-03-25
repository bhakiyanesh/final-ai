"use client";

import { useMutation, useQuery } from "@tanstack/react-query";

import {
  apiCreateTransfer,
  apiExecuteTransfer,
  apiGetTransfer,
  apiQuote,
} from "../api/agent";

export function useQuote(accessToken: string | null) {
  return useMutation({
    mutationFn: (body: any) => {
      if (!accessToken) throw new Error("Missing access token");
      return apiQuote(accessToken, body);
    },
  });
}

export function useCreateTransfer(accessToken: string | null) {
  return useMutation({
    mutationFn: (body: any) => {
      if (!accessToken) throw new Error("Missing access token");
      return apiCreateTransfer(accessToken, body);
    },
  });
}

export function useExecuteTransfer(accessToken: string | null) {
  return useMutation({
    mutationFn: (vars: { transactionId: string; idempotencyKey: string }) => {
      if (!accessToken) throw new Error("Missing access token");
      return apiExecuteTransfer(accessToken, vars.transactionId, vars.idempotencyKey);
    },
  });
}

export function useTransfer(accessToken: string | null, transactionId: string | null) {
  return useQuery({
    queryKey: ["transfer", transactionId],
    enabled: !!accessToken && !!transactionId,
    queryFn: () => {
      if (!accessToken || !transactionId) throw new Error("Missing access token");
      return apiGetTransfer(accessToken, transactionId);
    },
  });
}

