"""Register the HTTP routes."""

from .catalog import bp as catalog_bp
from .planning import bp as planning_bp
from .qr import bp as qr_bp
from .receipts import bp as receipts_bp
from .settings import bp as settings_bp


def register_routes(app):
    for blueprint in (qr_bp, receipts_bp, settings_bp, catalog_bp, planning_bp):
        app.register_blueprint(blueprint)
