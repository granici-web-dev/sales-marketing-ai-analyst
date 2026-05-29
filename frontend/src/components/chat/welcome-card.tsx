"use client";

// UI-SPEC § WelcomeCard — centered empty-state for the first-ever visit.
//
// H1 from i18n (chat.welcome.heading), body paragraph, plus the suggested-
// question chips inside the card. Mobile: H1 scales to text-xl per the
// Breakpoints table.

import { useTranslations } from "next-intl";
import { Card, CardContent } from "@/components/ui/card";
import { SuggestedQuestions } from "@/components/chat/suggested-questions";

interface WelcomeCardProps {
  onSelectQuestion: (question: string) => void;
}

export function WelcomeCard({ onSelectQuestion }: WelcomeCardProps) {
  const t = useTranslations("chat.welcome");

  return (
    <div className="flex flex-1 items-center justify-center px-4 py-12">
      <Card className="w-full max-w-2xl">
        <CardContent className="flex flex-col items-center gap-4 px-6 py-8 text-center">
          <h1 className="text-xl md:text-2xl font-semibold text-foreground">
            {t("heading")}
          </h1>
          <p className="text-sm text-[hsl(240_4%_46%)] max-w-prose">
            {t("body")}
          </p>
          <SuggestedQuestions onSelect={onSelectQuestion} />
        </CardContent>
      </Card>
    </div>
  );
}
