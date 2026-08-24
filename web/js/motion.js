/**
 * web/js/motion.js — MotionSite.ai inspired scroll dynamics & circular wave transition
 */

export function initWaveTransition(onSwitchCallback) {
  const wave = document.getElementById("transition-wave");
  const btnToConsole = document.getElementById("btn-to-console");
  const btnToLanding = document.getElementById("btn-to-landing");
  const navConsoleBtn = document.getElementById("nav-launch-btn");

  function triggerTransition(e, targetSpace) {
    if (!wave) {
      if (onSwitchCallback) onSwitchCallback(targetSpace);
      return;
    }

    let x = window.innerWidth * 0.05;
    let y = window.innerHeight * 0.5;

    if (e && (e.clientX || e.clientY)) {
      x = e.clientX;
      y = e.clientY;
    } else if (e && e.currentTarget) {
      const rect = e.currentTarget.getBoundingClientRect();
      x = rect.left + rect.width / 2;
      y = rect.top + rect.height / 2;
    }

    // Set origin for expanding circle
    wave.style.setProperty("--wave-x", `${x}px`);
    wave.style.setProperty("--wave-y", `${y}px`);

    // Add active animation class
    wave.classList.add("expanding");

    // At the midpoint (450ms), switch the active view
    setTimeout(() => {
      if (onSwitchCallback) onSwitchCallback(targetSpace);
    }, 450);

    // After animation completes (950ms), reset wave
    setTimeout(() => {
      wave.classList.remove("expanding");
      wave.classList.add("fading-out");
      setTimeout(() => {
        wave.classList.remove("fading-out");
      }, 300);
    }, 950);
  }

  if (btnToConsole) {
    btnToConsole.addEventListener("click", (e) => triggerTransition(e, "console"));
  }
  if (btnToLanding) {
    btnToLanding.addEventListener("click", (e) => triggerTransition(e, "landing"));
  }
  if (navConsoleBtn) {
    navConsoleBtn.addEventListener("click", (e) => triggerTransition(e, "console"));
  }

  return { triggerTransition };
}

export function initLandingMotion() {
  const heroSection = document.getElementById("hero-scroll-container");
  const heroLetters = document.getElementById("hero-giant-title");
  const heroCircle = document.getElementById("hero-center-circle");
  const heroContent1 = document.getElementById("hero-content-reveal-1");
  const heroContent2 = document.getElementById("hero-content-reveal-2");

  // Scroll listener for hero scrubbing
  function onScroll() {
    if (!heroSection) return;
    const rect = heroSection.getBoundingClientRect();
    const totalHeight = heroSection.offsetHeight - window.innerHeight;
    if (totalHeight <= 0) return;

    // Progress from 0 to 1
    const progress = Math.max(0, Math.min(1, -rect.top / totalHeight));

    // 1. Center concentric circle scaling
    if (heroCircle) {
      const scale = 0.8 + progress * 3.2; // 0.8 to 4.0
      const opacity = progress > 0.85 ? Math.max(0, (1 - progress) * 6.6) : 1;
      heroCircle.style.transform = `translate(-50%, -50%) scale(${scale})`;
      heroCircle.style.opacity = opacity;
    }

    // 2. Giant Typography fade out in first 25% of scroll
    if (heroLetters) {
      const letterOpacity = Math.max(0, 1 - progress * 4.0);
      const letterScale = 1 + progress * 0.3;
      heroLetters.style.opacity = letterOpacity;
      heroLetters.style.transform = `scale(${letterScale})`;
      heroLetters.style.pointerEvents = letterOpacity < 0.1 ? "none" : "auto";
    }

    // 3. Reveal Sequence 1: 0.12 -> 0.52
    if (heroContent1) {
      if (progress >= 0.12 && progress <= 0.52) {
        const p1 = (progress - 0.12) / 0.40;
        const opacity = p1 < 0.25 ? p1 * 4 : (p1 > 0.75 ? (1 - p1) * 4 : 1);
        const y = 30 * (1 - p1 * 2);
        heroContent1.style.opacity = Math.max(0, Math.min(1, opacity));
        heroContent1.style.transform = `translate(-50%, -50%) translateY(${y}px)`;
        heroContent1.style.pointerEvents = opacity > 0.5 ? "auto" : "none";
      } else {
        heroContent1.style.opacity = "0";
        heroContent1.style.pointerEvents = "none";
      }
    }

    // 4. Reveal Sequence 2: 0.48 -> 1.0
    if (heroContent2) {
      if (progress >= 0.48) {
        const p2 = Math.min(1, (progress - 0.48) / 0.35);
        const y = 30 * (1 - p2);
        heroContent2.style.opacity = p2;
        heroContent2.style.transform = `translate(-50%, -50%) translateY(${y}px)`;
        heroContent2.style.pointerEvents = p2 > 0.5 ? "auto" : "none";
      } else {
        heroContent2.style.opacity = "0";
        heroContent2.style.pointerEvents = "none";
      }
    }

    // 5. Stacking cards scroll calculation
    updateStackingCards();
  }

  window.addEventListener("scroll", onScroll, { passive: true });
  onScroll();

  // Paradox interactive slider
  initParadoxSlider();

  // 5-Theme accordion hover
  initThemeAccordion();
}

