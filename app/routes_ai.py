"""Flask Blueprint for the Ask AI (Groq gpt-oss text-to-SQL) endpoint."""

from flask import Blueprint, jsonify, request

from app.ai_sql import ask_ai_sql

ai_bp = Blueprint("ai", __name__)


@ai_bp.route("/api/ask-ai", methods=["POST"])
def ask_ai():
    data = request.get_json(silent=True) or {}
    question = (data.get("question") or "").strip()
    api_key = (data.get("api_key") or "").strip() or None

    if not question:
        return jsonify({"error": "question is required"}), 400

    try:
        result = ask_ai_sql(question, api_key=api_key)
    except Exception as exc:
        return jsonify({"error": f"Groq API request failed: {exc}"}), 502

    status = 400 if "error" in result and not result.get("answer") else 200
    return jsonify(result), status
