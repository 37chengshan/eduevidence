/* EduEvidence Motion Template — one-shot progressive enhancement. */
(function () {
  'use strict';
  var root = document.documentElement;
  var reduceMotion = !!(window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches);
  window.__EDUEVIDENCE_REDUCE_MOTION__ = reduceMotion;
  if (reduceMotion) return;

  root.classList.add('motion-ready');
  var groups = [
    ['.decision-hero', 0], ['.hero-insight', 70], ['.brief-block', 55],
    ['.outcome-group', 70], ['.tribunal-card', 75], ['.method-audit-item', 45],
    ['.trace-chain-card', 70], ['.action-node', 60], ['.flow-arrow', 60],
    ['.phase', 60], ['.full-chapter', 35], ['.brief-source', 40]
  ];
  groups.forEach(function (entry) {
    document.querySelectorAll(entry[0]).forEach(function (el, index) {
      el.setAttribute('data-animate', '');
      el.style.setProperty('--motion-delay', Math.min(index * entry[1], 320) + 'ms');
    });
  });
  document.querySelectorAll('.quality-meter,.balance-track').forEach(function (el, index) {
    el.style.setProperty('--motion-delay', Math.min((index % 8) * 35, 210) + 'ms');
  });

  var animated = document.querySelectorAll('[data-animate],.quality-meter,.balance-track,.flow-arrow');
  if (!('IntersectionObserver' in window)) {
    animated.forEach(function (el) { el.classList.add('is-visible'); });
    return;
  }
  var observer = new IntersectionObserver(function (entries, obs) {
    entries.forEach(function (entry) {
      if (!entry.isIntersecting) return;
      entry.target.classList.add('is-visible');
      obs.unobserve(entry.target);
    });
  }, {threshold:.12, rootMargin:'0px 0px -6% 0px'});
  animated.forEach(function (el) { observer.observe(el); });
})();
