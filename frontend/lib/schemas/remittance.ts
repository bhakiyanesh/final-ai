import { z } from "zod";

const countryCode = z
  .string()
  .trim()
  .length(2)
  .regex(/^[A-Za-z]{2}$/)
  .transform((s) => s.toUpperCase());

const currencyCode = z
  .string()
  .trim()
  .length(3)
  .regex(/^[A-Za-z]{3}$/)
  .transform((s) => s.toUpperCase());

const amountSchema = z
  .union([z.string(), z.number()])
  .transform((v) => (typeof v === "number" ? v.toString() : v))
  .refine((s) => {
    const n = Number(s);
    return Number.isFinite(n) && n > 0;
  }, "amount must be a positive number");

export const SpeedPreferenceSchema = z.enum(["fastest", "balanced", "cheapest"]);
export const PayoutPreferenceSchema = z.enum(["bank", "mobile", "cash", "stablecoin"]);

export const QuoteRequestSchema = z.object({
  sender_country: countryCode,
  receiver_country: countryCode,
  amount: amountSchema,
  currency: currencyCode,
  speed_preference: SpeedPreferenceSchema,
  payout_preference: PayoutPreferenceSchema,
  recipient_identifier: z.string().trim().min(1).optional().nullable(),
});

export const CreateTransferRequestSchema = QuoteRequestSchema.extend({
  idempotency_key: z
    .string()
    .min(8)
    .max(128)
    .regex(/^[A-Za-z0-9:_-]+$/),
});

