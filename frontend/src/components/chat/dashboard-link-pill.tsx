"use client";

// UI-SPEC § Markdown Rendering Rules → DashboardLinkPill (D-18 + D-18a).
//
// Renders `[Sales Dashboard](/sales)` as an inline accent pill. The href
// whitelist is enforced by `markdown-renderer.tsx`'s renderLink before this
// component is invoked.

import Link from "next/link";
import { ChevronRight } from "lucide-react";
import { cn } from "@/lib/utils";

interface DashboardLinkPillProps {
  href: string;
  children: React.ReactNode;
  className?: string;
}

export function DashboardLinkPill({
  href,
  children,
  className,
}: DashboardLinkPillProps) {
  return (
    <Link
      href={href}
      className={cn(
        "inline-flex items-center gap-1 bg-[hsl(221_83%_53%)]/10 text-[hsl(221_83%_53%)] rounded-md px-2 py-0.5 text-sm hover:bg-[hsl(221_83%_53%)]/20 transition-colors",
        className,
      )}
    >
      {children}
      <ChevronRight size={14} aria-hidden="true" />
    </Link>
  );
}
