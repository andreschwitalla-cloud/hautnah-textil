import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / 'hautnah.db'

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db() as db:
        db.executescript('''
            CREATE TABLE IF NOT EXISTS nachrichten (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                wa_id       TEXT NOT NULL,
                name        TEXT,
                telefon     TEXT,
                nachricht   TEXT NOT NULL,
                typ         TEXT DEFAULT 'eingehend',  -- eingehend / ausgehend
                status      TEXT DEFAULT 'neu',        -- neu / gelesen / beantwortet
                erstellt_am TEXT DEFAULT (datetime('now', 'localtime'))
            );

            CREATE TABLE IF NOT EXISTS anfragen (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                wa_id       TEXT NOT NULL,
                name        TEXT,
                druckart    TEXT,
                menge       TEXT,
                beschreibung TEXT,
                status      TEXT DEFAULT 'offen',  -- offen / in_bearbeitung / abgeschlossen
                erstellt_am TEXT DEFAULT (datetime('now', 'localtime'))
            );
        ''')
    print("Datenbank initialisiert.")
