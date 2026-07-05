# CONTEXT.md — Chénuke (ex GE SignalCheck)
**Última actualización:** 2026-07-05 · Bloque: conexión landing ↔ backend producción

---

## 1. Estado general

| Componente | Estado | Versión |
|---|---|---|
| Backend FastAPI (Railway) | ✅ Producción | **v15.22-commercial-risk** |
| Endpoint `/v3/demo` | ✅ Live, validado con curl y desde landing | — |
| Landing page | ✅ Conectada al backend real | `chenuke_landing_final.html` |
| Extensión Chrome MV3 | ⏳ Pendiente re-verificación con v15.22 | — |
| Pagos (PRO/PREMIUM) | ❌ No implementado (alerts placeholder) | — |

**URL producción:** `https://chenuke-production-8e78.up.railway.app/`
**Repo:** `github.com/Sakmyf/Chenuke` (branch `main`) · Local: `C:\chenuke`

---

## 2. Resolución del ciclo de deploy (bug crítico resuelto)

**Síntoma:** producción congelada en 15.16 pese a pushes correctos.
**Causa raíz:** `railway.json` tenía `"startCommand": "uvicorn main:app ..."` — pisaba al Procfile y a start.py. `main.py` no existe → crash → healthcheck fail → Railway mantenía el último deploy exitoso (viejo).
**Fix:** `railway.json` → `"startCommand": "uvicorn backend.app:app --host 0.0.0.0 --port ${PORT:-8000} --workers 4"`

**Regla aprendida:** prioridad de start command en Railway: `railway.json` > Procfile > start.py. Ante deploy "fantasma", revisar SIEMPRE railway.json primero y los Deploy Logs del deployment fallido (no los del activo).

---

## 3. Variables de entorno en Railway (estado actual)

| Variable | Valor | Nota |
|---|---|---|
| `DEMO_KEY` | `sc-demo-web-2026` | Header `x-demo-key` del endpoint demo |
| `DEV_MODE` | `false` | Antes estaba mal nombrada `ENV_MODE` — corregida |
| `ALLOWED_ORIGINS` | `https://chenuke.com,https://www.chenuke.com` | CORS. Agregar origen local si se testea local |
| `DATABASE_URL` | (privada railway.internal) | Verificada |
| `PRO_TOKEN_SECRET` | (seteada) | Para `/v3/verify` futuro |

Root endpoint confirma: `"dev_mode":false,"verify_rate_limit":"20/minute"` — demo rate limit 5/min por visitante.

---

## 4. Contrato del endpoint `/v3/demo`

**Request:** `POST /v3/demo` · headers `Content-Type: application/json`, `x-demo-key: <DEMO_KEY>` · body `{"text": "..."}` (máx 1000 chars)

**Response:**
```json
{
  "status": "success",
  "cached": false,
  "analysis": {
    "structural_index": 6,        // int 0-100 · NULL si texto breve
    "level": "bajo",              // bajo|medio|alto|green|yellow|red|alerta_breve
    "message": "...",             // presente en alerta_breve
    "signals": [{"label": "...", "detail": "...", "module": "..."}],
    "confidence": null,
    "insight": "...",
    "pro": {},
    "metrics": {}
  }
}
```

**Caso especial `alerta_breve`:** textos cortos → `structural_index: null`, sin barra de progreso en UI, solo señales + insight.

---

## 5. Landing final (`chenuke_landing_final.html`)

- Fetch real a `/v3/demo`, render 100% con datos del motor
- Maneja: índice null, señales con label/detail (detail oculto si == label — fix aplicado), insight, 429 rate limit, error de red
- **Fallback honesto:** nunca inventa resultados; muestra "servicio no disponible"
- Strip superior honesto: estado + versión real del motor (fetch al root) — se eliminó contador simulado de análisis (violaba ETHICS.md §no-engaño y era riesgo reputacional)
- Se eliminó input de token PRO hardcodeado (agujero de seguridad) — reintegrar cuando exista validación backend
- maxlength 1000 alineado al límite del endpoint
- Precios: FREE (extensión) / PRO $9/mes (20 informes) / PREMIUM $29/mes (100 + batch) / EXPERT cotización
- CTAs extensión Chrome: hero (discreto) + post-resultado + plan FREE — placeholder `chrome.google.com/webstore` a reemplazar con URL real

---

## 6. Próximos pasos (orden sugerido)

1. **Subir landing a chenuke.com** (CORS ya configurado para ese dominio)
2. **Re-verificar extensión** contra v15.22 (incluye re-test del falso positivo `buenosaires.gob.ar`)
3. **Pasarela de pago** PRO/PREMIUM (reemplazar alerts) + backend de tokens PRO (`/v3/verify` + `PRO_TOKEN_SECRET`)
4. **Página demo** con los 2 textos de ejemplo ya redactados (trading scam + noticia falsa estilo WhatsApp) — decisión tomada: dinámica contra `/v3/demo`, con revelación progresiva (score → dimensiones → citas → CTA)
5. URL real de Chrome Web Store en los 3 CTAs

---

## 7. Reglas operativas vigentes

- Verificar versión deployada ANTES de testear: `curl <railway-url>/` → `"version"`
- Calibrar solo con texto real de páginas (`document.body.innerText.slice(0,2000)`), nunca con textos inventados
- CMD Windows: curl en una sola línea, sin `\`
- Cambios de schema en responses → `TRUNCATE TABLE analysis_logs` (cache determinístico)
- ETHICS.md aplica también al marketing propio: sin métricas fabricadas, sin veredictos hardcodeados, fallbacks honestos