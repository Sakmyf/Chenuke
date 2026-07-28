// ======================================================
// CHENUKE POPUP.JS – VERSIÓN DEFINITIVA CON FALLBACK
// ======================================================

const API_URL = "https://chenuke-production-8e78.up.railway.app/v3/verify";
const CHAT_API_URL = "https://chenuke-production-8e78.up.railway.app/v3/chat-analysis";
const REGISTER_URL = "https://chenuke-production-8e78.up.railway.app/v3/register";
const PRO_URL = "https://chenuke.com/analysis";

const API_TIMEOUT = 30000;
const MAX_RETRIES = 2;
const CACHE_TTL = 30000;
const RETRY_HTTP_STATUS = [502, 503, 504];

let lastResult = null;
let extensionPlan = "free";
let proToken = null;

// ======================================================
// REGISTRO (FORZADO A PRO PARA PRUEBAS)
// ======================================================
async function registerExtension() {
    // 🔥 FORZAR PLAN PRO MANUALMENTE (SIN LLAMAR AL BACKEND)
    extensionPlan = "pro";
    proToken = "mi_token_de_prueba";
    await chrome.storage.local.set({ extension_plan: extensionPlan, pro_token: proToken });
    console.log("✅ Forzado PRO manualmente (sin backend)");
    return { plan: "pro", pro_token: "mi_token_de_prueba" };

    // ⚠️ CÓDIGO ORIGINAL COMENTADO (para restaurar después)
    /*
    try {
        const extId = chrome.runtime.id;
        const response = await fetch(REGISTER_URL, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ extension_id: extId })
        });
        if (!response.ok) throw new Error("Error registrando extensión");
        const data = await response.json();
        extensionPlan = data.plan || "free";
        proToken = data.pro_token || null;
        await chrome.storage.local.set({ extension_plan: extensionPlan, pro_token: proToken });
        console.log("✅ Extensión registrada, plan:", extensionPlan);
        return data;
    } catch (e) {
        console.warn("⚠️ No se pudo registrar la extensión:", e);
        const stored = await chrome.storage.local.get(["extension_plan", "pro_token"]);
        extensionPlan = stored.extension_plan || "free";
        proToken = stored.pro_token || null;
        return null;
    }
    */
}

async function buildHeaders() {
    const headers = {
        "Content-Type": "application/json",
        "x-extension-id": chrome.runtime.id
    };
    const token = proToken || (await chrome.storage.local.get("pro_token")).pro_token || null;
    if (token) headers["x-pro-token"] = token;
    return headers;
}

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

function cleanTextForApi(text) {
    return String(text || "")
        .normalize("NFKC")
        .replace(/[\u0000-\u001F\u007F-\u009F]/g, " ")
        .replace(/[\u200B-\u200D\uFEFF]/g, " ")
        .replace(/[\uD800-\uDFFF]/g, " ")
        .replace(/\s+/g, " ")
        .trim()
        .slice(0, 12000);
}

function getHttpErrorMessage(status) {
    if (status === 429) return "Límite temporal alcanzado. Esperá unos segundos.";
    if (status === 400) return "Solicitud inválida.";
    if (status === 401 || status === 403) return "Acceso no autorizado.";
    if (status === 404) return "Endpoint no encontrado.";
    if (status >= 500) return "Error interno de la API.";
    return `Error HTTP ${status}`;
}

function getUserErrorMessage(err) {
    const msg = String(err?.message || "");
    if (err?.name === "AbortError") return "Tiempo de espera agotado";
    if (msg.includes("Failed to fetch")) return "No se pudo conectar con la API";
    return msg || "Error de conexión";
}

async function getCachedResult(url) {
    try {
        const stored = await chrome.storage.local.get("chenuke_last_result");
        const cached = stored?.chenuke_last_result;
        if (!cached || cached.url !== url) return null;
        if (Date.now() - (cached.timestamp || 0) > CACHE_TTL) return null;
        return cached.data || null;
    } catch { return null; }
}

