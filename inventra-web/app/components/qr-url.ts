export class QrCaptureError extends Error {
  readonly reason: string;

  constructor(message: string, reason: string) {
    super(message);
    this.reason = reason;
  }
}

export function validateSefazUrl(value: string): string {
  let url: URL;
  try {
    const trimmed = value.trim();
    const normalized = /^sistemas\.sefaz\.am\.gov\.br\//i.test(trimmed)
      ? `https://${trimmed}`
      : trimmed;
    url = new URL(normalized);
  } catch {
    throw new QrCaptureError("O QR code não contém um link de NFC-e da SEFAZ-AM.", "invalid_url");
  }
  if (
    !["http:", "https:"].includes(url.protocol) ||
    url.hostname !== "sistemas.sefaz.am.gov.br" ||
    (url.port !== "" && url.port !== "443") ||
    url.pathname !== "/nfceweb/consultarNFCe.jsp" ||
    !url.searchParams.get("p")
  ) {
    throw new QrCaptureError("Este QR code não é de uma NFC-e da SEFAZ-AM compatível.", "unsupported_qr_url");
  }
  return url.toString();
}
