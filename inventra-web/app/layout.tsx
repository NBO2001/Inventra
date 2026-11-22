import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Inventra — suas compras, com clareza",
  description: "Entenda os gastos do mercado e planeje a próxima compra em Manaus.",
  robots: { index: false, follow: false },
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="pt-BR"><body>{children}</body></html>;
}
