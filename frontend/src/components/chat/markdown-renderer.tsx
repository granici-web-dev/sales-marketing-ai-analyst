"use client";

// UI-SPEC § Markdown Rendering Rules (D-19 KPI bolding + D-18 dashboard links
// + D-18a client-side whitelist defense + XSS hardening).
//
// `react-markdown` with `remark-gfm` (tables). `allowedElements` whitelist
// drops <script>/<iframe>/<img>/<svg>/<h1..6>/raw HTML; `unwrapDisallowed`
// is NOT set, so disallowed elements AND their children are removed entirely.

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { DashboardLinkPill } from "@/components/chat/dashboard-link-pill";
import { cn } from "@/lib/utils";

// D-18a — internal dashboard paths permitted to render as accent pills.
const DASHBOARD_PATHS = new Set([
  "/sales",
  "/salespeople",
  "/marketing",
  "/insights",
  "/chat",
]);

const ALLOWED_ELEMENTS = [
  "p",
  "strong",
  "em",
  "ul",
  "ol",
  "li",
  "a",
  "code",
  "table",
  "thead",
  "tbody",
  "tr",
  "th",
  "td",
  "br",
] as const;

interface MarkdownRendererProps {
  content: string;
  className?: string;
}

export function MarkdownRenderer({
  content,
  className,
}: MarkdownRendererProps) {
  return (
    <div
      className={cn("text-sm leading-normal text-foreground", className)}
      data-testid="markdown-renderer"
    >
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        allowedElements={[...ALLOWED_ELEMENTS]}
        // Disallowed elements and their children are silently dropped.
        unwrapDisallowed={false}
        components={{
          p: ({ children }) => (
            <p className="text-sm leading-normal mb-2 last:mb-0">{children}</p>
          ),
          strong: ({ children }) => (
            <strong className="font-semibold text-[hsl(221_83%_53%)]">
              {children}
            </strong>
          ),
          em: ({ children }) => <em className="italic">{children}</em>,
          ul: ({ children }) => (
            <ul className="list-disc list-inside ml-4 space-y-1 mb-2">
              {children}
            </ul>
          ),
          ol: ({ children }) => (
            <ol className="list-decimal list-inside ml-4 space-y-1 mb-2">
              {children}
            </ol>
          ),
          li: ({ children }) => <li className="text-sm">{children}</li>,
          code: ({ children }) => (
            <code className="font-mono text-xs bg-[hsl(240_5%_96%)] px-1 py-0.5 rounded">
              {children}
            </code>
          ),
          br: () => <br />,
          a: ({ href, children }) => {
            const raw = typeof href === "string" ? href : "";
            // UI-SPEC line 388: bare anchor → plain text.
            if (raw === "#") {
              return <span>{children}</span>;
            }
            if (DASHBOARD_PATHS.has(raw)) {
              return (
                <DashboardLinkPill href={raw}>{children}</DashboardLinkPill>
              );
            }
            // D-18a — non-whitelisted href: render as plain muted text.
            return (
              <span className="text-[hsl(240_4%_46%)] italic">{children}</span>
            );
          },
          // Tables — shadcn Table primitives wrapped for overflow.
          table: ({ children }) => (
            <div className="overflow-x-auto my-3">
              <Table>{children}</Table>
            </div>
          ),
          thead: ({ children }) => <TableHeader>{children}</TableHeader>,
          tbody: ({ children }) => <TableBody>{children}</TableBody>,
          tr: ({ children }) => <TableRow>{children}</TableRow>,
          th: ({ children }) => <TableHead>{children}</TableHead>,
          td: ({ children }) => <TableCell>{children}</TableCell>,
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}
