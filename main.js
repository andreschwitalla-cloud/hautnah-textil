// Intro entfernen nach Animation
const intro = document.getElementById('intro');
if (intro) {
  intro.addEventListener('animationend', () => intro.remove(), { once: true });
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

// Kontaktformular (Formspree oder mailto-Fallback)
document.getElementById('kontaktForm').addEventListener('submit', function(e) {
  e.preventDefault();
  const data = Object.fromEntries(new FormData(this));
  const subject = encodeURIComponent('Anfrage – ' + (data.druckart || 'Allgemein') + ' – ' + (data.name || ''));
  const body = encodeURIComponent(
    `Verein / Name: ${data.name}\nE-Mail: ${data.email}\nBedarf: ${data.druckart || '–'}\nStückzahl: ${data.menge || '–'}\n\n${data.nachricht}`
  );
  window.location.href = `mailto:hautnah-textil@gmx.de?subject=${subject}&body=${body}`;
});
