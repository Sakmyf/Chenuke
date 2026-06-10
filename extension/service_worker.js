// SignalCheck - Service Worker MV3 (CORREGIDO)

console.log("🔥 SignalCheck: Service Worker Inicializado");

// ------------------------------------------------------
// CONFIGURACIÓN
// ------------------------------------------------------
const KEEP_ALIVE_INTERVAL = 4.9; // minutos (Chrome mata a los 5 min de inactividad)
const ANALYSIS_CACHE_PREFIX = "analysis_";
const CACHE_MAX_AGE = 24 * 60 * 60 * 1000; // 24 horas

// ------------------------------------------------------
// PERSISTENCIA: Mantener el worker vivo
// ------------------------------------------------------
chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name === "keepAlive") {
    console.log("💓 Keep-alive ping");
    // No hacemos nada, solo el evento mantiene el worker activo
  }
});

// Crear alarma al instalar/activar
function setupKeepAlive() {
  chrome.alarms.get("keepAlive", (existing) => {
    if (!existing) {
      chrome.alarms.create("keepAlive", {
        periodInMinutes: KEEP_ALIVE_INTERVAL
      });
      console.log("⏰ Alarma keep-alive creada");
    }
  });
}

// ------------------------------------------------------
// INSTALACIÓN / ACTUALIZACIÓN
// ------------------------------------------------------
chrome.runtime.onInstalled.addListener((details) => {
  console.log("✅ SignalCheck: Instalada/Actualizada", details.reason);
  
  setupKeepAlive();
  
  // Limpiar caché vieja en actualizaciones
  if (details.reason === "update") {
    cleanOldCache();
  }
});

chrome.runtime.onStartup.addListener(() => {
  console.log("🚀 SignalCheck: Navegador iniciado");
  setupKeepAlive();
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
// CACHE DE ANÁLISIS (para recuperar al reabrir popup)
// ------------------------------------------------------
async function saveAnalysisCache(url, data) {
  const key = ANALYSIS_CACHE_PREFIX + btoa(url).replace(/[^a-zA-Z0-9]/g, "");
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
  const key = ANALYSIS_CACHE_PREFIX + btoa(url).replace(/[^a-zA-Z0-9]/g, "");
  
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
// NOTIFICACIONES
// ------------------------------------------------------
function showNotification(title, message, level = "info") {
  const icons = {
    info: "icons/icon48.png",
    warning: "icons/icon48.png",
    error: "icons/icon48.png"
  };
  
  chrome.notifications.create({
    type: "basic",
    iconUrl: icons[level] || icons.info,
    title: title,
    message: message,
    priority: level === "error" ? 2 : 1
  });
}

// ------------------------------------------------------
// ANÁLISIS EN BACKGROUND (cuando el popup se cierra)
// ------------------------------------------------------
async function runBackgroundAnalysis(tabId, url, text, isEcommerce) {
  const API_URL = "https://gesignalcheck-production-8e78.up.railway.app/v3/verify";
  
  console.log("🔬 Análisis en background iniciado");
  
  try {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 15000); // 15s para background
    
    const res = await fetch(API_URL, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "x-extension-id": chrome.runtime.id
      },
      body: JSON.stringify({
        text: text,
        url: url,
        is_ecommerce: isEcommerce
      }),
      signal: controller.signal
    });
    
    clearTimeout(timeoutId);
    
    if (!res.ok) {
      throw new Error(`HTTP ${res.status}`);
    }
    
    const data = await res.json();
    
    // Guardar en caché
    await saveAnalysisCache(url, data);
    
    // Notificar al usuario si el análisis tardó mucho
    showNotification(
      "SignalCheck - Análisis completo",
      `Nivel de riesgo: ${data.analysis?.level || "desconocido"}`,
      data.analysis?.level === "alto" ? "warning" : "info"
    );
    
    console.log("✅ Análisis en background completado");
    return data;
    
  } catch (err) {
    console.error("❌ Error en background analysis:", err);
    // Guardar error para que el popup lo sepa
    await saveAnalysisCache(url, {
      error: true,
      errorMessage: err.message,
      analysis: { level: "error", insight: "Error en análisis de fondo" }
    });
    return null;
  }
}

// ------------------------------------------------------
// LISTENER DE MENSAJES (CORREGIDO Y EXPANDIDO)
// ------------------------------------------------------
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  
  // Test de vida (Ping)
  if (message.type === "ping") {
    sendResponse({ status: "alive", timestamp: Date.now() });
    return true;
  }
  
  // Obtener caché de análisis para una URL
  if (message.type === "GET_CACHED_ANALYSIS") {
    getAnalysisCache(message.url).then(cached => {
      sendResponse({ found: !!cached, data: cached });
    });
    return true; // Async
  }
  
  // Iniciar análisis en background (para cuando el popup se cierra)
  if (message.type === "START_BACKGROUND_ANALYSIS") {
    const { tabId, url, text, is_ecommerce } = message;
    
    // Responder inmediatamente que se recibió
    sendResponse({ accepted: true, tabId });
    
    // Ejecutar en background
    runBackgroundAnalysis(tabId, url, text, is_ecommerce);
    return true;
  }
  
  // Limpiar caché manualmente
  if (message.type === "CLEAR_CACHE") {
    cleanOldCache().then(() => {
      sendResponse({ cleared: true });
    });
    return true;
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
  setupKeepAlive();
  event.waitUntil(clients.claim());
});