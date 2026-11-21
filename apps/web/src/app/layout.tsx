import type { Metadata } from "next";
import { Caveat, IBM_Plex_Mono, Inter, Newsreader } from "next/font/google";
import { SmoothScroll } from "@/components/SmoothScroll";
import "./globals.css";

const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
});

const newsreader = Newsreader({
  variable: "--font-newsreader",
  weight: ["300", "400"],
  style: ["normal", "italic"],
  subsets: ["latin"],
});

const plexMono = IBM_Plex_Mono({
  variable: "--font-plex-mono",
  weight: ["400", "500"],
  subsets: ["latin"],
});

const caveat = Caveat({
  variable: "--font-caveat",
  weight: "500",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Stock Mover · Today's stock moves",
  description:
    "Daily warehouse, store-to-store and pull-back moves for Manyavar merchandisers, checked and ready to approve.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="en"
      className={`${inter.variable} ${newsreader.variable} ${plexMono.variable} ${caveat.variable} h-full antialiased`}
    >
      <body className="flex min-h-full flex-col bg-white text-charcoal">
        <SmoothScroll />
        {children}
      </body>
    </html>
  );
}
