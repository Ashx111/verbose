"""Community dimension CRUD routes (GET, POST, PUT, PATCH, DELETE)."""

import sqlite3

from flask import Blueprint, jsonify, request

from app.db import get_connection

community_bp = Blueprint("community", __name__)

COMMUNITY_FIELDS = (
    "community_name",
    "population",
    "area_sqmile",
    "area_sqkm",
    "density_per_sqmi",
    "density_per_sqkm",
)


@community_bp.route("/api/community", methods=["GET"])
def list_communities():
    search = request.args.get("search", "").strip()
    conn = get_connection()
    try:
        if search:
            if not search.isdigit():
                return jsonify([])
            rows = conn.execute(
                """
                SELECT community_code, community_name, population,
                       area_sqmile, area_sqkm, density_per_sqmi, density_per_sqkm
                FROM community
                WHERE community_code = ?
                ORDER BY community_code
                """,
                (int(search),),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT community_code, community_name, population,
                       area_sqmile, area_sqkm, density_per_sqmi, density_per_sqkm
                FROM community
                ORDER BY community_code
                """
            ).fetchall()
        return jsonify([dict(r) for r in rows])
    finally:
        conn.close()


@community_bp.route("/api/community/<int:community_code>", methods=["GET"])
def get_community(community_code: int):
    conn = get_connection()
    try:
        row = conn.execute(
            """
            SELECT community_code, community_name, population,
                   area_sqmile, area_sqkm, density_per_sqmi, density_per_sqkm
            FROM community
            WHERE community_code = ?
            """,
            (community_code,),
        ).fetchone()
        if row is None:
            return jsonify({"error": f"Community {community_code} not found"}), 404
        return jsonify(dict(row))
    finally:
        conn.close()


@community_bp.route("/api/community", methods=["POST"])
def create_community():
    data = request.get_json(silent=True) or {}
    code = data.get("community_code")
    name = (data.get("community_name") or "").strip()

    if code is None or not name:
        return jsonify({"error": "community_code and community_name are required"}), 400

    conn = get_connection()
    try:
        if conn.execute(
            "SELECT community_code FROM community WHERE community_code = ?",
            (code,),
        ).fetchone():
            return jsonify({"error": f"Community code {code} already exists"}), 409

        if conn.execute(
            "SELECT community_code FROM community WHERE LOWER(community_name) = LOWER(?)",
            (name,),
        ).fetchone():
            return jsonify({"error": f"Community name '{name}' already exists"}), 409

        conn.execute(
            """
            INSERT INTO community (
                community_code, community_name, population,
                area_sqmile, area_sqkm, density_per_sqmi, density_per_sqkm
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                int(code),
                name,
                data.get("population"),
                data.get("area_sqmile"),
                data.get("area_sqkm"),
                data.get("density_per_sqmi"),
                data.get("density_per_sqkm"),
            ),
        )
        conn.commit()
        created = conn.execute(
            "SELECT * FROM community WHERE community_code = ?", (int(code),)
        ).fetchone()
        return jsonify(dict(created)), 201
    except sqlite3.IntegrityError as exc:
        return jsonify({"error": str(exc)}), 409
    finally:
        conn.close()


