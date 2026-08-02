// Chenuke - Service Worker MV3 (PRODUCCIÓN + SEGURIDAD)

console.log("🔥 Chenuke: Service Worker Inicializado");

const MAINTENANCE_INTERVAL = 60;
const ANALYSIS_CACHE_PREFIX = "analysis_";
const CACHE_MAX_AGE = 24 * 60 * 60 * 1000;
const API_URL = "https://chenuke-production-8e78.up.railway.app/v3/verify";
const REGISTER_URL = "https://chenuke-production-8e78.up.railway.app/v3/register";
const ACTIVATE_URL = "https://chenuke-production-8e78.up.railway.app/v3/activate";

// Revalidación de licencia: cada 12 h reconfirmamos contra Lemon (vía backend)
// que la suscripción sigue vigente. Refleja cancelaciones/expiraciones sin
// depender del webhook. Fail-open: solo un 403 explícito revoca.
const LICENSE_REVALIDATE_ALARM = "license_revalidate";
const LICENSE_REVALIDATE_INTERVAL = 12 * 60; // minutos

// --- REGISTRO DE EXTENSIÓN (al instalarse/actualizarse) ---
async function registerExtension() {
    // /v3/register es SOLO telemetría de instalación. NUNCA devuelve token.
    // No escribe en storage: el pro_token es propiedad del flujo de activación
    // (/v3/activate) y pisarlo acá borraría el plan que activó el usuario.
    try {
        const extId = chrome.runtime.id;
        const response = await fetch(REGISTER_URL, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ extension_id: extId })
        });
        if (!response.ok) throw new Error("Error registrando extensión");
        console.log("✅ Extensión registrada (telemetría)");
    } catch (e) {
        console.warn("⚠️ No se pudo registrar la extensión en background:", e);
    }
}

// --- ALARMAS ---
chrome.alarms.onAlarm.addListener((alarm) => {
    if (alarm.name === "maintenance") {
        console.log("⏰ Ejecutando mantenimiento programado...");
        cleanOldCache();
    }
    if (alarm.name === LICENSE_REVALIDATE_ALARM) {
        console.log("🔐 Revalidando licencia...");
        revalidateLicense();
    }
});

function setupAlarms() {
    chrome.alarms.get("maintenance", (existing) => {
        if (!existing) {
            chrome.alarms.create("maintenance", {
                periodInMinutes: MAINTENANCE_INTERVAL
            });
            console.log("⏰ Alarma de mantenimiento creada");
        }
    });
    chrome.alarms.get(LICENSE_REVALIDATE_ALARM, (existing) => {
        if (!existing) {
            chrome.alarms.create(LICENSE_REVALIDATE_ALARM, {
                periodInMinutes: LICENSE_REVALIDATE_INTERVAL
            });
            console.log("🔐 Alarma de revalidación de licencia creada");
        }
    });
}

// --- INSTALACIÓN / ACTUALIZACIÓN ---
chrome.runtime.onInstalled.addListener(async (details) => {
    console.log("✅ Chenuke: Instalada/Actualizada", details.reason);
    setupAlarms();
    await registerExtension();
    if (details.reason === "update") {
        cleanOldCache();
    }
});

chrome.runtime.onStartup.addListener(() => {
    console.log("🚀 Chenuke: Navegador iniciado");
    setupAlarms();
    revalidateLicense();
});

// --- LIMPIEZA DE CACHÉ ---
async function cleanOldCache() {
    try {
        const allStorage = await chrome.storage.local.get(null);
        const now = Date.now();
        const keysToRemove = [];
        for (const [key, value] of Object.entries(allStorage)) {
            if (key.startsWith(ANALYSIS_CACHE_PREFIX)) {
                const age = now - (value.timestamp || 0);
                if (age > CACHE_MAX_AGE) {
                    keysToRemove.push(key);
                }
            }
        }
        if (keysToRemove.length > 0) {
            await chrome.storage.local.remove(keysToRemove);
            console.log(`🗑️ Caché limpiada: ${keysToRemove.length} entradas viejas`);
        }
    } catch (err) {
        console.error("❌ Error limpiando caché:", err);
    }
}

// --- CACHE DE ANÁLISIS ---
function getUrlKey(url) {
    return ANALYSIS_CACHE_PREFIX + encodeURIComponent(url);
}

async function saveAnalysisCache(url, data) {
    const key = getUrlKey(url);
    const payload = { ...data, timestamp: Date.now(), _cached: true };
    try {
        await chrome.storage.local.set({ [key]: payload });
        console.log("💾 Análisis guardado en caché");
    } catch (err) {
        console.error("❌ Error guardando caché:", err);
    }
}

async function getAnalysisCache(url) {
    const key = getUrlKey(url);
    try {
        const result = await chrome.storage.local.get(key);
        const cached = result[key];
        if (!cached) return null;
        const age = Date.now() - (cached.timestamp || 0);
        if (age > CACHE_MAX_AGE) {
            await chrome.storage.local.remove(key);
            return null;
        }
        return cached;
    } catch (err) {
        console.error("❌ Error leyendo caché:", err);
        return null;
    }
}

// --- HELPERS DE API ---
async function buildHeaders() {
    const headers = {
        "Content-Type": "application/json",
        "x-extension-id": chrome.runtime.id
    };
    try {
        const stored = await chrome.storage.local.get("pro_token");
        if (stored && stored.pro_token && typeof stored.pro_token === 'string') {
            headers["x-pro-token"] = stored.pro_token;
        }
    } catch (e) {}
    return headers;
}

