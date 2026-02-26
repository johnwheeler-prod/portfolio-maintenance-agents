import { NextRequest, NextResponse } from "next/server";
import { getWorkflowRuns } from "@/lib/github";

export async function GET(request: NextRequest) {
  const workflow = request.nextUrl.searchParams.get("workflow");

  if (!workflow) {
    return NextResponse.json({ runs: [] }, { status: 400 });
  }

  try {
    const runs = await getWorkflowRuns(workflow);
    return NextResponse.json({ runs });
  } catch {
    return NextResponse.json({ runs: [], error: "Failed to fetch runs" }, { status: 500 });
  }
}
