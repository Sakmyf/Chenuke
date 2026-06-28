CHENUKE – ESTADO TÉCNICO ACTUAL (v15.1)
1. Arquitectura General
Frontend (Extensión Chrome MV3)
manifest.json (Inyección dinámica, permisos activeTab y scripting)
popup.html / popup.css / popup.js (UI, manejo de API, caché de sesión)
content_script.js (Extracción de DOM optimizada, no bloqueante)
service_worker.js (Caché local, análisis en background, alarmas)
Comunicación vía chrome.tabs.sendMessage y chrome.runtime.sendMessage
Headers seguros: x-extension-id, x-pro-token
Backend
FastAPI + Uvicorn (con múltiples workers y uvloop)
Deployment en Railway (PaaS)
Endpoint principal: /v3/verify
Control de acceso por ALLOWED_EXTENSIONS y PRO_TOKEN_SECRET
CORS habilitado para extensión
2. Flujo de Ejecución
Usuario hace click en la extensión.
popup.js valida el protocolo de la pestaña activa.
Se inyecta dinámicamente content_script.js (si no está cargado).
Se extrae texto limpio (máx 20.000 caracteres) y se detecta contexto ecommerce.
Se envía al backend:
{  "url": "...",  "text": "...",  "title": "...",  "is_ecommerce": true/false}
Backend procesa, clasifica contexto, ejecuta 15 módulos y devuelve:
json

{
  "analysis": {
    "level": "bajo | medio | alto",
    "structural_index": 0-100,
    "confidence": 0-100,
    "insight": "Explicación cualitativa",
    "metrics": { "manipulacion": 45, "evidencia": 20 }
  },
  "meta": { "plan": "free | pro" }
}
3. Motor de Análisis (Heurístico Dinámico)
Context Classifier
Clasifica el texto para ajustar pesos dinámicamente. Contextos soportados:
ecommerce, social, fact_check, institutional, news, news_media, health_science, politics, opinion, landing, general.

Weight Engine
15 módulos de análisis estructural (urgencia, emociones, autoridad, contradicciones, etc.).
Pesos base renormalizados a 1.0.
Multiplicadores ajustados según el context detectado.
Score y Riesgo
structural_index: Puntaje agregado (0-100).
confidence: Probabilidad de acierto del análisis basado en longitud y señales.
level: Semáforo de riesgo (bajo, medio, alto).
4. Estado de Madurez
Modular, Determinística, Escalable.
Separación clara de responsabilidades.
Caché en cliente (chrome.storage.session y local).
No es fact-checker, ni sistema ML, ni detector automático de “verdad”.
Es un motor heurístico de análisis estructural del discurso digital.
text


---