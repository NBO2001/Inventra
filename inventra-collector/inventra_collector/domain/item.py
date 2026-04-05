from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class Item:
    description: str
    value_unit: float
    quantity: float
    value_total: float
    unit: str
    key_access: str
    hash: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class Itens:
    itens: list[Item]

    def to_dict(self) -> dict:
        return {"itens": [item.to_dict() for item in self.itens]}
