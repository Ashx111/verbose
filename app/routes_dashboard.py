"""Dashboard analytics, PNG report export, health check, and '/' redirect to Streamlit."""

import io
import os
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns
from flask import Blueprint, jsonify, redirect, send_file

from app.db import get_connection

dashboard_bp = Blueprint("dashboard", __name__)

BASE_DIR = Path(__file__).resolve().parent.parent
EXPORTS_DIR = BASE_DIR / "exports" / "screenshots"
EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
STREAMLIT_URL = os.environ.get("STREAMLIT_URL", "http://127.0.0.1:8501/")


@dashboard_bp.route("/", methods=["GET"])
def home():
    """Redirect root '/' directly to the Streamlit dashboard."""
    return redirect(STREAMLIT_URL)


@dashboard_bp.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


def fetch_dashboard_data() -> dict:
    conn = get_connection()
    try:
        totals = conn.execute(
            """
            SELECT COUNT(*) AS total_crimes,
                   COALESCE(SUM(CASE WHEN arrest = 1 THEN 1 ELSE 0 END), 0) AS total_arrests
            FROM crime
            """
        ).fetchone()
        total_crimes = totals["total_crimes"]
        total_arrests = totals["total_arrests"]
        arrest_rate = round((total_arrests / total_crimes * 100.0), 2) if total_crimes else 0.0

        total_communities = conn.execute("SELECT COUNT(*) FROM community").fetchone()[0]

        yearly = [
            dict(r)
            for r in conn.execute(
                "SELECT Year, crime_count, arrest_count, arrest_rate FROM vw_crime_yearly ORDER BY Year"
            ).fetchall()
        ]

        top_categories = [
            dict(r)
            for r in conn.execute(
                """
                SELECT primary_type, crime_count, percentage
                FROM vw_crime_by_category
                ORDER BY crime_count DESC
                LIMIT 10
                """
            ).fetchall()
        ]

        top_communities = [
            dict(r)
            for r in conn.execute(
                """
                SELECT c.community_code,
                       COALESCE(c.community_name, 'Unknown') AS community_name,
                       COUNT(*) AS crime_count
                FROM crime f
                LEFT JOIN community c ON c.community_code = f.community_code
                GROUP BY c.community_code, c.community_name
                ORDER BY crime_count DESC
                LIMIT 10
                """
            ).fetchall()
        ]

        monthly_weekday = [
            dict(r)
            for r in conn.execute(
                """
                SELECT Month, DayOfWeek, COUNT(*) AS crime_count
                FROM crime
                GROUP BY Month, DayOfWeek
                ORDER BY Month, DayOfWeek
                """
            ).fetchall()
        ]

        top_crime = top_categories[0]["primary_type"] if top_categories else "N/A"
        top_comm = top_communities[0]["community_name"] if top_communities else "N/A"
        peak_year = max(yearly, key=lambda x: x["crime_count"])["Year"] if yearly else "N/A"

        insights = [
            f"Total recorded crimes: {total_crimes:,} across {total_communities} Chicago community areas.",
            f"Overall arrest rate is {arrest_rate}% ({total_arrests:,} arrests).",
            f"Most frequent crime category is {top_crime}.",
            f"Highest-crime community area is {top_comm}.",
            f"Peak crime year in the dataset is {peak_year}.",
        ]

        return {
            "kpis": {
                "total_crimes": total_crimes,
                "total_arrests": total_arrests,
                "arrest_rate": arrest_rate,
                "total_communities": total_communities,
                "top_crime_type": top_crime,
                "top_community": top_comm,
            },
            "yearly": yearly,
            "top_categories": top_categories,
            "top_communities": top_communities,
            "monthly_weekday": monthly_weekday,
            "insights": insights,
        }
    finally:
        conn.close()


@dashboard_bp.route("/api/dashboard", methods=["GET"])
def dashboard_data():
    return jsonify(fetch_dashboard_data())


@dashboard_bp.route("/api/dashboard/export", methods=["GET"])
def export_report():
    data = fetch_dashboard_data()
    sns.set_theme(style="whitegrid")
    fig, axes = plt.subplots(2, 2, figsize=(14, 9))
    fig.suptitle(
        "Chicago Crime Analytics Report (Use Cases 2-4)",
        fontsize=15,
        fontweight="bold",
    )

    yearly = data["yearly"]
    axes[0, 0].plot(
        [r["Year"] for r in yearly],
        [r["crime_count"] for r in yearly],
        marker="o",
        color="#1d4ed8",
        linewidth=2,
    )
    axes[0, 0].set_title("Crime Trend Over Years")
    axes[0, 0].set_xlabel("Year")
    axes[0, 0].set_ylabel("Crime Count")

    cats = list(reversed(data["top_categories"]))
    axes[0, 1].barh(
        [r["primary_type"] for r in cats],
        [r["crime_count"] for r in cats],
        color="#0f766e",
    )
    axes[0, 1].set_title("Top 10 Crime Categories")
    axes[0, 1].set_xlabel("Crime Count")

    axes[1, 0].bar(
        [str(r["Year"]) for r in yearly],
        [r["arrest_rate"] for r in yearly],
        color="#d97706",
    )
    axes[1, 0].set_title("Arrest Rate (%) by Year")
    axes[1, 0].set_xlabel("Year")
    axes[1, 0].set_ylabel("Arrest Rate (%)")

    comms = list(reversed(data["top_communities"]))
    axes[1, 1].barh(
        [r["community_name"] for r in comms],
        [r["crime_count"] for r in comms],
        color="#be123c",
    )
    axes[1, 1].set_title("Top 10 Community Areas")
    axes[1, 1].set_xlabel("Crime Count")

    insights_text = "Key Insights: " + " | ".join(data["insights"][:3])
    fig.text(0.5, 0.01, insights_text, ha="center", fontsize=9, color="#334155")
    plt.tight_layout(rect=[0, 0.04, 1, 0.95])

    report_path = EXPORTS_DIR / "chicago_crime_dashboard_report.png"
    fig.savefig(report_path, dpi=150)

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150)
    plt.close(fig)
    buf.seek(0)
    return send_file(
        buf,
        mimetype="image/png",
        as_attachment=True,
        download_name="chicago_crime_dashboard_report.png",
    )
