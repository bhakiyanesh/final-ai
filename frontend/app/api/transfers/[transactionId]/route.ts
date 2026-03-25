import { NextResponse } from "next/server";

export async function GET(
  req: Request,
  context: { params: Promise<{ transactionId: string }> },
) {
  const agentUrl = process.env.AGENT_API_URL;
  if (!agentUrl) {
    return NextResponse.json({ error: "Missing AGENT_API_URL" }, { status: 500 });
  }

  const params = await context.params;
  const { transactionId } = params;

  const auth = req.headers.get("authorization");
  if (!auth) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const res = await fetch(`${agentUrl.replace(/\/$/, "")}/transfers/${transactionId}`, {
    method: "GET",
    headers: {
      authorization: auth,
    },
    cache: "no-store",
  });

  const data = await res.json().catch(() => ({}));
  return NextResponse.json(data, { status: res.status });
}

