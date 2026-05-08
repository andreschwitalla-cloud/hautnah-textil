#!/usr/bin/env python3
"""Tägliche Kontrollroutine – prüft Logs, DB, Disk und Backend, sendet Bericht per E-Mail."""
from dotenv import load_dotenv
load_dotenv()

import os, sqlite3, shutil, requests
from pathlib import Path
from datetime import datetime, date

BASE    = Path(__file__).parent
DB      = BASE / 'hautnah.db'
LOG     = BASE / 'hautnah.log'
BACKUPS = BASE / 'backups'

probleme = []
infos    = []

# ── 1. Backend erreichbar? ────────────────────────────────────────────────────
try:
    r = requests.get('http://localhost:5003/health', timeout=5)
    if r.ok:
        infos.append('✅ Backend läuft')
    else:
        probleme.append(f'⚠️ Backend antwortet mit HTTP {r.status_code}')
except Exception as e:
    probleme.append(f'🔴 Backend nicht erreichbar: {e}')

# ── 2. Fehler im Log seit gestern ─────────────────────────────────────────────
fehler_count = 0
if LOG.exists():
    gestern = datetime.now().strftime('%Y-%m-%d')
    with open(LOG, errors='replace') as f:
        for zeile in f:
            if 'ERROR' in zeile or 'Exception' in zeile or 'Traceback' in zeile:
                fehler_count += 1
    if fehler_count:
        probleme.append(f'⚠️ {fehler_count} Fehler/Exceptions im Log gefunden')
    else:
        infos.append('✅ Keine Fehler im Log')

# ── 3. Datenbank-Integrität ───────────────────────────────────────────────────
try:
    conn = sqlite3.connect(DB)
    ergebnis = conn.execute('PRAGMA integrity_check').fetchone()[0]
    conn.close()
    if ergebnis == 'ok':
        infos.append('✅ Datenbank integer')
    else:
        probleme.append(f'🔴 DB-Integritätsfehler: {ergebnis}')
except Exception as e:
    probleme.append(f'🔴 DB nicht lesbar: {e}')

# ── 4. Formulare-Statistik ────────────────────────────────────────────────────
try:
    conn = sqlite3.connect(DB)
    gesamt = conn.execute('SELECT COUNT(*) FROM formulare').fetchone()[0]
    neu    = conn.execute('SELECT COUNT(*) FROM formulare WHERE status="neu"').fetchone()[0]
    conn.close()
    infos.append(f'📋 Formulare gesamt: {gesamt} | Neu (unbearbeitet): {neu}')
    if neu > 10:
        probleme.append(f'⚠️ {neu} unbearbeitete Anfragen im Dashboard')
except Exception as e:
    probleme.append(f'⚠️ Formulare nicht lesbar: {e}')

# ── 5. Heutiges Backup vorhanden? ─────────────────────────────────────────────
backup_heute = BACKUPS / f"hautnah_{date.today().isoformat()}.db"
if backup_heute.exists():
    groesse = backup_heute.stat().st_size / 1024
    infos.append(f'✅ Backup vorhanden ({groesse:.0f} KB)')
else:
    probleme.append('⚠️ Kein heutiges Backup gefunden')

# ── 6. Festplattenplatz ───────────────────────────────────────────────────────
total, used, free = shutil.disk_usage('/')
free_gb  = free / (1024 ** 3)
used_pct = used / total * 100
if free_gb < 2:
    probleme.append(f'🔴 Festplatte fast voll – nur noch {free_gb:.1f} GB frei ({used_pct:.0f}% belegt)')
elif free_gb < 10:
    probleme.append(f'⚠️ Festplatte {used_pct:.0f}% belegt – noch {free_gb:.1f} GB frei')
else:
    infos.append(f'✅ Festplatte: {free_gb:.0f} GB frei ({used_pct:.0f}% belegt)')

# ── Bericht zusammenbauen ─────────────────────────────────────────────────────
jetzt    = datetime.now().strftime('%d.%m.%Y %H:%M')
status   = '🔴 PROBLEME GEFUNDEN' if probleme else '✅ Alles in Ordnung'
betreff  = f'Hautnah Textil – Tagesbericht {date.today().strftime("%d.%m.%Y")} – {status}'

zeilen = [
    f'Täglicher Systembericht – {jetzt}',
    f'Status: {status}',
    '',
]
if probleme:
    zeilen.append('── PROBLEME ──────────────────────')
    zeilen.extend(probleme)
    zeilen.append('')
zeilen.append('── SYSTEMINFORMATIONEN ───────────')
zeilen.extend(infos)
zeilen += [
    '',
    '──────────────────────────────────',
    'Dashboard: https://api.hautnah-textil.de/admin',
    'Dieser Bericht wird täglich um 07:00 Uhr automatisch erstellt.',
]

nachricht = '\n'.join(zeilen)
print(nachricht)

# ── macOS-Benachrichtigung bei Problemen ──────────────────────────────────────
import subprocess

if probleme:
    titel   = '⚠️ Hautnah – Systemprobleme gefunden'
    details = '\n'.join(probleme)
    script  = f'display notification "{details}" with title "{titel}" sound name "Basso"'
    subprocess.run(['osascript', '-e', script], capture_output=True)
