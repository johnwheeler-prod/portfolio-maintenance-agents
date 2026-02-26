"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  Globe,
  Search,
  Briefcase,
  FileText,
  Play,
} from "lucide-react";

const nav = [
  { href: "/", label: "Overview", icon: LayoutDashboard },
  { href: "/site-audit", label: "Site Audit", icon: Globe },
  { href: "/seo-audit", label: "SEO Audit", icon: Search },
  { href: "/portfolio-audit", label: "Portfolio", icon: Briefcase },
  { href: "/content-plan", label: "Content Plan", icon: FileText },
  { href: "/run", label: "Run Pipelines", icon: Play },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="fixed top-0 left-0 h-screen w-56 bg-surface-2 border-r border-surface-4 flex flex-col z-30">
      <div className="p-4 border-b border-surface-4">
        <h1 className="text-sm font-mono font-semibold text-pine-400 tracking-wider uppercase">
          Agent Dash
        </h1>
      </div>
      <nav className="flex-1 py-2">
        {nav.map(({ href, label, icon: Icon }) => {
          const active =
            href === "/" ? pathname === "/" : pathname.startsWith(href);
          return (
            <Link
              key={href}
              href={href}
              className={`flex items-center gap-3 px-4 py-2.5 text-sm transition-colors ${
                active
                  ? "text-pine-400 bg-pine-500/10 border-r-2 border-pine-500"
                  : "text-neutral-400 hover:text-neutral-200 hover:bg-surface-3"
              }`}
            >
              <Icon size={16} />
              {label}
            </Link>
          );
        })}
      </nav>
      <div className="p-4 border-t border-surface-4 text-xs text-neutral-500 font-mono">
        v0.1.0
      </div>
    </aside>
  );
}
