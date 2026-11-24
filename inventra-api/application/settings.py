"""Inventra API application module."""

from infrastructure.database import db


def setting():
    return (
        db()
        .execute("SELECT share_mode FROM settings WHERE id = 1")
        .fetchone()["share_mode"]
    )
