# -*- coding: utf-8 -*-
"""Hautnah Textil – Flask Backend (Port 5003)"""
from dotenv import load_dotenv
load_dotenv()

import os
import json
import time
import bcrypt
import secrets as _secrets
import threading
from pathlib import Path
from collections import defaultdict
from datetime import timedelta
import requests as http
from werkzeug.utils import secure_filename
from flask import Flask, request, jsonify, render_template, session, redirect, url_for
from database import init_db, get_db, formular_speichern, produkt_suche

app = Flask(__name__)

import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
app.logger.setLevel(logging.INFO)

app.secret_key = os.environ['SECRET_KEY']  # KeyError bei Start wenn fehlt – Absicht
if len(app.secret_key) < 32:
    raise RuntimeError('SECRET_KEY zu kurz (mind. 32 Zeichen erforderlich)')

app.config.update(
    SESSION_COOKIE_SECURE=True,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    PERMANENT_SESSION_LIFETIME=timedelta(hours=8),
    MAX_CONTENT_LENGTH=20 * 1024 * 1024,  # 20 MB Gesamt-Upload (max 3 Fotos)
)

# Foto-Uploads für Reklamationen (von Flask-/static ausgeliefert)
UPLOAD_DIR = Path(app.static_folder) / 'uploads' / 'reklamationen'
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
ERLAUBTE_BILD_EXT = {'.jpg', '.jpeg', '.png', '.webp'}
ERLAUBTE_LOGO_EXT = {'.jpg', '.jpeg', '.png', '.webp', '.svg', '.pdf'}
MAX_FOTOS = 3
# Reklamationsgründe, die auch bei bedruckten Artikeln zulässig sind
DRUCK_GRUENDE = {'Falschdruck/Druckfehler'}

init_db()

# ── Einfaches In-Memory Rate-Limiting ────────────────────────────────────────
_login_attempts: dict = defaultdict(list)  # ip → [timestamps]

def _rate_ok(ip: str, max_versuche: int = 10, fenster: int = 300) -> bool:
    jetzt = time.time()
    versuche = [t for t in _login_attempts[ip] if jetzt - t < fenster]
    _login_attempts[ip] = versuche
    if len(versuche) >= max_versuche:
        return False
    _login_attempts[ip].append(jetzt)
    return True



# ── CSRF ─────────────────────────────────────────────────────────────────────

def _csrf_token() -> str:
    if 'csrf' not in session:
        session['csrf'] = _secrets.token_urlsafe(32)
    return session['csrf']

def _csrf_ok() -> bool:
    geliefert = request.headers.get('X-CSRF-Token', '')
    erwartet  = session.get('csrf', '')
    if not erwartet or not geliefert:
        return False
    return _secrets.compare_digest(geliefert, erwartet)

@app.context_processor
def _inject_csrf():
    return {'csrf_token': _csrf_token}


# ── Admin Dashboard ───────────────────────────────────────────────────────────

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        ip = request.headers.get('X-Forwarded-For', request.remote_addr).split(',')[0].strip()
        if not _rate_ok(ip):
            return render_template('login.html', fehler='Zu viele Versuche. Bitte 5 Minuten warten.')
        eingabe = request.form.get('passwort', '').encode('utf-8')
        hash_aus_env = os.environ.get('ADMIN_PASSWORD_HASH', '').encode('utf-8')
        if hash_aus_env and bcrypt.checkpw(eingabe, hash_aus_env):
            session.clear()
            session['admin'] = True
            session.permanent = True
            return redirect(url_for('admin_dashboard'))
        return render_template('login.html', fehler='Falsches Passwort')
    return render_template('login.html', fehler=None)

@app.route('/admin/logout')
def admin_logout():
    session.clear()
    return redirect(url_for('admin_login'))

