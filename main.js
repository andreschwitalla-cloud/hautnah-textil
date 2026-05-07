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
  const subject = encodeURIComponent('Anfrage Hautnah Textil – ' + (data.druckart || 'Allgemein'));
  const body = encodeURIComponent(
    `Name: ${data.name}\nE-Mail: ${data.email}\nDruckart: ${data.druckart || '–'}\nMenge: ${data.menge || '–'}\n\n${data.nachricht}`
  );
  window.location.href = `mailto:info@hautnah-textil.de?subject=${subject}&body=${body}`;
});
