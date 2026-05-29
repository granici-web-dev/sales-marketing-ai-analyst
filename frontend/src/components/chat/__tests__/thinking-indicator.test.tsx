import { describe, it, expect } from "vitest";
import { screen } from "@testing-library/react";
import { renderWithIntl } from "@/test/render-with-intl";
import { ThinkingIndicator } from "@/components/chat/thinking-indicator";

/**
 * UI-SPEC § States Matrix → ThinkingIndicator (TI1-TI5).
 */
describe("ThinkingIndicator — Phase 8", () => {
  it("TI1: state=thinking renders 3 pulse dots and no label", () => {
    renderWithIntl(<ThinkingIndicator state="thinking" />);
    const dots = screen.getAllByTestId("dot");
    expect(dots).toHaveLength(3);
    // No textual label in the thinking state.
    expect(screen.queryByText(/Caut datele/)).toBeNull();
    expect(screen.queryByText(/Verific cifrele/)).toBeNull();
  });

  it("TI2: state=looking-up renders 3 dots + 'Caut datele...' label", () => {
    renderWithIntl(<ThinkingIndicator state="looking-up" />);
    expect(screen.getAllByTestId("dot")).toHaveLength(3);
    expect(screen.getByText(/Caut datele/)).toBeInTheDocument();
  });

  it("TI3: state=verifying-numbers renders 3 dots + 'Verific cifrele...' label", () => {
    renderWithIntl(<ThinkingIndicator state="verifying-numbers" />);
    expect(screen.getAllByTestId("dot")).toHaveLength(3);
    expect(screen.getByText(/Verific cifrele/)).toBeInTheDocument();
  });

  it("TI4: outer span has role=status aria-live=polite", () => {
    renderWithIntl(<ThinkingIndicator state="thinking" />);
    const status = screen.getByRole("status");
    expect(status).toBeInTheDocument();
    expect(status).toHaveAttribute("aria-live", "polite");
  });

  it("TI5: dots carry the motion-safe:animate-pulse class (reduced-motion safety)", () => {
    renderWithIntl(<ThinkingIndicator state="thinking" />);
    const dots = screen.getAllByTestId("dot");
    for (const dot of dots) {
      expect(dot.className).toContain("motion-safe:animate-pulse");
    }
  });
});
