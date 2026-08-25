import type { Metadata } from "next";
import { Inter } from "next/font/google";
import { NextIntlClientProvider } from "next-intl";
import { Agentation } from "agentation";
import "./globals.css";

const inter = Inter({ subsets: ["latin"] });

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
    <html lang="ro">
      <body className={inter.className}>
        <NextIntlClientProvider>{children}</NextIntlClientProvider>
        {process.env.NODE_ENV === "development" && <Agentation endpoint="http://localhost:4747" />}
      </body>
    </html>
  );
}
