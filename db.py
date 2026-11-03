"""
Хранилище устройств и их местоположений (SQLite).

Это согласная модель: каждое устройство само присылает свои координаты,
когда у него открыто приложение. Никакого доступа к чужим телефонам без их
участия здесь нет и быть не может.
"""

import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path

DB_PATH = Path(__file__).parent / "devices.db"


@contextmanager
def _conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with _conn() as c:
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS devices (
                phone       TEXT PRIMARY KEY,   -- номер = идентификатор устройства
                name        TEXT,               -- человекочитаемое имя
                lat         REAL,
                lon         REAL,
                accuracy    REAL,               -- точность GPS в метрах
                updated_at  REAL,               -- unix-время последнего обновления
                ring        INTEGER DEFAULT 0   -- 1 = попросили подать звуковой сигнал
            )
            """
        )


def normalize_phone(phone: str) -> str:
    """Приводим номер к единому виду: оставляем цифры и ведущий +."""
    phone = (phone or "").strip()
    keep = []
    for i, ch in enumerate(phone):
        if ch.isdigit():
            keep.append(ch)
        elif ch == "+" and i == 0:
            keep.append(ch)
    return "".join(keep)


def register_device(phone: str, name: str = ""):
    """Добавить/обновить устройство (при добавлении по номеру)."""
    phone = normalize_phone(phone)
    if not phone:
        return
    with _conn() as c:
        row = c.execute("SELECT phone FROM devices WHERE phone = ?", (phone,)).fetchone()
        if row:
            if name:
                c.execute("UPDATE devices SET name = ? WHERE phone = ?", (name, phone))
        else:
            c.execute(
                "INSERT INTO devices (phone, name, updated_at, ring) VALUES (?, ?, ?, 0)",
                (phone, name or phone, time.time()),
            )


def update_location(phone: str, lat: float, lon: float, accuracy: float = None):
    """Устройство прислало свои координаты."""
    phone = normalize_phone(phone)
    if not phone:
        return
    with _conn() as c:
        c.execute(
            """
            INSERT INTO devices (phone, name, lat, lon, accuracy, updated_at, ring)
            VALUES (?, ?, ?, ?, ?, ?, 0)
            ON CONFLICT(phone) DO UPDATE SET
                lat = excluded.lat,
                lon = excluded.lon,
                accuracy = excluded.accuracy,
                updated_at = excluded.updated_at
            """,
            (phone, phone, lat, lon, accuracy, time.time()),
        )


def list_devices():
    with _conn() as c:
        return [dict(r) for r in c.execute("SELECT * FROM devices ORDER BY updated_at DESC").fetchall()]


def get_device(phone: str):
    phone = normalize_phone(phone)
    with _conn() as c:
        row = c.execute("SELECT * FROM devices WHERE phone = ?", (phone,)).fetchone()
        return dict(row) if row else None


def request_ring(phone: str):
    """Попросить устройство подать звуковой сигнал (громкий звонок)."""
    phone = normalize_phone(phone)
    with _conn() as c:
        c.execute("UPDATE devices SET ring = 1 WHERE phone = ?", (phone,))


def clear_ring(phone: str):
    """Устройство отыграло сигнал — сбрасываем флаг."""
    phone = normalize_phone(phone)
    with _conn() as c:
        c.execute("UPDATE devices SET ring = 0 WHERE phone = ?", (phone,))


def remove_device(phone: str):
    phone = normalize_phone(phone)
    with _conn() as c:
        c.execute("DELETE FROM devices WHERE phone = ?", (phone,))
