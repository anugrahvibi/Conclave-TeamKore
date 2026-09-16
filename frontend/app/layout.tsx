import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Conclave TeamKore Agro-Climate Platform",
  description: "Micro-climatic weather & field advisories for Kerala",
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
