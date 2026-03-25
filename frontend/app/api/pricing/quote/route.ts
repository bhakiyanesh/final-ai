import { NextResponse } from "next/server";

import { QuoteRequestSchema } from "../../../../lib/schemas/remittance";

export async function POST(req: Request) {
  const agentUrl = process.env.AGENT_API_URL;
  if (!agentUrl) {
    return NextResponse.json(
      { error: "Missing AGENT_API_URL" },
      { status: 500 },
    );
  }

  const auth = req.headers.get("authorization");
  if (!auth) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const body = await req.json();
  const parsed = QuoteRequestSchema.safeParse(body);
  if (!parsed.success) {
    return NextResponse.json({ error: parsed.error.flatten() }, { status: 400 });
  }

  const res = await fetch(`${agentUrl.replace(/\/$/, "")}/pricing/quote`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      authorization: auth,
    },
    body: JSON.stringify(parsed.data),
    cache: "no-store",
  });

  const data = await res.json().catch(() => ({}));
  return NextResponse.json(data, { status: res.status });
}

