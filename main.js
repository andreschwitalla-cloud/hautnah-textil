// Intro: 4s zeigen, dann Iris-Close, dann Hero einblenden – aber nur einmal pro Session.
const intro = document.getElementById('intro');
const heroEinblenden = () => document.querySelectorAll('.anim-up').forEach(el => el.classList.add('visible'));
if (intro) {
  let schonGesehen = false;
  try { schonGesehen = !!sessionStorage.getItem('introSeen'); } catch (e) {}
  if (schonGesehen) {
    // Beim Zurückspringen im selben Besuch: Intro überspringen, Inhalt direkt zeigen
    intro.remove();
    heroEinblenden();
  } else {
    try { sessionStorage.setItem('introSeen', '1'); } catch (e) {}
    setTimeout(() => {
      intro.classList.add('exit');
      setTimeout(() => {
        intro.remove();
        heroEinblenden();
      }, 700);
    }, 4000);
  }
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
// Lokal (file:// oder localhost) automatisch gegen den Dev-Server testen.
const API_BASE = /hautnah-textil\.de$/.test(location.hostname)
  ? 'https://api.hautnah-textil.de'
  : 'http://localhost:5003';
const KONTAKT_ENDPOINT = API_BASE + '/api/kontakt';
const PRODUKT_SUCHE_ENDPOINT = API_BASE + '/api/produkt/suche';

// Reklamationsgründe, die auch bei bedruckten Artikeln zulässig sind
const DRUCK_GRUENDE = ['Falschdruck/Druckfehler'];

const kategorienConfig = {
  bestellung: {
    felder: ['fg-vereinsname', 'fg-email', 'fg-telefon', 'fg-produktsuche', 'fg-beflockung', 'fg-lieferdatum', 'fg-nachricht'],
    pflicht: ['inp-vereinsname', 'inp-email'],
    nachrichtPlaceholder: 'Besondere Wünsche? Welche Saison, Größen?'
  },
  angebot: {
    felder: ['fg-vereinsname', 'fg-email', 'fg-telefon', 'fg-produktsuche', 'fg-beflockung', 'fg-nachricht'],
    pflicht: ['inp-vereinsname', 'inp-email'],
    nachrichtPlaceholder: 'Was soll angeboten werden? (optional)'
  },
  liefertermin: {
    felder: ['fg-vereinsname', 'fg-email', 'fg-bestellnummer', 'fg-nachricht'],
    pflicht: ['inp-vereinsname', 'inp-email', 'inp-nachricht'],
    nachrichtPlaceholder: 'Eure Frage zum Liefertermin …'
  },
  reklamation: {
    felder: ['fg-vereinsname', 'fg-email', 'fg-telefon', 'fg-bestellnummer', 'fg-produktsuche', 'fg-bedruckt', 'fg-grund', 'fg-fotos', 'fg-nachricht'],
    pflicht: ['inp-vereinsname', 'inp-email', 'inp-bedruckt', 'inp-grund', 'inp-nachricht'],
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

const alleFelder = ['fg-vereinsname', 'fg-email', 'fg-telefon', 'fg-beflockung',
  'fg-lieferdatum', 'fg-bestellnummer', 'fg-produktsuche', 'fg-bedruckt',
  'fg-grund', 'fg-fotos', 'fg-rueckruf_zeit', 'fg-nachricht'];

// Bei welchen Kategorien darf der Kunde mehrere Artikel wählen?
const MEHRFACH_PRODUKTE = ['bestellung', 'angebot'];
let aktuelleKategorie = null;
let gewaehlteProdukte = [];

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

    // Produktauswahl + Reklamationslogik bei Kategoriewechsel zurücksetzen
    aktuelleKategorie = kat;
    gewaehlteProdukte = [];
    renderProduktAuswahl();
    const ergebnisse = document.getElementById('produktErgebnisse');
    if (ergebnisse) ergebnisse.innerHTML = '';
    const sucheInput = document.getElementById('inp-produktsuche');
    if (sucheInput) sucheInput.value = '';
    setzeBedrucktRegel();
  });
});

// ── Produktsuche (Stanno-Katalog) ──────────────────────────────────────────────

function syncProdukteHidden() {
  const hidden = document.getElementById('inpProdukte');
  if (hidden) hidden.value = gewaehlteProdukte.length ? JSON.stringify(gewaehlteProdukte) : '';
}

