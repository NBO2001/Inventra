"""One-time, repeatable import of receipts from the old SQLite prototype."""

import argparse
import os
import sqlite3
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

from migrate import DEFAULT_URL, migrate


def import_sqlite(source: Path, database_url: str = DEFAULT_URL) -> int:
    if not source.is_file():
        raise FileNotFoundError(source)
    migrate(database_url)
    with sqlite3.connect(f"file:{source.resolve()}?mode=ro", uri=True) as old:
        old.row_factory = sqlite3.Row
        with psycopg.connect(database_url, row_factory=dict_row) as new:
            old_settings = old.execute(
                "SELECT share_mode FROM settings WHERE id = 1"
            ).fetchone()
            if old_settings:
                new.execute(
                    "UPDATE settings SET share_mode = %s WHERE id = 1",
                    (old_settings["share_mode"],),
                )
            imported = 0
            for receipt in old.execute("SELECT * FROM receipts ORDER BY id"):
                created = new.execute(
                    """INSERT INTO receipts
                    (key_hash, store, store_cnpj, issued_at, total, discount,
                     approx_tax, shared, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (key_hash) DO NOTHING RETURNING id""",
                    tuple(
                        receipt[key]
                        for key in (
                            "key_hash",
                            "store",
                            "store_cnpj",
                            "issued_at",
                            "total",
                            "discount",
                            "approx_tax",
                            "shared",
                            "created_at",
                        )
                    ),
                ).fetchone()
                if not created:
                    continue
                imported += 1
                for item in old.execute(
                    "SELECT * FROM items WHERE receipt_id = ? ORDER BY id",
                    (receipt["id"],),
                ):
                    new.execute(
                        """INSERT INTO items
                        (receipt_id, name, product_key, code, quantity, unit,
                         unit_price, amount)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                        (
                            created["id"],
                            *(
                                item[key]
                                for key in (
                                    "name",
                                    "product_key",
                                    "code",
                                    "quantity",
                                    "unit",
                                    "unit_price",
                                    "amount",
                                )
                            ),
                        ),
                    )
            for dismissed in old.execute("SELECT * FROM dismissed_suggestions"):
                new.execute(
                    """INSERT INTO dismissed_suggestions (product_key, last_bought)
                    VALUES (%s, %s) ON CONFLICT (product_key) DO NOTHING""",
                    (dismissed["product_key"], dismissed["last_bought"]),
                )
    return imported


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="Path to the old receipts.sqlite3")
    parser.add_argument(
        "--database-url", default=os.environ.get("DATABASE_URL", DEFAULT_URL)
    )
    args = parser.parse_args()
    print(f"Imported {import_sqlite(args.source, args.database_url)} receipts")
