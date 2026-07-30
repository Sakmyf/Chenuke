# CONTEXT.md — Chénuke (ex GE SignalCheck)
**Última actualización:** 2026-07-30 · Bloque: auditoría completa del sistema + patch de seguridad de tokens (v15.25)

---

## 1. Estado general

| Componente | Estado | Versión |
|---|---|---|
| Backend FastAPI (Railway) | ✅ Producción (pendiente deploy del patch v15.25) | **15.24-pro-full** en prod |
| Motor heurístico | ✅ 15 módulos + weight engine + context classifier | 15.24 |
| Endpoint `/v3/demo` | ✅ Live | — |
| Endpoint `/v3/chat-analysis` (informe IA DeepSeek) | ⚠️ Código OK pero **muerto en prod**: falta `openai` en requirements (fix listo) | — |
| Landing + páginas web | ⚠️ Funcionales con deuda de seguridad (ver §5) | — |
| Extensión Chrome MV3 | ⚠️ Bloqueada para Web Store (ver §6) | 0.5.1 |
| Pagos Lemon Squeezy | ⚠️ Checkout links de prueba en index; webhook v15.25 listo para deploy | — |

**URL producción:** `https://chenuke-production-8e78.up.railway.app/`
**Repo:** `github.com/Sakmyf/Chenuke` (branch `main`) · Local: `C:\chenuke`
**Web:** cPanel (`/home/chenuke/public_html`), PHP para webhook.

---

## 2. PATCH v15.25 — Modelo de seguridad de tokens (LISTO PARA DEPLOY)

**Problema raíz descubierto:** `chrome.runtime.id` es público e idéntico para todas las instalaciones de la Web Store → no sirve como identidad. El modelo anterior permitía: robar el token PRO vía `/v3/register` (lo devolvía a cualquiera), auto-otorgarse PRO vía `/v3/upgrade` (sin auth), y degradar el plan de clientes pagos (token inválido borraba plan y token).

**Modelo nuevo (archivos entregados):**
- **La identidad ES el token**, emitido por compra. `extension_id` queda como telemetría.
- `/v3/upgrade`: exige header `x-webhook-secret` == env `WEBHOOK_SECRET` (compare_digest; responde 404 si falla para no revelar el endpoint). Upsert por `reference` (`lemon:sub_X` / `lemon:order_X`, guardado en `Extension.extension_id` — sin migración de schema). `plan:"free"` = revocación (borra token).
- `/v3/register`: nunca devuelve token; solo registra instalación.
- `resolve_plan_from_db(pro_token)`: lookup por token, solo lectura, jamás muta la DB. Token inválido → "free" sin efectos.
- Comparaciones sensibles (`pro_token`, `demo_key`, webhook secret) con `secrets.compare_digest`.
- `ENGINE_VERSION` ahora se importa de `backend/engine.py` (fuente única; fallback local solo en modo degradado).
- Prompt de DeepSeek endurecido contra prompt injection (texto delimitado como dato; veredicto numérico siempre del heurístico).
- `_CHAT_CACHE` acotado a 500 entradas por worker (evicción del más viejo).

**webhook-lemon.php v15.25:** firma HMAC verificada → llama `/v3/upgrade` con secret → emite token → lo envía por email al comprador. Config y log FUERA del docroot (`/home/chenuke/config/`, `/home/chenuke/logs/`). Nunca loguea el payload (contiene emails). Mapeo: subscription_created/updated/payment_success → pro|premium (por product_name); cancelled/expired/payment_failed → free; order_created → pro con `analyses_limit:1`.

**Pasos de deploy del patch:**
1. Setear `WEBHOOK_SECRET` en Railway (valor largo aleatorio).
2. Reemplazar `backend/app.py`, `backend/Analysis/scientific_claims.py`, `backend/Analysis/credibility.py`, `requirements.txt` → push → verificar `"version"` en root.
3. Subir `webhook-lemon.php` + crear `/home/chenuke/config/webhook-config.php` (lemon_signing_secret + chenuke_webhook_secret + chenuke_api) y `/home/chenuke/logs/`.
4. Configurar webhook en Lemon Squeezy apuntando a `https://chenuke.com/webhook-lemon.php` con el signing secret.
5. Bump `ENGINE_VERSION` a `15.25-token-auth` en `engine.py` (única fuente) + `TRUNCATE analysis_logs`.
6. **Extensión:** agregar campo "clave de activación" en popup (pegar token → `chrome.storage.local.pro_token`). El flujo register→token ya no existe.

