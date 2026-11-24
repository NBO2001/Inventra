"use client";

import { useState } from "react";
import jsQR from "jsqr";

type Props = {
  onDecoded: (url: string) => void;
};

type Attempt = { width: number; height: number; found: boolean };

class QrCaptureError extends Error {
  constructor(message: string, readonly reason: string) {
    super(message);
  }
}

async function loadImage(file: File): Promise<HTMLImageElement> {
  const objectUrl = URL.createObjectURL(file);
  try {
    const image = new Image();
    await new Promise<void>((resolve, reject) => {
      image.onload = () => resolve();
      image.onerror = () => reject(new QrCaptureError("Não foi possível abrir esta imagem.", "image_load_failed"));
      image.src = objectUrl;
    });
    return image;
  } finally {
    URL.revokeObjectURL(objectUrl);
  }
}

async function readQr(file: File, attempts: Attempt[]): Promise<string> {
  const image = await loadImage(file);
  const canvas = document.createElement("canvas");
  const context = canvas.getContext("2d", { willReadFrequently: true });
  if (!context) throw new QrCaptureError("Seu navegador não conseguiu ler a imagem.", "canvas_unavailable");

  for (const maxSide of [1200, 2200]) {
    const scale = Math.min(1, maxSide / Math.max(image.naturalWidth, image.naturalHeight));
    canvas.width = Math.max(1, Math.round(image.naturalWidth * scale));
    canvas.height = Math.max(1, Math.round(image.naturalHeight * scale));
    context.drawImage(image, 0, 0, canvas.width, canvas.height);
    const pixels = context.getImageData(0, 0, canvas.width, canvas.height);
    const code = jsQR(pixels.data, pixels.width, pixels.height);
    attempts.push({ width: canvas.width, height: canvas.height, found: Boolean(code) });
    if (code) return code.data;
  }
  throw new QrCaptureError("Não encontrei o QR code. Aproxime a câmera e tente novamente.", "qr_not_found");
}

function validateSefazUrl(value: string): string {
  let url: URL;
  try {
    url = new URL(value);
  } catch {
    throw new QrCaptureError("O QR code não contém um link de NFC-e da SEFAZ-AM.", "invalid_url");
  }
  if (
    !["http:", "https:"].includes(url.protocol) ||
    url.hostname !== "sistemas.sefaz.am.gov.br" ||
    url.pathname !== "/nfceweb/consultarNFCe.jsp" ||
    !url.searchParams.get("p")
  ) {
    throw new QrCaptureError("Este QR code não é de uma NFC-e da SEFAZ-AM compatível.", "unsupported_qr_url");
  }
  return url.toString();
}

async function saveFailedCapture(file: File, reason: string, attempts: Attempt[]): Promise<string> {
  const form = new FormData();
  form.append("image", file);
  form.append("reason", reason);
  form.append("attempts", JSON.stringify(attempts));
  const response = await fetch("/api/qr-debug", { method: "POST", body: form });
  if (!response.ok) throw new Error(`Debug upload failed: ${response.status}`);
  const result = await response.json();
  return result.id;
}

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
    const attempts: Attempt[] = [];
    try {
      onDecoded(validateSefazUrl(await readQr(file, attempts)));
      console.info("QR capture decoded", { attempts });
    } catch (cause) {
      const reason = cause instanceof QrCaptureError ? cause.reason : "unexpected_error";
      setError(cause instanceof Error ? cause.message : "Não foi possível ler o QR code.");
      console.warn("QR capture failed", { reason, attempts, fileType: file.type, fileSize: file.size, error: cause });
      try {
        setDebugId(await saveFailedCapture(file, reason, attempts));
      } catch (saveError) {
        console.warn("Could not save failed QR image", saveError);
        setError((current) => `${current} Não foi possível salvar a imagem de diagnóstico.`);
      }
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
      <p>Fotografe o QR code de perto. Se a leitura falhar, a foto será enviada à API local e salva para diagnóstico.</p>
      {error && <p className="camera-error" role="alert">{error}</p>}
      {debugId && <p className="camera-error">Imagem de diagnóstico salva: {debugId}</p>}
    </div>
  );
}
