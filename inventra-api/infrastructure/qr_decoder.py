"""Decode NFC-e QR photos without persisting successful images or QR payloads."""

from io import BytesIO
import re
from urllib.parse import parse_qs, urlsplit, urlunsplit

from PIL import Image, ImageOps, UnidentifiedImageError
import zxingcpp

SEFAZ_HOST = "sistemas.sefaz.am.gov.br"
SEFAZ_PATH = "/nfceweb/consultarNFCe.jsp"


class QrDecodeError(ValueError):
    def __init__(self, reason: str, message: str, attempts=None):
        super().__init__(message)
        self.reason = reason
        self.attempts = attempts or []


def normalize_qr_url(value: str) -> str:
    value = value.strip()
    if re.match(r"^sistemas\.sefaz\.am\.gov\.br/", value, re.IGNORECASE):
        value = "https://" + value
    try:
        parsed = urlsplit(value)
        valid = (
            parsed.scheme in {"http", "https"}
            and parsed.hostname == SEFAZ_HOST
            and parsed.port in (None, 443)
            and parsed.username is None
            and parsed.password is None
            and parsed.path == SEFAZ_PATH
            and bool(parse_qs(parsed.query).get("p"))
        )
    except ValueError:
        valid = False
    if not valid:
        raise QrDecodeError(
            "unsupported_qr_url", "O QR code não contém um link de NFC-e da SEFAZ-AM."
        )
    return urlunsplit(parsed._replace(scheme="https"))


def decode_qr_image(data: bytes) -> tuple[str, list[dict]]:
    try:
        image = Image.open(BytesIO(data))
        if image.width * image.height > 25_000_000:
            raise QrDecodeError("image_too_large", "A imagem é grande demais para ler.")
        image.load()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise QrDecodeError(
            "invalid_image", "Não foi possível abrir esta imagem."
        ) from exc

    upright = ImageOps.exif_transpose(image)
    resized = upright.copy()
    resized.thumbnail((2200, 2200), Image.Resampling.LANCZOS)
    attempts = []
    unsupported = False
    for name, candidate in (("original", image), ("upright_resized", resized)):
        codes = zxingcpp.read_barcodes(candidate, formats=zxingcpp.BarcodeFormat.QRCode)
        attempts.append(
            {
                "variant": name,
                "width": candidate.width,
                "height": candidate.height,
                "found": bool(codes),
            }
        )
        for code in codes:
            try:
                return normalize_qr_url(code.text), attempts
            except QrDecodeError:
                unsupported = True
    if unsupported:
        raise QrDecodeError(
            "unsupported_qr_url",
            "O QR code não contém um link de NFC-e da SEFAZ-AM.",
            attempts,
        )
    raise QrDecodeError(
        "qr_not_found",
        "Não encontrei o QR code. Fotografe-o de perto e espere a câmera focar.",
        attempts,
    )
