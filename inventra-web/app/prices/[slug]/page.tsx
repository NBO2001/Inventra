import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

export const dynamic = "force-dynamic";

type Product = { name: string; unit: string; observation_count: number; receipt_count: number; store_count: number; observations: { store: string; issued_at: string; unit_price: string }[] };

async function getProduct(slug: string): Promise<Product | null> {
  try {
    const response = await fetch(`http://127.0.0.1:5000/api/public/products/${slug}`, { cache: "no-store" });
    return response.ok ? (await response.json()).product : null;
  } catch { return null; }
}

export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }): Promise<Metadata> {
  const { slug } = await params;
  const product = await getProduct(slug);
  if (!product) return { title: "Produto não encontrado", robots: { index: false } };
  return { title: `${product.name} — preços em Manaus | Inventra`,
    description: `Compare ${product.observation_count} preços observados para ${product.name} em supermercados de Manaus.`,
    robots: { index: product.receipt_count >= 2, follow: true } };
}

export default async function ProductPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const product = await getProduct(slug);
  if (!product) notFound();
  const currency = (value: string) => new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(Number(value));
  return <div className="public-shell"><header><Link href="/" className="public-logo">◩ &nbsp; Inventra</Link><span>Manaus, Amazonas</span></header><main><Link href="/prices" className="back-link">← Todos os produtos</Link><div className="eyebrow">PREÇOS OBSERVADOS</div><h1>{product.name}</h1><p>{product.observation_count} {product.observation_count === 1 ? "observação" : "observações"} em {product.store_count} {product.store_count === 1 ? "supermercado" : "supermercados"}. Compare a mesma embalagem e confira a data.</p><div className="public-list">{product.observations.map((observation, index) => <div className="public-observation" key={index}><strong>{observation.store}</strong><span>Compra em {new Date(`${observation.issued_at}T12:00:00`).toLocaleDateString("pt-BR")} · {product.unit}</span><b>{currency(observation.unit_price)}</b></div>)}</div><p className="public-footnote">Estes são preços pagos em compras anteriores. Não garantem o preço atual nem a disponibilidade do produto.</p></main></div>;
}
