"""Parse a saved SEFAZ-AM NFC-e consumer page without retaining its raw HTML."""

from __future__ import annotations

import re
from datetime import datetime
from decimal import Decimal, InvalidOperation

from bs4 import BeautifulSoup


class ReceiptParseError(ValueError):
    pass


def brl(value: str) -> Decimal:
    cleaned = re.sub(r"[^\d,.-]", "", value).replace(".", "").replace(",", ".")
    try:
        return Decimal(cleaned)
    except InvalidOperation as exc:
        raise ReceiptParseError(f"Invalid amount: {value!r}") from exc


def _text(element) -> str:
    return element.get_text(" ", strip=True) if element else ""


def _parse_item(row, index: int) -> dict:
    name = _text(row.select_one(".txtTit"))
    qty_text = _text(row.select_one(".Rqtd"))
    unit_text = _text(row.select_one(".RUN"))
    unit_price_text = _text(row.select_one(".RvlUnit"))
    amount_text = _text(row.select_one(".valor"))
    code_match = re.search(r"\d+", _text(row.select_one(".RCod")))
    try:
        quantity = brl(qty_text)
        unit_price = brl(unit_price_text)
        amount = brl(amount_text)
    except ReceiptParseError as exc:
        raise ReceiptParseError(f"Could not read item {index}.") from exc
    if not name or quantity <= 0 or amount < 0:
        raise ReceiptParseError(f"Invalid item {index}.")
    return {
        "name": name,
        "code": code_match.group() if code_match else None,
        "quantity": str(quantity),
        "unit": re.sub(r"^UN:\s*", "", unit_text, flags=re.I).strip(),
        "unit_price": str(unit_price),
        "amount": str(amount),
    }


def _parse_totals(soup) -> tuple[Decimal, Decimal]:
    total = None
    discount = Decimal("0")
    for row in soup.select("#totalNota div[id='linhaTotal']"):
        label = _text(row.select_one("label")).lower()
        value = _text(row.select_one("span.totalNumb"))
        if "valor a pagar" in label:
            total = brl(value)
        elif "descontos" in label:
            discount = brl(value)
    if total is None:
        raise ReceiptParseError("The payable total was not found.")
    return total, discount


def parse_receipt(html: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    if not soup.select_one("#tabResult tr[id^='Item']"):
        raise ReceiptParseError(
            "This does not look like a SEFAZ-AM itemized NFC-e page."
        )

    store = _text(soup.select_one(".txtTopo"))
    header = soup.select_one(".txtCenter")
    cnpj_match = re.search(r"CNPJ:\s*([\d./-]+)", _text(header))
    date_match = re.search(
        r"Emiss[aã]o:\s*(\d{2}/\d{2}/\d{4})", soup.get_text(" ", strip=True), re.I
    )
    key = re.sub(r"\D", "", _text(soup.select_one(".chave")))
    if len(key) != 44 or not store or not date_match:
        raise ReceiptParseError(
            "The receipt is missing its store, issue date, or access key."
        )

    items = [
        _parse_item(row, index)
        for index, row in enumerate(soup.select("#tabResult tr[id^='Item']"), 1)
    ]

    total, discount = _parse_totals(soup)

    tax_text = _text(soup.select_one(".spcTop .totalNumb.txtObs"))
    tax = brl(tax_text) if tax_text else None
    return {
        "store": store,
        "store_cnpj": cnpj_match.group(1) if cnpj_match else None,
        "issued_at": datetime.strptime(date_match.group(1), "%d/%m/%Y")
        .date()
        .isoformat(),
        "access_key": key,
        "total": str(total),
        "discount": str(discount),
        "approx_tax": str(tax) if tax is not None else None,
        "items": items,
    }
