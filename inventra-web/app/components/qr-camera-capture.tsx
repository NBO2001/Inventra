"use client";

import { useState } from "react";
import jsQR from "jsqr";

type Props = {
  onDecoded: (url: string) => void;
};

async function loadImage(file: File): Promise<HTMLImageElement> {
  const objectUrl = URL.createObjectURL(file);
  try {
    const image = new Image();
    await new Promise<void>((resolve, reject) => {
      image.onload = () => resolve();
      image.onerror = () => reject(new Error("Não foi possível abrir esta imagem."));
      image.src = objectUrl;
    });
    return image;
  } finally {
    URL.revokeObjectURL(objectUrl);
  }
}

async function readQr(file: File): Promise<string> {
  const image = await loadImage(file);
  const canvas = document.createElement("canvas");
  const context = canvas.getContext("2d", { willReadFrequently: true });
  if (!context) throw new Error("Seu navegador não conseguiu ler a imagem.");

  for (const maxSide of [1200, 2200]) {
    const scale = Math.min(1, maxSide / Math.max(image.naturalWidth, image.naturalHeight));
    canvas.width = Math.max(1, Math.round(image.naturalWidth * scale));
    canvas.height = Math.max(1, Math.round(image.naturalHeight * scale));
    context.drawImage(image, 0, 0, canvas.width, canvas.height);
    const pixels = context.getImageData(0, 0, canvas.width, canvas.height);
    const code = jsQR(pixels.data, pixels.width, pixels.height);
    if (code) return code.data;
  }
  throw new Error("Não encontrei o QR code. Aproxime a câmera e tente novamente.");
}

function validateSefazUrl(value: string): string {
  let url: URL;
  try {
    url = new URL(value);
  } catch {
    throw new Error("O QR code não contém um link de NFC-e da SEFAZ-AM.");
  }
  if (
    !["http:", "https:"].includes(url.protocol) ||
    url.hostname !== "sistemas.sefaz.am.gov.br" ||
    url.pathname !== "/nfceweb/consultarNFCe.jsp" ||
    !url.searchParams.get("p")
  ) {
    throw new Error("Este QR code não é de uma NFC-e da SEFAZ-AM compatível.");
  }
  return url.toString();
}

export default function QrCameraCapture({ onDecoded }: Props) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const handleImage = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const input = event.currentTarget;
    const file = input.files?.[0];
    if (!file) return;
    setBusy(true);
    setError("");
    try {
      onDecoded(validateSefazUrl(await readQr(file)));
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
      <p>Fotografe o QR code de perto. A imagem é lida no seu celular e não é enviada ao servidor.</p>
      {error && <p className="camera-error" role="alert">{error}</p>}
    </div>
  );
}