// --- REVALIDACIÓN DE LICENCIA ---
// Reenvía la license_key guardada a /v3/activate. El backend, en modo
// reactivación, la revalida contra Lemon y:
//   - si sigue vigente → 200 con pro_token (lo reafirmamos)
//   - si Lemon la reporta cancelada/expirada → 403 (el backend YA revocó su
//     fila) → limpiamos el estado local
// REGLA CLAVE (fail-open): SOLO un 403 revoca. Un error de red o un 5xx NO
// tocan el token: no le cortamos el acceso a un pagador por un backend caído.
async function revalidateLicense() {
    let stored;
    try {
        stored = await chrome.storage.local.get(["license_key", "pro_token", "extension_plan"]);
    } catch (e) {
        return { transient: true };
    }

    // Nada que revalidar si no hay plan pago con key guardada.
    if (!stored.license_key || !stored.pro_token) return { skipped: true };
    if (stored.extension_plan !== "pro" && stored.extension_plan !== "premium") {
        return { skipped: true };
    }

    try {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 15000);
        const res = await fetch(ACTIVATE_URL, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ license_key: stored.license_key }),
            signal: controller.signal
        });
        clearTimeout(timeoutId);

        const data = await res.json().catch(() => ({}));

        if (res.status === 403) {
            // Lemon reporta la licencia como no vigente. El backend ya la revocó.
            await chrome.storage.local.remove(["pro_token", "license_key", "extension_plan"]);
            await chrome.storage.local.set({ license_last_check: Date.now() });
            console.log("🔒 Licencia revocada tras revalidación");
            return { revoked: true };
        }

        if (res.ok && data.pro_token) {
            // Sigue vigente. Reafirmamos token/plan (por si cambió el plan) y marca de tiempo.
            await chrome.storage.local.set({
                pro_token: data.pro_token,
                extension_plan: data.plan || stored.extension_plan,
                license_last_check: Date.now()
            });
            return { ok: true, plan: data.plan || stored.extension_plan };
        }

        // Cualquier otro estado (5xx, respuesta inesperada) = transitorio: NO revocar.
        return { transient: true, status: res.status };
    } catch (e) {
        // Red caída / timeout: transitorio. NO revocar.
        return { transient: true, error: String(e && e.message) };
    }
}

// --- NOTIFICACIONES ---
function showNotification(title, message, level = "info") {
    chrome.notifications.create({
        type: "basic",
        iconUrl: "icons/icon48.png",
        title: title,
        message: message,
        priority: level === "warning" ? 2 : 1
    });
}

// --- ANÁLISIS EN BACKGROUND ---
async function runBackgroundAnalysis(tabId, url, text, isEcommerce, title = "") {
    console.log("🔬 Análisis en background iniciado");
    try {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 30000);

        const res = await fetch(API_URL, {
            method: "POST",
            headers: await buildHeaders(),
            body: JSON.stringify({
                text: text,
                url: url,
                title: title || "",
                is_ecommerce: isEcommerce
            }),
            signal: controller.signal
        });

        clearTimeout(timeoutId);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        await saveAnalysisCache(url, data);

        const level = data?.analysis?.level || "desconocido";
        if (level === "alto" || level === "red") {
            showNotification(
                "⚠️ Chenuke - Alerta de Riesgo",
                `Se detectó un nivel de riesgo ALTO en una página.`,
                "warning"
            );
        }
        console.log("✅ Análisis en background completado");
        return data;
    } catch (err) {
        console.error("❌ Error en background analysis:", err);
        await saveAnalysisCache(url, {
            error: true,
            errorMessage: err.message,
            analysis: { level: "error", insight: "Error en análisis de fondo" }
        });
        return null;
    }
}

// --- LISTENER DE MENSAJES ---
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    if (message.type === "ping") {
        sendResponse({ status: "alive", timestamp: Date.now() });
        return false;
    }
    if (message.type === "GET_CACHED_ANALYSIS") {
        getAnalysisCache(message.url).then(cached => {
            sendResponse({ found: !!cached, data: cached });
        });
        return true;
    }
    if (message.type === "START_BACKGROUND_ANALYSIS") {
        const { tabId, url, text, is_ecommerce, title } = message;
        sendResponse({ accepted: true, tabId });
        runBackgroundAnalysis(tabId, url, text, is_ecommerce, title);
        return false;
    }
    if (message.type === "CLEAR_CACHE") {
        cleanOldCache().then(() => {
            sendResponse({ cleared: true });
        });
        return true;
    }
    if (message.type === "REVALIDATE_LICENSE") {
        revalidateLicense().then((r) => sendResponse(r || { transient: true }));
        return true;
    }
});

// --- MANEJO DE ERRORES GLOBALES ---
self.addEventListener("error", (event) => {
    console.error("❌ Error en Service Worker:", event.message, event.filename, event.lineno);
});
self.addEventListener("unhandledrejection", (event) => {
    console.error("❌ Promesa rechazada no manejada:", event.reason);
});

// --- ACTIVACIÓN ---
self.addEventListener("activate", (event) => {
    console.log("🚀 Chenuke: Worker Activado");
    setupAlarms();
    event.waitUntil(clients.claim());
});