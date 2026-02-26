import Link from "next/link";
import { Header } from "@/components/layout/header";
import { getContentPlanDates } from "@/lib/data";
import { formatDate } from "@/lib/utils";

export const dynamic = "force-dynamic";

export default async function ContentPlanPage() {
  const dates = await getContentPlanDates();

  return (
    <>
      <Header
        title="Content Plan"
        description="GSC-driven content opportunity planning"
      />

      <div className="bg-surface-2 border border-surface-4 rounded-lg overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-surface-4">
              <th className="text-left px-4 py-3 text-xs text-neutral-500 font-medium uppercase tracking-wider">
                Date
              </th>
            </tr>
          </thead>
          <tbody>
            {dates.map((date) => (
              <tr
                key={date}
                className="border-b border-surface-4 last:border-0 hover:bg-surface-3 transition-colors"
              >
                <td className="px-4 py-3">
                  <Link
                    href={`/content-plan/${date}`}
                    className="text-pine-400 hover:text-pine-400/80 font-mono"
                  >
                    {formatDate(date)}
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {dates.length === 0 && (
          <div className="px-4 py-8 text-center text-sm text-neutral-500">
            No content plans found. Trigger one from the Run page.
          </div>
        )}
      </div>
    </>
  );
}
