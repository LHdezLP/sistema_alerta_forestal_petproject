"""SQLite local para historial de alertas."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "alerts.db"


def _conn() -> sqlite3.Connection:
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con


def init_db() -> None:
    with _conn() as con:
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                clase TEXT NOT NULL,
                confianza REAL NOT NULL,
                imagen_path TEXT,
                lat REAL,
                lon REAL,
                indice_riesgo REAL,
                nivel_riesgo TEXT
            )
            """
        )


def insertar_alerta(clase, confianza, imagen_path, lat, lon, indice, nivel) -> int:
    init_db()
    timestamp = datetime.now(timezone.utc).isoformat()
    with _conn() as con:
        cur = con.execute(
            """
            INSERT INTO alerts(timestamp, clase, confianza, imagen_path, lat, lon, indice_riesgo, nivel_riesgo)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (timestamp, clase, float(confianza), imagen_path, lat, lon, indice, nivel),
        )
        return int(cur.lastrowid)


def obtener_alertas(limite: int = 50, clase: str | None = None) -> list[dict]:
    init_db()
    with _conn() as con:
        if clase:
            rows = con.execute(
                "SELECT * FROM alerts WHERE clase = ? ORDER BY id DESC LIMIT ?",
                (clase, limite),
            ).fetchall()
        else:
            rows = con.execute("SELECT * FROM alerts ORDER BY id DESC LIMIT ?", (limite,)).fetchall()
    return [dict(r) for r in rows]


def obtener_ultima_alerta() -> dict | None:
    rows = obtener_alertas(1)
    return rows[0] if rows else None


def limpiar_alertas() -> int:
    init_db()
    with _conn() as con:
        cur = con.execute("SELECT COUNT(*) AS n FROM alerts")
        n = int(cur.fetchone()["n"])
        con.execute("DELETE FROM alerts")
        con.execute("DELETE FROM sqlite_sequence WHERE name = 'alerts'")
        return n
