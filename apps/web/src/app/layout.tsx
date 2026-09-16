import type {
  Metadata,
} from "next";

import "./globals.css";


export const metadata: Metadata = {
  title:
    "AgDA | Agricultural Data Assistant",

  description:
    "Evidence-backed agricultural intelligence from validated survey data.",
};


export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>
        {children}
      </body>
    </html>
  );
}