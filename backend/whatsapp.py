import os, requests

def _headers():
    return {
        'Authorization': f"Bearer {os.getenv('WA_TOKEN')}",
        'Content-Type':  'application/json'
    }

def _url():
    phone_id = os.getenv('WA_PHONE_ID')
    return f"https://graph.facebook.com/v19.0/{phone_id}/messages"

def sende_nachricht(an: str, text: str) -> bool:
    """Sendet eine WhatsApp-Textnachricht."""
    payload = {
        "messaging_product": "whatsapp",
        "to": an,
        "type": "text",
        "text": {"body": text}
    }
    r = requests.post(_url(), json=payload, headers=_headers(), timeout=10)
    return r.status_code == 200

def sende_vorlage(an: str, vorlage: str, sprache: str = "de") -> bool:
    """Sendet eine genehmigte WhatsApp-Vorlage."""
    payload = {
        "messaging_product": "whatsapp",
        "to": an,
        "type": "template",
        "template": {"name": vorlage, "language": {"code": sprache}}
    }
    r = requests.post(_url(), json=payload, headers=_headers(), timeout=10)
    return r.status_code == 200

def parse_webhook(data: dict) -> list[dict]:
    """Extrahiert Nachrichten aus einem Webhook-Payload."""
    nachrichten = []
    try:
        for entry in data.get('entry', []):
            for change in entry.get('changes', []):
                value = change.get('value', {})
                kontakte = {c['wa_id']: c.get('profile', {}).get('name', '')
                            for c in value.get('contacts', [])}
                for msg in value.get('messages', []):
                    if msg.get('type') == 'text':
                        nachrichten.append({
                            'wa_id':    msg['from'],
                            'name':     kontakte.get(msg['from'], ''),
                            'telefon':  msg['from'],
                            'nachricht': msg['text']['body'],
                        })
    except Exception:
        pass
    return nachrichten

# ── Automatische Antworten ────────────────────────────────────────────────────

WILLKOMMEN = (
    "👋 Hallo! Ich bin der digitale Assistent von *Hautnah Textil*.\n\n"
    "Schreib mir einfach was du brauchst, z.B.:\n"
    "• 50x Shirts Digitaldruck\n"
    "• Logo besticken lassen\n"
    "• Preisanfrage Siebdruck\n\n"
    "Wir melden uns so schnell wie möglich! 🎨"
)

def auto_antwort(nachricht: str):
    """Gibt eine automatische Antwort zurück oder None wenn keine passt."""
    n = nachricht.lower()
    if any(w in n for w in ['hallo', 'hi', 'guten', 'moin', 'servus']):
        return WILLKOMMEN
    if any(w in n for w in ['preis', 'kosten', 'was kostet', 'angebot']):
        return (
            "💰 Unsere Preise hängen von Druckart, Menge und Textil ab.\n"
            "Schick uns einfach:\n"
            "1. Gewünschte Druckart (Digital, Siebdruck, Stickerei)\n"
            "2. Ungefähre Stückzahl\n"
            "3. Dein Motiv (als Bild oder Beschreibung)\n\n"
            "Dann erstellen wir dir ein kostenloses Angebot! ✅"
        )
    return None
