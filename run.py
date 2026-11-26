"""Launcher for the Flask backend (http://127.0.0.1:5000)."""

from app import app
from app.db import init_db

if __name__ == "__main__":
    init_db()
    app.run(host="127.0.0.1", port=5000, debug=True)
