import * as React from "react";
import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";

import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[hsl(221_83%_53%)] disabled:pointer-events-none disabled:opacity-50 [&_svg]:pointer-events-none [&_svg]:size-4 [&_svg]:shrink-0",
  {
    variants: {
      variant: {
        default:
          "bg-[hsl(221_83%_53%)] text-white shadow hover:bg-[hsl(221_83%_45%)]",
        destructive:
          "bg-[hsl(0_72%_51%)] text-white shadow-sm hover:bg-[hsl(0_72%_45%)]",
        outline:
          "border border-[hsl(240_6%_90%)] bg-white shadow-sm hover:bg-[hsl(240_5%_96%)] hover:text-[hsl(240_10%_4%)]",
        secondary:
          "bg-[hsl(240_5%_96%)] text-[hsl(240_10%_4%)] shadow-sm hover:bg-[hsl(240_5%_92%)]",
        ghost: "hover:bg-[hsl(240_5%_96%)] hover:text-[hsl(240_10%_4%)]",
        link: "text-[hsl(221_83%_53%)] underline-offset-4 hover:underline",
      },
      size: {
        default: "h-9 px-4 py-2",
        sm: "h-8 rounded-md px-3 text-xs",
        lg: "h-10 rounded-md px-8",
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
