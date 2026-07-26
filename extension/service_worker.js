// Chenuke - Service Worker MV3 (PRODUCCIÓN + SEGURIDAD)

console.log("🔥 Chenuke: Service Worker Inicializado");

const MAINTENANCE_INTERVAL = 60;
const ANALYSIS_CACHE_PREFIX = "analysis_";
const CACHE_MAX_AGE = 24 * 60 * 60 * 1000;
const API_URL = "https://chenuke-production-8e78.up.railway.app/v3/verify";
const REGISTER_URL = "https://chenuke-production-8e78.up.railway.app/v3/register";

// --- REGISTRO DE EXTENSIÓN (al instalarse/actualizarse) ---
async function registerExtension() {
    try {
        const extId = chrome.runtime.id;
        const response = await fetch(REGISTER_URL, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ extension_id: extId })
        });
        if (!response.ok) throw new Error("Error registrando extensión");
        const data = await response.json();
        await chrome.storage.local.set({
            extension_plan: data.plan,
            pro_token: data.pro_token || null
        });
        console.log("✅ Extensión registrada en background, plan:", data.plan);
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