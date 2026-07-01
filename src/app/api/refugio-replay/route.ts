import { NextRequest, NextResponse } from "next/server";
import { getLocalReplay } from "@/lib/replay-store";

export async function GET(request: NextRequest) {
  const jobId = request.nextUrl.searchParams.get("jobId")?.trim() ?? "";
  const download = request.nextUrl.searchParams.get("download") === "1";

  try {
    const replay = await getLocalReplay(jobId);

    return NextResponse.json(replay, {
      headers: download
        ? {
            "content-disposition": `attachment; filename="refugio-replay-${jobId}.json"`,
          }
        : undefined,
    });
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Could not load replay." },
      { status: 400 },
    );
  }
}
