// Intro: 4s zeigen, dann Iris-Close, dann Hero einblenden
const intro = document.getElementById('intro');
if (intro) {
  setTimeout(() => {
    intro.classList.add('exit');
    setTimeout(() => {
      intro.remove();
      document.querySelectorAll('.anim-up').forEach(el => el.classList.add('visible'));
    }, 700);
  }, 4000);
}

// Nav scroll shadow
const nav = document.getElementById('nav');
window.addEventListener('scroll', () => {
  nav.classList.toggle('scrolled', window.scrollY > 20);
});

// Mobile Burger
const burger = document.getElementById('burger');
const mobileMenu = document.getElementById('mobileMenu');
burger.addEventListener('click', () => {
  mobileMenu.classList.toggle('open');
});
mobileMenu.querySelectorAll('a').forEach(a => {
  a.addEventListener('click', () => mobileMenu.classList.remove('open'));
});

// ── Kontakt Smart Form ────────────────────────────────────────────────────────

// Backend-Endpunkt: speichert im Dashboard-DB, sendet Email parallel
const KONTAKT_ENDPOINT = 'https://api.hautnah-textil.de/api/kontakt';

const kategorienConfig = {
  bestellung: {
    felder: ['fg-vereinsname', 'fg-email', 'fg-telefon', 'fg-artikel', 'fg-lieferdatum', 'fg-nachricht'],
    pflicht: ['inp-vereinsname', 'inp-email'],
    nachrichtPlaceholder: 'Besondere Wünsche? Welche Saison, Logos, Größen?'
  },
  angebot: {
    felder: ['fg-vereinsname', 'fg-email', 'fg-telefon', 'fg-artikel', 'fg-nachricht'],
    pflicht: ['inp-vereinsname', 'inp-email'],
    nachrichtPlaceholder: 'Was soll angeboten werden? (optional)'
  },
  liefertermin: {
    felder: ['fg-vereinsname', 'fg-email', 'fg-bestellnummer', 'fg-nachricht'],
    pflicht: ['inp-vereinsname', 'inp-email', 'inp-nachricht'],
    nachrichtPlaceholder: 'Eure Frage zum Liefertermin …'
  },
  reklamation: {
    felder: ['fg-vereinsname', 'fg-email', 'fg-telefon', 'fg-bestellnummer', 'fg-nachricht'],
    pflicht: ['inp-vereinsname', 'inp-email', 'inp-nachricht'],
    nachrichtPlaceholder: 'Beschreibt das Problem so genau wie möglich.'
  },
  rueckruf: {
    felder: ['fg-vereinsname', 'fg-email', 'fg-telefon', 'fg-rueckruf_zeit', 'fg-nachricht'],
    pflicht: ['inp-vereinsname', 'inp-email', 'inp-telefon'],
    nachrichtPlaceholder: 'Worum geht es? (optional)'
  },
  nachricht: {
    felder: ['fg-vereinsname', 'fg-email', 'fg-nachricht'],
    pflicht: ['inp-vereinsname', 'inp-email', 'inp-nachricht'],
    nachrichtPlaceholder: 'Eure Nachricht …'
  }
};

const alleFelder = ['fg-vereinsname', 'fg-email', 'fg-telefon', 'fg-artikel',
  'fg-lieferdatum', 'fg-bestellnummer', 'fg-rueckruf_zeit', 'fg-nachricht'];

document.querySelectorAll('.kat-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    const kat = btn.dataset.kat;
    const cfg = kategorienConfig[kat];

    document.querySelectorAll('.kat-btn').forEach(b => b.classList.remove('aktiv'));
    btn.classList.add('aktiv');

    alleFelder.forEach(id => {
      const el = document.getElementById(id);
      if (el) el.style.display = 'none';
    });
    cfg.felder.forEach(id => {
      const el = document.getElementById(id);
      if (el) el.style.display = 'block';
    });

    const nachrichtEl = document.getElementById('inp-nachricht');
    if (nachrichtEl) nachrichtEl.placeholder = cfg.nachrichtPlaceholder;

    document.querySelectorAll('#kontaktForm input, #kontaktForm textarea, #kontaktForm select').forEach(el => {
      el.required = false;
    });
    cfg.pflicht.forEach(id => {
      const el = document.getElementById(id);
      if (el) el.required = true;
    });

    document.getElementById('formKategorie').value = kat;
    document.getElementById('formTimestamp').value = Date.now();
    document.getElementById('kontaktForm').classList.add('aktiv');
  });
});

// Artikel-Repeater
const addRowBtn = document.querySelector('.btn-add-row');
if (addRowBtn) {
  addRowBtn.addEventListener('click', () => {
    const row = document.createElement('div');
    row.className = 'artikel-row';
    row.innerHTML = '<input type="text" name="artikel[]" placeholder="Artikel"><input type="number" name="menge[]" placeholder="Stück" min="1" class="inp-menge">';
    document.getElementById('artikelListe').appendChild(row);
  });
}

// Form Submit → Backend speichert im Dashboard, sendet Email
const kontaktForm = document.getElementById('kontaktForm');
if (kontaktForm) {
  kontaktForm.addEventListener('submit', async function(e) {
    e.preventDefault();
    const submitBtn = this.querySelector('[type=submit]');
    submitBtn.disabled = true;
    submitBtn.textContent = 'Wird gesendet …';

    const data = Object.fromEntries(new FormData(this).entries());
    // Artikel-Arrays separat zusammensetzen
    const artikel = [...this.querySelectorAll('[name="artikel[]"]')].map(el => el.value).filter(Boolean);
    const mengen  = [...this.querySelectorAll('[name="menge[]"]')].map(el => el.value);
    if (artikel.length) data.artikel = artikel.map((a, i) => ({ artikel: a, menge: mengen[i] || '' }));

    try {
      const resp = await fetch(KONTAKT_ENDPOINT, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
      });
      if (!resp.ok) throw new Error('server');
      this.classList.remove('aktiv');
      document.getElementById('formSuccess').classList.add('aktiv');
      document.getElementById('kategoriePicker').style.display = 'none';
    } catch {
      submitBtn.disabled = false;
      submitBtn.textContent = 'Absenden';
      alert('Beim Senden ist ein Fehler aufgetreten. Bitte versucht es erneut oder schreibt uns direkt: hautnah-textil@gmx.de');
    }
  });
}
