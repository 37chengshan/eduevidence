/**
 * web/landing.js — Motionsite.ai Exact Reconstruction Scroll Engine & Wave Transition
 */

(function () {
  'use strict';

  // Elements
  const navbar = document.getElementById('floating-navbar');
  const navContainer = document.querySelector('.floating-navbar-container');
  const heroContainer = document.getElementById('hero-section');
  const heroViewport = document.getElementById('hero-sticky-viewport');
  
  const circle1 = document.getElementById('circle-1');
  const circle2 = document.getElementById('circle-2');
  const circle3 = document.getElementById('circle-3');
  const circle4 = document.getElementById('circle-4');
  
  const giantTypography = document.getElementById('hero-giant-typography');
  const contentSeq1 = document.getElementById('content-seq-1');
  const contentSeq2 = document.getElementById('content-seq-2');
  
  const stackingSection = document.getElementById('stacking-section');
  const card1 = document.getElementById('stack-card-1');
  const card2 = document.getElementById('stack-card-2');
  const card3 = document.getElementById('stack-card-3');

  // Math helper
  const clamp = (val, min, max) => Math.min(Math.max(val, min), max);
  const mapRange = (val, inMin, inMax, outMin, outMax) => {
    const norm = clamp((val - inMin) / (inMax - inMin), 0, 1);
    return outMin + norm * (outMax - outMin);
  };

  // Scroll Engine
  function onScroll() {
    const scrollY = window.scrollY || window.pageYOffset;

    // 1. Navbar Scrolled State (>40px)
    if (navbar) {
      if (scrollY > 40) {
        navbar.classList.add('scrolled');
        if (navContainer) navContainer.classList.add('scrolled');
      } else {
        navbar.classList.remove('scrolled');
        if (navContainer) navContainer.classList.remove('scrolled');
      }
    }

    // 2. Hero Section Scrubbing (400vh)
    if (heroContainer && heroViewport) {
      const heroRect = heroContainer.getBoundingClientRect();
      const heroTop = heroRect.top;
      const heroHeight = heroContainer.offsetHeight - window.innerHeight;
      const progress = clamp(-heroTop / (heroHeight || 1), 0, 1);

      const scrollHint = document.getElementById('hero-scroll-hint');
      if (scrollHint) {
        const hintOp = mapRange(progress, 0.0, 0.04, 1.0, 0.0);
        scrollHint.style.opacity = `${hintOp}`;
      }

      // (A) Concentric Scaling Circles
      if (circle1) {
        const s1 = mapRange(progress, 0.0, 0.70, 1.0, 5.0);
        circle1.style.transform = `scale(${s1})`;
      }
      if (circle2) {
        const s2 = mapRange(progress, 0.05, 0.65, 0.8, 4.2);
        const op2 = mapRange(progress, 0.30, 0.45, 1.0, 0.0);
        circle2.style.transform = `scale(${s2})`;
        circle2.style.opacity = `${op2}`;
      }
      if (circle3) {
        const s3 = mapRange(progress, 0.10, 0.60, 0.6, 3.5);
        const op3 = mapRange(progress, 0.30, 0.45, 1.0, 0.0);
        circle3.style.transform = `scale(${s3})`;
        circle3.style.opacity = `${op3}`;
      }
      if (circle4) {
        const s4 = mapRange(progress, 0.15, 0.55, 0.4, 2.8);
        const op4 = mapRange(progress, 0.30, 0.45, 1.0, 0.0);
        circle4.style.transform = `scale(${s4})`;
        circle4.style.opacity = `${op4}`;
      }

      // (B) Giant Typography ("EDU [ E ] VIDENCE"): Fades out quickly in first 7% of scroll
      if (giantTypography) {
        const giantOp = mapRange(progress, 0.0, 0.07, 1.0, 0.0);
        const giantScale = mapRange(progress, 0.0, 0.07, 1.0, 0.94);
        giantTypography.style.opacity = `${giantOp}`;
        giantTypography.style.transform = `translate(-50%, -50%) scale(${giantScale})`;
      }

      // (C) Content Sequence 1: Fades in (0.08->0.18), stays visible, fades out (0.30->0.38)
      if (contentSeq1) {
        let op1 = 0;
        let y1 = 60;
        if (progress < 0.25) {
          op1 = mapRange(progress, 0.08, 0.18, 0.0, 1.0);
          y1 = mapRange(progress, 0.08, 0.18, 60, 0);
        } else {
          op1 = mapRange(progress, 0.30, 0.38, 1.0, 0.0);
          y1 = mapRange(progress, 0.30, 0.38, 0, -60);
        }
        contentSeq1.style.opacity = `${op1}`;
        contentSeq1.style.transform = `translateY(${y1}px)`;
        contentSeq1.style.pointerEvents = op1 > 0.5 ? 'auto' : 'none';
      }

      // (D) Content Sequence 2: Fades in (0.38->0.48) and stays visible until hero exit
      if (contentSeq2) {
        const op2 = mapRange(progress, 0.38, 0.48, 0.0, 1.0);
        const y2 = mapRange(progress, 0.38, 0.48, 60, 0);
        contentSeq2.style.opacity = `${op2}`;
        contentSeq2.style.transform = `translateY(${y2}px)`;
        contentSeq2.style.pointerEvents = op2 > 0.5 ? 'auto' : 'none';
      }

      // (E) Sticky Viewport Shrink in final 25% (0.72 -> 1.0)
      if (progress > 0.70) {
        const heroScale = mapRange(progress, 0.72, 1.0, 1.0, 0.70);
        const heroRadius = mapRange(progress, 0.72, 1.0, 0, 60);
        const heroOp = mapRange(progress, 0.85, 1.0, 1.0, 0.0);
        heroViewport.style.transform = `scale(${heroScale})`;
        heroViewport.style.borderRadius = `${heroRadius}px`;
        heroViewport.style.opacity = `${heroOp}`;
      } else {
        heroViewport.style.transform = `scale(1)`;
        heroViewport.style.borderRadius = `0px`;
        heroViewport.style.opacity = `1`;
      }
    }

    // 3. Stacking Cards Scrubbing (300vh, -mt-[100vh])
    if (stackingSection && card1 && card2 && card3) {
      const stackRect = stackingSection.getBoundingClientRect();
      const stackTop = stackRect.top;
      const stackHeight = stackingSection.offsetHeight - window.innerHeight;
      const stackProgress = clamp(-stackTop / (stackHeight || 1), 0, 1);

      // Card 2 slides up from 100% to 0% (0.15 -> 0.50)
      const c2Y = mapRange(stackProgress, 0.15, 0.50, 100, 0);
      const c1Scale = mapRange(stackProgress, 0.20, 0.50, 1.0, 0.95);
      card2.style.transform = `translateY(${c2Y}%)`;
      card1.style.transform = `scale(${c1Scale})`;

      // Card 3 slides up from 100% to 0% (0.50 -> 0.85)
      const c3Y = mapRange(stackProgress, 0.50, 0.85, 100, 0);
      const c2Scale = mapRange(stackProgress, 0.55, 0.85, 1.0, 0.95);
      const c1ScaleFinal = mapRange(stackProgress, 0.55, 0.85, 0.95, 0.90);
      card3.style.transform = `translateY(${c3Y}%)`;
      if (stackProgress > 0.50) {
        card2.style.transform = `translateY(0%) scale(${c2Scale})`;
        card1.style.transform = `scale(${c1ScaleFinal})`;
      }
    }
  }

  // 5-Panel Horizontal Accordion Interaction
  function initAccordion() {
    const panels = document.querySelectorAll('.accordion-panel');
    if (!panels.length) return;

    panels.forEach(panel => {
      panel.addEventListener('mouseenter', () => {
        panels.forEach(p => p.classList.remove('active'));
        panel.classList.add('active');
      });
      panel.addEventListener('click', (e) => {
        if (e.target.closest('.acc-open-btn')) return;
        panels.forEach(p => p.classList.remove('active'));
        panel.classList.add('active');
      });
    });
  }

  // Asymmetric Left-to-Right Expanding Circular Wave Transition to Console
  function initWaveTransition() {
    const waveOverlay = document.createElement("div");
    waveOverlay.id = "landing-wave-overlay";
    waveOverlay.style.cssText = `
      position: fixed;
      inset: 0;
      pointer-events: none;
      z-index: 99999;
      background: radial-gradient(circle at center, #f24d29 0%, #c63d25 50%, #111111 100%);
      clip-path: circle(0px at 0px 0px);
      opacity: 0;
      transition: clip-path 0.52s cubic-bezier(0.22, 1, 0.36, 1), opacity 0.2s ease;
    `;
    document.body.appendChild(waveOverlay);

    // 控制台 (dashboard_server) 可能与落地页不同源：
    // 探测一个能应答 /api/projects 的 Studio 基址（同源优先，其次 8765-8774 默认端口段），
    // 保证「进入控制台」落到的永远是带数据的控制台，而不是静态服务器上的空壳 /index.html。
    let studioBase = window.location.origin;
    (async () => {
      const candidates = [window.location.origin];
      for (let i = 0; i < 10; i++) {
        candidates.push("http://" + (window.location.hostname || "127.0.0.1") + ":" + (8765 + i));
      }
      for (const base of candidates) {
        try {
          const r = await fetch(base + "/api/projects", { method: "GET", cache: "no-store" });
          if (r.ok && (r.headers.get("content-type") || "").includes("json")) {
            studioBase = base;
            break;
          }
        } catch (e) {
          /* 端口未监听 / 跨源被拒，试下一个 */
        }
      }
    })();

    function triggerTransition(targetUrl, e) {
      const btn = e ? e.currentTarget : document.getElementById("btn-to-studio");
      const rect = btn ? btn.getBoundingClientRect() : null;
      const x = rect ? rect.left + rect.width / 2 : (e ? e.clientX : 50);
      const y = rect ? rect.top + rect.height / 2 : (e ? e.clientY : window.innerHeight / 2);
      
      const maxRadius = Math.hypot(
        Math.max(x, window.innerWidth - x),
        Math.max(y, window.innerHeight - y)
      ) * 1.15;

      waveOverlay.style.transition = 'none';
      waveOverlay.style.opacity = '1';
      waveOverlay.style.clipPath = `circle(0px at ${x}px ${y}px)`;
      
      requestAnimationFrame(() => {
        waveOverlay.style.transition = 'clip-path 0.52s cubic-bezier(0.22, 1, 0.36, 1)';
        waveOverlay.style.clipPath = `circle(${maxRadius}px at ${x}px ${y}px)`;
      });

      setTimeout(() => {
        window.location.href = targetUrl;
      }, 480);
    }

    const launchBtns = document.querySelectorAll("#btn-to-studio, #nav-launch-btn, #hero-btn-studio, #footer-knockout-btn");
    launchBtns.forEach(btn => {
      btn.addEventListener("click", (e) => {
        e.preventDefault();
        triggerTransition((studioBase || window.location.origin) + "/index.html", e);
      });
    });
  }

  // Initialization
  document.addEventListener('DOMContentLoaded', () => {
    initAccordion();
    initWaveTransition();
    window.addEventListener('scroll', onScroll, { passive: true });
    window.addEventListener('resize', onScroll, { passive: true });
    onScroll();
  });

})();
