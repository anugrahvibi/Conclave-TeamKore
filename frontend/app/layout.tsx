import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Village Weather & Agro-Advisory Engine",
  description: "Hyper-local weather downscaling & agro-advisory platform",
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
      className="font-sans h-full antialiased"
    >
      <body suppressHydrationWarning className="min-h-full flex flex-col">
        {children}
      </body>
    </html>
  );
}
