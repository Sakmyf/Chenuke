// SignalCheck - Service Worker MV3 (CORREGIDO v2)

console.log("🔥 SignalCheck: Service Worker Inicializado");

// ------------------------------------------------------
// CONFIGURACIÓN
// ------------------------------------------------------
const MAINTENANCE_INTERVAL = 60; // minutos (para limpieza de caché)
const ANALYSIS_CACHE_PREFIX = "analysis_";
const CACHE_MAX_AGE = 24 * 60 * 60 * 1000; // 24 horas
const API_URL = "https://gesignalcheck-production-8e78.up.railway.app/v3/verify";

// ------------------------------------------------------
// PERSISTENCIA Y MANTENIMIENTO
// ------------------------------------------------------
chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name === "maintenance") {
    console.log("⏰ Ejecutando mantenimiento programado...");
    cleanOldCache();
  }
});

// Crear alarma al instalar/activar
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

// ------------------------------------------------------
// INSTALACIÓN / ACTUALIZACIÓN
// ------------------------------------------------------
chrome.runtime.onInstalled.addListener((details) => {
  console.log("✅ SignalCheck: Instalada/Actualizada", details.reason);
  setupAlarms();
  
  if (details.reason === "update") {
    cleanOldCache();
  }
});

chrome.runtime.onStartup.addListener(() => {
  console.log("🚀 SignalCheck: Navegador iniciado");
  setupAlarms();
});

// ------------------------------------------------------
// LIMPIEZA DE CACHÉ
// ------------------------------------------------------
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

// ------------------------------------------------------
// CACHE DE ANÁLISIS
// ------------------------------------------------------
// FIX: Usar encodeURIComponent en lugar de btoa para evitar crashes con URLs Unicode
function getUrlKey(url) {
  return ANALYSIS_CACHE_PREFIX + encodeURIComponent(url);
}

async function saveAnalysisCache(url, data) {
  const key = getUrlKey(url);
  const payload = {
    ...data,
    timestamp: Date.now(),
    _cached: true
  };
  
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

// ------------------------------------------------------
// HELPERS DE API
// ------------------------------------------------------
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

// ------------------------------------------------------
// NOTIFICACIONES
// ------------------------------------------------------
function showNotification(title, message, level = "info") {
  chrome.notifications.create({
    type: "basic",
    iconUrl: "icons/icon48.png",
    title: title,
    message: message,
    priority: level === "warning" ? 2 : 1
  });
}

// ------------------------------------------------------
// ANÁLISIS EN BACKGROUND
// ------------------------------------------------------
async function runBackgroundAnalysis(tabId, url, text, isEcommerce, title = "") {
  console.log("🔬 Análisis en background iniciado");
  
  try {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 15000); // 15s para background
    
    const res = await fetch(API_URL, {
      method: "POST",
      headers: await buildHeaders(), // FIX: Ahora incluye el token PRO
      body: JSON.stringify({
        text: text,
        url: url,
        title: title || "",
        is_ecommerce: isEcommerce
      }),
      signal: controller.signal
    });
    
    clearTimeout(timeoutId);
    
    if (!res.ok) {
      throw new Error(`HTTP ${res.status}`);
    }
    
    const data = await res.json();
    await saveAnalysisCache(url, data);
    
    // MEJORA: Solo notificar si el riesgo es Alto para no hacer spam
    const level = data?.analysis?.level || "desconocido";
    if (level === "alto" || level === "red") {
      showNotification(
        "⚠️ SignalCheck - Alerta de Riesgo",
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

// ------------------------------------------------------
// LISTENER DE MENSAJES
// ------------------------------------------------------
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  
  // Test de vida (Ping) - Síncrono
  if (message.type === "ping") {
    sendResponse({ status: "alive", timestamp: Date.now() });
    return false; // FIX: false para cerrar el puerto inmediatamente
  }
  
  // Obtener caché de análisis - Asíncrono
  if (message.type === "GET_CACHED_ANALYSIS") {
    getAnalysisCache(message.url).then(cached => {
      sendResponse({ found: !!cached, data: cached });
    });
    return true; // Mantener abierto para async
  }
  
  // Iniciar análisis en background - Asíncrono
  if (message.type === "START_BACKGROUND_ANALYSIS") {
    const { tabId, url, text, is_ecommerce, title } = message;
    
    // Responder inmediatamente que se recibió
    sendResponse({ accepted: true, tabId });
    
    // Ejecutar en background (no bloquea el sendResponse)
    runBackgroundAnalysis(tabId, url, text, is_ecommerce, title);
    return false; // FIX: Ya respondimos arriba, así que false.
  }
  
  // Limpiar caché manualmente - Asíncrono
  if (message.type === "CLEAR_CACHE") {
    cleanOldCache().then(() => {
      sendResponse({ cleared: true });
    });
    return true; // Mantener abierto para async
  }
});

// ------------------------------------------------------
// MANEJO DE ERRORES GLOBALES
// ------------------------------------------------------
self.addEventListener("error", (event) => {
  console.error("❌ Error en Service Worker:", event.message, event.filename, event.lineno);
});

self.addEventListener("unhandledrejection", (event) => {
  console.error("❌ Promesa rechazada no manejada:", event.reason);
});

// ------------------------------------------------------
// ACTIVACIÓN
// ------------------------------------------------------
self.addEventListener("activate", (event) => {
  console.log("🚀 SignalCheck: Worker Activado");
  setupAlarms();
  event.waitUntil(clients.claim());
});