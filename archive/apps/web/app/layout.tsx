import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "SHOWME — Build and test a process model",
  description: "Build a reviewed process model from a task video, inspect learner attempts, and test alternative step orders.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
