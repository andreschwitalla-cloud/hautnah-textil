# -*- coding: utf-8 -*-
"""Hautnah Textil – Flask Backend (Port 5003)"""
from dotenv import load_dotenv
load_dotenv()

import os
from flask import Flask, request, jsonify, render_template, session, redirect, url_for
from database import init_db, get_db
from whatsapp import parse_webhook, sende_nachricht, auto_antwort

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'hautnah-dev-key')

init_db()


# ── WhatsApp Webhook ──────────────────────────────────────────────────────────

@app.route('/webhook', methods=['GET'])
def webhook_verify():
    """Meta verifiziert den Webhook mit einem Challenge."""
    if request.args.get('hub.verify_token') == os.getenv('WA_VERIFY_TOKEN'):
        return request.args.get('hub.challenge', ''), 200
    return 'Forbidden', 403

@app.route('/webhook', methods=['POST'])
def webhook_receive():
    """Eingehende WhatsApp-Nachrichten empfangen."""
    data = request.get_json(silent=True) or {}
    nachrichten = parse_webhook(data)

    with get_db() as db:
        for n in nachrichten:
            # Speichern
            db.execute(
                'INSERT INTO nachrichten (wa_id, name, telefon, nachricht) VALUES (?,?,?,?)',
                (n['wa_id'], n['name'], n['telefon'], n['nachricht'])
            )
            # Auto-Antwort
            antwort = auto_antwort(n['nachricht'])
            if antwort:
                sende_nachricht(n['wa_id'], antwort)
                db.execute(
                    'INSERT INTO nachrichten (wa_id, name, telefon, nachricht, typ) VALUES (?,?,?,?,?)',
                    (n['wa_id'], 'Hautnah Bot', '', antwort, 'ausgehend')
                )

    return jsonify({'status': 'ok'})


# ── Admin Dashboard ───────────────────────────────────────────────────────────

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
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
        nachrichten = db.execute(
            'SELECT * FROM nachrichten ORDER BY erstellt_am DESC LIMIT 100'
        ).fetchall()
        stats = {
            'gesamt':      db.execute('SELECT COUNT(*) FROM nachrichten WHERE typ="eingehend"').fetchone()[0],
            'neu':         db.execute('SELECT COUNT(*) FROM nachrichten WHERE status="neu"').fetchone()[0],
            'anfragen':    db.execute('SELECT COUNT(*) FROM anfragen').fetchone()[0],
        }
    return render_template('admin.html', nachrichten=nachrichten, stats=stats)

@app.route('/admin/antworten', methods=['POST'])
def admin_antworten():
    if not session.get('admin'):
        return jsonify({'ok': False}), 401
    wa_id = request.json.get('wa_id')
    text  = request.json.get('text')
    if not wa_id or not text:
        return jsonify({'ok': False, 'error': 'Fehlende Parameter'})
    ok = sende_nachricht(wa_id, text)
    if ok:
        with get_db() as db:
            db.execute(
                'INSERT INTO nachrichten (wa_id, name, telefon, nachricht, typ, status) VALUES (?,?,?,?,?,?)',
                (wa_id, 'Hautnah Textil', '', text, 'ausgehend', 'gesendet')
            )
            db.execute('UPDATE nachrichten SET status="beantwortet" WHERE wa_id=? AND typ="eingehend"', (wa_id,))
    return jsonify({'ok': ok})

@app.route('/admin/nachrichten')
def admin_nachrichten_api():
    if not session.get('admin'):
        return jsonify({'ok': False}), 401
    with get_db() as db:
        rows = db.execute(
            'SELECT * FROM nachrichten ORDER BY erstellt_am DESC LIMIT 50'
        ).fetchall()
    return jsonify([dict(r) for r in rows])


# ── Health ────────────────────────────────────────────────────────────────────

@app.route('/health')
def health():
    return jsonify({'status': 'ok', 'service': 'hautnah-textil'})


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5003, debug=False)