@app.route('/admin')
def admin_dashboard():
    if not session.get('admin'):
        return redirect(url_for('admin_login'))
    with get_db() as db:
        # Auto-Clean: Einträge im Papierkorb die älter als 30 Tage sind löschen
        db.execute("DELETE FROM formulare_geloescht WHERE geloescht_am < datetime('now','-30 days','localtime')")

        rows = db.execute(
            'SELECT * FROM formulare ORDER BY erstellt_am DESC LIMIT 50'
        ).fetchall()
        formulare = []
        for r in rows:
            fd = dict(r)
            fd['daten'] = json.loads(fd['data'] or '{}')
            formulare.append(fd)
        stats = {
            'neu':            db.execute('SELECT COUNT(*) FROM formulare WHERE status="neu"').fetchone()[0],
            'anfragen':       db.execute('SELECT COUNT(*) FROM formulare').fetchone()[0],
            'gelesen':        db.execute('SELECT COUNT(*) FROM formulare WHERE status="gelesen"').fetchone()[0],
            'heute_erledigt': db.execute("SELECT COUNT(*) FROM formulare WHERE status='erledigt' AND date(erstellt_am)=date('now','localtime')").fetchone()[0],
            'monat':          db.execute("SELECT COUNT(*) FROM formulare WHERE strftime('%Y-%m',erstellt_am)=strftime('%Y-%m','now','localtime')").fetchone()[0],
        }
        typ_rows = db.execute(
            'SELECT typ, COUNT(*) as cnt FROM formulare GROUP BY typ ORDER BY cnt DESC'
        ).fetchall()
        max_cnt = typ_rows[0]['cnt'] if typ_rows else 1
        typ_stats = [
            {'typ': r['typ'], 'cnt': r['cnt'], 'pct': int(r['cnt'] / max_cnt * 100)}
            for r in typ_rows
        ]
        papierkorb_rows = db.execute(
            'SELECT * FROM formulare_geloescht ORDER BY geloescht_am DESC'
        ).fetchall()
        papierkorb = []
        for r in papierkorb_rows:
            fd = dict(r)
            fd['daten'] = json.loads(fd['data'] or '{}')
            papierkorb.append(fd)
    return render_template('admin.html',
                           formulare=formulare,
                           stats=stats,
                           typ_stats=typ_stats,
                           papierkorb=papierkorb)


@app.route('/admin/formular/<int:fid>/status', methods=['POST'])
def formular_status(fid):
    if not session.get('admin'):
        return jsonify({'ok': False}), 401
    if not _csrf_ok():
        return jsonify({'ok': False, 'error': 'CSRF'}), 403
    status = (request.json or {}).get('status')
    if status not in ('neu', 'gelesen', 'erledigt', 'beantwortet'):
        return jsonify({'ok': False})
    with get_db() as db:
        db.execute('UPDATE formulare SET status=? WHERE id=?', (status, fid))
    return jsonify({'ok': True})

@app.route('/admin/anfrage/<int:fid>')
def admin_anfrage_detail(fid):
    if not session.get('admin'):
        return redirect(url_for('admin_login'))
    with get_db() as db:
        row = db.execute('SELECT * FROM formulare WHERE id=?', (fid,)).fetchone()
    if not row:
        return 'Nicht gefunden', 404
    f = dict(row)
    f['daten'] = json.loads(f['data'] or '{}')
    return render_template('admin_detail.html', f=f)

