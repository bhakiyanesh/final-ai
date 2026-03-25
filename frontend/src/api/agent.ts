"use client";

import axios from "axios";

import type { PricingQuoteResponse } from "../state/transferStore";

// Re-exported types will be added in later iterations.

export async function apiQuote(
  accessToken: string,
  body: any,
): Promise<PricingQuoteResponse> {
  const baseURL = process.env.NEXT_PUBLIC_BACKEND_URL;
  if (!baseURL) throw new Error("NEXT_PUBLIC_BACKEND_URL is not set");

  const client = axios.create({
    baseURL: baseURL.replace(/\/$/, ""),
    headers: { "Content-Type": "application/json" },
  });

  const res = await client.post("/pricing/quote", body, {
    headers: { authorization: accessToken.startsWith("Bearer ") ? accessToken : `Bearer ${accessToken}` },
  });

  return res.data as PricingQuoteResponse;
}

export async function apiCreateTransfer(
  accessToken: string,
  body: any,
): Promise<any> {
  const baseURL = process.env.NEXT_PUBLIC_BACKEND_URL;
  if (!baseURL) throw new Error("NEXT_PUBLIC_BACKEND_URL is not set");

  const client = axios.create({
    baseURL: baseURL.replace(/\/$/, ""),
    headers: { "Content-Type": "application/json" },
  });

  const res = await client.post("/transfers", body, {
    headers: {
      authorization: accessToken.startsWith("Bearer ") ? accessToken : `Bearer ${accessToken}`,
      "Idempotency-Key": body.idempotency_key,
    },
  });

  return res.data;
}

export async function apiExecuteTransfer(
  accessToken: string,
  transactionId: string,
  idempotencyKey: string,
): Promise<any> {
  const baseURL = process.env.NEXT_PUBLIC_BACKEND_URL;
  if (!baseURL) throw new Error("NEXT_PUBLIC_BACKEND_URL is not set");

  const client = axios.create({
    baseURL: baseURL.replace(/\/$/, ""),
    headers: { "Content-Type": "application/json" },
  });

  const res = await client.post(
    `/transfers/${transactionId}/execute`,
    {},
    {
      headers: {
        authorization: accessToken.startsWith("Bearer ") ? accessToken : `Bearer ${accessToken}`,
        "Idempotency-Key": idempotencyKey,
      },
    },
  );
  return res.data;
}

export async function apiGetTransfer(
  accessToken: string,
  transactionId: string,
): Promise<any> {
  const baseURL = process.env.NEXT_PUBLIC_BACKEND_URL;
  if (!baseURL) throw new Error("NEXT_PUBLIC_BACKEND_URL is not set");

  const client = axios.create({
    baseURL: baseURL.replace(/\/$/, ""),
    headers: { "Content-Type": "application/json" },
  });

  const res = await client.get(`/transfers/${transactionId}`, {
    headers: { authorization: accessToken.startsWith("Bearer ") ? accessToken : `Bearer ${accessToken}` },
  });
  return res.data;
}