**Fixes de módulos incluidos en el patch:**
- `scientific_claims.py`: `has_support` era código muerto (`has_weak` nunca aportaba) → ahora respaldo débil = penalización reducida, no anulación; `"peer.?review"` era regex en check de substring (nunca matcheaba) → strings planos.
- `credibility.py`: eliminado "exceso de adjetivos" (re-puntuaba los mismos hits de `EMOTIONAL_WORDS` del paso 1: doble conteo interno).

---

## 3. Deuda de calibración del motor (detectada, NO parcheada — decisión de diseño pendiente)

- **Triple conteo entre módulos:** "impactante" dispara `structural` (clickbait) + `credibility` + `emotions`. Patrones de escasez duplicados literalmente en `urgency` y `commercial_risk.SCARCITY_RE`. `ROI_RE`/`FAST_MONEY_RE` duplicados en `promises` y `commercial_risk`. La renormalización protege proporciones entre módulos pero no evita que una frase infle 3 scores correlacionados. Probable causa del falso positivo `buenosaires.gob.ar`. **Propuesta:** cada patrón léxico con un solo módulo dueño (escasez→urgency, promesas→promises; commercial_risk consume resultados).
- **Gameable con una palabra:** "universidad" da trust_bonus en `authority` Y anula penalización en `scientific_claims`. Mitigación propuesta: exigir universidad nombrada (`universidad de \w+`).
- **`narrative_patterns.RECONSTRUCTION`** ("narrativa", "relato", "escena", "ficción") → falsos positivos en reseñas de cine/libros; no hay contexto `culture`. Testear Chénuke contra chenuke.com antes del launch (auto-flagging probable).
- **`contradictions.py`** dispara en artículos de fact-checking ("no hay evidencia" + "comprobado" al desmentir) → debería abstenerse en contexto `fact_check` (patrón `_SKIP_CONTEXTS` de `detect_uncertainty`).
- Módulo modelo a imitar: `detect_uncertainty` v3.1 (abstención estructural, anti-falsificación, atenuación por longitud).

---

## 4. Deuda del backend (menor, post-patch)

- `commercial_risk` escala 0-10 → normalizado en engine (`/10` en `_commercial_contribution`) ✅ verificado, no es bug.
- Redis agregado a requirements como opcional (solo si `REDIS_URL`).

---

## 5. Deuda de las páginas web (pendiente — próximo bloque sugerido)

| Archivo | Problema | Gravedad |
|---|---|---|
| `gracias.html` | Expone `PRO_TOKEN_SECRET` en JS cliente + depende de localStorage (falla cross-device). **Reemplazar por flujo order_id → nuevo endpoint de verificación contra API de Lemon**, o simplemente instruir "revisá tu email" (el webhook ya envía el token). | 🔴 |
| `analysis.html` | Acepta `?score=X&level=Y` → informes fabricables con marca Chénuke (viola ETHICS.md). Insight inventado client-side. | 🔴 |
| `ia-report.html` | XSS: param `report` → innerHTML sin escapar. | 🔴 |
| `index.html` | Placeholder `TU_ENLACE_UNICO_DE_LS` (botón informe único roto); links de checkout aún de prueba. | 🔴 |
| Legales (privacidad/aviso/cookies) | Mencionan Stripe pero el MoR real es Lemon Squeezy (debe figurar); titular inconsistente (persona física con domicilio particular vs Grupo Eryma LLC → unificar en LLC); `[EMAIL_DE_SOPORTE]` sin reemplazar; falta PREMIUM $29 en aviso legal; "todos los precios en USD" vs cobro ARS por Mercado Pago. | 🟡 |
| `pending/failure.html` | Sin identidad visual (momento de máxima ansiedad post-pago). | 🟢 |
| `soporte.html` | Mezcla tuteo/voseo. | 🟢 |

