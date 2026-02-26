import Link from "next/link";
import type { PriorityPage } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import { scoreBg, slugFromUrl } from "@/lib/utils";

export function PagesTable({
  pages,
  dateParam,
}: {
  pages: PriorityPage[];
  dateParam: string;
}) {
  return (
    <div className="bg-surface-2 border border-surface-4 rounded-lg overflow-hidden">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-surface-4">
            <th className="text-left px-4 py-3 text-xs text-neutral-500 font-medium uppercase tracking-wider">
              Page
            </th>
            <th className="text-right px-4 py-3 text-xs text-neutral-500 font-medium uppercase tracking-wider">
              Score
            </th>
          </tr>
        </thead>
        <tbody>
          {pages.map((page) => {
            const slug = slugFromUrl(page.url);
            return (
              <tr
                key={page.url}
                className="border-b border-surface-4 last:border-0 hover:bg-surface-3 transition-colors"
              >
                <td className="px-4 py-3">
                  <Link
                    href={`/site-audit/${dateParam}/${slug}`}
                    className="text-pine-400 hover:text-pine-400/80 font-mono text-xs"
                  >
                    {new URL(page.url).pathname}
                  </Link>
                </td>
                <td className="px-4 py-3 text-right">
                  <Badge className={scoreBg(page.score)}>
                    {page.score}
                  </Badge>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
