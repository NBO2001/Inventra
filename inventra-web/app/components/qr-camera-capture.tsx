"use client";

import { useState } from "react";

type Props = {
  onDecoded: (url: string) => void;
};

type DecodeResponse = { url?: string; error?: string; reason?: string; id?: string };

export default function QrCameraCapture({ onDecoded }: Props) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [debugId, setDebugId] = useState("");

  const handleImage = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const input = event.currentTarget;
    const file = input.files?.[0];
    if (!file) return;
    setBusy(true);
    setError("");
    setDebugId("");
    try {
      const form = new FormData();
      form.append("image", file);
      const response = await fetch("/api/qr/decode", { method: "POST", body: form });
      const result = (await response.json().catch(() => {
        throw new Error("Não foi possível acessar a API local. Verifique se ela está em execução.");
      })) as DecodeResponse;
      if (!response.ok || !result.url) {
        setDebugId(result.id ?? "");
        console.warn("QR decode failed", { reason: result.reason, id: result.id, status: response.status });
        throw new Error(result.error || "Não foi possível ler o QR code.");
      }
      onDecoded(result.url);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Não foi possível ler o QR code.");
    } finally {
      input.value = "";
      setBusy(false);
    }
  };

  return (
    <div className="camera-capture">
      <label className={`camera-button ${busy ? "busy" : ""}`}>
        <span className="camera-icon" aria-hidden="true">▣</span>
        <span>{busy ? "Lendo QR code..." : "Escanear QR com a câmera"}</span>
        <input type="file" accept="image/*" capture="environment" onChange={handleImage} disabled={busy} />
      </label>
      <p>Fotografe o QR code de perto. A foto é enviada à API local para leitura. Fotos com falha são salvas para diagnóstico.</p>
      {error && <p className="camera-error" role="alert">{error}</p>}
      {debugId && <p className="camera-error">Imagem de diagnóstico salva: {debugId}</p>}
    </div>
  );
}
