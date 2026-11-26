"""Simple Groq (gpt-oss) text-to-SQL agent for chicago_crime.db."""

import os
import re
from pathlib import Path

import requests

from app.db import get_connection

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
DEFAULT_GROQ_MODEL = os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b")
ENV_PATH = Path(__file__).resolve().parent.parent / ".env"


def _load_api_key(api_key: str | None = None) -> str:
    """Resolve Groq API key from argument, environment, or local .env file."""
    if api_key and api_key.strip():
        return api_key.strip()
    if os.environ.get("GROQ_API_KEY", "").strip():
        return os.environ["GROQ_API_KEY"].strip()
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("GROQ_API_KEY="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return ""


def get_tables_and_attributes() -> str:
    """Return every table/view name and its columns from SQLite."""
    conn = get_connection()
    try:
        items = conn.execute(
            """
            SELECT type, name
            FROM sqlite_master
            WHERE type IN ('table', 'view') AND name NOT LIKE 'sqlite_%'
            ORDER BY type, name
            """
        ).fetchall()
        lines = []
        for item in items:
            cols = conn.execute(f"PRAGMA table_info('{item['name']}')").fetchall()
            col_str = ", ".join(f"{c['name']} ({c['type'] or 'TEXT'})" for c in cols)
            lines.append(f"{item['type'].upper()} {item['name']}: {col_str}")
        return "\n".join(lines)
    finally:
        conn.close()


def _clean_sql(text: str) -> str:
    """Extract SQL from markdown fences if present."""
    cleaned = text.strip()
    match = re.search(r"```(?:sql)?\s*(.*?)```", cleaned, flags=re.DOTALL | re.IGNORECASE)
    if match:
        cleaned = match.group(1).strip()
    return cleaned.rstrip(";") + ";"


def _is_allowed_sql(sql: str) -> bool:
    """Allow SELECT, WITH, INSERT, UPDATE, and DELETE; block DDL/system commands."""
    upper = sql.strip().upper()
    allowed_starts = ("SELECT", "WITH", "INSERT", "UPDATE", "DELETE")
    if not upper.startswith(allowed_starts):
        return False
    blocked = ("DROP ", "ALTER ", "ATTACH ", "DETACH ", "PRAGMA ", "VACUUM ")
    return not any(word in upper for word in blocked)


def _call_groq(messages: list[dict], api_key: str, model: str = DEFAULT_GROQ_MODEL) -> str:
    """Call Groq chat completions endpoint using standard requests."""
    resp = requests.post(
        GROQ_API_URL,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": model,
            "messages": messages,
            "temperature": 0,
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"].strip()


def ask_ai_sql(question: str, api_key: str | None = None) -> dict:
    """Generate SQL with Groq (gpt-oss), run it (1 retry on SQL error), and answer."""
    key = _load_api_key(api_key)
    if not key:
        return {"error": "Missing Groq API key. Set GROQ_API_KEY, add it to .env, or enter it in the sidebar."}

    schema = get_tables_and_attributes()
    sql_messages = [
        {
            "role": "system",
            "content": (
                "You are a SQLite expert. Given the tables and attributes below, "
                "return ONLY one valid SQLite query (SELECT, INSERT, UPDATE, or DELETE) "
                "with no explanation.\n\n"
                f"{schema}"
            ),
        },
        {"role": "user", "content": question},
    ]

    sql = _clean_sql(_call_groq(sql_messages, key))
    rows: list[dict] = []
    affected_rows: int | None = None
    last_error: str | None = None

    # Run SQL; if SQLite returns an error, send error back to Groq once to fix SQL
    for attempt in range(2):
        if not _is_allowed_sql(sql):
            return {"sql": sql, "error": "Only SELECT, INSERT, UPDATE, and DELETE queries are allowed."}

        conn = get_connection()
        try:
            upper = sql.strip().upper()
            if upper.startswith(("SELECT", "WITH")):
                result = conn.execute(sql).fetchall()
                rows = [dict(r) for r in result[:50]]
            else:
                cur = conn.execute(sql)
                conn.commit()
                affected_rows = cur.rowcount
            last_error = None
            break
        except Exception as exc:
            last_error = str(exc)
            if attempt == 0:
                sql_messages.append({"role": "assistant", "content": sql})
                sql_messages.append(
                    {
                        "role": "user",
                        "content": f"SQLite error: {last_error}. Return ONLY the corrected SQLite query.",
                    }
                )
                sql = _clean_sql(_call_groq(sql_messages, key))
        finally:
            conn.close()

    if last_error:
        return {"sql": sql, "rows": [], "error": f"SQL error after retry: {last_error}"}

    result_context = (
        f"Affected rows: {affected_rows}"
        if affected_rows is not None
        else f"Result rows: {rows[:20]}"
    )
    answer_messages = [
        {
            "role": "system",
            "content": "Give a short, clear 1-3 sentence answer based only on the SQL execution result.",
        },
        {
            "role": "user",
            "content": f"Question: {question}\nSQL: {sql}\n{result_context}",
        },
    ]
    answer = _call_groq(answer_messages, key)
    return {
        "sql": sql,
        "rows": rows,
        "affected_rows": affected_rows,
        "answer": answer,
    }
