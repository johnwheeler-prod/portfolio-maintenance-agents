import { notFound } from "next/navigation";
import { Header } from "@/components/layout/header";
import { getContentBriefs } from "@/lib/data";
import { BriefsTable } from "@/components/tables/briefs-table";
import { formatDate } from "@/lib/utils";
import type { ContentBrief } from "@/lib/types";

export const dynamic = "force-dynamic";

export default async function ContentPlanDatePage({
  params,
}: {
  params: Promise<{ date: string }>;
}) {
  const { date } = await params;
  const data = await getContentBriefs(date);
  if (!data) notFound();

  const briefs = (Array.isArray(data) ? data : []) as ContentBrief[];

  return (
    <>
      <Header
        title={`Content Plan — ${formatDate(date)}`}
        description={`${briefs.length} content opportunities identified`}
      />

      {briefs.length > 0 ? (
        <BriefsTable briefs={briefs} />
      ) : (
        <div className="bg-surface-2 border border-surface-4 rounded-lg px-4 py-8 text-center text-sm text-neutral-500">
          No briefs found for this date.
        </div>
      )}
    </>
  );
}
