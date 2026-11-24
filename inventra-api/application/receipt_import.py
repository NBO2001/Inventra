"""Prepare a receipt from uploaded HTML or a SEFAZ QR link."""

import re

from domain.receipt_parser import ReceiptParseError, parse_receipt
from infrastructure.sefaz import fetch_qr_url


def parse_receipt_source(html_bytes: bytes | None, qr_url: str, access_key: str):
    if html_bytes is not None:
        html = html_bytes.decode("utf-8", errors="replace")
    elif qr_url.strip():
        html = fetch_qr_url(qr_url)
    else:
        raise ReceiptParseError("Provide a SEFAZ-AM QR link or saved HTML page.")
    parsed = parse_receipt(html)
    typed_key = re.sub(r"\D", "", access_key)
    if typed_key and typed_key != parsed["access_key"]:
        raise ReceiptParseError("The access key does not match the receipt page.")
    return parsed
