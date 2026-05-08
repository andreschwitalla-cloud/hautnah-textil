"""WhatsApp Bot Flow Engine – Hautnah Textil"""
import os, requests
from database import session_get, session_save, session_reset, formular_speichern, nachricht_loggen

# ── HA API ────────────────────────────────────────────────────────────────────

def _headers():
    return {'Authorization': f"Bearer {os.getenv('WA_TOKEN')}",
            'Content-Type': 'application/json'}

def _url():
    return f"https://graph.facebook.com/v19.0/{os.getenv('WA_PHONE_ID')}/messages"

def sende_nachricht(an: str, text: str) -> bool:
    payload = {"messaging_product": "whatsapp", "to": an,
               "type": "text", "text": {"body": text}}
    try:
        r = requests.post(_url(), json=payload, headers=_headers(), timeout=10)
        nachricht_loggen(an, 'ausgehend', text)
        return r.status_code == 200
    except Exception:
        return False

def parse_webhook(data: dict) -> list:
    msgs = []
    try:
        for entry in data.get('entry', []):
            for change in entry.get('changes', []):
                value = change.get('value', {})
                kontakte = {c['wa_id']: c.get('profile', {}).get('name', '')
                            for c in value.get('contacts', [])}
                for msg in value.get('messages', []):
                    if msg.get('type') == 'text':
                        msgs.append({'wa_id': msg['from'],
                                     'name': kontakte.get(msg['from'], ''),
                                     'text': msg['text']['body']})
    except Exception:
        pass
    return msgs


# ── Flow Definitionen ─────────────────────────────────────────────────────────

KONTAKTFELDER = [
    ('name',    '👤 Dein Name:'),
    ('adresse', '🏠 Adresse (Straße, PLZ, Ort):'),
    ('typ',     '🏢 Verein / Firma / Privat?'),
    ('email',   '✉️  E-Mail-Adresse:'),
    ('telefon', '📞 Telefonnummer:'),
]

ARTIKELFELDER = [
    ('artikel_name',    '📦 Artikelname:'),
    ('artikel_nr',      '🔢 Artikelnummer:'),
    ('stueckzahl',      '🔢 Stückzahl:'),
    ('groessen',        '👕 Größen (z.B. 2x S, 3x M, 1x L):'),
    ('druckposition',   '🎯 Druckposition (z.B. Brust links, Rücken):'),
    ('nummer_name',     '🏷  Nummer / Name (oder "nein" zum Überspringen):'),
]

FLOWS = {
    '1': {
        'titel': 'Bestellung',
        'typ':   'bestellung',
        'schritte': KONTAKTFELDER + [
            ('rechnungsadresse', '📋 Abweichende Rechnungsadresse? (oder "nein"):'),
        ],
        'mit_artikel': True,
    },
    '2': {
        'titel': 'Angebotsanfrage',
        'typ':   'angebot',
        'schritte': KONTAKTFELDER + [
            ('rechnungsadresse', '📋 Abweichende Rechnungsadresse? (oder "nein"):'),
        ],
        'mit_artikel': True,
    },
    '3': {
        'titel': 'Liefertermin',
        'typ':   'liefertermin',
        'schritte': KONTAKTFELDER + [
            ('bestellnummer',        '🔖 Bestellnummer:'),
            ('lieferterminanfrage',  '📅 Deine Lieferterminanfrage (Freitext):'),
        ],
        'mit_artikel': False,
    },
    '4': {
        'titel': 'Feedback',
        'typ':   'feedback',
        'schritte': [('feedback', '💬 Dein Feedback (einfach drauflosschreiben):')],
        'mit_artikel': False,
    },
    '5': {
        'titel': 'FAQ',
        'typ':   'faq',
        'schritte': [],
        'mit_artikel': False,
        'faq': True,
    },
    '6': {
        'titel': 'Kontakt',
        'typ':   'kontakt',
        'schritte': [
            ('name',    '👤 Dein Name:'),
            ('adresse', '🏠 Adresse (Straße, PLZ, Ort):'),
            ('telefon', '📞 Telefonnummer:'),
            ('email',   '✉️  E-Mail-Adresse:'),
        ],
        'mit_artikel': False,
    },
}

FAQ_ANTWORTEN = {
    '1': (
        '🧺 *Waschanleitung:*\n\n'
        'Unsere bedruckten / bestickten Textilien pflegst du am besten so:\n\n'
        '• Waschen bei max. 30–40 °C\n'
        '• Druck nicht bügeln\n'
        '• Nicht in den Trockner\n'
        '• Textil auf links waschen\n'
        '• Keine aggressiven Waschmittel\n\n'
        'So hält der Druck lange schön! 👕'
    ),
    '2': (
        '✅ *Produktqualität:*\n\n'
        'Wir arbeiten ausschließlich mit geprüften Marken-Textilien (z.B. Stanley/Stella, B&C, Fruit of the Loom).\n\n'
        'Unsere Druckfarben sind:\n'
        '• OEKO-TEX zertifiziert\n'
        '• Waschecht & langlebig\n'
        '• Frei von Schadstoffen\n\n'
        'Jede Bestellung wird vor dem Versand geprüft. 🎨'
    ),
}

# ── Texte ─────────────────────────────────────────────────────────────────────

HAUPTMENU = (
    '👋 Herzlich willkommen bei *Hautnah Textil*!\n\n'
    'Wie kann ich dir helfen? Bitte wähle eine Kategorie:\n\n'
    '1️⃣  Bestellung aufgeben\n'
    '2️⃣  Angebotsanfrage\n'
    '3️⃣  Liefertermin anfragen\n'
    '4️⃣  Feedback geben\n'
    '5️⃣  FAQ\n'
    '6️⃣  Kontakt\n\n'
    '_Einfach die Zahl tippen_ 👆'
)

