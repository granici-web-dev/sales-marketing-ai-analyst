import type { Metadata } from "next";
import { Geist, Inter } from "next/font/google";
import { NextIntlClientProvider } from "next-intl";
import { Agentation } from "agentation";
import "./globals.css";

/* Geist с Inter в запасе — та же пара, что в портале Davoq. Оба подключены
   переменными, а не классом: `font-sans` в globals.css собирает из них стек,
   и шрифт остаётся частью системы токенов, а не отдельным решением в
   разметке. */
const geist = Geist({ subsets: ["latin"], variable: "--font-geist", display: "swap" });
const inter = Inter({ subsets: ["latin"], variable: "--font-inter", display: "swap" });

export const metadata: Metadata = {
  title: "Sofa Belle — Analytics",
  description: "Sales & Marketing AI Analyst for Sofa Belle",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="ro" className={`${geist.variable} ${inter.variable}`}>
      <body className="font-sans">
        <NextIntlClientProvider>{children}</NextIntlClientProvider>
        {process.env.NODE_ENV === "development" && <Agentation endpoint="http://localhost:4747" />}
      </body>
    </html>
  );
}
