"use client";

import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useTranslations } from "next-intl";
import { useRouter } from "next/navigation";
import { Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

function LoginForm() {
  const t = useTranslations("auth");
  const router = useRouter();
  const [authError, setAuthError] = useState<string | null>(null);

  const loginSchema = z.object({
    email: z.string().email(t("emailInvalid")),
    password: z.string().min(1, t("fieldRequired")),
  });

  type LoginFormData = z.infer<typeof loginSchema>;

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<LoginFormData>({
    resolver: zodResolver(loginSchema),
  });

  const onSubmit = async (data: LoginFormData) => {
    setAuthError(null);
    try {
      const response = await fetch("/api/v1/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: data.email, password: data.password }),
        credentials: "include",
      });

      if (response.ok) {
        const result = await response.json();
        // Store access token in non-HttpOnly cookie so proxy.ts can read it server-side (D-03, A1)
        document.cookie = `access_token=${result.access_token}; path=/; SameSite=Lax`;
        router.push("/");
      } else if (response.status === 401) {
        setAuthError(t("invalidCredentials"));
      } else {
        setAuthError(t("networkError"));
      }
    } catch {
      setAuthError(t("networkError"));
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-white">
      <div className="w-[400px] p-8 bg-[hsl(240_5%_96%)] rounded-xl border border-[hsl(240_6%_90%)]">
        {/* Wordmark */}
        <div className="mb-6 text-center">
          <h1 className="text-3xl font-semibold text-[hsl(240_10%_4%)]">
            {t("wordmark")}
          </h1>
          <p className="mt-1 text-sm text-[#71717A]">{t("subtitle")}</p>
        </div>

        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4" noValidate>
          {/* Email field */}
          <div className="space-y-1">
            <Label htmlFor="email" className="text-xs text-[hsl(240_10%_4%)]">
              {t("email")}
            </Label>
            <Input
              id="email"
              type="email"
              placeholder={t("emailPlaceholder")}
              autoComplete="email"
              aria-invalid={!!errors.email}
              {...register("email")}
              className={
                errors.email
                  ? "border-[#DC2626] focus-visible:ring-[#DC2626]"
                  : ""
              }
            />
            {errors.email && (
              <p className="text-xs text-[#DC2626]">{errors.email.message}</p>
            )}
          </div>

          {/* Password field */}
          <div className="space-y-1">
            <Label htmlFor="password" className="text-xs text-[hsl(240_10%_4%)]">
              {t("password")}
            </Label>
            <Input
              id="password"
              type="password"
              placeholder={t("passwordPlaceholder")}
              autoComplete="current-password"
              aria-invalid={!!errors.password}
              {...register("password")}
              className={
                errors.password
                  ? "border-[#DC2626] focus-visible:ring-[#DC2626]"
                  : ""
              }
            />
            {errors.password && (
              <p className="text-xs text-[#DC2626]">{errors.password.message}</p>
            )}
          </div>

          {/* Submit button */}
          <Button
            type="submit"
            className="w-full h-10 bg-[hsl(221_83%_53%)] hover:bg-[hsl(221_83%_45%)] text-white text-sm font-semibold"
            disabled={isSubmitting}
          >
            {isSubmitting && (
              <Loader2 size={16} className="animate-spin mr-2" aria-hidden="true" />
            )}
            {t("loginButton")}
          </Button>
        </form>

        {/* Auth error banner */}
        {authError && (
          <div
            className="mt-4 border-l-4 border-[#DC2626] bg-[#FEF2F2] px-4 py-3 text-[#DC2626] text-xs"
            role="alert"
          >
            {authError}
          </div>
        )}
      </div>
    </div>
  );
}

export default function LoginPage() {
  return <LoginForm />;
}
