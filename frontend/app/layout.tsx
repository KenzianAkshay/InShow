import type { Metadata } from "next";
import { GeistSans } from "geist/font/sans";
import { GeistMono } from "geist/font/mono";
import "./globals.css";
import { Providers } from "./providers";
import NavBar from "./components/NavBar";
import MetalBackground from "./components/metal/MetalBackground";

export const metadata: Metadata = {
  title: "ShowSphere",
  description: "Exhibitor Services Agent Platform",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html
      lang="en"
      suppressHydrationWarning
      className={`${GeistSans.variable} ${GeistMono.variable}`}
    >
      <body>
        <Providers>
          <MetalBackground />
          <NavBar />
          {children}
        </Providers>
      </body>
    </html>
  );
}
