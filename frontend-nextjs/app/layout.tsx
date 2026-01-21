import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import { Analytics } from "@vercel/analytics/react";
import { ApolloProvider } from "@/lib/providers/ApolloProvider";
import { AuthProvider } from "@/lib/providers/AuthProvider";
import { FilterProvider } from "@/lib/providers/FilterProvider";
import { AISearchProvider } from "@/lib/providers/AISearchProvider";
import { Header } from "@/components/Header";
import { Toaster } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { CommandPalette, AISearchWrapper } from "@/components/ClientComponents";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "CardWatch - Auction Aggregator",
  description: "Browse and track auction items from multiple auction houses",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" data-theme="charcoal-blue">
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased min-h-screen bg-bg`}
      >
        <AuthProvider>
          <ApolloProvider>
            <FilterProvider>
              <AISearchProvider>
                <TooltipProvider>
                  <Header />
                  <div className="pb-20">{children}</div>
                  <CommandPalette />
                  <AISearchWrapper />
                  <Toaster richColors position="bottom-right" />
                </TooltipProvider>
              </AISearchProvider>
            </FilterProvider>
          </ApolloProvider>
        </AuthProvider>
        <Analytics />
      </body>
    </html>
  );
}
