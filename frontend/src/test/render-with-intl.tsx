// Test helper — renders a React tree with a real NextIntlClientProvider
// wired against `messages/ro.json` so component tests exercise the actual
// Romanian copy.

import { render, type RenderOptions } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import { type ReactElement } from "react";
import roMessages from "../../messages/ro.json";

export function renderWithIntl(
  ui: ReactElement,
  options?: RenderOptions,
): ReturnType<typeof render> {
  return render(
    <NextIntlClientProvider locale="ro" messages={roMessages}>
      {ui}
    </NextIntlClientProvider>,
    options,
  );
}
