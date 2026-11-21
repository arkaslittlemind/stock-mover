import type { Metadata } from "next";
import { Instrument_Sans, Instrument_Serif } from "next/font/google";
import "./globals.css";

const instrumentSans = Instrument_Sans({
  variable: "--font-instrument-sans",
  subsets: ["latin"],
});

const instrumentSerif = Instrument_Serif({
  variable: "--font-instrument-serif",
  weight: "400",
  style: ["normal", "italic"],
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
      className={`${instrumentSans.variable} ${instrumentSerif.variable} h-full antialiased motion-safe:scroll-smooth`}
    >
      <body className="flex min-h-full flex-col bg-ivory text-charcoal">{children}</body>
    </html>
  );
}
