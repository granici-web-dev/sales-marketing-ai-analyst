import * as React from "react";

import { cn } from "@/lib/utils";

/**
 * Высота та же, что у кнопки, и по той же причине.
 *
 * Поле — такая же цель нажатия, как кнопка, и D-24 не делает между ними
 * разницы. Но есть и вторая причина, чисто зрительная: поле и кнопка стоят
 * в одном ряду (`knowledge.tsx` — адрес страницы и «Добавить»), и поднять
 * одну кнопку до 44 px, оставив поле на 36, значило бы починить попадание
 * и сломать ряд.
 */
const Input = React.forwardRef<
  HTMLInputElement,
  React.ComponentProps<"input">
>(({ className, type, ...props }, ref) => {
  return (
    <input
      type={type}
      className={cn(
        "flex h-11 w-full rounded-md border border-border bg-transparent px-3 py-1 text-sm shadow-sm transition-colors file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50",
        className,
      )}
      ref={ref}
      {...props}
    />
  );
});
Input.displayName = "Input";

export { Input };
