"use client";

import { useEffect, useMemo, useState } from "react";
import QrCameraCapture from "./components/qr-camera-capture";

type Receipt = { id: number; store: string; issued_at: string; total: string; approx_tax: string | null; shared: number; item_count: number };
type Month = { month: string; spend: string; tax: string; count: number; tax_count: number };
type Dashboard = { receipts: Receipt[]; months: Month[]; available_store_count: number };
type Item = { name: string; code?: string | null; quantity: string; unit: string; unit_price: string; amount: string };
type Preview = { store: string; issued_at: string; total: string; discount: string; approx_tax: string | null; items: Item[] };
type Product = { product_key: string; name: string; unit: string; quantity: string; last_seen: string };
type Suggestion = { product_key: string; name: string; last_bought: string; typical_days: number; estimated_next: string };
type Observation = { name: string; unit: string; unit_price: string; store: string; issued_at: string };
type PlanItem = { name: string; quantity: string; amount: string; observed_at: string };
type Plan = { stores: Record<string, PlanItem[]>; missing: string[]; total: string; single_store_total: string | null; coverage: number; count: number } | null;
type Tab = "overview" | "import" | "plan" | "prices" | "settings";

const currency = (value: string | number | null | undefined) => value == null ? "—" : new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(Number(value));
const dateLabel = (value: string) => new Date(`${value}T12:00:00`).toLocaleDateString("pt-BR");
const monthLabel = (value: string) => new Date(`${value}-01T12:00:00`).toLocaleDateString("pt-BR", { month: "long", year: "numeric" });

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api${path}`, { cache: "no-store", ...init });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || "Não foi possível concluir a operação.");
  return data as T;
}

function Icon({ name, size = 20 }: { name: string; size?: number }) {
  const common = { width: size, height: size, viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", strokeWidth: 1.8, strokeLinecap: "round" as const, strokeLinejoin: "round" as const };
  const paths: Record<string, React.ReactNode> = {
    grid: <><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/></>,
    receipt: <><path d="M5 3h14v18l-3-2-4 2-4-2-3 2V3Z"/><path d="M9 8h6M9 12h6"/></>,
    cart: <><circle cx="9" cy="20" r="1"/><circle cx="19" cy="20" r="1"/><path d="M2 3h2l3 12h13l2-9H5"/></>,
    tag: <><path d="M3 12V4h8l10 10-7 7L3 12Z"/><circle cx="8" cy="8" r="1"/></>,
    settings: <><circle cx="12" cy="12" r="3"/><path d="M12 2v3m0 14v3M2 12h3m14 0h3M5 5l2 2m10 10 2 2M19 5l-2 2M7 17l-2 2"/></>,
    arrow: <><path d="M5 12h14m-6-6 6 6-6 6"/></>,
    plus: <><path d="M12 5v14M5 12h14"/></>,
    check: <path d="m5 12 4 4L19 6"/>,
    shield: <><path d="M12 2 4 5v6c0 5 3.3 8.3 8 11 4.7-2.7 8-6 8-11V5l-8-3Z"/><path d="m9 12 2 2 4-4"/></>,
    spark: <><path d="m12 2 2 7 7 3-7 2-2 8-2-8-7-2 7-3 2-7Z"/></>,
  };
  return <svg {...common} aria-hidden="true">{paths[name]}</svg>;
}

export default function Home() {
  const [tab, setTab] = useState<Tab>("overview");
  const [dashboard, setDashboard] = useState<Dashboard>({ receipts: [], months: [], available_store_count: 0 });
  const [shareMode, setShareMode] = useState<"ask" | "always" | "never">("ask");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [selectedReceipt, setSelectedReceipt] = useState<number | null>(null);
  const [receiptDetail, setReceiptDetail] = useState<{ receipt: Receipt; items: Item[] } | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [qrUrl, setQrUrl] = useState("");
  const [accessKey, setAccessKey] = useState("");
  const [preview, setPreview] = useState<Preview | null>(null);
  const [share, setShare] = useState(false);
  const [busy, setBusy] = useState(false);
  const [products, setProducts] = useState<Product[]>([]);
  const [suggestions, setSuggestions] = useState<Suggestion[]>([]);
  const [selectedProducts, setSelectedProducts] = useState<string[]>([]);
  const [quantities, setQuantities] = useState<Record<string, string>>({});
  const [maxStores, setMaxStores] = useState(1);
  const [plan, setPlan] = useState<Plan>(null);
  const [planAttempted, setPlanAttempted] = useState(false);
  const [priceQuery, setPriceQuery] = useState("");
  const [observations, setObservations] = useState<Observation[]>([]);

  const refresh = async () => {
    const [data, settings, catalog, refill] = await Promise.all([
      api<Dashboard>("/dashboard"),
      api<{ share_mode: "ask" | "always" | "never" }>("/settings"),
      api<{ products: Product[] }>("/products"),
      api<{ suggestions: Suggestion[] }>("/replenishment"),
    ]);
    setDashboard(data);
    setShareMode(settings.share_mode);
    setProducts(catalog.products);
    setSuggestions(refill.suggestions);
    setShare(settings.share_mode === "always");
  };

  useEffect(() => {
    refresh().catch((e) => setError(e.message)).finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (tab === "prices") api<{ observations: Observation[] }>(`/prices?q=${encodeURIComponent(priceQuery)}`).then((data) => setObservations(data.observations)).catch((e) => setError(e.message));
  }, [tab, priceQuery]);

  const openReceipt = async (id: number) => {
    setError("");
    try {
      const detail = await api<{ receipt: Receipt; items: Item[] }>(`/receipts/${id}`);
      setReceiptDetail(detail);
      setSelectedReceipt(id);
    } catch (e) { setError((e as Error).message); }
  };

  const sourceData = () => {
    const form = new FormData();
    if (file) form.append("receipt_html", file);
    if (qrUrl.trim()) form.append("qr_url", qrUrl.trim());
    if (accessKey.trim()) form.append("access_key", accessKey.trim());
    return form;
  };

  const previewImport = async () => {
    setBusy(true); setError(""); setPreview(null);
    try {
      const data = await api<{ receipt: Preview }>("/receipts/preview", { method: "POST", body: sourceData() });
      setPreview(data.receipt);
    } catch (e) {
      console.warn("Receipt preview failed", { source: file ? "html" : "qr_url", error: e });
      setError((e as Error).message);
    }
    finally { setBusy(false); }
  };

  const saveImport = async () => {
    setBusy(true); setError("");
    try {
      const form = sourceData(); form.append("share", share ? "yes" : "no");
      const data = await api<{ id: number }>("/receipts", { method: "POST", body: form });
      await refresh();
      setPreview(null); setFile(null); setQrUrl(""); setAccessKey("");
      setNotice("Nota adicionada ao seu histórico.");
      setTab("overview");
      await openReceipt(data.id);
    } catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  };

  const updateSharing = async (id: number, shared: boolean) => {
    try {
      await api(`/receipts/${id}/sharing`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ shared }) });
      await refresh(); await openReceipt(id);
      setNotice(shared ? "Preços desta nota compartilhados." : "Preços desta nota removidos da página pública.");
    } catch (e) { setError((e as Error).message); }
  };

  const saveSettings = async (mode: typeof shareMode) => {
    try {
      await api("/settings", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ share_mode: mode }) });
      setShareMode(mode); setShare(mode === "always");
      setNotice("Preferência salva para as próximas notas.");
    } catch (e) { setError((e as Error).message); }
  };

  const runPlan = async () => {
    setBusy(true); setError("");
    try {
      const data = await api<{ plan: Plan }>("/plan", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ products: selectedProducts, quantities, max_stores: maxStores }) });
      setPlan(data.plan);
      setPlanAttempted(true);
    } catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  };

  const dismissSuggestion = async (productKey: string) => {
    try {
      await api("/replenishment/dismiss", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ product_key: productKey }) });
      setSuggestions((current) => current.filter((item) => item.product_key !== productKey));
    } catch (e) { setError((e as Error).message); }
  };

  const totalSpend = useMemo(() => dashboard.months.reduce((sum, month) => sum + Number(month.spend), 0), [dashboard]);
  const totalTax = useMemo(() => dashboard.months.reduce((sum, month) => sum + Number(month.tax), 0), [dashboard]);
  const nav: { id: Tab; label: string; icon: string }[] = [
    { id: "overview", label: "Visão geral", icon: "grid" },
    { id: "import", label: "Adicionar nota", icon: "receipt" },
    { id: "plan", label: "Próxima compra", icon: "cart" },
    { id: "prices", label: "Preços da comunidade", icon: "tag" },
    { id: "settings", label: "Configurações", icon: "settings" },
  ];

  return <div className="shell">
    <aside className="sidebar">
      <div className="brand"><div className="brand-mark"><Icon name="cart" size={22}/></div><div><strong>Inventra</strong><small>COMPRAS COM CONTEXTO</small></div></div>
      <div className="side-heading">SEU ESPAÇO</div>
      <nav aria-label="Navegação principal">{nav.map((item) => <button key={item.id} className={`nav-item ${tab === item.id ? "active" : ""}`} onClick={() => { setTab(item.id); setError(""); setNotice(""); }}><Icon name={item.icon}/><span>{item.label}</span>{item.id === "import" && <Icon name="plus" size={15}/>}</button>)}</nav>
      <div className="sidebar-bottom"><div className="local-badge"><Icon name="shield" size={18}/><div><strong>Protótipo local</strong><span>Suas notas ficam neste computador.</span></div></div><div className="location">◉ &nbsp; Manaus, Amazonas</div></div>
    </aside>

    <main className="main">
      <div className="topbar"><div className="crumb">Inventra <span>/</span> {nav.find((item) => item.id === tab)?.label}</div><div className="top-actions"><span className="today">{new Date().toLocaleDateString("pt-BR", { day: "numeric", month: "long", year: "numeric" })}</span><div className="avatar">IN</div></div></div>
      {error && <div className="alert error" role="alert">{error}<button onClick={() => setError("")}>×</button></div>}
      {notice && <div className="alert success" role="status">{notice}<button onClick={() => setNotice("")}>×</button></div>}

      {tab === "overview" && <section>
        <div className="hero"><div><div className="eyebrow light">SEU DINHEIRO, MAIS CLARO</div><h1>Entenda suas compras.<br/><em>Planeje a próxima.</em></h1><p>Cada nota vira uma visão melhor dos seus gastos e uma decisão mais inteligente para a próxima ida ao mercado.</p><button className="button white" onClick={() => setTab("import")}>Adicionar uma nota <Icon name="arrow" size={17}/></button></div><div className="hero-art"><div className="art-circle one"/><div className="art-circle two"/><div className="hero-card"><span>GASTOS DO MÊS</span><strong>{currency(dashboard.months[0]?.spend ?? 0)}</strong><small>em {dashboard.months[0] ? monthLabel(dashboard.months[0].month) : "suas compras"}</small><div className="hero-bars"><i/><i/><i/><i/><i/><i/><i/></div></div></div></div>
        <div className="section-heading"><div><div className="eyebrow">VISÃO GERAL</div><h2>Seu resumo</h2></div><span className="subtle">Todas as notas, todos os mercados</span></div>
        <div className="stat-grid"><div className="stat-card"><div className="stat-icon mint"><Icon name="cart"/></div><span>Gasto registrado</span><strong>{currency(totalSpend)}</strong><small>{dashboard.receipts.length} {dashboard.receipts.length === 1 ? "nota importada" : "notas importadas"}</small></div><div className="stat-card"><div className="stat-icon sand"><Icon name="receipt"/></div><span>Tributos aproximados</span><strong>{currency(totalTax)}</strong><small>Soma dos valores informados nas notas</small></div><div className="stat-card"><div className="stat-icon lavender"><Icon name="tag"/></div><span>Mercados visitados</span><strong>{new Set(dashboard.receipts.map((r) => r.store)).size}</strong><small>Em todo o seu histórico</small></div></div>
        <div className="content-grid"><div className="panel"><div className="panel-head"><div><h3>Evolução mensal</h3><p>Gasto e tributos aproximados, somando todos os mercados</p></div></div>{dashboard.months.length ? <div className="month-list">{dashboard.months.map((month) => <div className="month-row" key={month.month}><div><strong>{monthLabel(month.month)}</strong><small>{month.count} {month.count === 1 ? "nota" : "notas"} · tributos em {month.tax_count}/{month.count}</small></div><div className="month-values"><strong>{currency(month.spend)}</strong><small>{currency(month.tax)} em tributos aprox.</small></div></div>)}</div> : <Empty title="Ainda não há compras" text="Adicione sua primeira nota para acompanhar seus gastos mês a mês." action={() => setTab("import")}/>}</div><div className="panel recent"><div className="panel-head"><div><h3>Notas recentes</h3><p>Seu histórico de compras</p></div></div>{dashboard.receipts.length ? dashboard.receipts.slice(0, 5).map((receipt) => <button className="receipt-row" key={receipt.id} onClick={() => openReceipt(receipt.id)}><div className="receipt-icon"><Icon name="receipt"/></div><div><strong>{receipt.store}</strong><small>{dateLabel(receipt.issued_at)} · {receipt.item_count} itens</small></div><b>{currency(receipt.total)}</b></button>) : <Empty title="Tudo começa com uma nota" text="Importe uma NFC-e para ver os detalhes aqui." action={() => setTab("import")}/>}</div></div>
      </section>}

      {tab === "import" && <section className="narrow"><div className="eyebrow">PASSO 01 · IMPORTAR</div><h1 className="page-title">Uma nota, muito mais clareza.</h1><p className="lead">Use o link do QR code da NFC-e ou envie a página HTML salva do portal da SEFAZ-AM. Confira os dados antes de guardar.</p><div className="panel form-panel"><h3>De onde vem sua nota?</h3><QrCameraCapture onDecoded={(url) => { setQrUrl(url); setFile(null); setPreview(null); setError(""); }}/><div className="form-grid"><label>Link do QR code <span>cole a URL da SEFAZ-AM</span><input type="url" value={qrUrl} onChange={(e) => { setQrUrl(e.target.value); setPreview(null); }} placeholder="https://sistemas.sefaz.am.gov.br/nfceweb/..." /></label><div className="or">OU</div><label className="file-drop"><Icon name="receipt" size={28}/><strong>{file ? file.name : "Escolher página HTML"}</strong><span>Arquivo salvo do portal da SEFAZ-AM · até 1 MB</span><input type="file" accept=".html,.htm,text/html" onChange={(e) => { setFile(e.target.files?.[0] ?? null); setPreview(null); }}/></label></div><label className="key-label">Chave de acesso <span>opcional: confere se a nota é a correta</span><input value={accessKey} onChange={(e) => setAccessKey(e.target.value)} inputMode="numeric" maxLength={54} placeholder="44 dígitos"/></label><p className="help">A consulta pela chave no portal pode pedir CAPTCHA. Nesse caso, abra a nota na SEFAZ-AM, salve a página HTML e envie o arquivo acima.</p><button className="button primary" disabled={busy || (!file && !qrUrl.trim())} onClick={previewImport}>{busy ? "Lendo nota..." : "Conferir nota"}<Icon name="arrow" size={17}/></button></div>
        {preview && <div className="panel preview"><div className="panel-head"><div><div className="eyebrow">PASSO 02 · CONFERIR</div><h3>{preview.store}</h3><p>{dateLabel(preview.issued_at)} · {preview.items.length} itens</p></div><div className="big-number">{currency(preview.total)}</div></div><div className="preview-items">{preview.items.map((item, index) => <div className="preview-item" key={index}><span>{item.name}<small>{item.quantity} {item.unit} × {currency(item.unit_price)}</small></span><strong>{currency(item.amount)}</strong></div>)}</div><div className="preview-total"><span>Tributos aproximados informados na nota</span><strong>{currency(preview.approx_tax)}</strong></div><div className="sharing-choice"><div><strong>Contribuir com preços para Manaus?</strong><p>Somente item, preço, mercado e data aproximada. Seus dados pessoais e a nota completa não serão publicados.</p></div><label className="toggle"><input type="checkbox" checked={share} onChange={(e) => setShare(e.target.checked)}/><span/></label></div><button className="button primary" disabled={busy} onClick={saveImport}>{busy ? "Salvando..." : "Salvar no meu histórico"}<Icon name="check" size={17}/></button></div>}
      </section>}

      {tab === "plan" && <section><div className="eyebrow">SUA PRÓXIMA IDA AO MERCADO</div><h1 className="page-title">Monte a lista. Compare o caminho.</h1><p className="lead">Escolha seus itens e quantos supermercados você aceita visitar. Os preços são observações de compras anteriores, sujeitos a mudança.</p><div className="suggestions">{suggestions.length > 0 && <><div className="eyebrow">PODE ESTAR ACABANDO</div><div className="suggestion-list">{suggestions.map((item) => <div className="suggestion" key={item.product_key}><div><strong>{item.name}</strong><small>Última compra: {dateLabel(item.last_bought)} · intervalo típico: {item.typical_days} dias</small></div><button onClick={() => { setSelectedProducts((current) => current.includes(item.product_key) ? current : [...current, item.product_key]); setPlan(null); }}>Adicionar à lista</button><button className="dismiss" onClick={() => dismissSuggestion(item.product_key)}>Dispensar</button></div>)}</div></>}</div><div className="content-grid plan-grid"><div className="panel"><div className="panel-head"><div><h3>Itens da sua lista</h3><p>Baseados nas suas notas importadas</p></div><span className="count-pill">{selectedProducts.length} selecionados</span></div>{products.length ? <div className="product-list">{products.map((product) => <div className="product-line" key={product.product_key}><label><input type="checkbox" checked={selectedProducts.includes(product.product_key)} onChange={(e) => { setSelectedProducts((current) => e.target.checked ? [...current, product.product_key] : current.filter((key) => key !== product.product_key)); setPlan(null); setPlanAttempted(false); }}/><span><strong>{product.name}</strong><small>Última compra: {dateLabel(product.last_seen)}</small></span></label><input className="qty" aria-label={`Quantidade de ${product.name}`} type="number" min="0.001" step="0.001" value={quantities[product.product_key] ?? product.quantity} onChange={(e) => setQuantities((current) => ({ ...current, [product.product_key]: e.target.value }))}/></div>)}</div> : <Empty title="Sua lista está vazia" text="Importe uma nota para escolher itens da próxima compra." action={() => setTab("import")}/>}</div><div className="plan-side"><div className="panel"><h3>Quantos mercados?</h3><p className="muted">O limite é seu. Usaremos menos se não houver economia estimada.</p><div className="store-selector">{Array.from({ length: Math.max(1, Math.min(20, dashboard.available_store_count)) }, (_, index) => index + 1).map((n) => <button key={n} className={maxStores === n ? "selected" : ""} onClick={() => { setMaxStores(n); setPlan(null); setPlanAttempted(false); }}>{n}</button>)}</div><button className="button primary wide" disabled={busy || selectedProducts.length === 0} onClick={runPlan}>{busy ? "Comparando..." : "Comparar opções"}<Icon name="arrow" size={17}/></button></div>{plan && <div className="panel result"><div className="eyebrow">MELHOR ESTIMATIVA DISPONÍVEL</div><h3>{currency(plan.total)}</h3>{plan.single_store_total && Object.keys(plan.stores).length > 1 && <p>Um mercado: {currency(plan.single_store_total)} · economia estimada: {currency(Number(plan.single_store_total) - Number(plan.total))}</p>}<p>{plan.coverage}/{plan.count} itens com preço observado · {Object.keys(plan.stores).length} {Object.keys(plan.stores).length === 1 ? "mercado" : "mercados"}</p>{Object.entries(plan.stores).map(([store, items]) => <div className="store-result" key={store}><strong>{store}</strong>{items.map((item, i) => <div key={i}><span>{item.name} <small>· {dateLabel(item.observed_at)}</small></span><b>{currency(item.amount)}</b></div>)}</div>)}{plan.missing.length > 0 && <div className="missing"><strong>Sem preço comparável</strong><p>{plan.missing.join(", ")}</p></div>}<small className="disclaimer">Estimativa parcial; não inclui deslocamento nem garante preço ou estoque atual.</small></div>}{!plan && <div className="tip"><Icon name="spark"/><p>{planAttempted ? "Ainda não há preços compartilhados dos últimos 30 dias para esses itens. Experimente outra lista ou aguarde novas contribuições." : "Compartilhar preços das notas ajuda a melhorar as comparações para todos."}</p></div>}</div></div></section>}

      {tab === "prices" && <section><div className="eyebrow">PREÇOS OBSERVADOS EM MANAUS</div><h1 className="page-title">Compare com contexto.</h1><p className="lead">Preços compartilhados por pessoas que aceitaram contribuir. Sempre confira a data e o tamanho da embalagem.</p><div className="search-box"><Icon name="tag"/><input aria-label="Buscar produto" value={priceQuery} onChange={(e) => setPriceQuery(e.target.value)} placeholder="Busque um produto, marca ou embalagem"/></div><div className="panel"><div className="panel-head"><div><h3>Observações recentes</h3><p>{observations.length} registros encontrados</p></div></div>{observations.length ? <div className="price-table"><div className="table-head"><span>PRODUTO</span><span>SUPERMERCADO</span><span>OBSERVADO EM</span><span>PREÇO UNIT.</span></div>{observations.map((obs, i) => <div className="table-row" key={i}><strong>{obs.name}<small>{obs.unit}</small></strong><span>{obs.store}</span><span>{dateLabel(obs.issued_at)}</span><b>{currency(obs.unit_price)}</b></div>)}</div> : <Empty title="Ainda não há preços compartilhados" text="Ao importar uma nota, você pode contribuir com preços sem publicar seus dados pessoais." action={() => setTab("import")}/>}</div></section>}

      {tab === "settings" && <section className="narrow"><div className="eyebrow">SUAS PREFERÊNCIAS</div><h1 className="page-title">Você decide o que compartilha.</h1><p className="lead">Esta escolha vale somente para notas futuras. Você pode mudar a decisão em uma nota específica depois.</p><div className="panel settings-panel"><h3>Compartilhamento de preços</h3><p>Publicamos apenas produto, preço, supermercado e data aproximada. Nunca a nota completa ou os dados do consumidor.</p>{([ ["ask", "Perguntar em cada nota", "Escolha ao importar cada nova nota."], ["always", "Compartilhar notas futuras", "Ative expressamente e confira a escolha em cada importação."], ["never", "Não compartilhar notas futuras", "Mantenha seus preços somente no histórico privado."] ] as const).map(([mode, title, description]) => <button className={`setting-option ${shareMode === mode ? "selected" : ""}`} key={mode} onClick={() => saveSettings(mode)}><span className="radio"><i/></span><span><strong>{title}</strong><small>{description}</small></span></button>)}</div><div className="privacy-note"><Icon name="shield"/><p>Você pode retirar uma contribuição abrindo a nota no seu histórico. Páginas já armazenadas por buscadores podem demorar para desaparecer.</p></div></section>}

      {selectedReceipt && receiptDetail && <div className="modal-backdrop" onClick={() => setSelectedReceipt(null)}><div className="modal" role="dialog" aria-modal="true" aria-label="Detalhes da nota" onClick={(e) => e.stopPropagation()}><button className="close" onClick={() => setSelectedReceipt(null)}>×</button><div className="eyebrow">NOTA FISCAL</div><h2>{receiptDetail.receipt.store}</h2><p>{dateLabel(receiptDetail.receipt.issued_at)} · {receiptDetail.items.length} itens</p><div className="modal-summary"><div><span>VALOR PAGO</span><strong>{currency(receiptDetail.receipt.total)}</strong></div><div><span>TRIBUTOS APROX.</span><strong>{currency(receiptDetail.receipt.approx_tax)}</strong></div></div><div className="modal-items">{receiptDetail.items.map((item, i) => <div key={i}><span>{item.name}<small>{item.quantity} {item.unit}</small></span><strong>{currency(item.amount)}</strong></div>)}</div><div className="modal-sharing"><div><strong>Preços públicos</strong><small>{receiptDetail.receipt.shared ? "Compartilhados sem seus dados pessoais" : "Somente no seu histórico"}</small></div><button className="button secondary" onClick={() => updateSharing(receiptDetail.receipt.id, !receiptDetail.receipt.shared)}>{receiptDetail.receipt.shared ? "Retirar contribuição" : "Compartilhar preços"}</button></div></div></div>}
      {loading && <div className="loading">Carregando suas compras...</div>}
    </main>
  </div>;
}

function Empty({ title, text, action }: { title: string; text: string; action: () => void }) {
  return <div className="empty"><div className="empty-icon"><Icon name="receipt" size={27}/></div><strong>{title}</strong><p>{text}</p><button onClick={action}>Adicionar nota <Icon name="arrow" size={15}/></button></div>;
}
