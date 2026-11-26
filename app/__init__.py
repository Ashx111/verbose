"""Flask application factory and blueprint registration."""

from flask import Flask

from app.routes_ai import ai_bp
from app.routes_community import community_bp
from app.routes_dashboard import dashboard_bp


def create_app() -> Flask:
    flask_app = Flask(__name__)
    flask_app.register_blueprint(dashboard_bp)
    flask_app.register_blueprint(community_bp)
    flask_app.register_blueprint(ai_bp)
    return flask_app


app = create_app()
