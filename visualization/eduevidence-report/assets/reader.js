/* Offline reader: navigation and display only; no research state mutations. */
(function () {
  "use strict";
  var root = document.documentElement;
  var copy = {
    zh: {
      brief: "\u6458\u8981",
      full: "\u5b8c\u6574\u62a5\u544a",
      print: "\u6253\u5370",
      matched: "\u6761\u8bc1\u636e",
    },
    en: {
      brief: "Brief",
      full: "Full report",
      print: "Print",
      matched: "findings",
    },
  };
  function labels() {
    var lang = root.lang.indexOf("en") === 0 ? "en" : "zh";
    document.querySelectorAll("[data-copy]").forEach(function (el) {
      el.textContent = copy[lang][el.dataset.copy];
    });
  }
  labels();
  new MutationObserver(labels).observe(root, {
    attributes: true,
    attributeFilter: ["lang"],
  });
  document.querySelectorAll(".reader-print").forEach(function (b) {
    b.addEventListener("click", function () {
      window.print();
    });
  });
  document.querySelectorAll(".reader-home").forEach(function (a) {
    a.addEventListener("click", function (e) {
      e.preventDefault();
      window.scrollTo({ top: 0, behavior: "instant" });
    });
  });
  var scheduled = false;
  function progress() {
    scheduled = false;
    var max = document.documentElement.scrollHeight - window.innerHeight;
    var fraction = max > 0 ? Math.min(1, Math.max(0, window.scrollY / max)) : 0;
    var bar = document.querySelector(".reader-progress>span");
    if (bar) bar.style.transform = "scaleX(" + fraction + ")";
    var shell = Array.from(document.querySelectorAll(".report-shell")).find(
      function (s) {
        return getComputedStyle(s).display !== "none";
      },
    );
    if (!shell) return;
    var blocks = Array.from(shell.querySelectorAll(".brief-block[id]"));
    var current = blocks
      .filter(function (b) {
        return b.getBoundingClientRect().top < 150;
      })
      .pop();
    shell.querySelectorAll(".brief-navigation a").forEach(function (a) {
      var active = current && a.hash === "#" + current.id;
      a.classList.toggle("active", !!active);
      if (active) a.setAttribute("aria-current", "location");
      else a.removeAttribute("aria-current");
    });
  }
  function queue() {
    if (!scheduled) {
      scheduled = true;
      requestAnimationFrame(progress);
    }
  }
  window.addEventListener("scroll", queue, { passive: true });
  window.addEventListener("resize", queue);
  document.addEventListener("click", queue);
  progress();
  document.querySelectorAll(".report-view-btn").forEach(function (btn) {
    btn.addEventListener("click", function () {
      window.scrollTo({ top: 0, behavior: "instant" });
    });
  });
  document
    .querySelectorAll(".table-wrap,.evidence-to-action")
    .forEach(function (el) {
      el.tabIndex = 0;
      el.setAttribute("role", "region");
      el.setAttribute(
        "aria-label",
        root.lang.indexOf("en") === 0
          ? "Scrollable data table"
          : "\u53ef\u6eda\u52a8\u6570\u636e\u8868",
      );
    });
  document
    .querySelectorAll('table[id^="evidence-matrix-"]')
    .forEach(function (table) {
      var suffix = table.id.replace(/^evidence-matrix-/, "");
      var counter = document.createElement("p");
      counter.className = "reader-filter-count";
      counter.setAttribute("role", "status");
      counter.setAttribute("aria-live", "polite");
      table.parentElement.insertAdjacentElement("beforebegin", counter);
      function count() {
        var rows = Array.from(table.querySelectorAll("tbody tr"));
        var visible = rows.filter(function (r) {
          return r.style.display !== "none";
        }).length;
        counter.textContent =
          visible +
          " / " +
          rows.length +
          " " +
          copy[suffix.endsWith("en") ? "en" : "zh"].matched;
      }
      ["matrix-search-", "matrix-direction-", "matrix-outcome-"].forEach(
        function (prefix) {
          var input = document.getElementById(prefix + suffix);
          if (input) {
            input.addEventListener("input", count);
            input.addEventListener("change", count);
          }
        },
      );
      count();
    });
  document
    .querySelectorAll('a[href^="http:"] , a[href^="https:"]')
    .forEach(function (a) {
      a.target = "_blank";
      a.rel = "noopener noreferrer";
    });
})();
