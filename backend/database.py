import sqlite3, json
from pathlib import Path

DB_PATH = Path(__file__).parent / 'hautnah.db'

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db() as db:
        db.executescript('''
            -- Aktive Bot-Sessions (State Machine pro User)
            CREATE TABLE IF NOT EXISTS sessions (
                wa_id       TEXT PRIMARY KEY,
                name        TEXT,
                flow        TEXT,      -- 1-6 oder NULL (im Hauptmenü)
                step        INTEGER DEFAULT 0,
                artikel_step INTEGER DEFAULT 0,
                data        TEXT DEFAULT '{}',   -- JSON: gesammelte Felder
                artikel     TEXT DEFAULT '[]',   -- JSON: Liste der Artikel
                erstellt_am TEXT DEFAULT (datetime('now','localtime')),
                aktualisiert TEXT DEFAULT (datetime('now','localtime'))
            );

            -- Abgeschlossene Formulare
            CREATE TABLE IF NOT EXISTS formulare (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                wa_id       TEXT NOT NULL,
                name        TEXT,
                typ         TEXT NOT NULL,  -- bestellung/angebot/liefertermin/feedback/kontakt
                data        TEXT NOT NULL,  -- JSON
                status      TEXT DEFAULT 'neu',  -- neu/gelesen/erledigt
                erstellt_am TEXT DEFAULT (datetime('now','localtime'))
            );

            -- Gelöschte Formulare (Papierkorb, auto-clear nach 30 Tagen)
            CREATE TABLE IF NOT EXISTS formulare_geloescht (
                id          INTEGER PRIMARY KEY,
                wa_id       TEXT NOT NULL,
                name        TEXT,
                typ         TEXT NOT NULL,
                data        TEXT NOT NULL,
                status      TEXT,
                erstellt_am TEXT,
                geloescht_am TEXT DEFAULT (datetime('now','localtime'))
            );

            -- Nachrichtenlog
            CREATE TABLE IF NOT EXISTS nachrichten (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                wa_id       TEXT NOT NULL,
                name        TEXT,
                nachricht   TEXT NOT NULL,
                typ         TEXT DEFAULT 'eingehend',  -- eingehend/ausgehend
                status      TEXT DEFAULT 'neu',
                erstellt_am TEXT DEFAULT (datetime('now','localtime'))
            );

            -- Produktkatalog (Stanno-Import; speist Kontaktformular & später Shop)
            CREATE TABLE IF NOT EXISTS produkte (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                ean           TEXT,
                artikelnummer TEXT,
                marke         TEXT,
                bezeichnung   TEXT,
                groesse       TEXT,
                hauptfarbe    TEXT,
                farbe         TEXT,
                beschreibung  TEXT,
                preis         TEXT,
                materialspez  TEXT,
                bilder        TEXT,   -- JSON-Liste nicht-leerer Bild-URLs
                link          TEXT,
                herkunft      TEXT,
                hs_code       TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_produkte_ean   ON produkte(ean);
            CREATE INDEX IF NOT EXISTS idx_produkte_artnr ON produkte(artikelnummer);
        ''')
    # Migration: neue Spalten nachrüsten falls noch nicht vorhanden
    with get_db() as db:
        for col, definition in [('antwort', 'TEXT'), ('beantwortet_am', 'TEXT')]:
            try:
                db.execute(f'ALTER TABLE formulare ADD COLUMN {col} {definition}')
            except Exception:
                pass
    print("Datenbank initialisiert.")

# ── Session Helpers ───────────────────────────────────────────────────────────

def session_get(wa_id: str) -> dict:
    with get_db() as db:
        row = db.execute('SELECT * FROM sessions WHERE wa_id=?', (wa_id,)).fetchone()
        if row:
            d = dict(row)
            d['data']    = json.loads(d['data'] or '{}')
            d['artikel'] = json.loads(d['artikel'] or '[]')
            return d
    return {'wa_id': wa_id, 'name': None, 'flow': None, 'step': 0,
            'artikel_step': 0, 'data': {}, 'artikel': []}

