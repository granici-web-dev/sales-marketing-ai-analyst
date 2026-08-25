import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"

import { cn } from "@/lib/utils"

const badgeVariants = cva(
  "inline-flex items-center rounded-md border px-2.5 py-0.5 text-xs font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2",
  {
    variants: {
      variant: {
        default:
          "border-transparent bg-primary text-primary-foreground shadow hover:bg-primary/80",
        secondary:
          "border-transparent bg-secondary text-secondary-foreground hover:bg-secondary/80",
        destructive:
          "border-transparent bg-destructive text-destructive-foreground shadow hover:bg-destructive/80",
        outline: "text-foreground",
        /* Смысловые тона. Взяты из токенов, а не из палитры Tailwind:
           bg-yellow-100 с text-yellow-800 в тёмной теме нечитаемы, а
           --warn и --danger определены для обеих. Заливка на 12 %
           оставляет текст на полном токене выше 4.5:1. */
        danger: "border-danger/25 bg-danger/12 text-danger",
        warn: "border-warn/25 bg-warn/12 text-warn",
        ok: "border-ok/25 bg-ok/12 text-ok",
        /* Лайм означает выбранное и подтверждённое — то же, чем является
           недельный план: список действий, которые приняли к работе. */
        accent: "border-accent-strong/40 bg-accent/25 text-accent-foreground",
        /* Низкая важность цветом не помечается: порядок в списке уже
           несёт её, а третий оттенок рядом с двумя смысловыми читался бы
           как третья степень тревоги. */
        neutral: "border-border bg-muted text-muted-foreground",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  }
)

export interface BadgeProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, ...props }: BadgeProps) {
  return (
    <div className={cn(badgeVariants({ variant }), className)} {...props} />
  )
}

export { Badge, badgeVariants }
