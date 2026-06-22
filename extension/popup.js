// ======================================================
// SIGNALCHECK POPUP.JS – CLEAN FIXED VERSION (v2)
// ======================================================

const API_URL = "https://gesignalcheck-production-8e78.up.railway.app/v3/verify";
const PRO_URL = "https://gesignalcheck.com/analysis";

const API_TIMEOUT = 30000; // 30 segundos
const MAX_RETRIES = 2;
const MIN_TEXT_LENGTH = 30;

// Headers comunes: incluye x-pro-token si el usuario activó PRO
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

document.addEventListener("DOMContentLoaded", async () => {
  const analyzeBtn = document.getElementById("analyzeBtn");
  const scanLine = document.getElementById("scanLine");
  const labelBadge = document.getElementById("labelBadge");
  const summaryBox = document.getElementById("summary");
  const scoreEl = document.getElementById("scoreValue");
  const confEl = document.getElementById("confidenceValue");

  const upgradeBtn = document.getElementById("upgradeBtn");
  const proSection = document.getElementById("proSection");
  const proWarning = document.getElementById("proWarning");
  const proMetrics = document.getElementById("proMetrics");
  const proList = document.getElementById("proList");

  const errorBox = document.getElementById("errorBox");
  const errorMessage = document.getElementById("errorMessage");
  const retryErrorBtn = document.getElementById("retryErrorBtn");

  let isAnalyzing = false;

  function showError(message) {
    labelBadge.textContent = message;
    labelBadge.style.background = "rgba(239,68,68,0.2)";
    labelBadge.style.color = "#f87171";

    if (errorBox && errorMessage) {
      errorMessage.textContent = message;
      errorBox.classList.remove("hidden");
    }
  }

  function hideError() {
    if (errorBox) errorBox.classList.add("hidden");
    if (errorMessage) errorMessage.textContent = "";
  }

  function startScanUI() {
    hideError();
    if (scanLine) scanLine.classList.add("active");

    labelBadge.textContent = "Analizando contenido...";
    labelBadge.style.background = "#1e293b";
    labelBadge.style.color = "#94a3b8";

    if (summaryBox) summaryBox.classList.add("hidden");
    if (scoreEl) scoreEl.textContent = "--";
    if (confEl) confEl.textContent = "--";
    if (proList) proList.innerHTML = "";
  }

  function stopScanUI() {
    if (scanLine) scanLine.classList.remove("active");
  }

  async function isContentScriptReady(tabId) {
    return new Promise((resolve) => {
      const timeout = setTimeout(() => resolve(false), 700);
      chrome.tabs.sendMessage(tabId, { type: "ping" }, (response) => {
        clearTimeout(timeout);
        if (chrome.runtime.lastError) {
          resolve(false);
        } else {
          resolve(response && response.injected === true);
        }
      });
    });
  }

  async function ensureContentScript(tabId) {
    if (await isContentScriptReady(tabId)) return true;

    try {
      await chrome.scripting.executeScript({
        target: { tabId },
        files: ["content_script.js"]
      });

      // Bucle de ping: espera a que el script esté listo sin usar timeouts fijos
      let attempts = 0;
      while (attempts < 5) {
        if (await isContentScriptReady(tabId)) return true;
        await new Promise((r) => setTimeout(r, 100));
        attempts++;
      }
      return false;
    } catch (e) {
      console.warn("⚠️ No se pudo inyectar content script:", e);
      return false;
    }
  }

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

  async function runAnalysis() {
    if (isAnalyzing) return;
    isAnalyzing = true;

    const MIN_TIME = 1200;
    const startTime = Date.now();

    startScanUI();

    try {
      const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });

      if (!tab?.id || !tab?.url) {
        showError("Página no compatible");
        stopScanUI();
        isAnalyzing = false;
        return;
      }

      // Validación segura de protocolos
      let urlObj;
      try {
        urlObj = new URL(tab.url);
      } catch (e) {
        showError("URL inválida");
        stopScanUI();
        isAnalyzing = false;
        return;
      }

      const validProtocols = ["http:", "https:"];
      if (!validProtocols.includes(urlObj.protocol)) {
        showError("Página no compatible");
        stopScanUI();
        isAnalyzing = false;
        return;
      }

      const scriptReady = await ensureContentScript(tab.id);
      if (!scriptReady) {
        showError("No se pudo inicializar en esta página");
        stopScanUI();
        isAnalyzing = false;
        return;
      }

      chrome.tabs.sendMessage(
        tab.id,
        { action: "extractText" },
        async (extracted) => {
          if (chrome.runtime.lastError) {
            showError("Error de comunicación con la página");
            stopScanUI();
            isAnalyzing = false;
            return;
          }

          if (!extracted?.ok || !extracted.text || extracted.text.length < MIN_TEXT_LENGTH) {
            showError("Texto insuficiente o error de extracción");
            stopScanUI();
            isAnalyzing = false;
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
            data._timestamp = Date.now();

            // Guardar en caché de sesión para no recargar al abrir/cerrar popup
            await chrome.storage.session.set({ lastResult: data });

            const elapsed = Date.now() - startTime;
            const delay = Math.max(0, MIN_TIME - elapsed);

            setTimeout(() => {
              renderResult(data);
              stopScanUI();
              isAnalyzing = false;
            }, delay);

          } catch (err) {
            console.error("❌ Error API:", err?.name, err?.message, err);
            let errorMsg = "Error de conexión";

            if (err.name === "AbortError") errorMsg = "Tiempo de espera agotado";
            else if ((err.message || "").includes("HTTP")) errorMsg = "Error del servidor";
            else if ((err.message || "").includes("Failed to fetch")) errorMsg = "No se pudo conectar con la API";

            showError(errorMsg);
            stopScanUI();
            isAnalyzing = false;
          }
        }
      );
    } catch (err) {
      console.error("❌ Error inesperado:", err);
      showError("Error inesperado");
      stopScanUI();
      isAnalyzing = false;
    }
  }

  function renderResult(data) {
    hideError();

    const analysis = data?.analysis || data;
    if (!analysis) {
      showError("Respuesta inválida del servidor");
      return;
    }

    const level = String(analysis.level || "medio").toLowerCase();

    // Reset visual de elementos PRO
    if (proWarning) proWarning.style.display = "none";
    if (upgradeBtn) upgradeBtn.style.display = "none";
    if (proMetrics) proMetrics.classList.add("hidden");

    // Estados de abstención (Privado, Insuficiente, Alerta Breve)
    if (["skipped", "none", "insuficiente", "alerta_breve"].includes(level) || data?.status === "skipped") {
      if (level === "alerta_breve") {
        labelBadge.textContent = "⚠️ Texto breve — precaución";
        labelBadge.style.background = "rgba(250,204,21,0.18)";
        labelBadge.style.color = "#facc15";
        if (scoreEl) scoreEl.textContent = "!";
      } else {
        labelBadge.textContent = level === "insuficiente" ? "⚪ Texto insuficiente" : "⚪ No analizado";
        labelBadge.style.background = "rgba(148,163,184,0.18)";
        labelBadge.style.color = "#cbd5e1";
        if (scoreEl) scoreEl.textContent = "—";
      }
      
      if (confEl) confEl.textContent = "—";
      if (summaryBox) {
        summaryBox.textContent = analysis.insight || analysis.message || "SignalCheck no analiza este tipo de contenido.";
        summaryBox.classList.remove("hidden");
      }
      if (proSection) proSection.classList.add("locked");
      return;
    }

    // Estados estándar de riesgo
    if (level === "bajo" || level === "green") {
      labelBadge.textContent = "🟢 Bajo riesgo";
      labelBadge.style.background = "rgba(34,197,94,0.2)";
      labelBadge.style.color = "#4ade80";
    } else if (level === "medio" || level === "yellow") {
      labelBadge.textContent = "🟡 Riesgo moderado";
      labelBadge.style.background = "rgba(250,204,21,0.2)";
      labelBadge.style.color = "#facc15";
    } else {
      labelBadge.textContent = "🔴 Alto riesgo";
      labelBadge.style.background = "rgba(239,68,68,0.2)";
      labelBadge.style.color = "#f87171";
    }

    // Parseo seguro de números
    let score = analysis.structural_index ?? analysis.score ?? 0;
    score = typeof score === "number" ? (score <= 1 ? Math.round(score * 100) : Math.min(Math.round(score), 100)) : 0;
    if (scoreEl) scoreEl.textContent = score;

    let conf = analysis.confidence ?? 0;
    conf = typeof conf === "number" ? (conf <= 1 ? Math.round(conf * 100) : Math.min(Math.round(conf), 100)) : 0;
    if (confEl) confEl.textContent = conf;

    if (summaryBox) {
      summaryBox.textContent = analysis.insight || analysis.message || "El contenido no presenta señales relevantes.";
      summaryBox.classList.remove("hidden");
    }

    // Sección PRO
    const plan = data?.meta?.plan || "free";
    if (plan === "free") {
      if (proSection) proSection.classList.add("locked");
      if (proWarning) proWarning.style.display = "flex";
      if (upgradeBtn) upgradeBtn.style.display = "block";
    } else {
      if (proSection) proSection.classList.remove("locked");

      if (proMetrics && proList) {
        proMetrics.classList.remove("hidden");
        proList.innerHTML = ""; // Limpiar lista

        const metrics = analysis.metrics;
        if (metrics && Object.keys(metrics).length > 0) {
          for (const [key, value] of Object.entries(metrics)) {
            const numericValue = typeof value === "number" ? value : 0;
            const color = obtenerColorPorcentaje(numericValue, key);

            const li = document.createElement("li");
            li.style.cssText = "display:flex; justify-content:space-between; align-items:center; padding:4px 0;";

            // FIX XSS: Crear elementos con textContent en lugar de innerHTML
            const spanKey = document.createElement("span");
            spanKey.style.color = "#94a3b8";
            spanKey.textContent = key; // Sanitizado automáticamente

            const strongValue = document.createElement("strong");
            strongValue.style.cssText = `color:${color}; font-size:13px;`;
            strongValue.textContent = `${numericValue}%`; // Sanitizado automáticamente

            li.appendChild(spanKey);
            li.appendChild(strongValue);
            proList.appendChild(li);
          }
        } else {
          const li = document.createElement("li");
          li.style.cssText = "text-align:center; color:#64748b; font-style:italic;";
          li.textContent = "Métricas detalladas no disponibles";
          proList.appendChild(li);
        }
      }
    }
  }

  // --- EVENT LISTENERS ---
  if (upgradeBtn) {
    upgradeBtn.addEventListener("click", () => chrome.tabs.create({ url: PRO_URL }));
  }

  if (analyzeBtn) {
    analyzeBtn.addEventListener("click", () => {
      // Si hacemos clic manual, forzamos análisis ignorando la caché de sesión
      chrome.storage.session.remove("lastResult");
      runAnalysis();
    });
  }

  if (retryErrorBtn) {
    retryErrorBtn.addEventListener("click", runAnalysis);
  }

  // --- INICIALIZACIÓN ---
  try {
    const { lastResult } = await chrome.storage.session.get("lastResult");
    const now = Date.now();

    // Si tenemos un resultado de hace menos de 30 segundos, lo mostramos sin recargar
    if (lastResult && now - (lastResult._timestamp || 0) < 30000) {
      renderResult(lastResult);
    } else {
      runAnalysis();
    }
  } catch (e) {
    // Si storage.session falla por alguna razón, simplemente ejecutamos el análisis
    runAnalysis();
  }
});