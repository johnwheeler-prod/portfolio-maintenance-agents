import { NextRequest, NextResponse } from "next/server";
import { triggerWorkflow } from "@/lib/github";

export async function POST(request: NextRequest) {
  try {
    const { workflowFile, inputs } = await request.json();

    if (!workflowFile) {
      return NextResponse.json({ ok: false, error: "Missing workflowFile" }, { status: 400 });
    }

    const success = await triggerWorkflow(workflowFile, inputs ?? {});

    if (success) {
      return NextResponse.json({ ok: true });
    } else {
      return NextResponse.json({ ok: false, error: "Failed to trigger workflow" }, { status: 500 });
    }
  } catch {
    return NextResponse.json({ ok: false, error: "Internal server error" }, { status: 500 });
  }
}
