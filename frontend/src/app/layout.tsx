import type { Metadata } from "next";
import { Caveat, Geist_Mono, Shantell_Sans } from "next/font/google";
import "./globals.css";

// Handwritten display face for headings.
const caveat = Caveat({
  variable: "--font-caveat",
  subsets: ["latin"],
  weight: ["600", "700"],
});

// Informal but very readable face for the interface.
const shantell = Shantell_Sans({
  variable: "--font-shantell",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "AskDB",
  description: "Ask your database questions in plain English.",
};

// Apply the saved theme before first paint so there is no flash.
const themeScript = `try{var t=localStorage.getItem("askdb-theme");if(t==="light"||t==="dark")document.documentElement.dataset.theme=t}catch(e){}`;

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="en"
      suppressHydrationWarning
      className={`${caveat.variable} ${shantell.variable} ${geistMono.variable} h-full antialiased`}
    >
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeScript }} />
      </head>
      <body className="min-h-full flex flex-col font-sans">{children}</body>
    </html>
  );
}
