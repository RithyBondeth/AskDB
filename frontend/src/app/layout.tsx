import type { Metadata } from "next";
import { Caveat, Geist_Mono, Nunito } from "next/font/google";
import "./globals.css";

// Handwritten face, used sparingly: the logo and the home headline.
const caveat = Caveat({
  variable: "--font-caveat",
  subsets: ["latin"],
  weight: ["600", "700"],
});

// Rounded, friendly, and easy to read: the interface font.
const nunito = Nunito({
  variable: "--font-nunito",
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
      className={`${caveat.variable} ${nunito.variable} ${geistMono.variable} h-full antialiased`}
    >
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeScript }} />
      </head>
      <body className="min-h-full flex flex-col font-sans">{children}</body>
    </html>
  );
}
