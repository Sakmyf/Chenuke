// ======================================================
// SIGNALCHECK POPUP.JS – CLEAN FIXED VERSION
// ======================================================

const API_URL = "https://gesignalcheck-production-8e78.up.railway.app/v3/verify";
const PRO_URL = "https://gesignalcheck.com/analysis";

const API_TIMEOUT = 30000;
const MAX_RETRIES = 2;

async function buildHeaders() {
  const headers = {
    "Content-Type": "application/json",
    "x-extension-id": chrome.runtime.id
  };
  try {
    const stored = await chrome.storage.local.get("pro_token");
    if (stored && stored.pro_token) {
      headers["x-pro-token"] = stored.pro_token;
    }
  } catch (e) { /* sin token PRO */ }
  return headers;
}

function obtenerColorPorcentaje(valor, metrica) {
  const m = String(metrica || "").toLowerCase();
  if (m === "emocionalidad" || m === "emotionality") {
    if (valor > 70) return "#ef4444";
    if (valor > 40) return "#facc15";
    return "#4ade80";
  }
  if (m === "manipulación" || m === "manipulacion" || m === "manipulation") {
    if (valor > 70) return "#ef4444";
    if (valor > 40) return "#facc15";
    return "#4ade80";
  }
  if (m === "evidencia" || m === "evidence") {
    if (valor < 40) return "#ef4444";
    if (valor < 70) return "#facc15";
    return "#4ade80";
  }
  if (m === "coherencia" || m === "coherence") {
    if (valor < 40) return "#ef4444";
    if (valor < 70) return "#facc15";
    return "#4ade80";
  }
  return "#f1f5f9";
}

