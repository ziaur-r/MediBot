import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "MediAssist - Enterprise Medical Assistant",
  description: "Enterprise medical assistant with RBAC-enforced hybrid retrieval and analytics",
  viewport: "width=device-width, initial-scale=1, maximum-scale=1",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body style={{ margin: 0, padding: 0, height: "100vh", overflow: "hidden" }}>
        {children}
      </body>
    </html>
  );
}