FAQ_MENU = (
    '❓ *FAQ – Häufige Fragen:*\n\n'
    '1️⃣  Waschanleitung\n'
    '2️⃣  Produktqualität\n\n'
    '0️⃣  Zurück zum Hauptmenü'
)

def abschluss_text(titel: str) -> str:
    return (
        f'✅ *{titel} erfolgreich übermittelt!*\n\n'
        'Vielen Dank – wir melden uns so schnell wie möglich bei dir.\n\n'
        '💬 Schreib *"Menü"* um erneut zu starten.'
    )

def admin_benachrichtigung(typ: str, name: str, data: dict, artikel: list) -> str:
    lines = [f'📬 *Neue {typ.capitalize()}* von {name}\n']
    for k, v in data.items():
        lines.append(f'• {k}: {v}')
    if artikel:
        lines.append(f'\n📦 *{len(artikel)} Artikel:*')
        for i, a in enumerate(artikel, 1):
            lines.append(f'\n_Artikel {i}:_')
            for k, v in a.items():
                lines.append(f'  • {k}: {v}')
    return '\n'.join(lines)


# ── Bot Engine ────────────────────────────────────────────────────────────────

def verarbeite_nachricht(wa_id: str, name: str, text: str) -> str:
    """Haupteingang. Gibt die Antwort-Nachricht zurück."""
    text = text.strip()
    nachricht_loggen(wa_id, 'eingehend', text)

    s = session_get(wa_id)
    if name and not s.get('name'):
        s['name'] = name

    # Jederzeit: "Menü" oder "0" bricht ab und zeigt Hauptmenü
    if text.lower() in ('menü', 'menu', 'menue', 'start', '0', 'abbrechen'):
        session_reset(wa_id, s.get('name'))
        return HAUPTMENU

    # ── Hauptmenü ──
    if not s['flow']:
        if text in FLOWS:
            flow = FLOWS[text]
            if flow.get('faq'):
                s['flow'] = '5'
                session_save(s)
                return FAQ_MENU
            s['flow'] = text
            s['step'] = 0
            s['artikel_step'] = 0
            s['data'] = {}
            s['artikel'] = []
            session_save(s)
            _, frage = FLOWS[text]['schritte'][0]
            return (f'*{flow["titel"]}*\n\n'
                    f'Super! Ich begleite dich Schritt für Schritt.\n'
                    f'_(Tippe "0" zum Abbrechen)_\n\n{frage}')
        return HAUPTMENU

    # ── FAQ ──
    if s['flow'] == '5':
        if text in FAQ_ANTWORTEN:
            session_reset(wa_id, s.get('name'))
            return FAQ_ANTWORTEN[text] + '\n\n_Tippe "Menü" um zurückzukehren._'
        return FAQ_MENU

    # ── Aktiver Flow ──
    flow    = FLOWS[s['flow']]
    schritte = flow['schritte']
    mit_art  = flow['mit_artikel']

    # Artikel-Loop
    if mit_art and s['step'] >= len(schritte):
        return _artikel_schritt(s, text, flow)

    # Normaler Schritt: Antwort speichern
    key, _ = schritte[s['step']]
    s['data'][key] = text
    s['step'] += 1

    # Nächsten Schritt bestimmen
    if s['step'] < len(schritte):
        _, frage = schritte[s['step']]
        session_save(s)
        return frage

    # Alle Basis-Felder fertig
    if mit_art:
        # Erster Artikel
        s['artikel_step'] = 0
        session_save(s)
        _, frage = ARTIKELFELDER[0]
        return f'📦 *Artikel 1*\n\n{frage}'

    # Flow ohne Artikel → Abschluss
    return _abschluss(s, flow)

def _artikel_schritt(s: dict, text: str, flow: dict) -> str:
    ast = s['artikel_step']

    if ast < len(ARTIKELFELDER):
        key, _ = ARTIKELFELDER[ast]
        # Aktuellen Artikel befüllen
        if not s['artikel'] or len(s['artikel'][-1]) >= ast + 1:
            if ast == 0:
                s['artikel'].append({})
        s['artikel'][-1][key] = text
        s['artikel_step'] += 1

        if s['artikel_step'] < len(ARTIKELFELDER):
            _, frage = ARTIKELFELDER[s['artikel_step']]
            session_save(s)
            return frage

        # Alle Artikelfelder fertig → weiterer Artikel?
        session_save(s)
        return (f'✅ Artikel {len(s["artikel"])} gespeichert.\n\n'
                f'Möchtest du einen weiteren Artikel hinzufügen?\n'
                f'👉 *ja* oder *nein*')

    # Entscheidung: weiterer Artikel?
    if text.lower() in ('ja', 'j', 'yes'):
        s['artikel_step'] = 0
        session_save(s)
        _, frage = ARTIKELFELDER[0]
        return f'📦 *Artikel {len(s["artikel"]) + 1}*\n\n{frage}'

    # Nein → Abschluss
    return _abschluss(s, flow)

def _abschluss(s: dict, flow: dict) -> str:
    wa_id = s['wa_id']
    name  = s.get('name', 'Unbekannt')
    data  = dict(s['data'])
    if s.get('name'):
        data['_name'] = s['name']

    formular_speichern(wa_id, name, flow['typ'], {**data, 'artikel': s['artikel']})

    # Admin benachrichtigen
    admin_nr = os.getenv('ADMIN_WA_NR')
    if admin_nr:
        notiz = admin_benachrichtigung(flow['titel'], name, data, s['artikel'])
        sende_nachricht(admin_nr, notiz)

    session_reset(wa_id, name)
    return abschluss_text(flow['titel'])