document.addEventListener("DOMContentLoaded", () => {
  const analyzeBtn    = document.getElementById("analyzeBtn");
  const scanLine      = document.getElementById("scanLine");
  const labelBadge    = document.getElementById("labelBadge");
  const summaryBox    = document.getElementById("summary");
  const scoreEl       = document.getElementById("scoreValue");
  const confEl        = document.getElementById("confidenceValue");
  const cacheBadge    = document.getElementById("cacheBadge");
  const bgBadge       = document.getElementById("backgroundBadge");
  const upgradeBtn    = document.getElementById("upgradeBtn");
  const proSection    = document.getElementById("proSection");
  const proWarning    = document.getElementById("proWarning");
  const proMetrics    = document.getElementById("proMetrics");
  const proList       = document.getElementById("proList");
  const errorBox      = document.getElementById("errorBox");
  const errorMessage  = document.getElementById("errorMessage");
  const retryErrorBtn = document.getElementById("retryErrorBtn");

  let lastResult = null;

  // ─── helpers de visibilidad ───────────────────────────────────────────────

  function hide(el) { if (el) el.classList.add("hidden"); }
  function show(el) { if (el) el.classList.remove("hidden"); }

  /** Limpia TODOS los elementos dinámicos antes de renderizar cualquier estado. */
  function resetDynamicUI() {
    hide(cacheBadge);
    hide(bgBadge);
    hide(errorBox);
    hide(summaryBox);
    hide(proWarning);
    hide(proMetrics);
    if (upgradeBtn)  upgradeBtn.style.display = "none";
    if (proSection)  proSection.classList.add("locked");
    if (errorMessage) errorMessage.textContent = "";
  }

  function showError(message) {
    resetDynamicUI();
    stopScanUI();

    labelBadge.textContent = message;
    labelBadge.removeAttribute("data-level");
    labelBadge.style.background = "rgba(239,68,68,0.2)";
    labelBadge.style.color = "#f87171";

    if (scoreEl) scoreEl.textContent = "--";
    if (confEl)  confEl.textContent  = "--";

    if (errorBox && errorMessage) {
      errorMessage.textContent = message;
      show(errorBox);
    }
  }

  function hideError() {
    hide(errorBox);
    if (errorMessage) errorMessage.textContent = "";
  }

  function startScanUI() {
    resetDynamicUI();
    hideError();
    if (scanLine) scanLine.classList.add("active");
    labelBadge.textContent = "Analizando contenido...";
    labelBadge.removeAttribute("data-level");
    labelBadge.style.background = "#333";
    labelBadge.style.color = "#aaa";
    if (scoreEl) scoreEl.textContent = "--";
    if (confEl)  confEl.textContent  = "--";
    if (proList) proList.innerHTML = "";
  }

  function stopScanUI() {
    if (scanLine) scanLine.classList.remove("active");
  }

  // ─── content script ──────────────────────────────────────────────────────

  async function isContentScriptReady(tabId) {
    return new Promise((resolve) => {
      const timeout = setTimeout(() => resolve(false), 700);
      chrome.tabs.sendMessage(tabId, { type: "ping" }, (response) => {
        clearTimeout(timeout);
        if (chrome.runtime.lastError) { resolve(false); }
        else { resolve(response && response.injected === true); }
      });
    });
  }

  async function ensureContentScript(tabId) {
    const ready = await isContentScriptReady(tabId);
    if (ready) { console.log("✅ Content script activo"); return; }
    try {
      await chrome.scripting.executeScript({ target: { tabId }, files: ["content_script.js"] });
      await new Promise((r) => setTimeout(r, 400));
    } catch (e) {
      console.warn("⚠️ No se pudo inyectar content script:", e);
    }
  }

  // ─── fetch ────────────────────────────────────────────────────────────────

  async function fetchWithRetry(url, options, retries = 0) {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), API_TIMEOUT);
    try {
      const res = await fetch(url, { ...options, signal: controller.signal });
      clearTimeout(timeoutId);
      return res;
    } catch (err) {
      clearTimeout(timeoutId);
      if (retries < MAX_RETRIES && err.name !== "AbortError") {
        const delay = Math.pow(2, retries) * 1000;
        console.log(`🔄 Reintento ${retries + 1} en ${delay}ms...`);
        await new Promise((r) => setTimeout(r, delay));
        return fetchWithRetry(url, options, retries + 1);
      }
      throw err;
    }
  }

  // ─── análisis ────────────────────────────────────────────────────────────

  async function runAnalysis() {
    const MIN_TIME = 1200;
    const startTime = Date.now();
    startScanUI();

    try {
      const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });

      if (!tab?.id || !tab?.url ||
          tab.url.startsWith("chrome://") ||
          tab.url.startsWith("chrome-extension://") ||
          tab.url.startsWith("about:")) {
        showError("Página no compatible");
        return;
      }

      await ensureContentScript(tab.id);
      await new Promise((r) => setTimeout(r, 150));

      chrome.tabs.sendMessage(tab.id, { action: "extractText" }, async (extracted) => {
        if (chrome.runtime.lastError) {
          console.error("❌ Error de comunicación:", chrome.runtime.lastError);
          showError("Error de comunicación con la página");
          return;
        }

        if (!extracted || !extracted.ok || !extracted.text || extracted.text.length < 30) {
          showError("Texto insuficiente o error de extracción");
          return;
        }

        try {
          const res = await fetchWithRetry(API_URL, {
            method: "POST",
            headers: await buildHeaders(),
            body: JSON.stringify({
              text: extracted.text,
              url: extracted.url || tab.url,
              title: extracted.title || tab.title || "",
              is_ecommerce: extracted.is_ecommerce || false
            })
          });

          if (!res.ok) {
            const errorText = await res.text().catch(() => "Error desconocido");
            throw new Error(`HTTP ${res.status}: ${errorText}`);
          }

          const data = await res.json();
          lastResult = { ...data, _timestamp: Date.now() };

          const elapsed = Date.now() - startTime;
          const delay = Math.max(0, MIN_TIME - elapsed);

          setTimeout(() => {
            renderResult(data);
            stopScanUI();
          }, delay);

        } catch (err) {
          console.error("❌ Error API:", err?.name, err?.message, err);
          let errorMsg = "Error de conexión";
          if (err.name === "AbortError") {
            errorMsg = "Tiempo de espera agotado";
          } else if ((err.message || "").includes("HTTP")) {
            errorMsg = "Error del servidor";
          } else if ((err.message || "").includes("Failed to fetch")) {
            errorMsg = "No se pudo conectar con la API";
          } else if (err instanceof DOMException) {
            errorMsg = "Error de conexión con la API";
          }
          showError(errorMsg);
        }
      });

    } catch (err) {
      console.error("❌ Error inesperado:", err);
      showError("Error inesperado");
    }
  }

  // ─── render ───────────────────────────────────────────────────────────────

  function renderResult(data) {
    resetDynamicUI();
    stopScanUI();

    const analysis = data?.analysis || data;
    if (!analysis) { showError("Respuesta inválida del servidor"); return; }

    const level = String(analysis.level || "medio").toLowerCase();

    // Estados sin score numérico: privado / insuficiente / alerta_breve
    if (data?.status === "skipped" || level === "none") {
      labelBadge.textContent = "⚪ No analizado";
      labelBadge.style.cssText = "background:rgba(148,163,184,0.18);color:#cbd5e1";
      if (scoreEl) scoreEl.textContent = "—";
      if (confEl)  confEl.textContent  = "—";
      if (summaryBox) {
        summaryBox.textContent = analysis.insight || analysis.message ||
          "SignalCheck no analiza ni registra páginas de contenido privado.";
        show(summaryBox);
      }
      return;
    }

    if (level === "insuficiente") {
      labelBadge.textContent = "⚪ Texto insuficiente";
      labelBadge.style.cssText = "background:rgba(148,163,184,0.18);color:#cbd5e1";
      if (scoreEl) scoreEl.textContent = "—";
      if (confEl)  confEl.textContent  = "—";
      if (summaryBox) {
        summaryBox.textContent = analysis.insight || analysis.message ||
          "El contenido es demasiado corto para un análisis estructural confiable.";
        show(summaryBox);
      }
      return;
    }

    if (level === "alerta_breve") {
      labelBadge.textContent = "⚠️ Texto breve — precaución";
      labelBadge.style.cssText = "background:rgba(250,204,21,0.18);color:#facc15";
      if (scoreEl) scoreEl.textContent = "!";
      if (confEl)  confEl.textContent  = "—";
      if (summaryBox) {
        summaryBox.textContent = analysis.insight || analysis.message ||
          "Texto corto con señales de presión. Leé con cautela.";
        show(summaryBox);
      }
      return;
    }

    // Estados normales con score
    labelBadge.style.cssText = "";
    if (level === "bajo" || level === "green") {
      labelBadge.textContent = "🟢 Bajo riesgo";
      labelBadge.setAttribute("data-level", "bajo");
    } else if (level === "medio" || level === "yellow") {
      labelBadge.textContent = "🟡 Riesgo moderado";
      labelBadge.setAttribute("data-level", "medio");
    } else {
      labelBadge.textContent = "🔴 Alto riesgo";
      labelBadge.setAttribute("data-level", "alto");
    }

    let score = analysis.structural_index ?? analysis.score ?? 0;
    if (typeof score === "number") {
      score = score <= 1 ? Math.round(score * 100) : Math.min(Math.round(score), 100);
    } else { score = 0; }
    if (scoreEl) scoreEl.textContent = score;

    let conf = analysis.confidence ?? 0;
    if (typeof conf === "number") {
      conf = conf <= 1 ? Math.round(conf * 100) : Math.min(Math.round(conf), 100);
    } else { conf = 0; }
    if (confEl) confEl.textContent = conf;

    if (summaryBox) {
      summaryBox.textContent = analysis.insight || analysis.message ||
        "El contenido no presenta señales relevantes de manipulación o riesgo.";
      show(summaryBox);
    }

    const plan = data?.meta?.plan || "free";

    if (plan === "free") {
      if (proSection) proSection.classList.add("locked");
      show(proWarning);
      if (upgradeBtn) upgradeBtn.style.display = "block";
      hide(proMetrics);
    } else {
      if (proSection) proSection.classList.remove("locked");
      hide(proWarning);
      if (upgradeBtn) upgradeBtn.style.display = "none";

      if (proMetrics && proList) {
        show(proMetrics);
        proList.innerHTML = "";
        const metrics = analysis.pro?.metrics || analysis.metrics;
        if (metrics && Object.keys(metrics).length > 0) {
          for (const [key, value] of Object.entries(metrics)) {
            const numericValue = typeof value === "number" ? value : 0;
            const color = obtenerColorPorcentaje(numericValue, key);
            const li = document.createElement("li");
            li.style.cssText = "display:flex;justify-content:space-between;align-items:center;padding:4px 0";
            li.innerHTML = `<span style="color:#94a3b8">${key}</span><strong style="color:${color};font-size:13px">${numericValue}%</strong>`;
            proList.appendChild(li);
          }
        } else {
          const li = document.createElement("li");
          li.style.cssText = "text-align:center;color:#64748b;font-style:italic";
          li.textContent = "Métricas detalladas no disponibles";
          proList.appendChild(li);
        }
      }
    }
  }

  // ─── eventos ─────────────────────────────────────────────────────────────

  if (upgradeBtn)  upgradeBtn.addEventListener("click", () => chrome.tabs.create({ url: PRO_URL }));
  if (analyzeBtn)  analyzeBtn.addEventListener("click", runAnalysis);
  if (retryErrorBtn) retryErrorBtn.addEventListener("click", runAnalysis);

  const now = Date.now();
  if (lastResult && now - (lastResult._timestamp || 0) < 30000) {
    renderResult(lastResult);
  } else {
    runAnalysis();
  }
});