function renderProduktAuswahl() {
  const box = document.getElementById('produktAuswahl');
  if (!box) return;
  const mitMenge = MEHRFACH_PRODUKTE.includes(aktuelleKategorie);
  box.innerHTML = gewaehlteProdukte.map((p, i) => `
    <div class="produkt-chip">
      <span class="produkt-chip-info">${p.bezeichnung} · Gr. ${p.groesse || '–'} · ${p.farbe || p.hauptfarbe || ''} <small>(${p.artikelnummer || p.ean})</small></span>
      ${mitMenge ? `<label class="produkt-chip-menge">Menge <input type="number" min="1" value="${p.menge || 1}" data-i="${i}" aria-label="Menge"></label>` : ''}
      <button type="button" class="produkt-chip-x" data-i="${i}" aria-label="Entfernen">✕</button>
    </div>`).join('');
  syncProdukteHidden();
  box.querySelectorAll('.produkt-chip-x').forEach(btn => {
    btn.addEventListener('click', () => {
      gewaehlteProdukte.splice(Number(btn.dataset.i), 1);
      renderProduktAuswahl();
    });
  });
  box.querySelectorAll('.produkt-chip-menge input').forEach(inp => {
    inp.addEventListener('input', () => {
      const v = Math.max(1, parseInt(inp.value, 10) || 1);
      gewaehlteProdukte[Number(inp.dataset.i)].menge = v;
      syncProdukteHidden();
    });
  });
}

function produktWaehlen(p) {
  p.menge = p.menge || 1;
  if (MEHRFACH_PRODUKTE.includes(aktuelleKategorie)) {
    if (!gewaehlteProdukte.some(x => x.ean === p.ean)) gewaehlteProdukte.push(p);
  } else {
    gewaehlteProdukte = [p];  // Reklamation: genau ein Artikel
  }
  renderProduktAuswahl();
  document.getElementById('produktErgebnisse').innerHTML = '';
  document.getElementById('inp-produktsuche').value = '';
}

let sucheSeq = 0;  // gegen veraltete Antworten (Race) bei schnellem Tippen

async function produktSuchen(showLoading = false) {
  const q = (document.getElementById('inp-produktsuche').value || '').trim();
  const box = document.getElementById('produktErgebnisse');
  if (q.length < 2) { box.innerHTML = ''; return; }
  if (showLoading) box.innerHTML = '<p class="produkt-hinweis">Suche läuft …</p>';
  const seq = ++sucheSeq;
  try {
    const resp = await fetch(`${PRODUKT_SUCHE_ENDPOINT}?q=${encodeURIComponent(q)}`);
    const json = await resp.json();
    if (seq !== sucheSeq) return;  // eine neuere Suche ist schon unterwegs
    const treffer = json.treffer || [];
    if (!treffer.length) { box.innerHTML = '<p class="produkt-hinweis">Kein Artikel gefunden.</p>'; return; }
    box.innerHTML = treffer.map((p, i) => `
      <button type="button" class="produkt-treffer" data-i="${i}">
        ${p.bild ? `<img src="${p.bild}" alt="" loading="lazy">` : '<span class="produkt-noimg"></span>'}
        <span class="produkt-treffer-info">
          <strong>${p.bezeichnung}</strong>
          <small>Gr. ${p.groesse || '–'} · ${p.farbe || p.hauptfarbe || ''} · ${p.artikelnummer || p.ean}</small>
        </span>
      </button>`).join('');
    box.querySelectorAll('.produkt-treffer').forEach(btn => {
      btn.addEventListener('click', () => produktWaehlen(treffer[Number(btn.dataset.i)]));
    });
  } catch {
    if (seq === sucheSeq) box.innerHTML = '<p class="produkt-hinweis">Suche momentan nicht möglich. Bitte später erneut versuchen.</p>';
  }
}

const btnSuche = document.getElementById('btnProduktSuche');
if (btnSuche) btnSuche.addEventListener('click', () => produktSuchen(true));
const sucheInputEl = document.getElementById('inp-produktsuche');
if (sucheInputEl) {
  let sucheTimer = null;
  // Live-Autovervollständigung: schon beim Tippen suchen (entprellt)
  sucheInputEl.addEventListener('input', () => {
    clearTimeout(sucheTimer);
    sucheTimer = setTimeout(() => produktSuchen(false), 220);
  });
  sucheInputEl.addEventListener('keydown', e => {
    if (e.key === 'Enter') { e.preventDefault(); clearTimeout(sucheTimer); produktSuchen(true); }
  });
}

