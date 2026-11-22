import Link from "next/link";
import type { Metadata } from "next";

export const dynamic = "force-dynamic";
export const metadata: Metadata = {
  title: "Preços de supermercado em Manaus | Inventra",
  description: "Compare preços observados em compras de supermercado em Manaus, com data e informações do produto.",
  robots: { index: true, follow: true },
};

type Product = { name: string; unit: string; slug: string; observation_count: number; store_count: number; last_seen: string };

export default async function PublicPrices({ searchParams }: { searchParams: Promise<{ q?: string }> }) {
  const { q = "" } = await searchParams;
  let products: Product[] = [];
  try {
    const response = await fetch(`http://127.0.0.1:5000/api/public/products?q=${encodeURIComponent(q)}`, { cache: "no-store" });
    if (response.ok) products = (await response.json()).products;
  } catch { /* Show an empty state while the local API is offline. */ }
  return <div className="public-shell"><header><Link href="/" className="public-logo">◩ &nbsp; Inventra</Link><span>Manaus, Amazonas</span></header><main><div className="eyebrow">OBSERVAÇÕES DA COMUNIDADE</div><h1>Preços para a próxima compra.</h1><p>Valores pagos em supermercados de Manaus. São registros de compras anteriores: preço e estoque podem mudar.</p><form action="/prices"><input name="q" defaultValue={q} placeholder="Procure um produto" aria-label="Buscar produto"/><button type="submit">Buscar</button></form><div className="public-list">{products.length ? products.map((product) => <Link href={`/prices/${product.slug}`} key={product.slug}><strong>{product.name}</strong><span>{product.store_count} {product.store_count === 1 ? "mercado" : "mercados"} · {product.observation_count} {product.observation_count === 1 ? "observação" : "observações"} · última em {new Date(`${product.last_seen}T12:00:00`).toLocaleDateString("pt-BR")}</span><b>Ver preços →</b></Link>) : <div className="public-empty">Ainda não há preços compartilhados para esta busca.</div>}</div></main></div>;
}