async function setCachedResult(url, data) {
    try {
        await chrome.storage.local.set({
            chenuke_last_result: { url, data, timestamp: Date.now() }
        });
    } catch {}
}

function obtenerColorPorcentaje(valor, metrica) {
    const m = String(metrica || "").toLowerCase();
    if (m.includes("emocionalidad") || m.includes("emotionality")) {
        if (valor > 70) return "#ef4444";
        if (valor > 40) return "#facc15";
        return "#4ade80";
    }
    if (m.includes("manipulación") || m.includes("manipulacion")) {
        if (valor > 70) return "#ef4444";
        if (valor > 40) return "#facc15";
        return "#4ade80";
    }
    if (m.includes("evidencia") || m.includes("evidence")) {
        if (valor < 40) return "#ef4444";
        if (valor < 70) return "#facc15";
        return "#4ade80";
    }
    if (m.includes("coherencia") || m.includes("coherence")) {
        if (valor < 40) return "#ef4444";
        if (valor < 70) return "#facc15";
        return "#4ade80";
    }
    return "#f1f5f9";
}

function updateAIButton(plan) {
    const aiBtnText = document.getElementById("aiBtnText");
    const aiBtn = document.getElementById("aiAnalyzeBtn");
    if (!aiBtnText || !aiBtn) return;
    if (plan === "pro" || plan === "premium") {
        aiBtnText.textContent = "🤖 Analizar con IA";
        aiBtn.disabled = false;
        aiBtn.style.opacity = "1";
    } else {
        aiBtnText.textContent = "🔒 Actualizar a PRO";
        aiBtn.disabled = false;
        aiBtn.style.opacity = "0.8";
    }
}

async function runAIAnalysis() {
    const userPlan = lastResult?.meta?.plan || extensionPlan || "free";
    if (userPlan === "free") {
        chrome.tabs.create({ url: "https://chenuke.com/#planes" });
        return;
    }
    const aiBtn = document.getElementById("aiAnalyzeBtn");
    const aiBtnText = document.getElementById("aiBtnText");
    const originalText = aiBtnText.textContent;
    aiBtnText.textContent = "⏳ Generando informe...";
    aiBtn.disabled = true;

    try {
        const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
        const extracted = await extractPageContent(tab);
        if (!extracted || !extracted.ok || !extracted.text) {
            showError("No se pudo extraer el contenido de la página");
            return;
        }
        const response = await fetchWithTimeout(CHAT_API_URL, {
            method: "POST",
            headers: await buildHeaders(),
            body: JSON.stringify({
                text: extracted.text,
                title: extracted.title || tab.title || "",
                url: extracted.url || tab.url,
                heuristic: lastResult
            })
        });
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || `Error ${response.status}`);
        }
        const data = await response.json();
        const encoded = encodeURIComponent(data.report);
        chrome.tabs.create({ url: `https://chenuke.com/ia-report.html?report=${encoded}` });
    } catch (err) {
        console.error("❌ Error en análisis IA:", err);
        showError(`Error generando informe: ${err.message}`);
    } finally {
        aiBtnText.textContent = originalText;
        aiBtn.disabled = false;
    }
}

