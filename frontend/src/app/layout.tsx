import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import Navbar from "@/components/layout/Navbar";
import Footer from "@/components/layout/Footer";
import ChatWidget from "@/components/chat/ChatWidget";
import { LanguageProvider } from "@/context/LanguageContext";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: {
    default: "SevanaGPT - Find Government Schemes",
    template: "%s | SevanaGPT",
  },
  description:
    "Your AI-powered guide to Indian government schemes. Search from 2,300+ central and state government schemes across India.",
  keywords: [
    "government schemes",
    "India",
    "eligibility",
    "scholarships",
    "subsidies",
    "central government",
    "state government",
    "SevanaGPT",
  ],
  openGraph: {
    title: "SevanaGPT - Find Government Schemes",
    description:
      "Your AI-powered guide to Indian government schemes. Check your eligibility and apply.",
    type: "website",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className={`${geistSans.variable} ${geistMono.variable} antialiased`}>
        <LanguageProvider>
          <div className="min-h-screen flex flex-col">
            <Navbar />
            <main className="flex-1">{children}</main>
            <Footer />
          </div>
          <ChatWidget />
        </LanguageProvider>
      </body>
    </html>
  );
}
