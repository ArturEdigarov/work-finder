import type { Metadata } from "next";
import { NextIntlClientProvider } from "next-intl";
import { getLocale } from "next-intl/server";
import { Fira_Sans, Fira_Sans_Extra_Condensed } from "next/font/google";

import "./globals.css";

// Fira (Erik Spiekermann): technical German signage feel, with Cyrillic for RU/UK.
const text = Fira_Sans({
  subsets: ["latin", "latin-ext", "cyrillic"],
  weight: ["400", "500", "600"],
  variable: "--font-text",
});
const display = Fira_Sans_Extra_Condensed({
  subsets: ["latin", "latin-ext", "cyrillic"],
  weight: ["500", "700"],
  variable: "--font-display",
});

export const metadata: Metadata = {
  title: "work-finder",
  description: "Job search assistant for the German market",
};

export default async function RootLayout({ children }: LayoutProps<"/">) {
  const locale = await getLocale();
  return (
    <html lang={locale} className={`${text.variable} ${display.variable}`}>
      <body>
        <NextIntlClientProvider>{children}</NextIntlClientProvider>
      </body>
    </html>
  );
}