document.addEventListener("DOMContentLoaded", async () => {
    await registerExtension();

    const analyzeBtn = document.getElementById("analyzeBtn");
    const clearCacheBtn = document.getElementById("clearCacheBtn");
    const scanLine = document.getElementById("scanLine");
    const labelBadge = document.getElementById("labelBadge");
    const summaryBox = document.getElementById("summary");
    const scoreEl = document.getElementById("scoreValue");
    const confEl = document.getElementById("confidenceValue");
    const cacheBadge = document.getElementById("cacheBadge");
    const upgradeBtn = document.getElementById("upgradeBtn");
    const proSection = document.getElementById("proSection");
    const proWarning = document.getElementById("proWarning");
    const proMetrics = document.getElementById("proMetrics");
    const proList = document.getElementById("proList");
    const errorBox = document.getElementById("errorBox");
    const errorMessage = document.getElementById("errorMessage");
    const retryErrorBtn = document.getElementById("retryErrorBtn");
    const aiAnalyzeBtn = document.getElementById("aiAnalyzeBtn");

    if (aiAnalyzeBtn) {
        aiAnalyzeBtn.addEventListener("click", runAIAnalysis);
    }

    function showError(message) {
        if (labelBadge) {
            labelBadge.textContent = message;
            labelBadge.style.background = "rgba(239,68,68,0.2)";
            labelBadge.style.color = "#f87171";
        }
        if (scoreEl) scoreEl.textContent = "--";
        if (confEl) confEl.textContent = "--";
        if (summaryBox) summaryBox.classList.add("hidden");
        if (errorBox && errorMessage) {
            errorMessage.textContent = message;
            errorBox.classList.remove("hidden");
        }
        if (cacheBadge) cacheBadge.classList.add("hidden");
        if (clearCacheBtn) clearCacheBtn.classList.add("hidden");
        updateAIButton("free");
    }

    function hideError() {
        if (errorBox) errorBox.classList.add("hidden");
        if (errorMessage) errorMessage.textContent = "";
    }

    function startScanUI() {
        hideError();
        if (scanLine) scanLine.classList.add("active");
        if (labelBadge) {
            labelBadge.textContent = "Analizando contenido...";
            labelBadge.style.background = "#333";
            labelBadge.style.color = "#aaa";
        }
        if (summaryBox) summaryBox.classList.add("hidden");
        if (scoreEl) scoreEl.textContent = "--";
        if (confEl) confEl.textContent = "--";
        if (proList) proList.innerHTML = "";
        if (cacheBadge) cacheBadge.classList.add("hidden");
        if (clearCacheBtn) clearCacheBtn.classList.add("hidden");
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
        const ready = await isContentScriptReady(tabId);
        if (ready) return;
        try {
            await chrome.scripting.executeScript({
                target: { tabId },
                files: ["content_script.js"]
            });
            await sleep(400);
        } catch (e) {
            console.warn("⚠️ No se pudo inyectar content script:", e);
        }
    }

    async function fetchWithTimeout(url, options) {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), API_TIMEOUT);
        try {
            const res = await fetch(url, { ...options, signal: controller.signal });
            clearTimeout(timeoutId);
            return res;
        } catch (err) {
            clearTimeout(timeoutId);
            throw err;
        }
    }

    async function fetchAnalysis(payload, attempt = 0) {
        const safePayload = {
            text: cleanTextForApi(payload?.text),
            url: String(payload?.url || "").slice(0, 2048),
            title: cleanTextForApi(payload?.title || "").slice(0, 300),
            is_ecommerce: Boolean(payload?.is_ecommerce)
        };

        if (!safePayload.text || safePayload.text.length < 80) {
            throw new Error("Texto insuficiente o error de extracción");
        }

        const res = await fetchWithTimeout(API_URL, {
            method: "POST",
            headers: await buildHeaders(),
            body: JSON.stringify(safePayload)
        });

        if (!res.ok) {
            const errorText = await res.text().catch(() => "");
            if (RETRY_HTTP_STATUS.includes(res.status) && attempt < MAX_RETRIES) {
                const delay = Math.pow(2, attempt) * 1000;
                console.log(`🔄 Reintento ${attempt + 1} en ${delay}ms...`);
                await sleep(delay);
                return fetchAnalysis(safePayload, attempt + 1);
            }
            const error = new Error(getHttpErrorMessage(res.status));
            error.status = res.status;
            error.raw = errorText;
            throw error;
        }

        return res.json();
    }

    async function extractPageContent(tab) {
        await ensureContentScript(tab.id);
        await sleep(150);

        return new Promise((resolve, reject) => {
            chrome.tabs.sendMessage(
                tab.id,
                { action: "extractText" },
                (extracted) => {
                    if (chrome.runtime.lastError) {
                        reject(new Error("Error de comunicación con la página"));
                        return;
                    }
                    resolve(extracted);
                }
            );
        });
    }

    async function runAnalysis(options = {}) {
        const force = options.force === true;
        const MIN_TIME = 1200;
        const startTime = Date.now();

        startScanUI();

        try {
            const [tab] = await chrome.tabs.query({
                active: true,
                currentWindow: true
            });

            if (
                !tab?.id ||
                !tab?.url ||
                tab.url.startsWith("chrome://") ||
                tab.url.startsWith("chrome-extension://") ||
                tab.url.startsWith("about:")
            ) {
                showError("Página no compatible");
                stopScanUI();
                return;
            }

            if (!force) {
                const cached = await getCachedResult(tab.url);
                if (cached) {
                    renderResult(cached, true);
                    stopScanUI();
                    return;
                }
            }

            const extracted = await extractPageContent(tab);

            if (
                !extracted ||
                !extracted.ok ||
                !extracted.text ||
                cleanTextForApi(extracted.text).length < 30
            ) {
                showError("Texto insuficiente o error de extracción");
                stopScanUI();
                return;
            }

            const data = await fetchAnalysis({
                text: extracted.text,
                url: extracted.url || tab.url,
                title: extracted.title || tab.title || "",
                is_ecommerce: extracted.is_ecommerce || false
            });

            lastResult = { ...data, _timestamp: Date.now() };
            await setCachedResult(tab.url, lastResult);

            const elapsed = Date.now() - startTime;
            const delay = Math.max(0, MIN_TIME - elapsed);

            setTimeout(() => {
                renderResult(data, false);
                stopScanUI();
            }, delay);
        } catch (err) {
            console.error("❌ Error Chenuke:", err?.name, err?.message, err);
            showError(getUserErrorMessage(err));
            stopScanUI();
        }
    }

    // ============================================================
    // RENDER RESULTADO
    // ============================================================
    function renderResult(data, fromCache = false) {
        hideError();

        if (fromCache && cacheBadge) {
            cacheBadge.classList.remove("hidden");
            if (clearCacheBtn) clearCacheBtn.classList.remove("hidden");
        } else {
            if (cacheBadge) cacheBadge.classList.add("hidden");
            if (clearCacheBtn) clearCacheBtn.classList.add("hidden");
        }

        const analysis = data?.analysis || data;

        if (!analysis) {
            showError("Respuesta inválida del servidor");
            return;
        }

        const level = String(analysis.level || "medio").toLowerCase();

        if (data?.status === "skipped" || level === "none") {
            if (labelBadge) {
                labelBadge.textContent = "⚪ No analizado";
                labelBadge.style.background = "rgba(148,163,184,0.18)";
                labelBadge.style.color = "#cbd5e1";
            }
            if (scoreEl) scoreEl.textContent = "—";
            if (confEl) confEl.textContent = "—";
            if (summaryBox) {
                summaryBox.textContent = analysis.insight || analysis.message || "Chenuke no analiza ni registra páginas de contenido privado.";
                summaryBox.classList.remove("hidden");
            }
            if (proSection) proSection.classList.add("locked");
            if (proWarning) proWarning.style.display = "none";
            if (upgradeBtn) upgradeBtn.style.display = "none";
            if (proMetrics) proMetrics.classList.add("hidden");
            const userPlan = data?.meta?.plan || extensionPlan || "free";
            updateAIButton(userPlan);
            return;
        }

        if (level === "insuficiente") {
            if (labelBadge) {
                labelBadge.textContent = "⚪ Texto insuficiente";
                labelBadge.style.background = "rgba(148,163,184,0.18)";
                labelBadge.style.color = "#cbd5e1";
            }
            if (scoreEl) scoreEl.textContent = "—";
            if (confEl) confEl.textContent = "—";
            if (summaryBox) {
                summaryBox.textContent = analysis.insight || analysis.message || "El contenido es demasiado corto para un análisis estructural confiable.";
                summaryBox.classList.remove("hidden");
            }
            if (proSection) proSection.classList.add("locked");
            if (proWarning) proWarning.style.display = "none";
            if (upgradeBtn) upgradeBtn.style.display = "none";
            if (proMetrics) proMetrics.classList.add("hidden");
            const userPlan = data?.meta?.plan || extensionPlan || "free";
            updateAIButton(userPlan);
            return;
        }

        if (level === "alerta_breve") {
            if (labelBadge) {
                labelBadge.textContent = "⚠️ Texto breve — precaución";
                labelBadge.style.background = "rgba(250,204,21,0.18)";
                labelBadge.style.color = "#facc15";
            }
            if (scoreEl) scoreEl.textContent = "!";
            if (confEl) confEl.textContent = "—";
            if (summaryBox) {
                summaryBox.textContent = analysis.insight || analysis.message || "Texto corto con señales de presión. Leé con cautela.";
                summaryBox.classList.remove("hidden");
            }
            if (proSection) proSection.classList.add("locked");
            if (proWarning) proWarning.style.display = "none";
            if (upgradeBtn) upgradeBtn.style.display = "none";
            if (proMetrics) proMetrics.classList.add("hidden");
            const userPlan = data?.meta?.plan || extensionPlan || "free";
            updateAIButton(userPlan);
            return;
        }

        if (level === "bajo" || level === "green") {
            if (labelBadge) {
                labelBadge.textContent = "🟢 Bajo riesgo";
                labelBadge.style.background = "rgba(34,197,94,0.2)";
                labelBadge.style.color = "#4ade80";
            }
        } else if (level === "medio" || level === "yellow") {
            if (labelBadge) {
                labelBadge.textContent = "🟡 Riesgo moderado";
                labelBadge.style.background = "rgba(250,204,21,0.2)";
                labelBadge.style.color = "#facc15";
            }
        } else {
            if (labelBadge) {
                labelBadge.textContent = "🔴 Alto riesgo";
                labelBadge.style.background = "rgba(239,68,68,0.2)";
                labelBadge.style.color = "#f87171";
            }
        }

        // --- Obtener score real o estimado ---
        let score = analysis.structural_index ?? analysis.score ?? 0;
        if (typeof score === "number") {
            if (score <= 1) score = Math.round(score * 100);
            else score = Math.min(Math.round(score), 100);
        } else {
            score = 0;
        }

        // 🔥 FALLBACK FORZADO: si no hay score, asignar según el nivel
        if (score === 0) {
            if (level === "bajo" || level === "green") score = 15;
            else if (level === "medio" || level === "yellow") score = 50;
            else if (level === "alto" || level === "red") score = 85;
            else score = 30; // valor neutral
        }

        const userPlan = data?.meta?.plan || extensionPlan || "free";

        if (scoreEl) {
            if (userPlan === "free") {
                scoreEl.textContent = "—";
            } else {
                scoreEl.textContent = score;
            }
        }

        let conf = analysis.confidence ?? 0;
        if (typeof conf === "number") {
            if (conf <= 1) conf = Math.round(conf * 100);
            else conf = Math.min(Math.round(conf), 100);
        } else {
            conf = 0;
        }
        if (confEl) confEl.textContent = conf;

        if (summaryBox) {
            summaryBox.textContent = analysis.insight || analysis.message || "El contenido no presenta señales relevantes de manipulación o riesgo.";
            summaryBox.classList.remove("hidden");
        }

        // ============================================================
        // MANEJO DEL BOTÓN "VER ANÁLISIS COMPLETO"
        // ============================================================
        if (userPlan === "free") {
            if (proSection) proSection.classList.add("locked");
            if (proWarning) proWarning.style.display = "flex";
            if (upgradeBtn) upgradeBtn.style.display = "none";
            if (proMetrics) proMetrics.classList.add("hidden");
        } else {
            if (proSection) proSection.classList.remove("locked");
            if (proWarning) proWarning.style.display = "none";
            if (upgradeBtn) {
                upgradeBtn.style.display = "block";
                upgradeBtn.textContent = "📊 Ver análisis completo";
            }
            if (proMetrics && proList) {
                proMetrics.classList.remove("hidden");
                proList.innerHTML = "";
                const metrics = analysis.metrics;
                if (metrics && Object.keys(metrics).length > 0) {
                    for (const [key, value] of Object.entries(metrics)) {
                        const numericValue = typeof value === "number" ? value : 0;
                        const color = obtenerColorPorcentaje(numericValue, key);
                        const li = document.createElement("li");
                        li.style.display = "flex";
                        li.style.justifyContent = "space-between";
                        li.style.alignItems = "center";
                        li.style.padding = "4px 0";
                        li.innerHTML = `
                            <span style="color:#94a3b8;">${key}</span>
                            <strong style="color:${color}; font-size:13px;">${numericValue}%</strong>
                        `;
                        proList.appendChild(li);
                    }
                } else {
                    const li = document.createElement("li");
                    li.style.textAlign = "center";
                    li.style.color = "#64748b";
                    li.style.fontStyle = "italic";
                    li.textContent = "Métricas detalladas no disponibles";
                    proList.appendChild(li);
                }
            }
        }

        updateAIButton(userPlan);
    }

    // ============================================================
    // EVENT LISTENER DEL BOTÓN "VER ANÁLISIS COMPLETO" (FALLBACK)
    // ============================================================
    if (upgradeBtn) {
        upgradeBtn.addEventListener("click", () => {
            const userPlan = lastResult?.meta?.plan || extensionPlan || "free";
            if (userPlan === "free") {
                chrome.tabs.create({ url: "https://chenuke.com/#planes" });
                return;
            }

            // Obtener datos del análisis
            const raw = lastResult?.analysis || lastResult || {};
            const level = (raw.level || "bajo").toLowerCase();

            // 1. Intentar obtener score real
            let score = raw.structural_index ?? raw.score ?? null;
            if (typeof score === "number") {
                if (score <= 1) score = Math.round(score * 100);
                else score = Math.round(score);
            }

            // 2. Si no hay score real, asignar según el nivel (fallback definitivo)
            if (score === null || score === undefined || isNaN(score) || score === 0) {
                if (level === "bajo" || level === "green") score = 15;
                else if (level === "medio" || level === "yellow") score = 50;
                else if (level === "alto" || level === "red") score = 85;
                else score = 30;
            }

            // 3. Asegurar rango 0-100
            score = Math.min(Math.max(score, 0), 100);

            // 4. Confianza
            let conf = raw.confidence != null
                ? Math.round(raw.confidence <= 1 ? raw.confidence * 100 : raw.confidence)
                : "";

            // 5. Guardar en localStorage
            try {
                localStorage.setItem('chenuke_last_analysis', JSON.stringify({
                    score: score,
                    level: level,
                    confidence: conf
                }));
            } catch (e) {}

            // 6. Construir y abrir URL
            const url = `${PRO_URL}?score=${score}&level=${level}&conf=${conf}`;
            console.log("🔗 Abriendo URL:", url); // Para depuración
            chrome.tabs.create({ url });
        });
    }

    // --- OTROS EVENT LISTENERS ---
    if (analyzeBtn) {
        analyzeBtn.addEventListener("click", () => runAnalysis({ force: true }));
    }
    if (retryErrorBtn) {
        retryErrorBtn.addEventListener("click", () => runAnalysis({ force: true }));
    }
    if (clearCacheBtn) {
        clearCacheBtn.addEventListener("click", async () => {
            try {
                const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
                if (tab?.url) {
                    await chrome.storage.local.remove("chenuke_last_result");
                    if (cacheBadge) cacheBadge.classList.add("hidden");
                    if (clearCacheBtn) clearCacheBtn.classList.add("hidden");
                    runAnalysis({ force: true });
                }
            } catch (e) {
                console.warn("Error limpiando caché:", e);
            }
        });
    }

    runAnalysis({ force: false });
});