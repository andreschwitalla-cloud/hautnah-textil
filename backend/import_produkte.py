# -*- coding: utf-8 -*-
"""Einmaliger Import des Stanno-Produktkatalogs in die ``produkte``-Tabelle.

Die gelieferte XLSX ist faktisch eine CSV in einer einzigen Spalte (A): jede Zeile
ist ein ``|``-getrennter String mit gequoteten Feldern. Zusätzlich sind die Texte
doppelt kodiert (Mojibake: „GrÃ¶sse" statt „Größe") – das wird hier korrigiert.

Aufruf:
    python import_produkte.py [pfad/zur.xlsx]
"""
import sys
import csv
import io
import json

import openpyxl

from database import get_db, init_db

DEFAULT_XLSX = (
    '/Users/andreschwitalla/Library/Mobile Documents/com~apple~CloudDocs/'
    'Lumia Anhänge/Uploads/20260609_181133_CSV_DATEN_STANNO.xlsx'
)

# Spaltenreihenfolge laut Header der Quelldatei
# EAN | Artikelnummer | Marke | Produktbezeichnung | Größe | Hauptfarbe | Farbe |
# Produktbeschreibung | Preis | Menge | Materialspezifikation | Lieferdatum |
# Bild 1..9 | Link | Country of origin | HS codes
IDX = {
    'ean': 0, 'artikelnummer': 1, 'marke': 2, 'bezeichnung': 3, 'groesse': 4,
    'hauptfarbe': 5, 'farbe': 6, 'beschreibung': 7, 'preis': 8,
    'materialspez': 10, 'link': 21, 'herkunft': 22, 'hs_code': 23,
}
BILD_IDX = range(12, 21)  # Bild 1..9


def fix_mojibake(s: str) -> str:
    """Doppelt kodierte UTF-8-Texte reparieren (latin-1 → utf-8)."""
    if not s:
        return s
    try:
        return s.encode('latin-1', 'ignore').decode('utf-8', 'ignore')
    except Exception:
        return s


def parse_zeile(raw: str):
    """Eine Roh-Zeile (pipe-delimited, gequotet) in eine Feldliste zerlegen."""
    reader = csv.reader(io.StringIO(raw), delimiter='|', quotechar='"')
    for felder in reader:
        return [fix_mojibake(f.strip()) for f in felder]
    return []


def main(pfad: str):
    init_db()
    wb = openpyxl.load_workbook(pfad, read_only=True, data_only=True)
    ws = wb.active

    eintraege = []
    for i, row in enumerate(ws.iter_rows(values_only=True)):
        if i == 0:
            continue  # Header
        raw = row[0]
        if not raw:
            continue
        f = parse_zeile(str(raw))
        if len(f) < 22 or not f[IDX['ean']]:
            continue
        bilder = [f[b] for b in BILD_IDX if b < len(f) and f[b]]
        eintraege.append((
            f[IDX['ean']], f[IDX['artikelnummer']], f[IDX['marke']],
            f[IDX['bezeichnung']], f[IDX['groesse']], f[IDX['hauptfarbe']],
            f[IDX['farbe']], f[IDX['beschreibung']], f[IDX['preis']],
            f[IDX['materialspez']], json.dumps(bilder, ensure_ascii=False),
            f[IDX['link']] if IDX['link'] < len(f) else '',
            f[IDX['herkunft']] if IDX['herkunft'] < len(f) else '',
            f[IDX['hs_code']] if IDX['hs_code'] < len(f) else '',
        ))

    with get_db() as db:
        db.execute('DELETE FROM produkte')  # idempotent: vor jedem Import leeren
        db.executemany(
            '''INSERT INTO produkte
               (ean, artikelnummer, marke, bezeichnung, groesse, hauptfarbe, farbe,
                beschreibung, preis, materialspez, bilder, link, herkunft, hs_code)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
            eintraege
        )
    print(f'Import abgeschlossen: {len(eintraege)} Produkte.')


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else DEFAULT_XLSX)