function updateStackingCards() {
  const stackContainer = document.getElementById("protocol-stack-container");
  if (!stackContainer) return;

  const cards = stackContainer.querySelectorAll(".stack-card");
  if (!cards.length) return;

  const rect = stackContainer.getBoundingClientRect();
  const total = stackContainer.offsetHeight - window.innerHeight;
  if (total <= 0) return;

  const progress = Math.max(0, Math.min(1, -rect.top / total));

  cards.forEach((card, index) => {
    const cardStart = index / cards.length;
    const cardEnd = (index + 1) / cards.length;
    
    if (progress < cardStart) {
      const offset = (cardStart - progress) * 120;
      card.style.transform = `translateY(${offset}px) scale(0.95)`;
      card.style.opacity = "0.4";
      card.style.zIndex = index + 1;
    } else if (progress >= cardStart && progress <= cardEnd) {
      const localP = (progress - cardStart) / (cardEnd - cardStart);
      const scale = 0.95 + localP * 0.05;
      card.style.transform = `translateY(0px) scale(${scale})`;
      card.style.opacity = "1";
      card.style.zIndex = index + 10;
    } else {
      const scale = 1 - (progress - cardEnd) * 0.05 - (cards.length - 1 - index) * 0.03;
      const translateY = -((cards.length - 1 - index) * 12);
      card.style.transform = `translateY(${translateY}px) scale(${Math.max(0.85, scale)})`;
      card.style.opacity = `${Math.max(0.6, 1 - (cards.length - 1 - index) * 0.15)}`;
      card.style.zIndex = index + 1;
    }
  });
}

function initParadoxSlider() {
  const slider = document.getElementById("paradox-range-slider");
  const splitLeft = document.getElementById("paradox-split-left");
  const splitRight = document.getElementById("paradox-split-right");
  const speedCounter = document.getElementById("paradox-speed-val");
  const examCounter = document.getElementById("paradox-exam-val");

  if (!slider) return;

  function updateParadox() {
    const val = parseFloat(slider.value);
    
    if (splitLeft) splitLeft.style.flex = `${100 - val}`;
    if (splitRight) splitRight.style.flex = `${val}`;

    if (splitLeft && splitRight) {
      if (val < 40) {
        splitLeft.classList.add("focus-glow");
        splitRight.classList.remove("focus-glow");
      } else if (val > 60) {
        splitRight.classList.add("focus-glow");
        splitLeft.classList.remove("focus-glow");
      } else {
        splitLeft.classList.remove("focus-glow");
        splitRight.classList.remove("focus-glow");
      }
    }

    if (speedCounter) speedCounter.textContent = `+${(0.64 * (1 - val/200)).toFixed(2)}g`;
    if (examCounter) examCounter.textContent = `-${(0.28 * (0.5 + val/200)).toFixed(2)}g`;
  }

  slider.addEventListener("input", updateParadox);
  updateParadox();
}

function initThemeAccordion() {
  const items = document.querySelectorAll(".theme-accordion-item");
  if (!items.length) return;

  items.forEach(item => {
    item.addEventListener("mouseenter", () => {
      items.forEach(other => {
        if (other === item) {
          other.classList.add("active");
        } else {
          other.classList.remove("active");
        }
      });
    });
  });
}
