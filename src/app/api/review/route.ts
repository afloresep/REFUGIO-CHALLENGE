import { NextRequest, NextResponse } from "next/server";
import { reviewPolicySource } from "@/lib/safety-review";

export async function POST(request: NextRequest) {
  const contentType = request.headers.get("content-type") ?? "";

  if (contentType.includes("application/json")) {
    const body = await request.json() as { source?: unknown };
    return NextResponse.json(reviewPolicySource(typeof body.source === "string" ? body.source : ""));
  }

  const formData = await request.formData();
  const source = formData.get("source");
  const file = formData.get("submission");

  if (typeof source === "string" && source.trim()) {
    return NextResponse.json(reviewPolicySource(source));
  }

  if (file instanceof File) {
    return NextResponse.json(reviewPolicySource(await file.text()));
  }

  return NextResponse.json({ error: "Expected source text or a Python file." }, { status: 400 });
}