def session_save(s: dict):
    with get_db() as db:
        db.execute('''
            INSERT INTO sessions (wa_id, name, flow, step, artikel_step, data, artikel, aktualisiert)
            VALUES (:wa_id,:name,:flow,:step,:artikel_step,:data,:artikel,datetime('now','localtime'))
            ON CONFLICT(wa_id) DO UPDATE SET
                name=excluded.name, flow=excluded.flow, step=excluded.step,
                artikel_step=excluded.artikel_step, data=excluded.data,
                artikel=excluded.artikel, aktualisiert=excluded.aktualisiert
        ''', {**s, 'data': json.dumps(s['data'], ensure_ascii=False),
                    'artikel': json.dumps(s['artikel'], ensure_ascii=False)})

def session_reset(wa_id: str, name: str = None):
    s = session_get(wa_id)
    s.update({'flow': None, 'step': 0, 'artikel_step': 0, 'data': {}, 'artikel': []})
    if name: s['name'] = name
    session_save(s)

def formular_speichern(wa_id: str, name: str, typ: str, data: dict):
    with get_db() as db:
        db.execute(
            'INSERT INTO formulare (wa_id, name, typ, data) VALUES (?,?,?,?)',
            (wa_id, name, typ, json.dumps(data, ensure_ascii=False))
        )
        return db.execute('SELECT last_insert_rowid()').fetchone()[0]

def nachricht_loggen(wa_id: str, richtung: str, text: str):
    with get_db() as db:
        db.execute('INSERT INTO nachrichten (wa_id, typ, nachricht) VALUES (?,?,?)',
                   (wa_id, richtung, text))

# ── Produkt-Suche ──────────────────────────────────────────────────────────────

def produkt_suche(q: str, limit: int = 25) -> list:
    """Volltext-artige Suche im Produktkatalog (Autovervollständigung).

    Die Eingabe wird in Tokens zerlegt; jedes Token muss in einem der durchsuchten
    Felder vorkommen (UND-Verknüpfung) – so funktioniert auch „field 128" oder
    „stanno royal". Durchsucht werden Bezeichnung, Artikelnummer, EAN, Farbe(n) und
    Größe. Treffer werden nach Relevanz sortiert (exakte EAN → Artikelnummer-Präfix
    → Name). ``bild`` ist die erste verfügbare URL.
    """
    q = (q or '').strip()
    if len(q) < 2:
        return []
    tokens = q.split()
    bedingungen, params = [], []
    for t in tokens:
        like = f'%{t}%'
        bedingungen.append(
            '(bezeichnung LIKE ? OR artikelnummer LIKE ? OR ean LIKE ? '
            'OR farbe LIKE ? OR hauptfarbe LIKE ? OR groesse LIKE ?)'
        )
        params += [like, like, like, like, like, like]
    where_sql = ' AND '.join(bedingungen)
    params += [q, f'{q}%', limit]  # Rang-Parameter + Limit
    with get_db() as db:
        rows = db.execute(
            f'''SELECT * FROM produkte
               WHERE {where_sql}
               ORDER BY (ean = ?) DESC, (artikelnummer LIKE ?) DESC, bezeichnung, groesse
               LIMIT ?''',
            params
        ).fetchall()
    treffer = []
    for r in rows:
        d = dict(r)
        try:
            bilder = json.loads(d.get('bilder') or '[]')
        except Exception:
            bilder = []
        treffer.append({
            'ean':           d['ean'],
            'artikelnummer': d['artikelnummer'],
            'bezeichnung':   d['bezeichnung'],
            'groesse':       d['groesse'],
            'hauptfarbe':    d['hauptfarbe'],
            'farbe':         d['farbe'],
            'preis':         d['preis'],
            'bild':          bilder[0] if bilder else '',
        })
    return treffer
