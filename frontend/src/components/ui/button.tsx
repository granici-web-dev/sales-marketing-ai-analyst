import * as React from "react";
import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";

import { cn } from "@/lib/utils";

/**
 * Кнопка пришла из shadcn нетронутой: синяя заливка, белый текст, радиус 6 px.
 * Ни то, ни другое, ни третье не принадлежало этой дизайн-системе — карточки
 * скруглены на 14 px, а действие в ней обозначается почти-чёрным в светлой
 * теме и почти-белым в тёмной, а не синим из палитры Tailwind.
 *
 * Отдельно про белый текст: он был написан словом, а не токеном, поэтому
 * в тёмной теме оставался белым на почти-белой заливке. --primary-fg меняется
 * вместе с --primary и держит пару читаемой в обеих.
 */
const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-control text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:pointer-events-none disabled:opacity-50 [&_svg]:pointer-events-none [&_svg]:size-4 [&_svg]:shrink-0",
  {
    variants: {
      variant: {
        default:
          "bg-primary text-primary-foreground shadow-card hover:bg-primary-hover",
        destructive:
          "bg-danger text-destructive-foreground shadow-card hover:bg-danger/90",
        outline:
          "border border-border bg-card shadow-card hover:bg-muted hover:text-foreground",
        secondary:
          "bg-muted text-foreground shadow-card hover:bg-muted/70",
        ghost: "hover:bg-muted hover:text-foreground",
        link: "text-primary underline-offset-4 hover:underline",
      },
      size: {
        default: "h-9 px-4 py-2",
        sm: "h-8 rounded-control px-3 text-xs",
        lg: "h-10 rounded-control px-8",
        icon: "h-9 w-9",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  },
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean;
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : "button";
    return (
      <Comp
        className={cn(buttonVariants({ variant, size, className }))}
        ref={ref}
        {...props}
      />
    );
  },
);
Button.displayName = "Button";

export { Button, buttonVariants };
