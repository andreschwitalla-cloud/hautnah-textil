# -*- coding: utf-8 -*-
"""Hautnah Textil – Flask Backend (Port 5003)"""
from dotenv import load_dotenv
load_dotenv()

import os
import json
import time
from collections import defaultdict
import requests as http
from flask import Flask, request, jsonify, render_template, session, redirect, url_for
from database import init_db, get_db, formular_speichern
from whatsapp import parse_webhook, sende_nachricht, verarbeite_nachricht

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'hautnah-dev-key')

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


# ── WhatsApp Webhook ──────────────────────────────────────────────────────────

@app.route('/webhook', methods=['GET'])
def webhook_verify():
    if request.args.get('hub.verify_token') == os.getenv('WA_VERIFY_TOKEN'):
        return request.args.get('hub.challenge', ''), 200
    return 'Forbidden', 403

@app.route('/webhook', methods=['POST'])
def webhook_receive():
    data = request.get_json(silent=True) or {}
    msgs = parse_webhook(data)
    for m in msgs:
        antwort = verarbeite_nachricht(m['wa_id'], m['name'], m['text'])
        sende_nachricht(m['wa_id'], antwort)
    return jsonify({'status': 'ok'})


# ── Admin Dashboard ───────────────────────────────────────────────────────────

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        ip = request.headers.get('X-Forwarded-For', request.remote_addr).split(',')[0].strip()
        if not _rate_ok(ip):
            return render_template('login.html', fehler='Zu viele Versuche. Bitte 5 Minuten warten.')
        if request.form.get('passwort') == os.getenv('ADMIN_PASSWORD', 'hautnah2025'):
            session['admin'] = True
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

        nachrichten = db.execute(
            'SELECT * FROM nachrichten ORDER BY erstellt_am ASC LIMIT 500'
        ).fetchall()
        namen = dict(db.execute(
            'SELECT wa_id, name FROM sessions WHERE name IS NOT NULL'
        ).fetchall())
        rows = db.execute(
            'SELECT * FROM formulare ORDER BY erstellt_am DESC LIMIT 50'
        ).fetchall()
        formulare = []
        for r in rows:
            fd = dict(r)
            fd['daten'] = json.loads(fd['data'] or '{}')
            formulare.append(fd)
        stats = {
            'gesamt':         db.execute('SELECT COUNT(*) FROM nachrichten WHERE typ="eingehend"').fetchone()[0],
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
                           nachrichten=nachrichten,
                           formulare=formulare,
                           stats=stats,
                           namen=namen,
                           typ_stats=typ_stats,
                           papierkorb=papierkorb)

@app.route('/admin/antworten', methods=['POST'])
def admin_antworten():
    if not session.get('admin'):
        return jsonify({'ok': False}), 401
    wa_id = (request.json or {}).get('wa_id')
    text  = (request.json or {}).get('text')
    if not wa_id or not text:
        return jsonify({'ok': False, 'error': 'Fehlende Parameter'})
    ok = sende_nachricht(wa_id, text)
    return jsonify({'ok': ok})

@app.route('/admin/formular/<int:fid>/status', methods=['POST'])
def formular_status(fid):
    if not session.get('admin'):
        return jsonify({'ok': False}), 401
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
    api_key = os.getenv('RESEND_API_KEY')
    if not api_key:
        return jsonify({'ok': False, 'error': 'RESEND_API_KEY fehlt'})

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
        'from':     'Hautnah Textil <noreply@hautnah-textil.de>',
        'to':       [email_to],
        'subject':  f"Re: Ihre Anfrage bei Hautnah Textil – {f['typ']}",
        'text':     text,
        'reply_to': 'hautnah-textil@gmx.de',
    }
    try:
        r = http.post(
            'https://api.resend.com/emails',
            headers={'Authorization': f'Bearer {api_key}'},
            json=payload,
            timeout=8
        )
        if not r.ok:
            app.logger.error(f'Resend Fehler {r.status_code}: {r.text}')
            return jsonify({'ok': False, 'error': r.text})
    except Exception as e:
        app.logger.error(f'Resend Exception: {e}')
        return jsonify({'ok': False, 'error': str(e)})
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
        wa    = db.execute('SELECT COUNT(*) FROM nachrichten').fetchone()[0]
    return jsonify({'neu': neu, 'total': total, 'wa': wa})

@app.route('/admin/nachrichten')
def admin_nachrichten_api():
    if not session.get('admin'):
        return jsonify({'ok': False}), 401
    with get_db() as db:
        rows = db.execute(
            'SELECT * FROM nachrichten ORDER BY erstellt_am DESC LIMIT 100'
        ).fetchall()
    return jsonify([dict(r) for r in rows])


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

@app.route('/api/kontakt', methods=['POST', 'OPTIONS'])
def api_kontakt():
    if request.method == 'OPTIONS':
        return '', 204

    data      = request.get_json(silent=True) or {}

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

    # quelle markieren damit im Dashboard klar ist: Website vs. WhatsApp
    data['quelle'] = 'website'

    formular_speichern(wa_id='web', name=name, typ=kategorie, data=data)
    _email_benachrichtigung(kategorie, name, email_von, data)

    return jsonify({'ok': True})


def _email_benachrichtigung(kategorie: str, name: str, email_von: str, data: dict):
    api_key = os.getenv('RESEND_API_KEY')
    if not api_key:
        app.logger.warning('Email-Versand übersprungen: RESEND_API_KEY nicht gesetzt.')
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
        'from':    'Hautnah Textil <noreply@hautnah-textil.de>',
        'to':      [os.getenv('RESEND_TO', 'hautnah-textil@gmx.de')],
        'subject': f'Neue Anfrage – {kategorie.capitalize()} – {name}',
        'text':    '\n'.join(zeilen),
    }
    if email_von:
        payload['reply_to'] = email_von

    try:
        r = http.post(
            'https://api.resend.com/emails',
            headers={'Authorization': f'Bearer {api_key}'},
            json=payload,
            timeout=8
        )
        if not r.ok:
            app.logger.error(f'Resend Fehler {r.status_code}: {r.text}')
    except Exception as e:
        app.logger.error(f'Resend Exception: {e}')


# ── Health ────────────────────────────────────────────────────────────────────

@app.route('/health')
def health():
    return jsonify({'status': 'ok', 'service': 'hautnah-textil'})


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5003, debug=False)
