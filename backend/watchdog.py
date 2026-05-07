#!/usr/bin/env python3
"""Watchdog für Hautnah Textil Backend — startet app.py neu wenn es abstürzt."""
import subprocess, time, sys
from pathlib import Path

APP  = Path(__file__).parent / 'app.py'
VENV = Path(__file__).parent / 'venv/bin/python'

def starte():
    return subprocess.Popen([str(VENV), str(APP)], cwd=str(APP.parent))

proc = starte()
print(f"Hautnah Backend gestartet (PID {proc.pid})")

while True:
    time.sleep(10)
    if proc.poll() is not None:
        print("Backend abgestürzt — starte neu …")
        proc = starte()
        print(f"Neu gestartet (PID {proc.pid})")