---

## 6. Deuda de la extensión (pendiente — bloquea Web Store)

1. **Eliminar ofuscación** (`obfuscate.js` + package.json): CWS prohíbe código ofuscado desde 2018; la config actual (controlFlowFlattening, selfDefending, debugProtection) garantiza rechazo. La IP real está en el backend.
2. **`popup.html` arranca con resultado fabricado** ("🔴 Alto riesgo 85/100" hardcodeado) → estado inicial neutro (viola ETHICS.md si popup.js falla).
3. **Eliminar `forceReportBtn`** ("FORZADO") + su style inline.
4. **Descripción del manifest** dice "Optimiza ventas con métricas" — copy de otro producto. Propuesta: "Detecta señales estructurales de manipulación, urgencia artificial y promesas desproporcionadas en cualquier página web."
5. **Copy FOMO** en `proWarning` ("señales más profundas que no estás viendo") → informativo: "El informe completo incluye desglose por dimensión y citas textuales."
6. **NUEVO por patch v15.25:** campo de activación de clave (token) en popup; el service worker ya no recibe token por register.
7. Menores: quitar `web_accessible_resources` (fingerprinting), quitar `el.name`/`el.id` del extractor (ruido de calibración), `.hidden` duplicado en popup.css, `"type": "module"` innecesario en manifest.

---

## 7. Variables de entorno en Railway

| Variable | Estado | Nota |
|---|---|---|
| `DEMO_KEY` | ✅ `sc-demo-web-2026` | Header `x-demo-key` |
| `WEBHOOK_SECRET` | ⏳ **NUEVA — setear antes del deploy v15.25** | Auth de `/v3/upgrade` |
| `DEEPSEEK_API_KEY` | Verificar seteada | Sin ella, informe IA → 503 |
| `DEV_MODE` | `false` | |
| `ALLOWED_ORIGINS` | `https://chenuke.com,https://www.chenuke.com` | |
| `DATABASE_URL` | ✅ | |
| `PRO_TOKEN_SECRET` | ⚠️ Obsoleta en el modelo v15.25 (los tokens viven en DB) — no borrar hasta confirmar que nada la lee | |

---

## 8. Reglas operativas vigentes

- Verificar versión deployada ANTES de testear: `curl <railway-url>/` → `"version"`
- Calibrar solo con texto real de páginas (`document.body.innerText.slice(0,2000)`), nunca inventado
- CMD Windows: curl en una sola línea, sin `\`
- Cambios de schema en responses → `TRUNCATE TABLE analysis_logs`
- `railway.json` es LA fuente del start command (prioridad: railway.json > Procfile > start.py). Hoy apunta a `python start.py` — funciona, pero decisión pendiente: consolidar en un solo mecanismo y borrar los otros dos.
- ETHICS.md aplica al marketing y a la propia UI: sin métricas fabricadas, sin veredictos hardcodeados, sin upsell por miedo, fallbacks honestos
- `ENGINE_VERSION` se edita SOLO en `engine.py` (app.py la importa desde v15.25)

---

## 9. Orden de trabajo restante (pre-launch)

1. ✅ ~~Auth de tokens backend + webhook~~ (este bloque — falta deploy)
2. `gracias.html` (flujo "revisá tu email") + fix `analysis.html` + XSS `ia-report.html`
3. Popup extensión: estado neutro + campo de activación + copy + manifest + sacar ofuscación
4. Legales: Stripe→Lemon, titular único, placeholders, PREMIUM en aviso legal
5. Links de checkout Live de Lemon + reemplazar placeholder de informe único
6. Smoke test ampliado (5 endpoints + alerta_breve + contexto news) + re-test `buenosaires.gob.ar`
7. Decisión de diseño: dedupe de patrones entre módulos (§3)
8. Publicación Chrome Web Store
