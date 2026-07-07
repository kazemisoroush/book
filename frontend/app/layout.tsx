import type { Metadata } from "next";
import { Archivo, Fraunces } from "next/font/google";

import { ThemeToggle } from "@/components/ThemeToggle";

import "./globals.css";

// Applies the saved light theme before paint, so there is no flash of the dark default.
const themeScript = `try{if(localStorage.getItem('theme')==='light'){document.documentElement.dataset.theme='light';}}catch(e){}`;

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
  title: "Book Studio",
  description: "Cast and produce multi-voice audiobooks.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className={`${display.variable} ${sans.variable}`}>
      <body>
        <script dangerouslySetInnerHTML={{ __html: themeScript }} />
        <header className="masthead">
          <div className="shell masthead__row">
            <div className="wordmark">
              <span className="wordmark__mark">
                Book <em>Studio</em>
              </span>
              <span className="wordmark__tag">Audiobook</span>
            </div>
            <div className="masthead__actions">
              <span className="masthead__meta">Casting Room</span>
              <ThemeToggle />
            </div>
          </div>
        </header>
        <main className="shell">{children}</main>
      </body>
    </html>
  );
}