// ── Reklamation: bedruckte Artikel nur bei Druckfehler reklamierbar ─────────────

function setzeBedrucktRegel() {
  const bedruckt = document.getElementById('inp-bedruckt');
  const grund = document.getElementById('inp-grund');
  const hinweis = document.getElementById('bedrucktHinweis');
  if (!bedruckt || !grund) return;
  const istBedruckt = bedruckt.value === 'ja';
  if (hinweis) hinweis.style.display = istBedruckt ? 'block' : 'none';
  [...grund.options].forEach(opt => {
    if (!opt.value) return;
    const erlaubt = !istBedruckt || DRUCK_GRUENDE.includes(opt.value);
    opt.disabled = !erlaubt;
  });
  // Falls aktuell unzulässiger Grund gewählt ist → zurücksetzen
  if (istBedruckt && grund.value && !DRUCK_GRUENDE.includes(grund.value)) {
    grund.value = '';
  }
}

const bedrucktEl = document.getElementById('inp-bedruckt');
if (bedrucktEl) bedrucktEl.addEventListener('change', setzeBedrucktRegel);

// Form Submit → Backend speichert im Dashboard, sendet Email
const kontaktForm = document.getElementById('kontaktForm');
if (kontaktForm) {
  kontaktForm.addEventListener('submit', async function(e) {
    e.preventDefault();

    // Client-seitige Bedruckt-Sperre (Backend prüft zusätzlich)
    if (aktuelleKategorie === 'reklamation') {
      const bedruckt = document.getElementById('inp-bedruckt').value;
      const grund    = document.getElementById('inp-grund').value;
      if (bedruckt === 'ja' && !DRUCK_GRUENDE.includes(grund)) {
        alert('Bedruckte bzw. individualisierte Artikel können nur bei Druckfehlern (z. B. Falschdruck) reklamiert werden.');
        return;
      }
    }

    const submitBtn = this.querySelector('[type=submit]');
    submitBtn.disabled = true;
    submitBtn.textContent = 'Wird gesendet …';

    const data = Object.fromEntries(new FormData(this).entries());

    // Ausgewählte Katalog-Produkte (inkl. Menge) mitschicken
    if (gewaehlteProdukte.length) data.produkte = gewaehlteProdukte;

    // Datei-Uploads → multipart wenn Fotos (Reklamation) oder Logo (Bestellung/Angebot) dabei
    const fotoInput = document.getElementById('inp-fotos');
    const fotos = fotoInput && fotoInput.files ? [...fotoInput.files].slice(0, 3) : [];
    const logoInput = document.getElementById('inp-logo');
    const logo = logoInput && logoInput.files && logoInput.files[0] ? logoInput.files[0] : null;

    let fetchOpts;
    if (fotos.length || logo) {
      const fd = new FormData();
      Object.entries(data).forEach(([k, v]) => {
        if (k === 'fotos' || k === 'logo') return;  // Datei-Inputs separat behandeln
        fd.append(k, typeof v === 'object' ? JSON.stringify(v) : v);
      });
      fotos.forEach(f => fd.append('fotos', f));
      if (logo) fd.append('logo', logo);
      fetchOpts = { method: 'POST', body: fd };  // Browser setzt multipart-Header
    } else {
      delete data.fotos; delete data.logo;
      fetchOpts = { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) };
    }

    try {
      const resp = await fetch(KONTAKT_ENDPOINT, fetchOpts);
      if (!resp.ok) {
        let msg = '';
        try { msg = (await resp.json()).error || ''; } catch {}
        if (resp.status === 400 && msg) { alert(msg); throw new Error('validierung'); }
        throw new Error('server');
      }
      this.classList.remove('aktiv');
      document.getElementById('formSuccess').classList.add('aktiv');
      document.getElementById('kategoriePicker').style.display = 'none';
    } catch (err) {
      submitBtn.disabled = false;
      submitBtn.textContent = 'Absenden';
      if (err.message !== 'validierung') {
        alert('Beim Senden ist ein Fehler aufgetreten. Bitte versucht es erneut oder schreibt uns direkt: hautnah-textil@gmx.de');
      }
    }
  });
}
