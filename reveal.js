// Scroll-Reveal: Elemente gestaffelt einblenden, sobald sie in den Viewport kommen.
// Klassen werden automatisch vergeben (kein HTML-Gefummel). Hero (.anim-up) bleibt unberührt.
(function () {
  var reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  // Sektionsweise Kandidaten – über alle Seiten hinweg (index, vereinswelt, ueber-uns)
  var SELECTORS = [
    '.section-head',
    '.cards > .card',
    '.galerie-bild',
    '.usps .usp',
    '.steps > .step',
    '.kontakt-kopf',
    '.shop-teaser-inner > *',
    '.stanno-banner-content',
    '.stanno-grid > .stanno-item',
    '.charity > div',
    '.familie-text'
  ];

  var els = [].slice.call(document.querySelectorAll(SELECTORS.join(',')));
  els = els.filter(function (el) {
    return !el.classList.contains('anim-up') && !(el.closest && el.closest('.hero-banner'));
  });
  if (!els.length) return;

  els.forEach(function (el) { el.classList.add('reveal'); });
  // Bilder/Kacheln zarter „rein-zoomen"
  document.querySelectorAll('.galerie-bild, .stanno-grid > .stanno-item').forEach(function (el) {
    el.classList.add('r-scale');
  });

  if (reduce || !('IntersectionObserver' in window)) {
    els.forEach(function (el) { el.classList.add('in'); });
    return;
  }

  // Staffelung nach Geschwister-Index innerhalb desselben Eltern-Elements (gedeckelt)
  var counts = new Map();
  els.forEach(function (el) {
    var p = el.parentElement;
    var i = counts.get(p) || 0;
    counts.set(p, i + 1);
    el.style.transitionDelay = Math.min(i * 90, 360) + 'ms';
  });

  var io = new IntersectionObserver(function (entries) {
    entries.forEach(function (e) {
      if (e.isIntersecting) {
        e.target.classList.add('in');
        io.unobserve(e.target);
      }
    });
  }, { threshold: 0.12, rootMargin: '0px 0px -8% 0px' });

  els.forEach(function (el) { io.observe(el); });

  // Kontakt: Kategorie-Buttons nacheinander einmal aufleuchten lassen
  var picker = document.querySelector('.kategorie-picker');
  if (picker && !reduce && 'IntersectionObserver' in window) {
    var btns = [].slice.call(picker.querySelectorAll('.kat-btn'));
    var pio = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (e.isIntersecting) {
          btns.forEach(function (b, i) {
            b.style.animationDelay = (i * 150) + 'ms';
            b.classList.add('kat-glow');
          });
          pio.disconnect();
        }
      });
    }, { threshold: 0.45 });
    pio.observe(picker);
  }
})();