@community_bp.route("/api/community/<int:community_code>", methods=["PUT"])
def replace_community(community_code: int):
    data = request.get_json(silent=True) or {}
    name = (data.get("community_name") or "").strip()
    if not name:
        return jsonify({"error": "community_name is required for PUT"}), 400

    conn = get_connection()
    try:
        if (
            conn.execute(
                "SELECT community_code FROM community WHERE community_code = ?",
                (community_code,),
            ).fetchone()
            is None
        ):
            return jsonify({"error": f"Community {community_code} not found"}), 404

        if conn.execute(
            """
            SELECT community_code FROM community
            WHERE LOWER(community_name) = LOWER(?) AND community_code <> ?
            """,
            (name, community_code),
        ).fetchone():
            return jsonify({"error": f"Community name '{name}' already exists"}), 409

        conn.execute(
            """
            UPDATE community
            SET community_name = ?,
                population = ?,
                area_sqmile = ?,
                area_sqkm = ?,
                density_per_sqmi = ?,
                density_per_sqkm = ?
            WHERE community_code = ?
            """,
            (
                name,
                data.get("population"),
                data.get("area_sqmile"),
                data.get("area_sqkm"),
                data.get("density_per_sqmi"),
                data.get("density_per_sqkm"),
                community_code,
            ),
        )
        conn.commit()
        updated = conn.execute(
            "SELECT * FROM community WHERE community_code = ?", (community_code,)
        ).fetchone()
        return jsonify(dict(updated))
    finally:
        conn.close()


@community_bp.route("/api/community/<int:community_code>", methods=["PATCH"])
def patch_community(community_code: int):
    data = request.get_json(silent=True) or {}
    updates = {k: v for k, v in data.items() if k in COMMUNITY_FIELDS}
    if not updates:
        return jsonify({"error": "Provide at least one valid field to update"}), 400

    if "community_name" in updates:
        updates["community_name"] = (updates["community_name"] or "").strip()
        if not updates["community_name"]:
            return jsonify({"error": "community_name cannot be empty"}), 400

    conn = get_connection()
    try:
        if (
            conn.execute(
                "SELECT community_code FROM community WHERE community_code = ?",
                (community_code,),
            ).fetchone()
            is None
        ):
            return jsonify({"error": f"Community {community_code} not found"}), 404

        if "community_name" in updates and conn.execute(
            """
            SELECT community_code FROM community
            WHERE LOWER(community_name) = LOWER(?) AND community_code <> ?
            """,
            (updates["community_name"], community_code),
        ).fetchone():
            return (
                jsonify(
                    {"error": f"Community name '{updates['community_name']}' already exists"}
                ),
                409,
            )

        set_clause = ", ".join(f"{col} = ?" for col in updates)
        values = list(updates.values()) + [community_code]
        conn.execute(
            f"UPDATE community SET {set_clause} WHERE community_code = ?",
            values,
        )
        conn.commit()
        updated = conn.execute(
            "SELECT * FROM community WHERE community_code = ?", (community_code,)
        ).fetchone()
        return jsonify(dict(updated))
    finally:
        conn.close()


@community_bp.route("/api/community/<int:community_code>", methods=["DELETE"])
def delete_community(community_code: int):
    conn = get_connection()
    try:
        if (
            conn.execute(
                "SELECT community_code FROM community WHERE community_code = ?",
                (community_code,),
            ).fetchone()
            is None
        ):
            return jsonify({"error": f"Community {community_code} not found"}), 404

        conn.execute(
            "DELETE FROM community WHERE community_code = ?", (community_code,)
        )
        conn.commit()
        return jsonify({"deleted": community_code}), 200
    finally:
        conn.close()


@community_bp.route("/api/community/<int:community_code>/crime-summary", methods=["GET"])
def community_crime_summary(community_code: int):
    conn = get_connection()
    try:
        community = conn.execute(
            "SELECT community_code, community_name FROM community WHERE community_code = ?",
            (community_code,),
        ).fetchone()
        if community is None:
            return jsonify({"error": f"Community {community_code} not found"}), 404

        row = conn.execute(
            """
            SELECT COUNT(*) AS crime_count,
                   COALESCE(SUM(CASE WHEN arrest = 1 THEN 1 ELSE 0 END), 0) AS arrest_count
            FROM crime
            WHERE community_code = ?
            """,
            (community_code,),
        ).fetchone()
        return jsonify(
            {
                "community_code": community["community_code"],
                "community_name": community["community_name"],
                "crime_count": row["crime_count"],
                "arrest_count": row["arrest_count"],
            }
        )
    finally:
        conn.close()
