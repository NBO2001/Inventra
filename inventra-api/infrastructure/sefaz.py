"""Inventra API infrastructure module."""

from urllib.parse import parse_qs, urlparse
from urllib.request import Request, urlopen

from domain.receipt_parser import ReceiptParseError

SEFAZ_HOST = "sistemas.sefaz.am.gov.br"


def fetch_qr_url(url: str) -> str:
    parsed = urlparse(url.strip())
    if (
        parsed.scheme not in {"http", "https"}
        or parsed.hostname != SEFAZ_HOST
        or parsed.port not in (None, 443)
        or parsed.path != "/nfceweb/consultarNFCe.jsp"
        or "p" not in parse_qs(parsed.query)
    ):
        raise ReceiptParseError(
            "Use a SEFAZ-AM NFC-e QR link, or upload its saved HTML page."
        )
    # Older printed QR codes use HTTP. Upgrade locally before sending the access token.
    secure_url = parsed._replace(scheme="https").geturl()
    req = Request(
        secure_url, headers={"User-Agent": "Mozilla/5.0 receipt-consumer-prototype"}
    )
    with urlopen(req, timeout=12) as response:
        if urlparse(response.url).hostname != SEFAZ_HOST:
            raise ReceiptParseError("The receipt link redirected outside SEFAZ-AM.")
        raw = response.read(1_000_001)
    if len(raw) > 1_000_000:
        raise ReceiptParseError("The receipt page is too large.")
    return raw.decode("utf-8", errors="replace")
