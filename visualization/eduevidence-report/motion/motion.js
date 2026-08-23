/* EduEvidence Motion Template — one-shot progressive enhancement.
   The [data-lieflat] gallery block implements the Lieflat mono-tokens
   obsReveal contract: reveal once when scrolled into view (threshold .3),
   click to replay (per-id timers cleared first so animations never stack),
   prefers-reduced-motion downgrade, and static-visible without JS. */
(function () {
  'use strict';
  var root = document.documentElement;
  var reduceMotion = !!(window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches);
  window.__EDUEVIDENCE_REDUCE_MOTION__ = reduceMotion;
  if (reduceMotion) return;

  root.classList.add('motion-ready');
  root.classList.add('js-lf');
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
  } else {
    var observer = new IntersectionObserver(function (entries, obs) {
      entries.forEach(function (entry) {
        if (!entry.isIntersecting) return;
        entry.target.classList.add('is-visible');
        obs.unobserve(entry.target);
      });
    }, {threshold:.12, rootMargin:'0px 0px -6% 0px'});
    animated.forEach(function (el) { observer.observe(el); });
  }

  // ---- data-lieflat gallery: reveal on scroll, click to replay ----
  // Per-container timers (mirrors mono-tokens `keep`): every scheduled
  // replay step is registered under the container id and cleared before the
  // next replay so staggered animations never stack on rapid clicking.
  var lfTimers = {};
  var lfBoxes = Array.prototype.slice.call(document.querySelectorAll('[data-lieflat]'));
  lfBoxes.forEach(function (box, index) {
    var base = (box.dataset.chartId || 'figure');
    var safe = 'lf-' + index + '-' + (window.CSS && CSS.escape ? CSS.escape(base) : base.replace(/[^a-zA-Z0-9_-]/g, '-'));
    box.dataset.lfId = safe;
    if (!box.hasAttribute('aria-label')) {
      box.setAttribute('aria-label', 'Lieflat chart — click to replay the reveal animation');
    }
  });

  function clearLfTimers(id) {
    (lfTimers[id] || []).forEach(function (t) { if (t) clearTimeout(t); });
    lfTimers[id] = [];
  }

  function replayLieflat(box) {
    var id = box.dataset.lfId;
    clearLfTimers(id);
    box.classList.remove('is-live');
    // force reflow so the re-added class restarts the CSS animations
    void box.offsetWidth;
    var raf = null;
    var tid = setTimeout(function () {
      box.classList.add('is-live');
      lfTimers[id] = lfTimers[id].filter(function (t) { return t !== tid; });
    }, 0);
    lfTimers[id].push(tid);
  }

  if (!('IntersectionObserver' in window)) {
    lfBoxes.forEach(function (box) { box.classList.add('is-live'); });
  } else {
    var lfObserver = new IntersectionObserver(function (entries, obs) {
      entries.forEach(function (entry) {
        if (!entry.isIntersecting) return;
        replayLieflat(entry.target);
        obs.unobserve(entry.target);
      });
    }, {threshold:.3});
    lfBoxes.forEach(function (box) { lfObserver.observe(box); });
  }
  lfBoxes.forEach(function (box) {
    box.addEventListener('click', function () { replayLieflat(box); });
  });
})();