@app.route('/admin/anfrage/<int:fid>/antworten', methods=['POST'])
def admin_anfrage_antworten(fid):
    if not session.get('admin'):
        return jsonify({'ok': False}), 401
    if not _csrf_ok():
        return jsonify({'ok': False, 'error': 'CSRF'}), 403
    with get_db() as db:
        row = db.execute('SELECT * FROM formulare WHERE id=?', (fid,)).fetchone()
    if not row:
        return jsonify({'ok': False, 'error': 'Nicht gefunden'}), 404
    f = dict(row)
    daten = json.loads(f['data'] or '{}')
    email_to = daten.get('email', '')
    if not email_to:
        return jsonify({'ok': False, 'error': 'Keine E-Mail-Adresse bekannt'})
    text = (request.json or {}).get('text', '').strip()
    if not text:
        return jsonify({'ok': False, 'error': 'Kein Text'})
    mailer_key = os.getenv('MAILER_KEY')
    if not mailer_key:
        return jsonify({'ok': False, 'error': 'MAILER_KEY fehlt'})

    SIGNATUR = (
        '\n\n'
        'Mit freundlichen Grüßen\n'
        'Das Team von Hautnah Textil\n\n'
        '──────────────────────────\n'
        'Hautnah Textil\n'
        'E-Mail: hautnah-textil@gmx.de\n'
        'Web: www.hautnah-textil.de\n'
        '──────────────────────────\n'
        'Bitte antworten Sie nicht direkt auf diese E-Mail.\n'
        'Für Rückfragen erreichen Sie uns unter hautnah-textil@gmx.de'
    )
    if 'hautnah-textil@gmx.de' not in text:
        text = text + SIGNATUR

    payload = {
        'to':       email_to,
        'subject':  f"Re: Ihre Anfrage bei Hautnah Textil – {f['typ']}",
        'text':     text,
        'reply_to': 'hautnah-textil@gmx.de',
    }
    try:
        r = http.post(
            'http://127.0.0.1:5020/send',
            headers={'Authorization': f'Bearer {mailer_key}'},
            json=payload,
            timeout=8
        )
        if not r.ok:
            app.logger.error(f'Mailer Fehler {r.status_code}: {r.text}')
            return jsonify({'ok': False, 'error': 'E-Mail-Versand fehlgeschlagen. Details im Server-Log.'}), 502
    except Exception as e:
        app.logger.error(f'Mailer Exception: {e}')
        return jsonify({'ok': False, 'error': 'E-Mail-Versand fehlgeschlagen. Details im Server-Log.'}), 502
    with get_db() as db:
        db.execute(
            "UPDATE formulare SET status='beantwortet', antwort=?, beantwortet_am=datetime('now','localtime') WHERE id=?",
            (text, fid)
        )
    return jsonify({'ok': True})

@app.route('/admin/anfrage/<int:fid>/loeschen', methods=['POST'])
def admin_anfrage_loeschen(fid):
    if not session.get('admin'):
        return jsonify({'ok': False}), 401
    if not _csrf_ok():
        return jsonify({'ok': False, 'error': 'CSRF'}), 403
    with get_db() as db:
        row = db.execute('SELECT * FROM formulare WHERE id=?', (fid,)).fetchone()
        if not row:
            return jsonify({'ok': False, 'error': 'Nicht gefunden'}), 404
        db.execute(
            'INSERT INTO formulare_geloescht (id, wa_id, name, typ, data, status, erstellt_am) '
            'VALUES (?,?,?,?,?,?,?)',
            (row['id'], row['wa_id'], row['name'], row['typ'],
             row['data'], row['status'], row['erstellt_am'])
        )
        db.execute('DELETE FROM formulare WHERE id=?', (fid,))
    return jsonify({'ok': True})

@app.route('/admin/papierkorb/<int:fid>')
def admin_papierkorb_detail(fid):
    if not session.get('admin'):
        return redirect(url_for('admin_login'))
    with get_db() as db:
        row = db.execute('SELECT * FROM formulare_geloescht WHERE id=?', (fid,)).fetchone()
    if not row:
        return 'Nicht gefunden', 404
    f = dict(row)
    f['daten'] = json.loads(f['data'] or '{}')
    return render_template('admin_detail.html', f=f, papierkorb=True)

