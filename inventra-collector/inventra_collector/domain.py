from dataclasses import dataclass


@dataclass(frozen=True)
class Item:
    description: str
    value_unit: float
    quantity: float
    value_total: float
    unit: str
    key_access: str
    hash: str


@dataclass(frozen=True)
class Itens:
    itens: list[Item]
    collection_started_at: str
