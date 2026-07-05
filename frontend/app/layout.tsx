import type { Metadata } from "next";
import { Archivo, Fraunces } from "next/font/google";

import "./globals.css";

const display = Fraunces({
  subsets: ["latin"],
  weight: ["400", "600", "900"],
  style: ["normal", "italic"],
  variable: "--font-display",
  fallback: ["Georgia", "Times New Roman", "serif"],
  display: "swap",
});

const sans = Archivo({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-sans",
  fallback: ["ui-sans-serif", "system-ui", "sans-serif"],
  display: "swap",
});

export const metadata: Metadata = {
  title: "The Gambler Studio",
  description: "Cast and produce a multi-voice audiobook of The Gambler.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className={`${display.variable} ${sans.variable}`}>
      <body>
        <header className="masthead">
          <div className="shell masthead__row">
            <div className="wordmark">
              <span className="wordmark__mark">
                The <em>Gambler</em> Studio
              </span>
              <span className="wordmark__tag">Audiobook</span>
            </div>
            <span className="masthead__meta">Casting Room</span>
          </div>
        </header>
        <main className="shell">{children}</main>
      </body>
    </html>
  );
}