@app.route('/admin/papierkorb/leeren', methods=['POST'])
def admin_papierkorb_leeren():
    if not session.get('admin'):
        return jsonify({'ok': False}), 401
    if not _csrf_ok():
        return jsonify({'ok': False, 'error': 'CSRF'}), 403
    with get_db() as db:
        db.execute('DELETE FROM formulare_geloescht')
    return jsonify({'ok': True})

@app.route('/admin/ping')
def admin_ping():
    if not session.get('admin'):
        return jsonify({'ok': False}), 401
    with get_db() as db:
        neu   = db.execute('SELECT COUNT(*) FROM formulare WHERE status="neu"').fetchone()[0]
        total = db.execute('SELECT COUNT(*) FROM formulare').fetchone()[0]
    return jsonify({'neu': neu, 'total': total})


# ── Website Kontaktformular ───────────────────────────────────────────────────

@app.after_request
def cors(response):
    origin = request.headers.get('Origin', '')
    allowed = {os.getenv('CORS_ORIGIN', 'https://hautnah-textil.de'), 'https://www.hautnah-textil.de'}
    if origin in allowed:
        response.headers['Access-Control-Allow-Origin'] = origin
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    response.headers['Access-Control-Allow-Methods'] = 'POST, GET, OPTIONS'
    return response

_kontakt_requests: dict = defaultdict(list)
_kontakt_lock = threading.Lock()

def _kontakt_rate_ok(ip: str, max_pro_stunde: int = 5) -> bool:
    jetzt = time.time()
    fenster = 3600
    with _kontakt_lock:
        versuche = [t for t in _kontakt_requests[ip] if jetzt - t < fenster]
        _kontakt_requests[ip] = versuche
        if len(versuche) >= max_pro_stunde:
            return False
        _kontakt_requests[ip].append(jetzt)
        return True

def _get_client_ip() -> str:
    return (
        request.headers.get('CF-Connecting-IP')
        or request.headers.get('X-Forwarded-For', '').split(',')[0].strip()
        or request.remote_addr
        or ''
    ).strip()

@app.route('/api/produkt/suche', methods=['GET', 'OPTIONS'])
def api_produkt_suche():
    if request.method == 'OPTIONS':
        return '', 204
    q = request.args.get('q', '')
    return jsonify({'treffer': produkt_suche(q)})


def _upload_speichern(dateien, erlaubte_ext, max_anzahl) -> list:
    """Hochgeladene Dateien validieren und speichern; gibt Web-Pfade zurück."""
    pfade = []
    for f in dateien[:max_anzahl]:
        if not f or not f.filename:
            continue
        ext = os.path.splitext(secure_filename(f.filename))[1].lower()
        if ext not in erlaubte_ext:
            continue
        name = f'{_secrets.token_hex(16)}{ext}'
        f.save(UPLOAD_DIR / name)
        pfade.append(f'/static/uploads/reklamationen/{name}')
    return pfade


