/**
 * web/js/wizard.js — 9-Step Canonical Protocol Interactive Simulator
 */
import { state, $, $$, toast } from './state.js';

export function initWizard() {
  const launchBtn = $("#wizard-simulate-btn");
  const presetChips = $$(".wizard-preset-chip");
  const inputEl = $("#wizard-question-input");
  const domainEl = $("#wizard-domain-input");
  const complexityEl = $("#wizard-complexity-select");

  presetChips.forEach(chip => {
    chip.addEventListener("click", () => {
      presetChips.forEach(c => c.classList.remove("active"));
      chip.classList.add("active");
      if (inputEl) inputEl.value = chip.dataset.q;
      if (domainEl) domainEl.value = chip.dataset.domain;
      if (complexityEl) complexityEl.value = chip.dataset.complexity || "M";
    });
  });

  if (launchBtn) {
    launchBtn.addEventListener("click", () => {
      runWizardSimulation();
    });
  }
}

function runWizardSimulation() {
  const q = $("#wizard-question-input")?.value.trim() || "高校大一计算机系引入 AI 编程助手评估";
  const domain = $("#wizard-domain-input")?.value.trim() || "Higher Education / CS1";
  const complexity = $("#wizard-complexity-select")?.value || "M";

  const statusEl = $("#wizard-status-banner");
  const stepsContainer = $("#wizard-steps-timeline");
  const verdictContainer = $("#wizard-verdict-box");
  const logEl = $("#wizard-terminal-logs");

  if (statusEl) {
    statusEl.className = "wizard-status-running";
    statusEl.innerHTML = `<span class="spin">⚡</span> 正在启动 9 步规范实证流水线推演中（Schema-Gated）...`;
  }

  if (stepsContainer) stepsContainer.innerHTML = "";
  if (verdictContainer) verdictContainer.style.display = "none";
  if (logEl) logEl.textContent = `[Init] Initializing Project Workspace for "${q}"...\n[Gate] Complexity Gate Tier: ${complexity}\n`;

  fetch("/api/wizard/simulate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question: q, domain, complexity })
  })
  .then(res => res.json())
  .then(data => {
    if (data.status === "success") {
      animateSteps(data);
    } else {
      toast("推演失败: " + data.message, true);
    }
  })
  .catch(err => {
    toast("推演异常: " + err.message, true);
  });
}

function animateSteps(data) {
  const steps = data.steps || [];
  const stepsContainer = $("#wizard-steps-timeline");
  const statusEl = $("#wizard-status-banner");
  const verdictContainer = $("#wizard-verdict-box");
  const logEl = $("#wizard-terminal-logs");

  let currentIndex = 0;

  function nextStep() {
    if (currentIndex >= steps.length) {
      // Completed!
      if (statusEl) {
        statusEl.className = "wizard-status-done";
        statusEl.innerHTML = `✅ 9 步协议推演完成 · 13 项契约全部校验通过 (100% Gated)`;
      }
      if (verdictContainer) {
        verdictContainer.style.display = "block";
        renderVerdictBox(data);
      }
      if (logEl) {
        logEl.textContent += `\n[Success] Tribunal Adjudication Completed. Snapshot frozen.\n`;
        logEl.scrollTop = logEl.scrollHeight;
      }
      return;
    }

    const s = steps[currentIndex];
    const stepCard = document.createElement("div");
    stepCard.className = "wizard-step-card animate-fade-in";
    stepCard.innerHTML = `
      <div class="step-num">${s.step}</div>
      <div class="step-body">
        <div class="step-head">
          <span class="step-name">${s.name}</span>
          <span class="step-schema tag tag-sm">${s.schema}</span>
          <span class="step-badge tag tag-emerald tag-sm">✓ PASS</span>
        </div>
        <div class="step-details">${s.details}</div>
      </div>
    `;

    if (stepsContainer) {
      stepsContainer.appendChild(stepCard);
      stepCard.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }

    if (logEl) {
      logEl.textContent += `[Step ${s.step}: ${s.name}] Validating against ${s.schema}... OK\n  → ${s.details}\n`;
      logEl.scrollTop = logEl.scrollHeight;
    }

    currentIndex++;
    setTimeout(nextStep, 350);
  }

  nextStep();
}

function renderVerdictBox(data) {
  const v = data.verdict_summary || {};
  const vEl = $("#wizard-verdict-tag");
  const gEl = $("#wizard-pooled-g");
  const confEl = $("#wizard-conf-score");
  const planEl = $("#wizard-action-plan");

  if (vEl) {
    vEl.textContent = v.verdict || "PILOT";
    vEl.className = "tag font-bold text-base " + (v.verdict === "ADOPT" ? "tag-emerald" : "tag-terracotta");
  }
  if (gEl) gEl.textContent = `+${v.pooled_g}g`;
  if (confEl) confEl.textContent = `${Math.round(v.confidence_score * 100)}%`;
  if (planEl) planEl.textContent = v.action_plan || "阶段性试点推进";
}
