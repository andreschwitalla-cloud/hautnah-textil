#!/usr/bin/env python3
"""Tägliches DB-Backup + Log-Rotation für Hautnah Textil."""
import shutil, os
from pathlib import Path
from datetime import datetime

BASE    = Path(__file__).parent
DB      = BASE / 'hautnah.db'
LOG     = BASE / 'hautnah.log'
BACKUPS = BASE / 'backups'

BACKUPS.mkdir(exist_ok=True)

# DB-Backup mit Datum
if DB.exists():
    ziel = BACKUPS / f"hautnah_{datetime.now().strftime('%Y-%m-%d')}.db"
    shutil.copy2(DB, ziel)
    print(f"Backup erstellt: {ziel}")

# Alte Backups löschen (älter als 30 Tage)
for f in BACKUPS.glob('hautnah_*.db'):
    alter = (datetime.now().timestamp() - f.stat().st_mtime) / 86400
    if alter > 30:
        f.unlink()
        print(f"Altes Backup gelöscht: {f.name}")

# Log rotieren wenn größer als 5 MB
if LOG.exists() and LOG.stat().st_size > 5 * 1024 * 1024:
    archiv = BASE / f"hautnah_{datetime.now().strftime('%Y-%m-%d')}.log"
    shutil.move(str(LOG), str(archiv))
    LOG.touch()
    print(f"Log rotiert: {archiv.name}")
    # Alte Log-Archive löschen (älter als 14 Tage)
    for f in BASE.glob('hautnah_*.log'):
        alter = (datetime.now().timestamp() - f.stat().st_mtime) / 86400
        if alter > 14:
            f.unlink()

print("Backup abgeschlossen.")