@app.route('/api/kontakt', methods=['POST', 'OPTIONS'])
def api_kontakt():
    if request.method == 'OPTIONS':
        return '', 204
    ip = _get_client_ip()
    app.logger.info(f'Kontakt-Anfrage von IP: {repr(ip)}')
    if not _kontakt_rate_ok(ip):
        app.logger.warning(f'Rate-Limit Kontaktformular: {ip}')
        return jsonify({'ok': True}), 200

    # Eingaben einheitlich aus JSON ODER multipart/form-data lesen
    if request.content_type and 'multipart/form-data' in request.content_type:
        data = {k: v for k, v in request.form.items()}
        # JSON-codierte Felder (Produkt-Auswahl) wieder zu Listen/Dicts machen
        for feld in ('produkte', 'artikel'):
            if isinstance(data.get(feld), str):
                try:
                    data[feld] = json.loads(data[feld])
                except (ValueError, TypeError):
                    pass
    else:
        data = request.get_json(silent=True) or {}

    # Bot-Schutz: Honeypot-Feld muss leer sein
    if data.get('website', ''):
        return jsonify({'ok': True})  # still 200 so bots don't retry

    # Bot-Schutz: Formular muss mind. 4 Sekunden offen gewesen sein
    try:
        t_geladen = int(data.get('_t', 0))
        if t_geladen and (time.time() * 1000 - t_geladen) < 4000:
            return jsonify({'ok': True})
    except (ValueError, TypeError):
        pass

    kategorie = data.get('kategorie', 'nachricht')
    name      = data.get('vereinsname') or data.get('name') or '–'
    email_von = data.get('email', '')

    # Reklamations-Sonderregel: bedruckte Artikel nur bei druckbezogenem Grund
    if kategorie == 'reklamation' and str(data.get('bedruckt', '')).lower() == 'ja' \
            and data.get('grund') not in DRUCK_GRUENDE:
        return jsonify({
            'ok': False,
            'error': 'Bedruckte bzw. individualisierte Artikel können nur bei '
                     'Druckfehlern (z. B. Falschdruck) reklamiert werden.'
        }), 400

    # Datei-Uploads (nur bei multipart) speichern und als Pfade in den Daten ablegen
    if request.files:
        fotos = _upload_speichern(request.files.getlist('fotos'), ERLAUBTE_BILD_EXT, MAX_FOTOS)
        if fotos:
            data['fotos'] = fotos
        logo = _upload_speichern(request.files.getlist('logo'), ERLAUBTE_LOGO_EXT, 1)
        if logo:
            data['logo'] = logo[0]

    # interne Felder nicht persistieren
    for feld in ('website', '_t'):
        data.pop(feld, None)

    # quelle markieren damit im Dashboard klar ist: Website vs. WhatsApp
    data['quelle'] = 'website'

    formular_speichern(wa_id='web', name=name, typ=kategorie, data=data)
    _email_benachrichtigung(kategorie, name, email_von, data)

    return jsonify({'ok': True})


def _email_benachrichtigung(kategorie: str, name: str, email_von: str, data: dict):
    # Versand über den zentralen DAMN-Mailer (Amazon SES) statt Resend.
    # Mailer läuft auf demselben Host (127.0.0.1:5020); Absender kommt aus der
    # Projekt-Config (kontakt@hautnah-textil.de). Key + Empfänger aus der .env.
    mailer_key = os.getenv('MAILER_KEY')
    if not mailer_key:
        app.logger.warning('Email-Versand übersprungen: MAILER_KEY nicht gesetzt.')
        return

    skip   = {'kategorie', 'quelle'}
    zeilen = [f'Neue Anfrage über hautnah-textil.de', f'Kategorie: {kategorie.upper()}', '']
    for k, v in data.items():
        if k in skip:
            continue
        if isinstance(v, list):
            zeilen.append(f'{k}:')
            for item in v:
                if isinstance(item, dict):
                    zeilen.append('  ' + '  |  '.join(f'{ik}: {iv}' for ik, iv in item.items() if iv))
                else:
                    zeilen.append(f'  {item}')
        elif v:
            zeilen.append(f'{k}: {v}')

    payload = {
        'to':      os.getenv('KONTAKT_TO', 'eingang@hautnah-textil.de'),
        'subject': f'Neue Anfrage – {kategorie.capitalize()} – {name}',
        'text':    '\n'.join(zeilen),
    }
    if email_von:
        payload['reply_to'] = email_von

    try:
        r = http.post(
            'http://127.0.0.1:5020/send',
            headers={'Authorization': f'Bearer {mailer_key}'},
            json=payload,
            timeout=8
        )
        if not r.ok:
            app.logger.error(f'Mailer Fehler {r.status_code}: {r.text}')
    except Exception as e:
        app.logger.error(f'Mailer Exception: {e}')


# ── Health ────────────────────────────────────────────────────────────────────

@app.route('/health')
def health():
    return jsonify({'status': 'ok', 'service': 'hautnah-textil'})


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5003, debug=False)
