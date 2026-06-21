import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "MediBot",
  description: "QnA chatbot UI for RAG backend",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
