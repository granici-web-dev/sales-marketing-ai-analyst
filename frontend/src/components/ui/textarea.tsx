"use client";

// UI-SPEC § Component Inventory: pure native textarea wrapper, no radix dep.
// Pattern from `input.tsx`. The auto-grow logic lives on the caller side
// (chat-input.tsx).

import * as React from "react";

import { cn } from "@/lib/utils";

const Textarea = React.forwardRef<
  HTMLTextAreaElement,
  React.ComponentProps<"textarea">
>(({ className, ...props }, ref) => {
  return (
    <textarea
      className={cn(
        "flex min-h-[60px] w-full rounded-md border border-[hsl(240_6%_90%)] bg-background px-3 py-2 text-sm shadow-sm placeholder:text-[hsl(240_4%_46%)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[hsl(221_83%_53%)] disabled:cursor-not-allowed disabled:opacity-50",
        className,
      )}
      ref={ref}
      {...props}
    />
  );
});
Textarea.displayName = "Textarea";

export { Textarea };
