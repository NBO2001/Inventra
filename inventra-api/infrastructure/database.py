"""Inventra API infrastructure module."""

import psycopg
from psycopg.rows import dict_row
from flask import current_app, g


def db():
    if "db" not in g:
        g.db = psycopg.connect(current_app.config["DATABASE_URL"], row_factory=dict_row)
    return g.db


def close_db(_error):
    connection = g.pop("db", None)
    if connection:
        connection.close()
