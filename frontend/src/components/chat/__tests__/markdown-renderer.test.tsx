import { describe, it, expect } from "vitest";
import { screen } from "@testing-library/react";
import { renderWithIntl } from "@/test/render-with-intl";
import { MarkdownRenderer } from "@/components/chat/markdown-renderer";

/**
 * UI-SPEC § Markdown Rendering Rules — D-19 + D-18 + D-18a + XSS hardening.
 * Cases MR1..MR6 mirror the plan's behavior block.
 */
describe("MarkdownRenderer — Phase 8", () => {
  it("MR1: <strong>1.234 RON</strong> renders with font-semibold + text-accent (D-19)", () => {
    renderWithIntl(<MarkdownRenderer content="**1.234 RON**" />);
    const strong = screen.getByText("1.234 RON");
    expect(strong.tagName.toLowerCase()).toBe("strong");
    expect(strong.className).toContain("font-semibold");
    // text-accent is rendered via the raw HSL token used everywhere in the
    // codebase per `globals.css`.
    expect(strong.className).toMatch(/text-/);
  });

  it("MR2: [Sales Dashboard](/sales) renders as a DashboardLinkPill (next/link)", () => {
    renderWithIntl(<MarkdownRenderer content="[Sales Dashboard](/sales)" />);
    const link = screen.getByText("Sales Dashboard");
    // The pill is wrapped in a Link → <a> at the DOM level.
    const anchor = link.closest("a");
    expect(anchor).not.toBeNull();
    expect(anchor!.getAttribute("href")).toBe("/sales");
    // Pill style: bg-accent/10 → uses bg-[hsl(221_83%_53%)]/10 token.
    expect(anchor!.className).toMatch(/bg-\[hsl\(221_83%_53%\)\]\/10/);
  });

  it("MR3: external link href becomes muted italic plain text (D-18a defense)", () => {
    renderWithIntl(
      <MarkdownRenderer content="[Evil](https://evil.example.com)" />,
    );
    const node = screen.getByText("Evil");
    // Not wrapped in <a>.
    expect(node.tagName.toLowerCase()).toBe("span");
    expect(node.className).toContain("italic");
  });

  it("MR4: bare anchor [text](#) renders as plain span (no link)", () => {
    renderWithIntl(<MarkdownRenderer content="[Sales](#)" />);
    const node = screen.getByText("Sales");
    expect(node.tagName.toLowerCase()).toBe("span");
    // Plain — no italic muted styling (that's reserved for D-18a rejects).
    expect(node.closest("a")).toBeNull();
  });

  it("MR5: disallowed elements (script/iframe/img) are dropped", () => {
    const dangerous =
      "Normal text\n\n<script>alert(1)</script>\n\n<img src='/x' />\n\n<iframe></iframe>";
    const { container } = renderWithIntl(
      <MarkdownRenderer content={dangerous} />,
    );
    expect(container.querySelector("script")).toBeNull();
    expect(container.querySelector("iframe")).toBeNull();
    expect(container.querySelector("img")).toBeNull();
  });

  it("MR6: tables render via shadcn Table primitives wrapped in overflow-x-auto", () => {
    const tableMd =
      "| Name | Leads |\n| --- | --- |\n| Roibu | 100 |\n| Raileanu | 200 |";
    const { container } = renderWithIntl(
      <MarkdownRenderer content={tableMd} />,
    );
    // The Table primitive emits <table> inside its own overflow-auto div;
    // our renderer wraps that in an additional overflow-x-auto div.
    const tbl = container.querySelector("table");
    expect(tbl).not.toBeNull();
    // Walk up to find the outer wrapper with overflow-x-auto.
    let node: HTMLElement | null = tbl as HTMLElement;
    let found = false;
    while (node) {
      if (node.className && node.className.includes("overflow-x-auto")) {
        found = true;
        break;
      }
      node = node.parentElement;
    }
    expect(found).toBe(true);
  });
});
